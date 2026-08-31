"""Offline contracts for HTTP retries, priming, and async lifecycle."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aynse.nse.http_client import (
    AsyncTokenBucket,
    NSEAsyncHttpClient,
    NSEHttpClient,
    TokenBucket,
)
from aynse.standard import UpstreamResponseError


def _replace_sync_transport(client: NSEHttpClient, handler) -> None:
    client._client.close()
    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
        headers={"Accept-Encoding": "gzip, deflate"},
    )


def test_successful_html_block_page_is_retried(monkeypatch) -> None:
    calls = {"prime": 0, "api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/get-quotes/equity":
            calls["prime"] += 1
            return httpx.Response(200, text="primed", request=request)
        calls["api"] += 1
        if calls["api"] == 1:
            return httpx.Response(
                200,
                text="<html>Access denied</html>",
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(
            200,
            json={"data": [1, 2, 3]},
            headers={"content-type": "application/json"},
            request=request,
        )

    client = NSEHttpClient(rate_limit_per_sec=100)
    _replace_sync_transport(client, handler)
    monkeypatch.setattr(client._request_with_retry.retry, "sleep", lambda _: None)
    try:
        assert client.get_json("/api/example") == {"data": [1, 2, 3]}
    finally:
        client.close()

    assert calls == {"prime": 2, "api": 2}


def test_failed_best_effort_prime_is_attempted_only_once() -> None:
    calls = {"prime": 0, "api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/get-quotes/equity":
            calls["prime"] += 1
            raise httpx.ConnectTimeout("prime unavailable", request=request)
        calls["api"] += 1
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
            request=request,
        )

    client = NSEHttpClient(rate_limit_per_sec=100)
    _replace_sync_transport(client, handler)
    try:
        assert client.get_json("/api/one") == {"ok": True}
        assert client.get_json("/api/two") == {"ok": True}
    finally:
        client.close()

    assert calls == {"prime": 1, "api": 2}


def test_403_response_re_primes_and_retries(monkeypatch) -> None:
    calls = {"prime": 0, "api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/get-quotes/equity":
            calls["prime"] += 1
            return httpx.Response(200, text="primed", request=request)
        calls["api"] += 1
        status = 403 if calls["api"] == 1 else 200
        return httpx.Response(
            status,
            json={"ok": status == 200},
            headers={"content-type": "application/json"},
            request=request,
        )

    client = NSEHttpClient(rate_limit_per_sec=100)
    _replace_sync_transport(client, handler)
    monkeypatch.setattr(client._request_with_retry.retry, "sleep", lambda _: None)
    try:
        assert client.get_json("/api/data") == {"ok": True}
    finally:
        client.close()

    assert calls == {"prime": 2, "api": 2}


def test_concurrent_first_requests_share_one_prime() -> None:
    calls = {"prime": 0, "api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/get-quotes/equity":
            calls["prime"] += 1
            return httpx.Response(200, text="primed", request=request)
        calls["api"] += 1
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
            request=request,
        )

    client = NSEHttpClient(rate_limit_per_sec=100)
    _replace_sync_transport(client, handler)
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(
                    lambda index: client.get_json(f"/api/{index}"),
                    range(4),
                )
            )
    finally:
        client.close()

    assert results == [{"ok": True}] * 4
    assert calls == {"prime": 1, "api": 4}


@pytest.mark.parametrize(
    "base_url",
    ["https://niftyindices.com", "https://nsearchives.nseindia.com"],
)
def test_non_interactive_hosts_are_never_primed(base_url: str) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
            request=request,
        )

    client = NSEHttpClient(base_url=base_url, rate_limit_per_sec=100)
    _replace_sync_transport(client, handler)
    try:
        assert client.get_json("/api/data") == {"ok": True}
    finally:
        client.close()

    assert paths == ["/api/data"]


def test_permanent_non_json_error_is_not_retried(monkeypatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            404,
            text="not found",
            headers={"content-type": "text/plain"},
            request=request,
        )

    client = NSEHttpClient(
        base_url="https://niftyindices.com",
        rate_limit_per_sec=100,
    )
    _replace_sync_transport(client, handler)
    monkeypatch.setattr(client._request_with_retry.retry, "sleep", lambda _: None)
    try:
        with pytest.raises(UpstreamResponseError, match="status 404"):
            client.get_json("/missing")
    finally:
        client.close()

    assert calls == 1


def test_vendor_json_content_type_is_supported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"ok":true}',
            headers={"content-type": "application/problem+json; charset=utf-8"},
            request=request,
        )

    client = NSEHttpClient(
        base_url="https://niftyindices.com",
        rate_limit_per_sec=100,
    )
    _replace_sync_transport(client, handler)
    try:
        assert client.get_json("/api/data") == {"ok": True}
    finally:
        client.close()


def test_async_recreation_closes_old_client_and_resets_priming() -> None:
    async def run() -> None:
        client = NSEAsyncHttpClient(rate_limit_per_sec=100)
        old_client = MagicMock()
        old_client.aclose = AsyncMock()
        replacement = MagicMock()
        client._client = old_client
        client._primed = True
        client._build_client = MagicMock(return_value=replacement)  # type: ignore[method-assign]

        await client._recreate_client()

        assert client._client is replacement
        assert client._primed is False
        old_client.aclose.assert_awaited_once()

    asyncio.run(run())


def test_async_components_can_be_constructed_without_a_running_loop() -> None:
    bucket = AsyncTokenBucket(tokens=2, refill_rate=100.0)
    client = NSEAsyncHttpClient(
        base_url="https://nsearchives.nseindia.com",
        rate_limit_per_sec=100,
    )

    assert bucket._lock is None
    assert client._prime_lock is None

    async def run() -> None:
        await bucket.acquire()
        await client.aclose()

    asyncio.run(run())
    assert bucket._lock is not None


@pytest.mark.parametrize("bucket_type", [TokenBucket, AsyncTokenBucket])
def test_token_buckets_reject_impossible_costs(bucket_type) -> None:
    bucket = bucket_type(tokens=2, refill_rate=1.0)
    if bucket_type is TokenBucket:
        with pytest.raises(ValueError, match="capacity"):
            bucket.acquire(3)
    else:
        async def run() -> None:
            with pytest.raises(ValueError, match="capacity"):
                await bucket.acquire(3)

        asyncio.run(run())
