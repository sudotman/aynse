import os
import collections
import json
import pickle
import time
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor
import click
from appdirs import user_cache_dir
import threading
import gzip

import calendar

import math

try:
    import numpy as np
except:
    np = None

def np_exception(function):
    def wrapper(*args, **kwargs):
        if not np:
            raise ModuleNotFoundError("Please install pandas and numpy using \n pip install pandas")
        return function(*args, **kwargs)

    return wrapper

@np_exception
def np_float(num):
    try:
        return np.float64(num)
    except:
        return np.nan

@np_exception
def np_date(dt):
    try:
        return np.datetime64(dt)
    except:
        pass

    try:
        dt = datetime.strptime(dt, "%d-%b-%Y").date()
        return np.datetime64(dt)
    except:
        pass

    try:
        dt = datetime.strptime(dt, "%d %b %Y").date()
        return np.datetime64(dt)
    except:
        pass



    return np.datetime64('nat') 

    
@np_exception
def np_int(num):
    try:
        return np.int64(num)
    except:
        return 0

def break_dates(from_date, to_date):
    """
    Break a date range into monthly chunks for efficient API calls.

    Issues identified:
    - Repeatedly calculates month ranges which could be cached
    - No optimization for consecutive months
    - Could benefit from vectorized operations for large ranges
    """
    # Handle same month case efficiently
    if from_date.replace(day=1) == to_date.replace(day=1):
        return [(from_date, to_date)]

    date_ranges = []

    # Use efficient month iteration starting exactly at from_date
    current_month_start = from_date

    while current_month_start <= to_date:
        # Calculate end of current month
        month_end = current_month_start.replace(day=calendar.monthrange(current_month_start.year, current_month_start.month)[1])

        # Ensure we don't go beyond the target end date
        actual_end = min(month_end, to_date)

        date_ranges.append((current_month_start, actual_end))

        # Move to next month
        if actual_end >= to_date:
            break

        # More efficient way to get next month start
        if current_month_start.month == 12:
            current_month_start = current_month_start.replace(year=current_month_start.year + 1, month=1, day=1)
        else:
            current_month_start = current_month_start.replace(month=current_month_start.month + 1, day=1)

    return date_ranges


def kw_to_fname(**kw):
    name = "-".join([str(kw[k]) for k in sorted(kw) if k != "self"])
    return name



def cached(app_name):
    """
        Note to self:
            This is a russian doll
            wrapper - actual caching mechanism
            _cached - actual decorator
            cached - wrapper around decorator to make 'app_name' dynamic
    """
    CACHE_VERSION = "v1"
    cache_lock = threading.RLock()

    def _cached(function):
        def wrapper(*args, **kw):
            kw.update(zip(function.__code__.co_varnames, args))
            env_dir = os.environ.get("J_CACHE_DIR")
            if not env_dir:
                cache_dir = user_cache_dir(app_name, app_name)
            else:
                # Mirror appdirs behaviour with nested app_name directory
                cache_dir = os.path.join(env_dir, app_name, app_name)

            file_name = kw_to_fname(**kw)
            path = os.path.join(cache_dir, f"{CACHE_VERSION}__{file_name}.gz")

            with cache_lock:
                if not os.path.isfile(path):    
                    if not os.path.exists(cache_dir):
                        os.makedirs(cache_dir)
                    j = function(**kw)
                    with gzip.open(path, 'wb') as fp:
                        pickle.dump(j, fp, protocol=pickle.HIGHEST_PROTOCOL)
                else:
                    try:
                        with gzip.open(path, 'rb') as fp:
                            j = pickle.load(fp)
                    except (pickle.UnpicklingError, OSError):
                        # Corrupted cache - rebuild
                        j = function(**kw)
                        with gzip.open(path, 'wb') as fp:
                            pickle.dump(j, fp, protocol=pickle.HIGHEST_PROTOCOL)
            return j
        return wrapper
    return _cached


def pool(function, params, use_threads=True, max_workers=2):
    """
    Execute a function over multiple parameters using threading or sequential processing.

    Issues identified:
    - Creates new ThreadPoolExecutor for each call instead of reusing
    - No error handling for individual function failures in threaded mode
    - No progress reporting for long-running operations
    - Thread pool size is fixed and not optimized for workload
    """
    if use_threads:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            # Submit all tasks and handle results with error handling
            futures = [ex.submit(function, *param) for param in params]
            results = []
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Log the error but continue processing other results
                    print(f"Error in pooled function: {e}")
                    results.append(None)
            return results
    else:
        dfs = []
        for param in params:
            try:
                r = function(*param)
            except Exception as e:
                print(f"Error in sequential function: {e}")
                r = None
            dfs.append(r)
    return dfs

def live_cache(app_name):
    """Caches the output for time_out specified. This is done in order to
    prevent hitting live quote requests to NSE too frequently. This wrapper
    will fetch the quote/live result first time and return the same result for
    any calls within 'time_out' seconds.

    Issues identified:
    - Cache key generation is fragile and may not handle complex arguments properly
    - No cache size limits - could grow indefinitely with many different parameters
    - Exception handling is too broad and may hide real issues
    - Cache cleanup is not implemented

    Logic:
        key = concat of args
        try:
            cached_value = self._cache[key]
            if now - self._cache['timestamp'] < time_out
                return cached_value['value']
        except AttributeError: # _cache attribute has not been created yet
            self._cache = {}
        except KeyError: # Cache key doesn't exist
            pass
        finally:
            val = fetch-new-value
            new_value = {'timestamp': now, 'value': val}
            self._cache[key] = new_value
            return val

    """
    def wrapper(self, *args, **kwargs):
        """Wrapper function which calls the function only after the timeout,
        otherwise returns value from the cache.

        """
        # Generate more robust cache key using function name and arguments
        # Use hash of string representation for better key handling
        import hashlib
        inputs = [str(a) for a in args] + [f"{k}:{kwargs[k]}" for k in sorted(kwargs.keys())]
        key_data = f"{app_name.__name__}:{','.join(inputs)}"
        key = hashlib.md5(key_data.encode()).hexdigest()

        now = datetime.now()
        time_out = self.time_out

        # Initialize cache and lock if they don't exist
        if not hasattr(self, '_cache'):
            self._cache = {}
        if not hasattr(self, '_cache_lock'):
            self._cache_lock = threading.RLock()

        with self._cache_lock:
            # Check cache for valid entry
            cache_obj = self._cache.get(key)
            if cache_obj and (now - cache_obj['timestamp']) < timedelta(seconds=time_out):
                return cache_obj['value']

            # Fetch new value and update cache
            value = app_name(self, *args, **kwargs)
            self._cache[key] = {'value': value, 'timestamp': now}

            # Implement simple cache size management (keep only last 100 entries)
            if len(self._cache) > 100:
                # Remove oldest entries (simple FIFO)
                oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k]['timestamp'])[:50]
                for old_key in oldest_keys:
                    del self._cache[old_key]

        return value

    return wrapper 

