"""Concurrent HTTP helpers must return their own response, not shared state."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from aynse.nse.archives import NSEArchives
from aynse.nse.history import NSEHistory


class _Response:
    def __init__(self, value: str) -> None:
        self.value = value


class _BarrierOnResponseAssignment:
    assignment_barrier: threading.Barrier

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "r" and isinstance(value, _Response):
            self.assignment_barrier.wait(timeout=5)


class _ConcurrentHistory(_BarrierOnResponseAssignment, NSEHistory):
    pass


class _ConcurrentArchives(_BarrierOnResponseAssignment, NSEArchives):
    pass


def test_history_get_returns_thread_local_response() -> None:
    instance = _ConcurrentHistory()
    instance.assignment_barrier = threading.Barrier(2)

    class Client:
        def get(self, path, params):
            return _Response(params["symbol"])

    instance.connection_pool = SimpleNamespace(get_client=lambda _: Client())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(instance._get, "stock_history", {"symbol": symbol})
            for symbol in ("A", "B")
        ]
        values = [future.result(timeout=5).value for future in futures]

    assert values == ["A", "B"]


def test_archive_get_returns_thread_local_response() -> None:
    instance = _ConcurrentArchives()
    instance.assignment_barrier = threading.Barrier(2)

    class Client:
        def _request_with_retry(self, method, path):
            return _Response(path)

    instance.connection_pool = SimpleNamespace(get_client=lambda _: Client())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                instance.get,
                "bhavcopy",
                yyyy=2026,
                MMM=month,
                dd="01",
            )
            for month in ("JAN", "FEB")
        ]
        values = [future.result(timeout=5).value for future in futures]

    assert "JAN" in values[0]
    assert "FEB" in values[1]
