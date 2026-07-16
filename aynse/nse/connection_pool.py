"""
NSE Connection Pool managing reusable httpx-based clients.
"""

import asyncio
import inspect
import threading
import time
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
        if (
            isinstance(session_ttl, bool)
            or not isinstance(session_ttl, int)
            or session_ttl <= 0
        ):
            raise ValueError("session_ttl must be a positive integer")
        if (
            isinstance(max_sessions, bool)
            or not isinstance(max_sessions, int)
            or max_sessions <= 0
        ):
            raise ValueError("max_sessions must be a positive integer")
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions
        self._clients: Dict[str, Dict[str, Dict[str, object]]] = {}
        # Structure: { host: { id: {'client': NSEHttpClient, 'created': ts, 'last_used': ts} } }
        self._aclients: Dict[str, Dict[str, Dict[str, object]]] = {}
        # Structure: { host: { id: {'client': NSEAsyncHttpClient, 'created': ts, 'last_used': ts} } }
        self._lock = threading.RLock()

    def _cleanup_expired(self, bucket: Dict[str, Dict[str, Dict[str, object]]]) -> None:
        now = time.monotonic()
        expired: Dict[str, list] = {}
        for host, items in bucket.items():
            to_del = [key for key, info in items.items() if (now - info['created']) >= self.session_ttl]
            if to_del:
                expired[host] = to_del
        for host, keys in expired.items():
            for key in keys:
                try:
                    client = bucket[host][key]['client']
                    self._close_or_schedule(client)
                except Exception:
                    pass
                del bucket[host][key]
            if not bucket[host]:
                del bucket[host]

    @staticmethod
    def _close_or_schedule(client: object) -> None:
        """Close a sync client or schedule/execute its async close safely."""
        close = getattr(client, "close", None)
        if callable(close):
            close()
            return
        aclose = getattr(client, "aclose", None)
        if not callable(aclose):
            return
        result = aclose()
        if not inspect.isawaitable(result):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(result)
        else:
            loop.create_task(result)

    def _is_valid(self, info: Dict[str, object]) -> bool:
        now = time.monotonic()
        created = info['created']  # type: ignore[index]
        return (now - created) < self.session_ttl  # type: ignore[operator]

    def get_client(self, base_url: str) -> NSEHttpClient:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        host = parsed.netloc
        with self._lock:
            self._cleanup_expired(self._clients)
            bucket = self._clients.setdefault(host, {})
            # Reuse
            for cid, info in bucket.items():
                if self._is_valid(info):
                    info['last_used'] = time.monotonic()
                    return info['client']  # type: ignore[return-value]
            # Create
            if len(bucket) < self.max_sessions:
                client = NSEHttpClient(base_url=parsed.scheme + "://" + host)
                cid = f"client_{len(bucket)}"
                now = time.monotonic()
                bucket[cid] = {'client': client, 'created': now, 'last_used': now}
                return client
            # Fallback: return LRU
            oldest_id = min(bucket.keys(), key=lambda k: bucket[k]['last_used'])
            bucket[oldest_id]['last_used'] = time.monotonic()
            return bucket[oldest_id]['client']  # type: ignore[return-value]

    # Backwards-compatibility shim for older tests
    def get_session(self, url: str) -> NSEHttpClient:
        """Compatibility: return a client for the given URL (was: requests.Session)."""
        return self.get_client(url)

    def get_async_client(self, base_url: str) -> NSEAsyncHttpClient:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        host = parsed.netloc
        with self._lock:
            self._cleanup_expired(self._aclients)
            bucket = self._aclients.setdefault(host, {})
            # Reuse
            for cid, info in bucket.items():
                if self._is_valid(info):
                    info['last_used'] = time.monotonic()
                    return info['client']  # type: ignore[return-value]
            # Create
            if len(bucket) < self.max_sessions:
                client = NSEAsyncHttpClient(base_url=parsed.scheme + "://" + host)
                cid = f"aclient_{len(bucket)}"
                now = time.monotonic()
                bucket[cid] = {'client': client, 'created': now, 'last_used': now}
                return client
            # Fallback LRU
            oldest_id = min(bucket.keys(), key=lambda k: bucket[k]['last_used'])
            bucket[oldest_id]['last_used'] = time.monotonic()
            return bucket[oldest_id]['client']  # type: ignore[return-value]

    def close_all(self) -> None:
        with self._lock:
            for host_bucket in (self._clients, self._aclients):
                for host_items in host_bucket.values():
                    for info in list(host_items.values()):
                        try:
                            client = info['client']
                            self._close_or_schedule(client)
                        except Exception:
                            pass
                host_bucket.clear()

    async def aclose_all(self) -> None:
        """Close all pooled clients, awaiting async client shutdown."""
        with self._lock:
            clients = [
                info["client"]
                for host_bucket in (self._clients, self._aclients)
                for host_items in host_bucket.values()
                for info in host_items.values()
            ]
            self._clients.clear()
            self._aclients.clear()

        pending = []
        for client in clients:
            close = getattr(client, "close", None)
            if callable(close):
                close()
                continue
            aclose = getattr(client, "aclose", None)
            if callable(aclose):
                result = aclose()
                if inspect.isawaitable(result):
                    pending.append(result)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

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
