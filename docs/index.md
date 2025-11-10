# `aynse`

Lean, modern NSE data library with resilient networking.

## Features

- Historical and derivatives data
- Bhavcopy downloads (Equity, F&O, Index)
- Live market data
- CLI helpers
- Resilient HTTP client (HTTP/2, retries, pooling)

## Install

```sh
pip install aynse
```

## Quick Start

```python
from datetime import date
from aynse.nse import stock_df

df = stock_df("RELIANCE", date(2024,1,1), date(2024,1,31))
print(df.head())
```

## HTTP Client (advanced)

```python
from aynse.nse.connection_pool import get_connection_pool
client = get_connection_pool().get_client("https://www.nseindia.com")
data = client.get_json("/api/marketStatus")
```

See `historical.md` and `live.md` for more.
