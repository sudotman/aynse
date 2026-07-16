import asyncio
import time
from datetime import date
from unittest.mock import patch

import pytest

from aynse.nse import history
from aynse.nse.request_batcher import (
    RequestBatcher,
    BatchStrategy,
    batch_derivatives_requests,
    batch_index_requests,
    batch_stock_requests,
)
from aynse.standard import InputValidationError


async def mock_async_request(value: int, delay_ms: int = 10):
    await asyncio.sleep(delay_ms / 1000.0)
    return value * 2


def test_async_batching_simple():
    batcher = RequestBatcher(max_batch_size=5, max_concurrent_batches=2, strategy=BatchStrategy.ADAPTIVE)
    requests = [{"value": i} for i in range(20)]

    async def run():
        results = await batcher.abatch_requests(requests, mock_async_request)
        # Ensure all results succeeded and are correctly transformed
        assert len(results) == len(requests)
        for i, r in enumerate(results):
            assert r.success
            assert r.data == i * 2

    asyncio.run(run())


def test_batch_helpers_normalize_date_inputs():
    with patch("aynse.nse.request_batcher.RequestBatcher.batch_requests", return_value=[]) as mock_batch:
        batch_stock_requests(["RELIANCE"], "2024-01-01", date(2024, 1, 5))
        requests = mock_batch.call_args[0][0]
        assert requests[0]["from_date"] == date(2024, 1, 1)
        assert requests[0]["to_date"] == date(2024, 1, 5)

    with patch("aynse.nse.request_batcher.RequestBatcher.batch_requests", return_value=[]) as mock_batch:
        batch_index_requests(["NIFTY 50"], "2024-01-01", "2024-01-05")
        requests = mock_batch.call_args[0][0]
        assert requests[0]["from_date"] == date(2024, 1, 1)
        assert requests[0]["to_date"] == date(2024, 1, 5)


def test_batch_helpers_can_return_records_without_writing_csv():
    with patch("aynse.nse.request_batcher.RequestBatcher.batch_requests", return_value=[]) as mock_batch:
        batch_stock_requests(
            ["RELIANCE"],
            "2024-01-01",
            "2024-01-05",
            output="records",
        )

    assert mock_batch.call_args.args[1] is history.stock_raw
    assert "show_progress" not in mock_batch.call_args.kwargs

    with patch("aynse.nse.request_batcher.RequestBatcher.batch_requests", return_value=[]) as mock_batch:
        batch_index_requests(
            ["NIFTY 50"],
            "2024-01-01",
            "2024-01-05",
            output="records",
        )

    assert mock_batch.call_args.args[1] is history.index_raw

    with patch("aynse.nse.request_batcher.RequestBatcher.batch_requests", return_value=[]) as mock_batch:
        batch_derivatives_requests(
            [
                {
                    "symbol": "NIFTY",
                    "from_date": "2024-01-01",
                    "to_date": "2024-01-05",
                    "expiry_date": "2024-01-25",
                    "instrument_type": "FUTIDX",
                }
            ],
            output="records",
        )

    assert mock_batch.call_args.args[1] is history.derivatives_raw
    request = mock_batch.call_args.args[0][0]
    assert request["from_date"] == date(2024, 1, 1)
    assert request["expiry_date"] == date(2024, 1, 25)


def test_batch_helpers_reject_unknown_output_mode():
    with pytest.raises(InputValidationError, match="csv.*records"):
        batch_stock_requests(
            ["RELIANCE"],
            "2024-01-01",
            "2024-01-05",
            output="parquet",
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_batch_size": 0}, "max_batch_size"),
        ({"max_concurrent_batches": -1}, "max_concurrent_batches"),
        ({"timeout": float("inf")}, "timeout"),
        ({"strategy": "unknown"}, "strategy"),
    ],
)
def test_batcher_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(InputValidationError, match=message):
        RequestBatcher(**kwargs)


def test_async_batcher_enforces_timeout_and_tracks_stats():
    async def slow_request() -> str:
        await asyncio.sleep(0.05)
        return "late"

    batcher = RequestBatcher(timeout=0.01)

    async def run():
        return await batcher.abatch_requests([{}], slow_request)

    results = asyncio.run(run())

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "request timed out after 0.01s"
    stats = batcher.get_stats()
    assert stats.total_requests == 1
    assert stats.failed_requests == 1
    assert stats.total_duration > 0


def test_get_stats_returns_a_defensive_snapshot():
    batcher = RequestBatcher()
    snapshot = batcher.get_stats()
    snapshot.total_requests = 999

    assert batcher.get_stats().total_requests == 0


def test_async_batcher_rejects_invalid_concurrency():
    batcher = RequestBatcher()

    async def run():
        return await batcher.abatch_requests(
            [{}],
            mock_async_request,
            max_concurrency=0,
        )

    with pytest.raises(InputValidationError, match="max_concurrency"):
        asyncio.run(run())


