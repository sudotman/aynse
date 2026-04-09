import asyncio
import time
from datetime import date
from unittest.mock import patch

from aynse.nse.request_batcher import (
    RequestBatcher,
    BatchStrategy,
    batch_index_requests,
    batch_stock_requests,
)


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


