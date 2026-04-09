# aynse

A standardized Python library for working with National Stock Exchange (NSE) and RBI datasets in a predictable `records / dataframe / save` style.

<div class="grid cards" markdown>

-   :material-chart-line:{ .lg .middle } __Historical Data__

    ---

    Download canonical OHLCV-style records for stocks, indices, and derivatives with automatic retry and caching.

    [:octicons-arrow-right-24: Historical Data](historical.md)

-   :material-lightning-bolt:{ .lg .middle } __Live Quotes__

    ---

    Real-time quotes, option chains, market status, corporate events, and standardized live summaries.

    [:octicons-arrow-right-24: Live Data](live.md)

-   :material-download:{ .lg .middle } __Bhavcopy__

    ---

    Work with bhavcopy and archive datasets as records, dataframes, or saved files.

    [:octicons-arrow-right-24: Historical Data](historical.md#download-bhavcopies)

-   :material-console:{ .lg .middle } __CLI__

    ---

    Command-line interface for quick downloads without writing code.

    [:octicons-arrow-right-24: CLI Reference](cli.md)

</div>

## Features

- **Standardized contracts:** canonical Python-native records across history, archives, live, holidays, and RBI
- **Historical data:** stocks, indices, derivatives (F&O)
- **Archives:** bhavcopy, bulk deals, index constituents, and dataframe/save helpers
- **Live market data:** real-time quotes, option chains, corporate announcements, actions, and results calendars
- **CLI:** simple commands for quick downloads
- **Resilient networking:** HTTP/2, connection pooling, retries with exponential backoff
- **Rate limiting:** token bucket algorithm prevents API throttling
- **Circuit breaker:** automatic failure detection and recovery
- **Batching & streaming:** adaptive concurrency and low-memory processing
- **Metadata & analytics:** supported dataset discovery, option chain summaries, returns, drawdowns, and event-window helpers
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
print(df[["date", "symbol", "open", "close"]].head())
```

### Get Live Stock Quote

```python
from aynse import NSELive

live = NSELive()
quote = live.stock_quote("INFY")

print(f"Price: ₹{quote['price']['last']}")
print(f"Change: {quote['price']['change_percent']}%")
print(f"Company: {quote['company_name']}")
```

### Download Bhavcopy

```python
from datetime import date
from aynse import bhavcopy_save

# Download equity bhavcopy
bhavcopy_save(date(2024, 7, 26), "downloads/")
```

### Metadata And Analytics

```python
from aynse import dataset_capabilities, summarize_option_chain

capabilities = dataset_capabilities()
print(capabilities["historical"]["outputs"])

chain = live.equities_option_chain("RELIANCE")
print(summarize_option_chain(chain))
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
