import datetime
import hashlib
import os
from unittest.mock import patch, Mock
import pandas as pd
from aynse import util as ut
import pytest
import math
from datetime import date
from unittest import TestCase
from appdirs import user_cache_dir
import pickle
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pyfakefs.fake_filesystem_unittest import TestCase


def test_break_dates():
    from_date = date(2000, 12, 14)
    to_date = date(2005, 1, 20)
    dates = ut.break_dates(from_date, to_date)
    assert from_date== dates[0][0]
    assert to_date == dates[-1][1]
    assert len(dates) ==  50

    from_date = date(2019, 1, 1)
    to_date = date(2020, 1, 31)
    dates = ut.break_dates(from_date, to_date)
    assert from_date == dates[0][0]
    assert to_date == dates[-1][1]
    assert len(dates) == 13

def test_np_float():
    assert 3.3 == pytest.approx(ut.np_float("3.3"))
    assert math.isnan(ut.np_float("-"))
    

def test_np_int():
    assert 3 == ut.np_int('3')
    assert 0 == ut.np_int('-')

def test_np_date():
    assert date(2020,1,1) == ut.np_date("2020-01-01")
    assert date(2020,7,30) == datetime.datetime.strptime("30-Jul-2020", "%d-%b-%Y").date()
    assert date(2020,7,30) == ut.np_date("30-Jul-2020")
    assert ut.np_date("20 Aug 2020") == date(2020, 8, 20)

def test_kw_to_fname():
    x = ut.kw_to_fname(self=[0], z='last', a='first')
    assert x == 'first-last'
    x = ut.kw_to_fname(z='last', a='first', self=[0])
    assert x == 'first-last'
    x = ut.kw_to_fname(self=[], symbol="SBIN", from_date=date(2020,1,1), to_date=date(2020,1,31))
    assert x == "2020-01-01-SBIN-2020-01-31"


def test_kw_to_fname_prevents_path_traversal_and_collisions():
    unsafe = ut.kw_to_fname(symbol="../../secret")
    similar = ut.kw_to_fname(symbol="secret")

    assert "/" not in unsafe
    assert "\\" not in unsafe
    assert ".." not in unsafe
    assert unsafe != similar
    assert unsafe == ut.kw_to_fname(symbol="../../secret")

def demo_for_pool(a, b):
    return (a + b)**2

class DemoForPool:
    def demo_for_pool(self, a, b):
        return (a + b)**2

    def pooled(self, params, use_threds):
        return ut.pool(self.demo_for_pool, params, use_threds)

def test_pool():
    for use_threads in [True, False]:
        params = [ (0, 1),
                    (1, 2),
                    (2, 3)]
        expected = [1, 9, 25]
        actual = ut.pool(demo_for_pool, params, use_threads)
        assert expected == list(actual)
        d = DemoForPool()
        actual = d.pooled(params, use_threads)
        assert expected == list(actual)




@ut.cached("testapp")
def demo_function(self, x, y):
    return {'x': x, 'y': y}

class DemoClass:
    @ut.cached("testapp")
    def demo_method(self, x, y):
        return {'x': x, 'y': y} 

@ut.cached("testapp")
def demo_crash(a, b):
    raise Exception("Terrible")

@ut.cached("testapp")
def demo_crashed(a, b):
    raise Exception("Terrible")

@ut.cached("testapp_ttl", max_age_seconds=1)
def demo_function_ttl(self, x, y):
    return {'x': x, 'y': y}

class TestCache(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        # Use environment variable to have predictable cache path with pyfakefs
        os.environ['J_CACHE_DIR'] = '/fakecache'
        self.cache_dir = os.path.join('/fakecache', 'testapp', 'testapp')

    def tearDown(self):
        if 'J_CACHE_DIR' in os.environ:
            del os.environ['J_CACHE_DIR']

    def test_demo_function(self):
        # Check if function returns correct value
        x = demo_function([0], 'v1', 'v2')
        self.assertEqual(x, {'x': 'v1', 'y': 'v2'})
        # Check if path exists
        path = os.path.join(self.cache_dir, 'v1__v1-v2.gz')
        self.assertTrue(os.path.isfile(path))
        # Next time it should read from cache, let us see if cache reading works
        # update the file with new values
        j = {'x': 'x1', 'y': 'y1'}
        import gzip
        with gzip.open(path, 'wb') as fp:
            pickle.dump(j, fp)
        # run the function
        x = demo_function([0], 'v1', 'v2')
        self.assertEqual(x, j)
    
    def test_demo_method(self):
        d = DemoClass()
        x = d.demo_method('v1', 'v2')
        self.assertEqual(x, {'x': 'v1', 'y': 'v2'})
        # Check if path exists
        path = os.path.join(self.cache_dir, 'v1__v1-v2.gz')
        self.assertTrue(os.path.isfile(path))
        # Next time it should read from cache, let us see if cache reading works
        # update the file with new values
        j = {'x': 'x1', 'y': 'y1'}
        import gzip
        with gzip.open(path, 'wb') as fp:
            pickle.dump(j, fp)
        # run the function
        x = d.demo_method('v1', 'v2')
        self.assertEqual(x, j)
        
    def test_demo_crashed(self):
        with pytest.raises(Exception):
            demo_crashed('fiz', 'buzz')        
        demo_function([0], 'lorem', 'ipsem') 
        path = os.path.join(self.cache_dir, 'v1__lorem-ipsem.gz')
        assert os.path.isfile(path)
        try:
            demo_crashed('buzz', 'fizz')
        except Exception:
            pass
        path = os.path.join(self.cache_dir, 'v1__buzz-fizz.gz')
        assert not os.path.isfile(path)
    
    def test_demo_with_environment_var(self):
        os.environ['J_CACHE_DIR'] = '/tmp/'
        x = demo_function([0], 'v1', 'v2')
        self.assertEqual(x, {'x': 'v1', 'y': 'v2'})
        
        # Check if path exists
        path = os.path.join("/tmp", 'testapp', 'testapp', 'v1__v1-v2.gz')
        self.assertTrue(os.path.isfile(path))
        # Next time it should read from cache, let us see if cache reading works
        # update the file with new values
        j = {'x': 'x1', 'y': 'y1'}
        import gzip
        with gzip.open(path, 'wb') as fp:
            pickle.dump(j, fp)
        # run the function
        x = demo_function([0], 'v1', 'v2')
        self.assertEqual(x, j)

    def test_cached_ttl_rebuilds_expired_entry(self):
        x = demo_function_ttl([0], 'v1', 'v2')
        self.assertEqual(x, {'x': 'v1', 'y': 'v2'})

        ttl_cache_dir = os.path.join('/fakecache', 'testapp_ttl', 'testapp_ttl')
        path = os.path.join(ttl_cache_dir, 'v1__v1-v2.gz')
        self.assertTrue(os.path.isfile(path))

        # Corrupt cached payload to prove fresh rebuild happens after expiry
        stale = {'x': 'stale', 'y': 'stale'}
        import gzip
        with gzip.open(path, 'wb') as fp:
            pickle.dump(stale, fp)

        # Expire cache by forcing old mtime
        old = time.time() - 120
        os.utime(path, (old, old))

        refreshed = demo_function_ttl([0], 'v1', 'v2')
        self.assertEqual(refreshed, {'x': 'v1', 'y': 'v2'})

class QuoteApp:
    time_out = 3
    @ut.live_cache
    def rt_quote(self):
        return datetime.datetime.now()

def test_live_cache():
    q = QuoteApp()
    r = q.rt_quote()
    import hashlib
    key_data = "rt_quote:"  # function name + ':' with no args
    cache_key = hashlib.md5(key_data.encode()).hexdigest()
    v = q._cache[cache_key]['value']
    ts = q._cache[cache_key]['timestamp']
    assert q.rt_quote() == v
    time.sleep(3)
    assert q.rt_quote() > v


def test_cached_does_not_serialize_unrelated_keys(fs, monkeypatch):
    monkeypatch.setenv("J_CACHE_DIR", "/cache")
    barrier = threading.Barrier(2)

    @ut.cached("parallel-cache")
    def load(key):
        barrier.wait(timeout=2)
        return key

    # Pick two cache keys that map to different lock stripes.
    candidates = [f"key-{index}" for index in range(100)]
    selected = None
    stripes = {}
    for key in candidates:
        path = os.path.join(
            "/cache",
            "parallel-cache",
            "parallel-cache",
            f"v1__{key}.gz",
        )
        digest = hashlib.sha256(path.encode("utf-8")).digest()
        stripe = int.from_bytes(digest[:4], "big") % 64
        if stripes and stripe not in stripes:
            selected = (next(iter(stripes.values())), key)
            break
        stripes[stripe] = key
    assert selected is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(load, key) for key in selected]
        assert [future.result(timeout=3) for future in futures] == list(selected)


def test_cached_computes_same_key_only_once(fs, monkeypatch):
    monkeypatch.setenv("J_CACHE_DIR", "/cache")
    calls = 0
    calls_lock = threading.Lock()

    @ut.cached("single-flight-cache")
    def load(key):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.02)
        return key

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(load, ["same"] * 4))

    assert results == ["same"] * 4
    assert calls == 1


def test_live_cache_allows_unrelated_keys_to_fetch_concurrently():
    barrier = threading.Barrier(2)

    class ConcurrentQuotes:
        time_out = 30

        @ut.live_cache
        def quote(self, symbol):
            barrier.wait(timeout=2)
            return symbol

    quotes = ConcurrentQuotes()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(quotes.quote, symbol) for symbol in ("A", "B")]
        assert [future.result(timeout=3) for future in futures] == ["A", "B"]


def test_live_cache_single_flights_identical_requests():
    calls = 0
    calls_lock = threading.Lock()

    class ConcurrentQuotes:
        time_out = 30

        @ut.live_cache
        def quote(self, symbol):
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.02)
            return symbol

    quotes = ConcurrentQuotes()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(quotes.quote, ["A"] * 4))

    assert results == ["A"] * 4
    assert calls == 1

