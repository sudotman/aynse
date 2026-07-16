"""
Request batching system for efficient NSE API calls.

This module implements request batching to reduce overhead when making
multiple API calls, especially useful for historical data fetching.
"""

import asyncio
import time
from math import isfinite
from typing import Awaitable, Dict, List, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from ..standard import InputValidationError, coerce_date

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
        if (
            isinstance(max_batch_size, bool)
            or not isinstance(max_batch_size, int)
            or max_batch_size <= 0
        ):
            raise InputValidationError("max_batch_size must be a positive integer")
        if (
            isinstance(max_concurrent_batches, bool)
            or not isinstance(max_concurrent_batches, int)
            or max_concurrent_batches <= 0
        ):
            raise InputValidationError(
                "max_concurrent_batches must be a positive integer"
            )
        if isinstance(timeout, bool):
            raise InputValidationError("timeout must be a positive finite number")
        try:
            normalized_timeout = float(timeout)
        except (TypeError, ValueError) as exc:
            raise InputValidationError(
                "timeout must be a positive finite number"
            ) from exc
        if not isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise InputValidationError("timeout must be a positive finite number")
        try:
            normalized_strategy = BatchStrategy(strategy)
        except (TypeError, ValueError) as exc:
            choices = ", ".join(item.value for item in BatchStrategy)
            raise InputValidationError(
                f"strategy must be one of: {choices}"
            ) from exc

        self.max_batch_size = max_batch_size
        self.max_concurrent_batches = max_concurrent_batches
        # Async requests are cancellable and enforce this timeout. Synchronous
        # callables must continue to apply their own transport-level timeout.
        self.timeout = normalized_timeout
        self.strategy = normalized_strategy

        self._stats = BatchStats(0, 0, 0, 0.0, 0.0, 0.0)
        self._lock = threading.Lock()

    def batch_requests(
        self,
        requests: List[Dict[str, Any]],
        request_func: Callable[..., Any],
        **kwargs: Any
    ) -> List[BatchResult]:
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

        start_time = time.monotonic()

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
        end_time = time.monotonic()
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
            if self._stats.total_requests > 0:
                self._stats.avg_request_time = (
                    self._stats.total_duration / self._stats.total_requests
                )
                self._stats.requests_per_second = (
                    self._stats.total_requests / self._stats.total_duration
                    if self._stats.total_duration > 0
                    else 0
                )

        return all_results

    async def abatch_requests(
        self,
        requests: List[Dict[str, Any]],
        request_coro_func: Callable[..., Awaitable[Any]],
        max_concurrency: Optional[int] = None,
        **kwargs: Any
    ) -> List[BatchResult]:
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

        if max_concurrency is not None and (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency <= 0
        ):
            raise InputValidationError("max_concurrency must be a positive integer")
        limit = max_concurrency or (
            self.max_concurrent_batches * self.max_batch_size
        )
        semaphore = asyncio.Semaphore(limit)
        results: List[BatchResult] = [None] * len(requests)  # type: ignore[assignment]
        batch_started = time.monotonic()

        async def run_one(idx: int, params: Dict[str, Any]) -> None:
            async with semaphore:
                start = time.monotonic()
                try:
                    merged = {**params, **kwargs}
                    data = await asyncio.wait_for(
                        request_coro_func(**merged),
                        timeout=self.timeout,
                    )
                    duration = time.monotonic() - start
                    results[idx] = BatchResult(True, data, None, duration, 0)
                except asyncio.TimeoutError:
                    duration = time.monotonic() - start
                    results[idx] = BatchResult(
                        False,
                        None,
                        f"request timed out after {self.timeout:g}s",
                        duration,
                        0,
                    )
                except Exception as e:
                    duration = time.monotonic() - start
                    results[idx] = BatchResult(False, None, str(e), duration, 0)

        await asyncio.gather(*(run_one(i, p) for i, p in enumerate(requests)))
        batch_duration = time.monotonic() - batch_started
        # Update statistics
        with self._lock:
            self._stats.total_requests += len(requests)
            self._stats.successful_requests += sum(1 for r in results if r and r.success)
            self._stats.failed_requests += sum(1 for r in results if r and not r.success)
            self._stats.total_duration += batch_duration
            self._stats.avg_request_time = (
                self._stats.total_duration / self._stats.total_requests
            )
            self._stats.requests_per_second = (
                self._stats.total_requests / self._stats.total_duration
                if self._stats.total_duration > 0
                else 0
            )
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
            start_time = time.monotonic()

            try:
                # Merge request parameters with additional kwargs
                merged_params = {**request_params, **kwargs}

                # Call the request function
                data = request_func(**merged_params)

                duration = time.monotonic() - start_time
                results.append(BatchResult(success=True, data=data, duration=duration))

            except Exception as e:
                duration = time.monotonic() - start_time
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
            start_time = time.monotonic()

            batch_results = self._process_batch_sequential(batch, request_func, **kwargs)
            all_results.extend(batch_results)

            batch_duration = time.monotonic() - start_time
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
            return BatchStats(**vars(self._stats))

    def reset_stats(self):
        """Reset batch processing statistics"""
        with self._lock:
            self._stats = BatchStats(0, 0, 0, 0.0, 0.0, 0.0)

# Convenience functions for common batching scenarios

def batch_stock_requests(symbols: List[str],
                        from_date,
                        to_date,
                        series: str = "EQ",
                        batcher: Optional[RequestBatcher] = None,
                        output: str = "csv") -> List[BatchResult]:
    """
    Batch multiple stock data requests.

    Args:
        symbols: List of stock symbols
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        series: Stock series (EQ, BE, etc.)
        batcher: Optional RequestBatcher instance
        output: "csv" for saved file paths or "records" for canonical
            in-memory records

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    start = coerce_date(from_date, "from_date")
    end = coerce_date(to_date, "to_date")

    requests = [
        {"symbol": symbol, "from_date": start, "to_date": end, "series": series}
        for symbol in symbols
    ]

    # Import here to avoid circular imports
    from .history import stock_csv, stock_raw

    mode = _normalize_batch_output(output)
    if mode == "records":
        return batcher.batch_requests(requests, stock_raw)
    return batcher.batch_requests(requests, stock_csv, show_progress=False)

def batch_index_requests(symbols: List[str],
                        from_date,
                        to_date,
                        batcher: Optional[RequestBatcher] = None,
                        output: str = "csv") -> List[BatchResult]:
    """
    Batch multiple index data requests.

    Args:
        symbols: List of index symbols
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        batcher: Optional RequestBatcher instance
        output: "csv" for saved file paths or "records" for canonical
            in-memory records

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    start = coerce_date(from_date, "from_date")
    end = coerce_date(to_date, "to_date")

    requests = [
        {"symbol": symbol, "from_date": start, "to_date": end}
        for symbol in symbols
    ]

    # Import here to avoid circular imports
    from .history import index_csv, index_raw

    mode = _normalize_batch_output(output)
    if mode == "records":
        return batcher.batch_requests(requests, index_raw)
    return batcher.batch_requests(requests, index_csv, show_progress=False)

def batch_derivatives_requests(requests_data: List[Dict[str, Any]],
                              batcher: Optional[RequestBatcher] = None,
                              output: str = "csv") -> List[BatchResult]:
    """
    Batch multiple derivatives data requests.

    Args:
        requests_data: List of request dictionaries with derivatives parameters
        batcher: Optional RequestBatcher instance
        output: "csv" for saved file paths or "records" for canonical
            in-memory records

    Returns:
        List of BatchResult objects
    """
    if batcher is None:
        batcher = RequestBatcher()

    normalized_requests = []
    for request in requests_data:
        item = dict(request)
        if "from_date" in item:
            item["from_date"] = coerce_date(item["from_date"], "from_date")
        if "to_date" in item:
            item["to_date"] = coerce_date(item["to_date"], "to_date")
        if "expiry_date" in item:
            item["expiry_date"] = coerce_date(item["expiry_date"], "expiry_date")
        normalized_requests.append(item)

    # Import here to avoid circular imports
    from .history import derivatives_csv, derivatives_raw

    mode = _normalize_batch_output(output)
    if mode == "records":
        return batcher.batch_requests(normalized_requests, derivatives_raw)
    return batcher.batch_requests(normalized_requests, derivatives_csv, show_progress=False)


def _normalize_batch_output(output: str) -> str:
    mode = str(output).strip().lower()
    if mode not in {"csv", "records"}:
        raise InputValidationError("output must be either 'csv' or 'records'")
    return mode
