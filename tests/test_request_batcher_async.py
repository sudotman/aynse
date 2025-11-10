import asyncio
import time
from aynse.nse.request_batcher import RequestBatcher, BatchStrategy


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


