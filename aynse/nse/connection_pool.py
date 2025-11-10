"""
NSE Connection Pool managing reusable httpx-based clients.
"""

import time
import threading
from typing import Dict, Optional
from urllib.parse import urlparse

from .http_client import NSEHttpClient, NSEAsyncHttpClient


class NSEConnectionPool:
    """
    Thread-safe pool that manages NSEHttpClient (sync/async) instances per host.
    """

    def __init__(self, session_ttl: int = 300, max_sessions: int = 10):
        """
        Args:
            session_ttl: Time-to-live for clients in seconds
            max_sessions: Maximum number of clients to maintain per host
        """
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions
        self._clients: Dict[str, Dict[str, Dict[str, object]]] = {}
        # Structure: { host: { id: {'client': NSEHttpClient, 'created': ts, 'last_used': ts} } }
        self._aclients: Dict[str, Dict[str, Dict[str, object]]] = {}
        # Structure: { host: { id: {'client': NSEAsyncHttpClient, 'created': ts, 'last_used': ts} } }
        self._lock = threading.RLock()

    def _cleanup_expired(self, bucket: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        now = time.time()
        expired: Dict[str, list] = {}
        for host, items in bucket.items():
            to_del = [key for key, info in items.items() if (now - info['created']) >= self.session_ttl]
            if to_del:
                expired[host] = to_del
        for host, keys in expired.items():
            for key in keys:
                try:
                    client = bucket[host][key]['client']
                    # Best-effort close
                    close = getattr(client, "close", None)
                    if callable(close):
                        close()
                except Exception:
                    pass
                del bucket[host][key]

    def _is_valid(self, info: Dict[str, object]) -> bool:
        now = time.time()
        created = info['created']  # type: ignore[index]
        return (now - created) < self.session_ttl  # type: ignore[operator]

    def get_client(self, base_url: str) -> NSEHttpClient:
        parsed = urlparse(base_url)
        host = parsed.netloc
        with self._lock:
            if host not in self._clients:
                self._clients[host] = {}
            bucket = self._clients[host]
            # Cleanup
            self._cleanup_expired(self._clients)
            # Reuse
            for cid, info in bucket.items():
                if self._is_valid(info):
                    info['last_used'] = time.time()
                    return info['client']  # type: ignore[return-value]
            # Create
            if len(bucket) < self.max_sessions:
                client = NSEHttpClient(base_url=parsed.scheme + "://" + host)
                cid = f"client_{len(bucket)}"
                bucket[cid] = {'client': client, 'created': time.time(), 'last_used': time.time()}
                return client
            # Fallback: return LRU
            oldest_id = min(bucket.keys(), key=lambda k: bucket[k]['last_used'])
            bucket[oldest_id]['last_used'] = time.time()
            return bucket[oldest_id]['client']  # type: ignore[return-value]

    # Backwards-compatibility shim for older tests
    def get_session(self, url: str) -> NSEHttpClient:
        """Compatibility: return a client for the given URL (was: requests.Session)."""
        return self.get_client(url)

    def get_async_client(self, base_url: str) -> NSEAsyncHttpClient:
        parsed = urlparse(base_url)
        host = parsed.netloc
        with self._lock:
            if host not in self._aclients:
                self._aclients[host] = {}
            bucket = self._aclients[host]
            # Cleanup
            self._cleanup_expired(self._aclients)
            # Reuse
            for cid, info in bucket.items():
                if self._is_valid(info):
                    info['last_used'] = time.time()
                    return info['client']  # type: ignore[return-value]
            # Create
            if len(bucket) < self.max_sessions:
                client = NSEAsyncHttpClient(base_url=parsed.scheme + "://" + host)
                cid = f"aclient_{len(bucket)}"
                bucket[cid] = {'client': client, 'created': time.time(), 'last_used': time.time()}
                return client
            # Fallback LRU
            oldest_id = min(bucket.keys(), key=lambda k: bucket[k]['last_used'])
            bucket[oldest_id]['last_used'] = time.time()
            return bucket[oldest_id]['client']  # type: ignore[return-value]

    def close_all(self) -> None:
        with self._lock:
            for host_bucket in (self._clients, self._aclients):
                for host_items in host_bucket.values():
                    for info in list(host_items.values()):
                        try:
                            client = info['client']
                            close = getattr(client, "close", None)
                            aclose = getattr(client, "aclose", None)
                            if callable(close):
                                close()
                            elif callable(aclose):
                                # Can't await here; rely on GC if needed
                                pass
                        except Exception:
                            pass
                host_bucket.clear()

    def get_pool_stats(self) -> Dict[str, int]:
        with self._lock:
            total_sync = sum(len(b) for b in self._clients.values())
            total_async = sum(len(b) for b in self._aclients.values())
            return {
                'sync_clients': total_sync,
                'async_clients': total_async,
                'hosts_sync': len(self._clients),
                'hosts_async': len(self._aclients),
                'max_per_host': self.max_sessions,
                'ttl_secs': self.session_ttl,
            }


# Global connection pool instance
_connection_pool: Optional[NSEConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> NSEConnectionPool:
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = NSEConnectionPool()
    return _connection_pool


def reset_connection_pool() -> None:
    global _connection_pool
    with _pool_lock:
        if _connection_pool:
            _connection_pool.close_all()
            _connection_pool = None
