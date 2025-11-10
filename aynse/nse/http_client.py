"""
Unified HTTP client for NSE with resilience and performance features.

Provides sync and async clients with:
- Standard NSE headers and cookie/session priming
- Connection pooling, HTTP/2 (when available)
- Unified retries with exponential backoff + jitter
- Respect for Retry-After on 429
- Simple circuit breaker and token-bucket rate limiter per host
- Content-type validation helpers
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
import asyncio
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_DEFAULT_UAS = [
    # Short, reasonable rotation of UAs
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
]


def _default_headers() -> Dict[str, str]:
    # Rotate a UA at process start; simple and sufficient
    ua = _DEFAULT_UAS[int(time.time()) % len(_DEFAULT_UAS)]
    return {
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=SBIN",
        "X-Requested-With": "XMLHttpRequest",
        "pragma": "no-cache",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }


def _is_retryable_response(resp: Optional[httpx.Response]) -> bool:
    if resp is None:
        return False
    return resp.status_code in (302, 403, 429, 500, 502, 503, 504)

def _retry_decorator():
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=5.0),
        retry=(
            retry_if_exception_type(httpx.HTTPError)
            | retry_if_exception(lambda e: isinstance(e, RuntimeError) and "client has been closed" in str(e))
            | retry_if_result(_is_retryable_response)
        ),
    )


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_timeout: float = 30.0

    def __post_init__(self) -> None:
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            # Half-open after timeout
            if (time.time() - self._opened_at) >= self.reset_timeout:
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.time()


class TokenBucket:
    """
    Simple token-bucket rate limiter.
    tokens: capacity of the bucket
    refill_rate: tokens per second
    """

    def __init__(self, tokens: int = 10, refill_rate: float = 10.0) -> None:
        self.capacity = tokens
        self.tokens = tokens
        self.refill_rate = refill_rate
        self._lock = threading.Lock()
        self._last_refill = time.time()

    def acquire(self, cost: int = 1) -> None:
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self._last_refill
                refill = elapsed * self.refill_rate
                if refill >= 1:
                    self.tokens = min(self.capacity, self.tokens + int(refill))
                    self._last_refill = now
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
            # Sleep briefly before retrying
            time.sleep(0.01)


class NSEHttpClient:
    """
    Sync HTTP client for NSE.
    """

    def __init__(
        self,
        base_url: str = "https://www.nseindia.com",
        timeout: float = 15.0,
        max_connections: int = 20,
        rate_limit_per_sec: int = 10,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Use a higher threshold by default to avoid flakiness under anti-bot
        self._circuit = circuit_breaker or CircuitBreaker(failure_threshold=50)
        self._rate = TokenBucket(tokens=rate_limit_per_sec, refill_rate=float(rate_limit_per_sec))

        self._max_connections = max_connections
        self._limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections)
        self._client = self._build_client()
        # Best-effort cookie/session priming
        self._prime_session()

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=_default_headers(),
            http2=True,
            limits=self._limits,
        )

    def _recreate_client(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
        self._client = self._build_client()

    def _prime_session(self) -> None:
        try:
            self._client.get("/get-quotes/equity", params={"symbol": "SBIN"})
        except Exception:
            # Priming is best-effort
            pass

    def close(self) -> None:
        self._client.close()

    def _respect_retry_after(self, resp: httpx.Response) -> None:
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    delay = float(ra)
                    time.sleep(min(delay, 5.0))
                except Exception:
                    pass

    def _check_circuit(self) -> None:
        if not self._circuit.allow():
            raise CircuitOpenError("Circuit is open due to repeated failures")

    @_retry_decorator()
    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._check_circuit()
        self._rate.acquire()
        start = time.time()
        try:
            resp = self._client.request(method, url, **kwargs)
        except Exception as exc:
            self._circuit.record_failure()
            logger.warning("nse_http_error", extra={"method": method, "url": url, "error": str(exc)})
            # If client has been closed, recreate and let tenacity retry
            if isinstance(exc, RuntimeError) and "client has been closed" in str(exc):
                self._recreate_client()
            raise exc

        if _is_retryable_response(resp):
            # Respect Retry-After for 429
            self._respect_retry_after(resp)
            # Attempt re-priming on 403 and try again
            if resp.status_code == 403:
                self._prime_session()
        else:
            self._circuit.record_success()

        duration = time.time() - start
        logger.info("nse_http_request", extra={
            "method": method,
            "url": str(resp.request.url),
            "status": resp.status_code,
            "duration_ms": int(duration * 1000),
        })
        return resp

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._request_with_retry("GET", path, params=params)

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = self.get(path, params)
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            # NSE sometimes serves HTML/blocked pages; force a retry by raising
            raise httpx.HTTPError(f"Unexpected content-type: {ctype}", request=resp.request, response=resp)
        return resp.json()

    def post_json(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        resp = self._request_with_retry("POST", path, json=json)
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            raise httpx.HTTPError(f"Unexpected content-type: {ctype}", request=resp.request, response=resp)
        return resp.json()


class NSEAsyncHttpClient:
    """
    Async HTTP client for NSE.
    """

    def __init__(
        self,
        base_url: str = "https://www.nseindia.com",
        timeout: float = 15.0,
        max_connections: int = 50,
        rate_limit_per_sec: int = 20,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._circuit = circuit_breaker or CircuitBreaker(failure_threshold=50)
        self._rate = TokenBucket(tokens=rate_limit_per_sec, refill_rate=float(rate_limit_per_sec))

        self._limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections)
        self._client = self._build_client()
        self._primed = False
        self._prime_lock = asyncio.Lock()  # type: ignore[name-defined]

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=_default_headers(),
            http2=True,
            limits=self._limits,
        )

    def _recreate_client(self) -> None:
        try:
            # Fire-and-forget close (cannot await here)
            close = getattr(self._client, "aclose", None)
            if callable(close):
                pass
        except Exception:
            pass
        self._client = self._build_client()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _aprime_session(self) -> None:
        # Ensure only one priming runs at a time
        async with self._prime_lock:
            if self._primed:
                return
            try:
                await self._client.get("/get-quotes/equity", params={"symbol": "SBIN"})
            except Exception:
                pass
            self._primed = True

    def _respect_retry_after(self, resp: httpx.Response) -> None:
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    delay = float(ra)
                    time.sleep(min(delay, 5.0))
                except Exception:
                    pass

    def _check_circuit(self) -> None:
        if not self._circuit.allow():
            raise CircuitOpenError("Circuit is open due to repeated failures")

    @_retry_decorator()
    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._check_circuit()
        self._rate.acquire()

        # Best-effort priming on first call
        if not self._primed:
            try:
                await self._aprime_session()
            except Exception:
                pass

        try:
            resp = await self._client.request(method, url, **kwargs)
        except Exception as exc:
            self._circuit.record_failure()
            if isinstance(exc, RuntimeError) and "client has been closed" in str(exc):
                self._recreate_client()
            raise exc

        if _is_retryable_response(resp):
            self._respect_retry_after(resp)
            if resp.status_code == 403:
                # Try to re-prime
                try:
                    self._primed = False
                    await self._aprime_session()
                except Exception:
                    pass
        else:
            self._circuit.record_success()

        return resp

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request_with_retry("GET", path, params=params)

    async def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = await self.get(path, params)
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            raise httpx.HTTPError(f"Unexpected content-type: {ctype}", request=resp.request, response=resp)
        return resp.json()

    async def post_json(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        resp = await self._request_with_retry("POST", path, json=json)
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            raise httpx.HTTPError(f"Unexpected content-type: {ctype}", request=resp.request, response=resp)
        return resp.json()


