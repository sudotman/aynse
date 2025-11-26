# API Reference

This page contains the auto-generated API reference for `aynse`.

## NSE Module

The main module for fetching NSE data.

### Historical Data

::: aynse.nse.history.stock_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.stock_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.stock_csv
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.derivatives_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.derivatives_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_df
    options:
      show_root_heading: true
      show_source: false

### Archives

::: aynse.nse.archives.bhavcopy_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_fo_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.expiry_dates
    options:
      show_root_heading: true
      show_source: false

### Live Data

::: aynse.nse.live.NSELive
    options:
      show_root_heading: true
      show_source: false
      members:
        - stock_quote
        - stock_quote_fno
        - trade_info
        - market_status
        - chart_data
        - tick_data
        - all_indices
        - live_index
        - index_option_chain
        - equities_option_chain
        - currency_option_chain
        - pre_open_market
        - holiday_list
        - corporate_announcements

## Holidays Module

::: aynse.holidays
    options:
      show_root_heading: true
      show_source: false
      members:
        - holidays
        - is_holiday
        - is_trading_day
        - get_trading_days
        - count_trading_days

## RBI Module

::: aynse.rbi.RBI
    options:
      show_root_heading: true
      show_source: false

::: aynse.rbi.policy_rate_archive
    options:
      show_root_heading: true
      show_source: false

## HTTP Client

The library includes resilient HTTP clients with retry logic, rate limiting, and circuit breakers.

### NSEHttpClient

```python
from aynse.nse.http_client import NSEHttpClient

client = NSEHttpClient(
    base_url="https://www.nseindia.com",
    timeout=15.0,
    max_connections=20,
    rate_limit_per_sec=10
)

# Make requests
response = client.get("/api/marketStatus")
data = client.get_json("/api/marketStatus")
```

### Connection Pool

```python
from aynse.nse.connection_pool import get_connection_pool

pool = get_connection_pool()
client = pool.get_client("https://www.nseindia.com")

# The pool manages client lifecycle and reuse
data = client.get_json("/api/marketStatus")

# Get pool statistics
stats = pool.get_pool_stats()
print(f"Active clients: {stats['sync_clients']}")
```

## Request Batching

::: aynse.nse.request_batcher.RequestBatcher
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.request_batcher.BatchStrategy
    options:
      show_root_heading: true
      show_source: false

## Streaming Processor

::: aynse.nse.streaming_processor.StreamingProcessor
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.streaming_processor.StreamConfig
    options:
      show_root_heading: true
      show_source: false

## Utilities

::: aynse.util.break_dates
    options:
      show_root_heading: true
      show_source: false

::: aynse.util.cached
    options:
      show_root_heading: true
      show_source: false

::: aynse.util.live_cache
    options:
      show_root_heading: true
      show_source: false

::: aynse.util.is_trading_day
    options:
      show_root_heading: true
      show_source: false
