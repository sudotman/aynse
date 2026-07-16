"""
Tests for the NSE connection pool module.

Tests cover:
- Connection pool initialization and configuration
- Client creation and reuse
- Session TTL and cleanup
- Thread safety
- Backwards compatibility
"""

from __future__ import annotations

import asyncio
import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from aynse.nse.connection_pool import (
    NSEConnectionPool,
    get_connection_pool,
    reset_connection_pool,
)
from aynse.nse.http_client import NSEAsyncHttpClient, NSEHttpClient


class TestNSEConnectionPool:
    """Tests for NSEConnectionPool class."""
    
    def test_pool_initialization(self):
        """Test that pool initializes with correct defaults."""
        pool = NSEConnectionPool()
        
        assert pool.session_ttl == 300
        assert pool.max_sessions == 10
        assert pool._clients == {}
        assert pool._aclients == {}
    
    def test_pool_custom_config(self):
        """Test pool with custom configuration."""
        pool = NSEConnectionPool(session_ttl=60, max_sessions=5)
        
        assert pool.session_ttl == 60
        assert pool.max_sessions == 5
    
    def test_get_client_creates_new(self):
        """Test that get_client creates a new client for a new host."""
        pool = NSEConnectionPool()
        
        with patch.object(NSEHttpClient, '__init__', return_value=None):
            with patch.object(NSEHttpClient, '_prime_session'):
                client = pool.get_client("https://www.nseindia.com")
        
        # Should have created a client entry
        assert "www.nseindia.com" in pool._clients
    
    def test_get_client_reuses_existing(self):
        """Test that get_client reuses existing valid client."""
        pool = NSEConnectionPool(session_ttl=300)
        
        # Create mock client
        mock_client = MagicMock(spec=NSEHttpClient)
        pool._clients["www.nseindia.com"] = {
            "client_0": {
                "client": mock_client,
                "created": time.monotonic(),
                "last_used": time.monotonic(),
            }
        }
        
        # Should return the same mock client
        result = pool.get_client("https://www.nseindia.com")
        assert result is mock_client
    
    def test_get_session_backwards_compat(self):
        """Test get_session is an alias for get_client."""
        pool = NSEConnectionPool()
        
        # get_session should work as get_client
        with patch.object(pool, 'get_client') as mock_get:
            pool.get_session("https://www.nseindia.com")
            mock_get.assert_called_once_with("https://www.nseindia.com")
    
    def test_pool_stats(self):
        """Test get_pool_stats returns correct information."""
        pool = NSEConnectionPool(session_ttl=300, max_sessions=10)
        
        stats = pool.get_pool_stats()
        
        assert stats['sync_clients'] == 0
        assert stats['async_clients'] == 0
        assert stats['max_per_host'] == 10
        assert stats['ttl_secs'] == 300
    
    def test_close_all(self):
        """Test close_all closes all clients."""
        pool = NSEConnectionPool()
        
        # Create mock clients
        mock_client = MagicMock(spec=NSEHttpClient)
        pool._clients["www.nseindia.com"] = {
            "client_0": {
                "client": mock_client,
                "created": time.monotonic(),
                "last_used": time.monotonic(),
            }
        }
        
        pool.close_all()
        
        # Should have called close on the client
        mock_client.close.assert_called_once()
        assert pool._clients == {}
    
    def test_client_expiry(self):
        """Test that expired clients are cleaned up."""
        pool = NSEConnectionPool(session_ttl=1)  # 1 second TTL
        
        # Create mock client that's expired
        mock_client = MagicMock(spec=NSEHttpClient)
        pool._clients["www.nseindia.com"] = {
            "client_0": {
                "client": mock_client,
                "created": time.monotonic() - 10,  # 10 seconds ago
                "last_used": time.monotonic() - 10,
            }
        }
        
        # Getting a client should trigger cleanup
        with patch.object(NSEHttpClient, '__init__', return_value=None):
            with patch.object(NSEHttpClient, '_prime_session'):
                pool.get_client("https://www.nseindia.com")
        
        # Old client should have been closed
        mock_client.close.assert_called()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"session_ttl": 0},
            {"session_ttl": True},
            {"max_sessions": -1},
        ],
    )
    def test_pool_rejects_invalid_configuration(self, kwargs):
        with pytest.raises(ValueError):
            NSEConnectionPool(**kwargs)

    @pytest.mark.parametrize("method_name", ["get_client", "get_async_client"])
    def test_pool_rejects_invalid_base_url(self, method_name):
        pool = NSEConnectionPool()

        with pytest.raises(ValueError, match="absolute HTTP"):
            getattr(pool, method_name)("nseindia.com")

    def test_aclose_all_awaits_async_clients(self):
        pool = NSEConnectionPool()
        async_client = MagicMock(spec=NSEAsyncHttpClient)
        pool._aclients["www.nseindia.com"] = {
            "aclient_0": {
                "client": async_client,
                "created": time.monotonic(),
                "last_used": time.monotonic(),
            }
        }

        asyncio.run(pool.aclose_all())

        async_client.aclose.assert_awaited_once()
        assert pool._aclients == {}


class TestGlobalConnectionPool:
    """Tests for global connection pool functions."""
    
    def test_get_connection_pool_singleton(self):
        """Test that get_connection_pool returns singleton."""
        reset_connection_pool()
        
        pool1 = get_connection_pool()
        pool2 = get_connection_pool()
        
        assert pool1 is pool2
    
    def test_reset_connection_pool(self):
        """Test that reset_connection_pool creates new pool."""
        pool1 = get_connection_pool()
        reset_connection_pool()
        pool2 = get_connection_pool()
        
        assert pool1 is not pool2


class TestThreadSafety:
    """Tests for thread safety of connection pool."""
    
    def test_concurrent_get_client(self):
        """Test concurrent access to get_client."""
        pool = NSEConnectionPool()
        results = []
        errors = []
        
        def get_client_thread():
            try:
                with patch.object(NSEHttpClient, '__init__', return_value=None):
                    with patch.object(NSEHttpClient, '_prime_session'):
                        client = pool.get_client("https://www.nseindia.com")
                        results.append(client)
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads concurrently
        threads = [threading.Thread(target=get_client_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 10
    
    def test_concurrent_close_all(self):
        """Test concurrent close_all calls."""
        pool = NSEConnectionPool()
        errors = []
        
        def close_thread():
            try:
                pool.close_all()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=close_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0

