# aynse

A lean, modern Python library for fetching data from the National Stock Exchange (NSE) of India.

<div class="grid cards" markdown>

-   :material-chart-line:{ .lg .middle } __Historical Data__

    ---

    Download OHLCV data for stocks, indices, and derivatives with automatic retry and caching.

    [:octicons-arrow-right-24: Historical Data](historical.md)

-   :material-lightning-bolt:{ .lg .middle } __Live Quotes__

    ---

    Real-time stock quotes, option chains, market status, and more.

    [:octicons-arrow-right-24: Live Data](live.md)

-   :material-download:{ .lg .middle } __Bhavcopy__

    ---

    Download daily bhavcopies for equity, F&O, and indices.

    [:octicons-arrow-right-24: Historical Data](historical.md#download-bhavcopies)

-   :material-console:{ .lg .middle } __CLI__

    ---

    Command-line interface for quick downloads without writing code.

    [:octicons-arrow-right-24: CLI Reference](cli.md)

</div>

## Features

- **Historical data:** stocks, indices, derivatives (F&O)
- **Bhavcopy:** equity, F&O, index downloads
- **Live market data:** real-time quotes, option chains
- **CLI:** simple commands for quick downloads
- **Resilient networking:** HTTP/2, connection pooling, retries with exponential backoff
- **Rate limiting:** token bucket algorithm prevents API throttling
- **Circuit breaker:** automatic failure detection and recovery
- **Batching & streaming:** adaptive concurrency and low-memory processing
- **Comprehensive type hints:** full typing support for IDE autocomplete

## Installation

```bash
pip install aynse
```

For development:

```bash
pip install aynse[dev]
# or
pip install -r requirements.dev.txt
```

## Quick Start

### Get Historical Stock Data

```python
from datetime import date
from aynse import stock_df

# Fetch RELIANCE data for January 2024
df = stock_df(
    symbol="RELIANCE",
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)
print(df.head())
```

### Get Live Stock Quote

```python
from aynse import NSELive

live = NSELive()
quote = live.stock_quote("INFY")

print(f"Price: ₹{quote['priceInfo']['lastPrice']}")
print(f"Change: {quote['priceInfo']['pChange']}%")
```

### Download Bhavcopy

```python
from datetime import date
from aynse import bhavcopy_save

# Download equity bhavcopy
bhavcopy_save(date(2024, 7, 26), "downloads/")
```

### CLI Usage

```bash
# Download historical stock data
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -o reliance.csv

# Get live quote
aynse quote -s RELIANCE

# List trading holidays
aynse holidays -y 2024
```

## Architecture

```
aynse/
├── nse/                    # NSE data fetching
│   ├── history.py         # Historical data (stocks, indices, derivatives)
│   ├── archives.py        # Bhavcopy downloads
│   ├── live.py            # Live market data
│   ├── http_client.py     # Resilient HTTP client
│   ├── connection_pool.py # Connection management
│   ├── request_batcher.py # Batch processing
│   └── streaming_processor.py  # Memory-efficient streaming
├── rbi/                   # RBI data
│   └── historical.py      # Policy rates
├── holidays.py            # Trading calendar
├── util.py                # Utilities (caching, date handling)
└── cli.py                 # Command-line interface
```

## Next Steps

- [Historical Data Guide](historical.md) - Download OHLCV data
- [Live Data Guide](live.md) - Real-time quotes and option chains
- [CLI Reference](cli.md) - Command-line usage
- [API Reference](api.md) - Complete API documentation
- [Data Calls Reference](data_calls.md) - All available data calls
