"""
Utility functions for the aynse library.

This module provides:
- Date range utilities for API calls
- Caching decorators for API responses
- Thread pool utilities for parallel processing
- NumPy type conversion helpers
"""

from __future__ import annotations

import os
import collections
import json
import pickle
import time
import gzip
import calendar
import hashlib
import threading
import logging
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import click
from appdirs import user_cache_dir

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Type variables for generic functions
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Optional numpy import
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False


class NumpyNotAvailableError(ModuleNotFoundError):
    """Raised when numpy is required but not installed."""
    pass


def require_numpy(func: F) -> F:
    """
    Decorator that raises an error if numpy is not available.
    
    Args:
        func: Function that requires numpy
        
    Returns:
        Wrapped function that checks for numpy availability
        
    Raises:
        NumpyNotAvailableError: If numpy is not installed
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not HAS_NUMPY:
            raise NumpyNotAvailableError(
                "numpy is required for this function. "
                "Install it with: pip install numpy pandas"
            )
        return func(*args, **kwargs)
    return wrapper  # type: ignore[return-value]


# Legacy alias for backwards compatibility
np_exception = require_numpy


@require_numpy
def np_float(num: Any) -> Any:
    """
    Convert a value to numpy float64.
    
    Args:
        num: Value to convert (can be string, int, or float)
        
    Returns:
        np.float64 value, or np.nan if conversion fails
    """
    try:
        return np.float64(num)
    except (ValueError, TypeError):
        return np.nan


@require_numpy
def np_date(dt: Any) -> Any:
    """
    Convert a value to numpy datetime64.
    
    Supports multiple date formats:
    - ISO format: 2020-01-01
    - NSE format: 01-Jan-2020
    - Alternate format: 01 Jan 2020
    
    Args:
        dt: Date value or string to convert
        
    Returns:
        np.datetime64 value, or np.datetime64('NaT') if conversion fails
    """
    # Try direct conversion first
    try:
        return np.datetime64(dt)
    except (ValueError, TypeError):
        pass

    # Try NSE format: 01-Jan-2020
    try:
        parsed = datetime.strptime(str(dt), "%d-%b-%Y").date()
        return np.datetime64(parsed)
    except (ValueError, TypeError):
        pass

    # Try alternate format: 01 Jan 2020
    try:
        parsed = datetime.strptime(str(dt), "%d %b %Y").date()
        return np.datetime64(parsed)
    except (ValueError, TypeError):
        pass

    return np.datetime64('NaT')


@require_numpy
def np_int(num: Any) -> Any:
    """
    Convert a value to numpy int64.
    
    Args:
        num: Value to convert
        
    Returns:
        np.int64 value, or 0 if conversion fails
    """
    try:
        return np.int64(num)
    except (ValueError, TypeError):
        return np.int64(0)


def break_dates(
    from_date: date,
    to_date: date,
    max_days_per_chunk: int = 31
) -> List[Tuple[date, date]]:
    """
    Break a date range into monthly chunks for efficient API calls.
    
    The NSE API typically limits requests to one month at a time,
    so this function splits larger date ranges into monthly chunks.
    
    Args:
        from_date: Start date of the range
        to_date: End date of the range
        max_days_per_chunk: Maximum days per chunk (default: 31)
        
    Returns:
        List of (start_date, end_date) tuples for each chunk
        
    Raises:
        ValueError: If from_date is after to_date
        
    Example:
        >>> from datetime import date
        >>> break_dates(date(2024, 1, 15), date(2024, 3, 20))
        [(date(2024, 1, 15), date(2024, 1, 31)),
         (date(2024, 2, 1), date(2024, 2, 29)),
         (date(2024, 3, 1), date(2024, 3, 20))]
    """
    if from_date > to_date:
        raise ValueError(
            f"from_date ({from_date}) must be before or equal to to_date ({to_date})"
        )
    
    # Handle same month case efficiently
    if from_date.replace(day=1) == to_date.replace(day=1):
        return [(from_date, to_date)]

    date_ranges: List[Tuple[date, date]] = []
    current_month_start = from_date

    while current_month_start <= to_date:
        # Calculate end of current month
        month_last_day = calendar.monthrange(
            current_month_start.year, 
            current_month_start.month
        )[1]
        month_end = current_month_start.replace(day=month_last_day)

        # Ensure we don't go beyond the target end date
        actual_end = min(month_end, to_date)
        date_ranges.append((current_month_start, actual_end))

        # Move to next month
        if actual_end >= to_date:
            break

        # Calculate next month start
        if current_month_start.month == 12:
            current_month_start = current_month_start.replace(
                year=current_month_start.year + 1, 
                month=1, 
                day=1
            )
        else:
            current_month_start = current_month_start.replace(
                month=current_month_start.month + 1, 
                day=1
            )

    return date_ranges


def kw_to_fname(**kwargs: Any) -> str:
    """
    Convert keyword arguments to a filename-safe string.
    
    Used for generating cache file names from function parameters.
    
    Args:
        **kwargs: Keyword arguments to convert
        
    Returns:
        Hyphen-separated string of sorted keyword values (excluding 'self')
        
    Example:
        >>> kw_to_fname(symbol="RELIANCE", from_date=date(2024, 1, 1))
        '2024-01-01-RELIANCE'
    """
    return "-".join(
        str(kwargs[k]) 
        for k in sorted(kwargs) 
        if k != "self"
    )


def cached(app_name: str) -> Callable[[F], F]:
    """
    Decorator for caching function results to disk.
    
    Results are stored as gzip-compressed pickle files in a user-specific
    cache directory. The cache key is generated from the function arguments.
    
    Args:
        app_name: Name of the application (used for cache directory)
        
    Returns:
        Decorator function
        
    Environment Variables:
        J_CACHE_DIR: Override default cache directory
        
    Example:
        @cached("myapp")
        def expensive_function(symbol, date):
            # ... expensive API call ...
            return data
    """
    CACHE_VERSION = "v1"
    cache_lock = threading.RLock()

    def decorator(function: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Convert positional args to kwargs using function signature
            kwargs.update(zip(function.__code__.co_varnames, args))
            
            # Determine cache directory
            env_dir = os.environ.get("J_CACHE_DIR")
            if env_dir:
                cache_dir = os.path.join(env_dir, app_name, app_name)
            else:
                cache_dir = user_cache_dir(app_name, app_name)

            # Generate cache file path
            file_name = kw_to_fname(**kwargs)
            cache_path = os.path.join(cache_dir, f"{CACHE_VERSION}__{file_name}.gz")

            with cache_lock:
                if os.path.isfile(cache_path):
                    # Try to read from cache
                    try:
                        with gzip.open(cache_path, 'rb') as fp:
                            return pickle.load(fp)
                    except (pickle.UnpicklingError, OSError, EOFError) as e:
                        # Corrupted cache - will rebuild below
                        logger.warning(
                            f"Corrupted cache file {cache_path}, rebuilding: {e}"
                        )

                # Create cache directory if needed
                os.makedirs(cache_dir, exist_ok=True)
                
                # Call function and cache result
                result = function(**kwargs)
                
                try:
                    with gzip.open(cache_path, 'wb') as fp:
                        pickle.dump(result, fp, protocol=pickle.HIGHEST_PROTOCOL)
                except (OSError, pickle.PicklingError) as e:
                    logger.warning(f"Failed to write cache file {cache_path}: {e}")
                
                return result
                
        return wrapper  # type: ignore[return-value]
    return decorator


def pool(
    function: Callable[..., T],
    params: List[Tuple[Any, ...]],
    use_threads: bool = True,
    max_workers: int = 2
) -> List[Optional[T]]:
    """
    Execute a function over multiple parameter sets, optionally in parallel.
    
    Args:
        function: Function to execute
        params: List of parameter tuples to pass to the function
        use_threads: If True, use ThreadPoolExecutor; otherwise sequential
        max_workers: Maximum number of concurrent threads
        
    Returns:
        List of results (None for failed calls)
        
    Example:
        >>> def add(a, b): return a + b
        >>> pool(add, [(1, 2), (3, 4), (5, 6)])
        [3, 7, 11]
    """
    results: List[Optional[T]] = []
    
    if use_threads and len(params) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = [executor.submit(function, *param) for param in params]
            
            # Collect results in order
            for i, future in enumerate(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.warning(
                        f"Error in pooled function call {i}: {e}",
                        exc_info=True
                    )
                    results.append(None)
    else:
        # Sequential processing
        for i, param in enumerate(params):
            try:
                result = function(*param)
                results.append(result)
            except Exception as e:
                logger.warning(
                    f"Error in sequential function call {i}: {e}",
                    exc_info=True
                )
                results.append(None)
    
    return results


def live_cache(func: F) -> F:
    """
    Decorator for time-based caching of live data functions.
    
    Caches the result of a function for a configurable timeout period.
    This is useful for live market data where we want to avoid hitting
    the API too frequently but still get reasonably fresh data.
    
    The decorated class must have a `time_out` attribute specifying
    the cache duration in seconds.
    
    Args:
        func: Method to cache (must be an instance method)
        
    Returns:
        Wrapped method with time-based caching
        
    Example:
        class LiveData:
            time_out = 5  # Cache for 5 seconds
            
            @live_cache
            def get_quote(self, symbol):
                # ... expensive API call ...
                return quote
    """
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Generate cache key using function name and arguments
        inputs = [str(a) for a in args]
        inputs.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        key_data = f"{func.__name__}:{','.join(inputs)}"
        cache_key = hashlib.md5(key_data.encode()).hexdigest()

        now = datetime.now()
        time_out = getattr(self, 'time_out', 5)  # Default 5 seconds

        # Initialize cache and lock if needed
        if not hasattr(self, '_cache'):
            self._cache: Dict[str, Dict[str, Any]] = {}
        if not hasattr(self, '_cache_lock'):
            self._cache_lock = threading.RLock()

        with self._cache_lock:
            # Check for valid cached value
            cache_obj = self._cache.get(cache_key)
            if cache_obj:
                age = now - cache_obj['timestamp']
                if age < timedelta(seconds=time_out):
                    return cache_obj['value']

            # Fetch new value
            value = func(self, *args, **kwargs)
            self._cache[cache_key] = {'value': value, 'timestamp': now}

            # Simple cache eviction: remove oldest entries if cache is too large
            max_cache_size = getattr(self, '_max_cache_size', 100)
            if len(self._cache) > max_cache_size:
                # Sort by timestamp and remove oldest half
                sorted_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k]['timestamp']
                )
                for old_key in sorted_keys[:len(sorted_keys) // 2]:
                    del self._cache[old_key]

            return value

    return wrapper  # type: ignore[return-value]


def clear_cache(app_name: str) -> int:
    """
    Clear all cached files for a given application.
    
    Args:
        app_name: Name of the application whose cache to clear
        
    Returns:
        Number of files deleted
    """
    env_dir = os.environ.get("J_CACHE_DIR")
    if env_dir:
        cache_dir = os.path.join(env_dir, app_name, app_name)
    else:
        cache_dir = user_cache_dir(app_name, app_name)
    
    if not os.path.isdir(cache_dir):
        return 0
    
    deleted = 0
    for filename in os.listdir(cache_dir):
        if filename.endswith('.gz'):
            try:
                os.remove(os.path.join(cache_dir, filename))
                deleted += 1
            except OSError as e:
                logger.warning(f"Failed to delete cache file {filename}: {e}")
    
    return deleted


def is_trading_day(dt: date, holidays_list: Optional[List[date]] = None) -> bool:
    """
    Check if a given date is a trading day.
    
    A trading day is a weekday (Monday-Friday) that is not a holiday.
    
    Args:
        dt: Date to check
        holidays_list: Optional list of holiday dates. If None, uses
                       the holidays from the holidays module.
                       
    Returns:
        True if the date is a trading day, False otherwise
    """
    # Check if weekend
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # Get holidays list if not provided
    if holidays_list is None:
        from .holidays import holidays
        holidays_list = holidays(year=dt.year)
    
    return dt not in holidays_list


def get_next_trading_day(
    dt: date,
    holidays_list: Optional[List[date]] = None
) -> date:
    """
    Get the next trading day on or after the given date.
    
    Args:
        dt: Starting date
        holidays_list: Optional list of holiday dates
        
    Returns:
        The next trading day
    """
    while not is_trading_day(dt, holidays_list):
        dt = dt + timedelta(days=1)
    return dt


def get_previous_trading_day(
    dt: date,
    holidays_list: Optional[List[date]] = None
) -> date:
    """
    Get the previous trading day before the given date.
    
    Args:
        dt: Starting date
        holidays_list: Optional list of holiday dates
        
    Returns:
        The previous trading day
    """
    dt = dt - timedelta(days=1)
    while not is_trading_day(dt, holidays_list):
        dt = dt - timedelta(days=1)
    return dt
