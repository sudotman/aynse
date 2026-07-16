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

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..standard import UpstreamResponseError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_JSON_EXTENSION_KEY = "aynse.decoded_json"
_PRIMING_HOSTS = {"nseindia.com", "www.nseindia.com"}


class _RetryableContentError(UpstreamResponseError):
    """A successful response that looks like an NSE block/error page."""

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
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }


def _is_retryable_response(resp: Optional[httpx.Response]) -> bool:
    if resp is None:
        return False
    return resp.status_code in (302, 403, 429, 500, 502, 503, 504)


def _prime_path_for(base_url: str) -> Optional[str]:
    """Return the cookie-prime path only for NSE's interactive web host."""
    hostname = (urlparse(base_url).hostname or "").lower()
    if hostname in _PRIMING_HOSTS:
        return "/get-quotes/equity"
    return None


def _decode_json_response(resp: httpx.Response) -> Any:
    """Validate and decode a JSON response once, caching the decoded value."""
    if _JSON_EXTENSION_KEY in resp.extensions:
        return resp.extensions[_JSON_EXTENSION_KEY]

    try:
        source_url = str(resp.request.url)
    except RuntimeError:
        source_url = "<unknown>"
    content_type = resp.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type != "application/json" and not media_type.endswith("+json"):
        raise UpstreamResponseError(
            f"Unexpected content-type {content_type or '<missing>'!r} "
            f"from {source_url} (status {resp.status_code})"
        )
    try:
        decoded = resp.json()
    except ValueError as exc:
        raise UpstreamResponseError(
            f"Invalid JSON from {source_url} (status {resp.status_code})"
        ) from exc
    resp.extensions[_JSON_EXTENSION_KEY] = decoded
    return decoded

def _retry_decorator():
    return retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=5.0),
        retry=(
            retry_if_exception_type(httpx.HTTPError)
            | retry_if_exception_type(_RetryableContentError)
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
            if (time.monotonic() - self._opened_at) >= self.reset_timeout:
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
                self._opened_at = time.monotonic()


class TokenBucket:
    """
    Simple token-bucket rate limiter.
    tokens: capacity of the bucket
    refill_rate: tokens per second
    """

    def __init__(self, tokens: int = 10, refill_rate: float = 10.0) -> None:
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens <= 0:
            raise ValueError("tokens must be a positive integer")
        if isinstance(refill_rate, bool) or refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.capacity = float(tokens)
        self.tokens = float(tokens)
        self.refill_rate = float(refill_rate)
        self._lock = threading.Lock()
        self._last_refill = time.monotonic()

    def acquire(self, cost: int = 1) -> None:
        if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
            raise ValueError("cost must be a positive integer")
        if cost > self.capacity:
            raise ValueError("cost cannot exceed bucket capacity")
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self.tokens = min(
                    self.capacity,
                    self.tokens + elapsed * self.refill_rate,
                )
                self._last_refill = now
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
                delay = (cost - self.tokens) / self.refill_rate
            time.sleep(max(0.001, delay))


class AsyncTokenBucket:
    """Event-loop friendly counterpart to :class:`TokenBucket`."""

    def __init__(self, tokens: int = 10, refill_rate: float = 10.0) -> None:
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens <= 0:
            raise ValueError("tokens must be a positive integer")
        if isinstance(refill_rate, bool) or refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.capacity = float(tokens)
        self.tokens = float(tokens)
        self.refill_rate = float(refill_rate)
        self._lock = asyncio.Lock()
        self._last_refill = time.monotonic()

    async def acquire(self, cost: int = 1) -> None:
        if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
            raise ValueError("cost must be a positive integer")
        if cost > self.capacity:
            raise ValueError("cost cannot exceed bucket capacity")
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self.tokens = min(
                    self.capacity,
                    self.tokens + elapsed * self.refill_rate,
                )
                self._last_refill = now
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
                delay = (cost - self.tokens) / self.refill_rate
            await asyncio.sleep(max(0.001, delay))


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
        self._prime_path = _prime_path_for(self.base_url)
        self._primed = self._prime_path is None
        self._prime_lock = threading.Lock()

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=_default_headers(),
            http2=True,
            follow_redirects=True,
            limits=self._limits,
        )

    def _recreate_client(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
        self._client = self._build_client()
        self._primed = self._prime_path is None

    def _prime_session(self, *, force: bool = False) -> None:
        """Prime NSE cookies lazily so importing aynse never performs I/O."""
        if self._prime_path is None:
            self._primed = True
            return
        with self._prime_lock:
            if self._primed and not force:
                return
            try:
                self._client.get(
                    self._prime_path,
                    params={"symbol": "SBIN"},
                    timeout=min(self.timeout, 5.0),
                )
            except Exception as exc:
                # Priming is best-effort; the requested API call may still work.
                logger.debug("nse_session_prime_failed", exc_info=exc)
            finally:
                # Mark the attempt complete so a failed best-effort prime does not
                # add its timeout to every otherwise-successful API request.
                self._primed = True

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
    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        _expect_json: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        self._check_circuit()
        self._rate.acquire()
        if not self._primed:
            self._prime_session()
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
            self._circuit.record_failure()
            # Respect Retry-After for 429
            self._respect_retry_after(resp)
            # Attempt re-priming on 403 and try again
            if resp.status_code == 403:
                self._primed = False
                self._prime_session(force=True)
        else:
            if _expect_json:
                try:
                    _decode_json_response(resp)
                except UpstreamResponseError as exc:
                    self._circuit.record_failure()
                    if 200 <= resp.status_code < 300:
                        # A 2xx HTML page is usually an NSE anti-bot response.
                        self._primed = False
                        self._prime_session(force=True)
                        raise _RetryableContentError(str(exc)) from exc
                    raise
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
        resp = self._request_with_retry(
            "GET",
            path,
            params=params,
            _expect_json=True,
        )
        return _decode_json_response(resp)

    def post_json(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        resp = self._request_with_retry(
            "POST",
            path,
            json=json,
            _expect_json=True,
        )
        return _decode_json_response(resp)


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
        self._rate = AsyncTokenBucket(tokens=rate_limit_per_sec, refill_rate=float(rate_limit_per_sec))

        self._limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections)
        self._client = self._build_client()
        self._prime_path = _prime_path_for(self.base_url)
        self._primed = self._prime_path is None
        self._prime_lock = asyncio.Lock()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=_default_headers(),
            http2=True,
            follow_redirects=True,
            limits=self._limits,
        )

    async def _recreate_client(self) -> None:
        old_client = self._client
        self._client = self._build_client()
        self._primed = self._prime_path is None
        try:
            await old_client.aclose()
        except Exception:
            pass

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _aprime_session(self, *, force: bool = False) -> None:
        if self._prime_path is None:
            self._primed = True
            return
        # Ensure only one priming runs at a time
        async with self._prime_lock:
            if self._primed and not force:
                return
            try:
                await self._client.get(
                    self._prime_path,
                    params={"symbol": "SBIN"},
                    timeout=min(self.timeout, 5.0),
                )
            except Exception as exc:
                logger.debug("nse_async_session_prime_failed", exc_info=exc)
            finally:
                self._primed = True

    async def _respect_retry_after(self, resp: httpx.Response) -> None:
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    delay = float(ra)
                    await asyncio.sleep(min(delay, 5.0))
                except Exception:
                    pass

    def _check_circuit(self) -> None:
        if not self._circuit.allow():
            raise CircuitOpenError("Circuit is open due to repeated failures")

    @_retry_decorator()
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        _expect_json: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        self._check_circuit()
        await self._rate.acquire()

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
                await self._recreate_client()
            raise exc

        if _is_retryable_response(resp):
            self._circuit.record_failure()
            await self._respect_retry_after(resp)
            if resp.status_code == 403:
                # Try to re-prime
                try:
                    self._primed = False
                    await self._aprime_session(force=True)
                except Exception:
                    pass
        else:
            if _expect_json:
                try:
                    _decode_json_response(resp)
                except UpstreamResponseError as exc:
                    self._circuit.record_failure()
                    if 200 <= resp.status_code < 300:
                        self._primed = False
                        await self._aprime_session(force=True)
                        raise _RetryableContentError(str(exc)) from exc
                    raise
            self._circuit.record_success()

        return resp

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request_with_retry("GET", path, params=params)

    async def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = await self._request_with_retry(
            "GET",
            path,
            params=params,
            _expect_json=True,
        )
        return _decode_json_response(resp)

    async def post_json(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        resp = await self._request_with_retry(
            "POST",
            path,
            json=json,
            _expect_json=True,
        )
        return _decode_json_response(resp)


