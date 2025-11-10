# API Reference

This page contains the auto-generated API reference for `aynse`.

::: aynse.nse

::: aynse.holidays

::: aynse.rbi

## HTTP Client

The library includes resilient HTTP clients:

- `aynse.nse.http_client.NSEHttpClient`
- `aynse.nse.http_client.NSEAsyncHttpClient`

Acquire clients via the connection pool:

```python
from aynse.nse.connection_pool import get_connection_pool
pool = get_connection_pool()
client = pool.get_client("https://www.nseindia.com")
data = client.get_json("/api/marketStatus")
```