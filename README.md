# `aynse`

[![build status](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml/badge.svg)](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml)
[![PyPI version](https://badge.fury.io/py/aynse.svg)](https://badge.fury.io/py/aynse)
[![license: CMIT](https://img.shields.io/badge/license-*CMIT-black.svg)](LICENSE.md)
[![misc badge](https://img.shields.io/badge/ayn-nse-black)](https://en.wikipedia.org/wiki/Ayn_Rand)

`aynse` is a lean, modern python library for fetching data from the national stock exchange (nse) of india. it includes a resilient http client (http/2, retries with jitter, connection pooling), adaptive batching, and efficient streaming utilities.

## features

- **historical data:** stocks, indices, derivatives (f&o)
- **bhavcopy:** equity, f&o, index downloads
- **live market data:** real-time quotes, option chains
- **cli:** simple commands for quick downloads
- **resilient networking:** http/2, connection pooling, retries with exponential backoff, rate limiting, circuit breaker
- **batching & streaming:** adaptive concurrency and low-memory processing
- **comprehensive type hints:** full typing support for ide autocomplete
- **extensive test coverage:** robust test suite for reliability

## installation

install `aynse` directly from pypi:

```sh
pip install aynse
```

for development:

```sh
pip install aynse[dev]
# or
pip install -r requirements.dev.txt
```

## quick start

### get historical stock data

retrieve historical data for a stock as a pandas dataframe:

```python
from datetime import date
from aynse import stock_df

# Fetch data for RELIANCE from January 1-31, 2024
df = stock_df(
    symbol="RELIANCE",
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)

print(df.head())
```

### download daily bhavcopy

download the daily bhavcopy for a specific date:

```python
from datetime import date
from aynse import bhavcopy_save

# Download equity bhavcopy for July 26, 2024
bhavcopy_save(date(2024, 7, 26), "downloads/")
```

### get live stock quote

fetch live price information for a stock:

```python
from aynse import NSELive

live = NSELive()
quote = live.stock_quote("INFY")
print(f"Price: ₹{quote['priceInfo']['lastPrice']}")
print(f"Change: {quote['priceInfo']['pChange']}%")
```

### get option chain data

fetch option chain for index or equity:

```python
from aynse import NSELive

live = NSELive()

# Index option chain
nifty_chain = live.index_option_chain("NIFTY")

# Equity option chain
reliance_chain = live.equities_option_chain("RELIANCE")
```

### check trading holidays

get the list of trading holidays:

```python
from aynse import holidays
from aynse.holidays import is_trading_day
from datetime import date

# Get all 2024 holidays
holidays_2024 = holidays(year=2024)
print(f"Trading holidays in 2024: {len(holidays_2024)}")

# Check if a date is a trading day
print(f"Is Jan 15, 2024 a trading day? {is_trading_day(date(2024, 1, 15))}")
```

## command-line interface

`aynse` comes with a command-line tool for quick downloads.

### download bhavcopy

```sh
# Download today's bhavcopy
aynse bhavcopy -d /path/to/directory

# Download for a specific date
aynse bhavcopy -d /path/to/directory -f 2024-01-15

# Download for a date range
aynse bhavcopy -d /path/to/directory -f 2024-01-01 -t 2024-01-31

# Download F&O bhavcopy
aynse bhavcopy -d /path/to/directory --fo

# Download index bhavcopy
aynse bhavcopy -d /path/to/directory --idx
```

### download historical stock data

```sh
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -o reliance_q1_2024.csv
```

### download historical index data

```sh
aynse index -s "NIFTY 50" -f 2024-01-01 -t 2024-03-31 -o nifty_q1_2024.csv
```

### download derivatives data

```sh
# Stock futures
aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i FUTSTK

# Index options
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-25 -e 2024-01-25 -i OPTIDX -p 21000 --pe
```

### get live quote

```sh
aynse quote -s RELIANCE
```

### list holidays

```sh
# Current year
aynse holidays

# Specific year
aynse holidays -y 2024
```

## advanced usage

### connection pooling

the library uses a centralized connection pool for efficient http connections:

```python
from aynse.nse import get_connection_pool

# Get the global connection pool
pool = get_connection_pool()

# Get a client for NSE
client = pool.get_client("https://www.nseindia.com")
data = client.get_json("/api/marketStatus")
```

### request batching

process multiple requests efficiently:

```python
from aynse import RequestBatcher, BatchStrategy

batcher = RequestBatcher(
    max_batch_size=10,
    max_concurrent_batches=3,
    strategy=BatchStrategy.ADAPTIVE
)

# Batch multiple stock requests
from aynse import batch_stock_requests

results = batch_stock_requests(
    symbols=["RELIANCE", "TCS", "INFY", "HDFC", "SBIN"],
    from_date="2024-01-01",
    to_date="2024-01-31"
)
```

### streaming for large datasets

process large files without loading everything into memory:

```python
from aynse import StreamingProcessor, StreamConfig

processor = StreamingProcessor(
    StreamConfig(chunk_size=1000)
)

def process_chunk(records):
    # Process each chunk of 1000 records
    return sum(r.get('volume', 0) for r in records)

total_volume = processor.process_csv_file(
    "large_bhavcopy.csv",
    process_chunk
)
```

## api reference

### historical data (`aynse.nse`)

| function | description |
|----------|-------------|
| `stock_raw(symbol, from_date, to_date, series="EQ")` | get raw stock data as list of dicts |
| `stock_df(symbol, from_date, to_date, series="EQ")` | get stock data as dataframe |
| `stock_csv(symbol, from_date, to_date, series="EQ", output="")` | save stock data to csv |
| `derivatives_raw(...)` | get raw derivatives data |
| `derivatives_df(...)` | get derivatives data as dataframe |
| `index_raw(symbol, from_date, to_date)` | get raw index data |
| `index_df(symbol, from_date, to_date)` | get index data as dataframe |

### archives (`aynse.nse`)

| function | description |
|----------|-------------|
| `bhavcopy_raw(dt)` | get equity bhavcopy as csv string |
| `bhavcopy_save(dt, dest)` | save equity bhavcopy to file |
| `bhavcopy_fo_raw(dt)` | get f&o bhavcopy |
| `bhavcopy_fo_save(dt, dest)` | save f&o bhavcopy |
| `expiry_dates(dt, instrument_type, symbol)` | calculate expiry dates |

### live data (`NSELive`)

| method | description |
|--------|-------------|
| `stock_quote(symbol)` | get live stock quote |
| `stock_quote_fno(symbol)` | get f&o quote for stock |
| `index_option_chain(symbol)` | get index option chain |
| `equities_option_chain(symbol)` | get equity option chain |
| `market_status()` | get market status |
| `all_indices()` | get all indices data |
| `live_index(symbol)` | get live index data |
| `pre_open_market(key)` | get pre-open market data |

### holidays (`aynse.holidays`)

| function | description |
|----------|-------------|
| `holidays(year=None, month=None)` | get list of trading holidays |
| `is_holiday(dt)` | check if date is a holiday |
| `is_trading_day(dt)` | check if date is a trading day |
| `get_trading_days(from_date, to_date)` | get trading days in range |

## etymology / musings

aynse is a portmanteau of "ayn" from miss ayn rand and "nse" from national stock exchange. ayn rand was a russian-american writer and philosopher known for her philosophy of objectivism, which emphasizes individualism and rational self-interest. among other things, she was a strong advocate for laissez-faire capitalism.

the name serves as a fun ironical reminder of the library's purpose: to provide a tool for individuals to access and analyze financial data independently, without relying on large institutions or complex systems.

in a cruel twist of fate, this open source library wouldn't be encouraged under ayn rand's philosophy, as she discouraged altruism and believed in the pursuit of one's own happiness as the highest moral purpose.

and as the final act of irony, we gather to use this library to analyze financial markets while generating zero (and possibly, negative) intrinsic value for humankind as a whole - this is capitalism.

## contributing

contributions are welcome! please:

1. fork the repository
2. create a feature branch
3. add tests for new functionality
4. ensure all tests pass (`pytest`)
5. submit a pull request

for bugs or feature requests, please open an issue on the [github repository](https://github.com/sudotman/aynse/issues).

## release workflow
1. make your changes
2. bump version
```sh
make bump-patch  # or bump-minor, bump-major
```

3. commit and tag
```sh
git commit -am "Bump version to X.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

4. create github release → automatically publishes to pypi.

## license

this project has a (custom) mit* license but extends limitations. if you're an agency/corporate with >2 employees, you cannot wrap this project or use it without prior written permission from the author. if you're an individual, you can use it freely for personal projects.

this project is not intended for commercial use without prior permission. if caught using this project in violation of the license, it may result in automated reporting and/or legal action.

please see the [license file](LICENSE.md) for more details.
