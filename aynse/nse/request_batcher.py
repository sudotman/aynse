"""
Request batching system for efficient NSE API calls.

This module implements request batching to reduce overhead when making
multiple API calls, especially useful for historical data fetching.
"""

import asyncio
import time
from typing import Dict, List, Any, Callable, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class BatchStrategy(Enum):
    """Different strategies for batching requests"""
    SEQUENTIAL = "sequential"  # Process batches one after another
    PARALLEL = "parallel"      # Process multiple batches in parallel
    ADAPTIVE = "adaptive"      # Dynamically adjust based on response times

@dataclass
class BatchResult:
    """Result of a batched request"""
    success: bool
    data: Any
    error: Optional[str] = None
    duration: float = 0.0
    retries: int = 0

@dataclass
class BatchStats:
    """Statistics for batch processing"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration: float
    avg_request_time: float
    requests_per_second: float

class RequestBatcher:
    """
    Efficient request batching system for NSE API calls.

    Supports both synchronous and asynchronous batching with different strategies.
    """

    def __init__(self,
                 max_batch_size: int = 10,
                 max_concurrent_batches: int = 3,
                 timeout: float = 30.0,
                 strategy: BatchStrategy = BatchStrategy.ADAPTIVE):
        """
        Initialize the request batcher.

        Args:
            max_batch_size: Maximum requests per batch
            max_concurrent_batches: Maximum concurrent batch processors
            timeout: Request timeout in seconds
            strategy: Batching strategy to use
        """
        self.max_batch_size = max_batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.timeout = timeout
        self.strategy = strategy

        self._stats = BatchStats(0, 0, 0, 0.0, 0.0, 0.0)
        self._lock = threading.Lock()

    def batch_requests(self,
                      requests: List[Dict[str, Any]],
                      request_func: Callable,
                      **kwargs) -> List[BatchResult]:
        """
        Process multiple requests in batches.

        Args:
            requests: List of request parameters
            request_func: Function to process individual requests
            **kwargs: Additional arguments for request_func

        Returns:
            List of BatchResult objects
        """
        if not requests:
            return []

        start_time = time.time()

        # Split requests into batches
        batches = self._create_batches(requests)

        all_results = []

        logger.info("batch_start", extra={
            "strategy": self.strategy.value,
            "requests": len(requests),
            "batches": len(batches),
            "max_batch_size": self.max_batch_size,
        })

        if self.strategy == BatchStrategy.SEQUENTIAL:
            # Process batches sequentially
            for batch in batches:
                batch_results = self._process_batch_sequential(batch, request_func, **kwargs)
                all_results.extend(batch_results)

        elif self.strategy == BatchStrategy.PARALLEL:
            # Process batches in parallel
            all_results = self._process_batch_parallel(batches, request_func, **kwargs)

        else:  # ADAPTIVE
            # Use adaptive strategy based on batch characteristics
            all_results = self._process_batch_adaptive(batches, request_func, **kwargs)

        # Update statistics
        end_time = time.time()
        duration = end_time - start_time

        logger.info("batch_complete", extra={
            "requests": len(requests),
            "duration_ms": int(duration * 1000),
            "success": sum(1 for r in all_results if r.success),
            "failed": sum(1 for r in all_results if not r.success),
        })

        with self._lock:
            self._stats.total_requests += len(requests)
            self._stats.successful_requests += sum(1 for r in all_results if r.success)
            self._stats.failed_requests += sum(1 for r in all_results if not r.success)
            self._stats.total_duration += duration
            if len(requests) > 0:
                self._stats.avg_request_time = duration / len(requests)
                self._stats.requests_per_second = len(requests) / duration if duration > 0 else 0

        return all_results

    async def abatch_requests(self,
                              requests: List[Dict[str, Any]],
                              request_coro_func: Callable[..., "asyncio.Future"],
                              max_concurrency: Optional[int] = None,
                              **kwargs) -> List[BatchResult]:
        """
        Async batch processing with bounded concurrency.

        Args:
            requests: List of request parameter dicts
            request_coro_func: Async function to call per request
            max_concurrency: Optional concurrency cap (defaults to max_concurrent_batches * max_batch_size)
            **kwargs: Extra kwargs for request function
        """
        if not requests:
            return []

        limit = max_concurrency or (self.max_concurrent_batches * self.max_batch_size)
        semaphore = asyncio.Semaphore(limit)
        results: List[BatchResult] = [None] * len(requests)  # type: ignore[assignment]

        async def run_one(idx: int, params: Dict[str, Any]) -> None:
            async with semaphore:
                start = time.time()
                try:
                    merged = {**params, **kwargs}
                    data = await request_coro_func(**merged)
                    duration = time.time() - start
                    results[idx] = BatchResult(True, data, None, duration, 0)
                except Exception as e:
                    duration = time.time() - start
                    results[idx] = BatchResult(False, None, str(e), duration, 0)

        await asyncio.gather(*(run_one(i, p) for i, p in enumerate(requests)))
        # Update statistics
        with self._lock:
            self._stats.total_requests += len(requests)
            self._stats.successful_requests += sum(1 for r in results if r and r.success)
            self._stats.failed_requests += sum(1 for r in results if r and not r.success)
            # avg/throughput not tracked for async in this simple implementation
        # type: ignore[return-value]
        return results

    def _create_batches(self, requests: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split requests into manageable batches"""
        batches = []
        for i in range(0, len(requests), self.max_batch_size):
            batch = requests[i:i + self.max_batch_size]
            batches.append(batch)
        return batches

    def _process_batch_sequential(self,
                                 batch: List[Dict[str, Any]],
                                 request_func: Callable,
                                 **kwargs) -> List[BatchResult]:
        """Process a batch sequentially"""
        results = []

        for request_params in batch:
            start_time = time.time()

            try:
                # Merge request parameters with additional kwargs
                merged_params = {**request_params, **kwargs}

                # Call the request function
                data = request_func(**merged_params)

                duration = time.time() - start_time
                results.append(BatchResult(success=True, data=data, duration=duration))

            except Exception as e:
                duration = time.time() - start_time
                results.append(BatchResult(
                    success=False,
                    data=None,
                    error=str(e),
                    duration=duration
                ))

        return results

    def _process_batch_parallel(self,
                               batches: List[List[Dict[str, Any]]],
                               request_func: Callable,
                               **kwargs) -> List[BatchResult]:
        """Process multiple batches in parallel"""
        all_results = [None] * len(batches)  # Pre-allocate for ordering

        with ThreadPoolExecutor(max_workers=self.max_concurrent_batches) as executor:
            # Submit all batches
            future_to_index = {
                executor.submit(self._process_batch_sequential, batch, request_func, **kwargs): i
                for i, batch in enumerate(batches)
            }

            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    batch_results = future.result()
                    all_results[index] = batch_results
                except Exception as e:
                    # If batch processing fails, create error results
                    batch_size = len(batches[index])
                    error_results = [
                        BatchResult(success=False, data=None, error=str(e), duration=0.0)
                        for _ in range(batch_size)
                    ]
                    all_results[index] = error_results

        # Flatten results while maintaining order
        flattened_results = []
        for batch_results in all_results:
            if batch_results:
                flattened_results.extend(batch_results)

        return flattened_results

    def _process_batch_adaptive(self,
                               batches: List[List[Dict[str, Any]]],
                               request_func: Callable,
                               **kwargs) -> List[BatchResult]:
        """Process batches using adaptive strategy"""
        # For small number of batches, use parallel processing
        if len(batches) <= self.max_concurrent_batches:
            return self._process_batch_parallel(batches, request_func, **kwargs)
        else:
            # For many batches, use sequential with progress monitoring
            return self._process_batch_sequential_adaptive(batches, request_func, **kwargs)

    def _process_batch_sequential_adaptive(self,
                                          batches: List[List[Dict[str, Any]]],
                                          request_func: Callable,
                                          **kwargs) -> List[BatchResult]:
        """Sequential processing with adaptive timing"""
        all_results = []
        batch_times = []

        for i, batch in enumerate(batches):
            start_time = time.time()

            batch_results = self._process_batch_sequential(batch, request_func, **kwargs)
            all_results.extend(batch_results)

            batch_duration = time.time() - start_time
            batch_times.append(batch_duration)

            # Adaptive delay based on recent performance
            if i > 0 and i % 5 == 0:  # Every 5 batches, adjust timing
                avg_recent = sum(batch_times[-5:]) / min(5, len(batch_times))
                if avg_recent > 10.0:  # If batches are taking too long
                    time.sleep(0.1)  # Small delay to prevent overwhelming the server

        return all_results

    def get_stats(self) -> BatchStats:
        """Get current batch processing statistics"""
        with self._lock:
            return self._stats

    def reset_stats(self):
        """Reset batch processing statistics"""
        with self._lock:
            self._stats = BatchStats(0, 0, 0, 0.0, 0.0, 0.0)

# Convenience functions for common batching scenarios

def batch_stock_requests(symbols: List[str],
                        from_date: str,
                        to_date: str,
                        series: str = "EQ",
                        batcher: Optional[RequestBatcher] = None) -> List[BatchResult]:
    """
    Batch multiple stock data requests.

    Args:
        symbols: List of stock symbols
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        series: Stock series (EQ, BE, etc.)
        batcher: Optional RequestBatcher instance

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    requests = [
        {"symbol": symbol, "from_date": from_date, "to_date": to_date, "series": series}
        for symbol in symbols
    ]

    # Import here to avoid circular imports
    from .history import stock_csv

    return batcher.batch_requests(requests, stock_csv, show_progress=False)

def batch_index_requests(symbols: List[str],
                        from_date: str,
                        to_date: str,
                        batcher: Optional[RequestBatcher] = None) -> List[BatchResult]:
    """
    Batch multiple index data requests.

    Args:
        symbols: List of index symbols
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        batcher: Optional RequestBatcher instance

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    requests = [
        {"symbol": symbol, "from_date": from_date, "to_date": to_date}
        for symbol in symbols
    ]

    # Import here to avoid circular imports
    from .history import index_csv

    return batcher.batch_requests(requests, index_csv, show_progress=False)

def batch_derivatives_requests(requests_data: List[Dict[str, Any]],
                              batcher: Optional[RequestBatcher] = None) -> List[BatchResult]:
    """
    Batch multiple derivatives data requests.

    Args:
        requests_data: List of request dictionaries with derivatives parameters
        batcher: Optional RequestBatcher instance

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    # Import here to avoid circular imports
    from .history import derivatives_csv

    return batcher.batch_requests(requests_data, derivatives_csv, show_progress=False)
