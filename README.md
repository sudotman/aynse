# `aynse`

[![build status](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml/badge.svg)](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml)
[![PyPI version](https://badge.fury.io/py/aynse.svg)](https://badge.fury.io/py/aynse)
[![license: CMIT](https://img.shields.io/badge/license-*CMIT-black.svg)](LICENSE.md)
[![misc badge](https://img.shields.io/badge/ayn-nse-black)](https://en.wikipedia.org/wiki/Ayn_Rand)

`aynse` is a lean, modern python library for fetching data from the national stock exchange (nse) of india. it includes a resilient http client (http/2, retries with jitter, connection pooling), adaptive batching, and efficient streaming utilities.

## features

- **Historical data:** canonical stock, index, derivative, and index valuation records
- **Archive datasets:** bhavcopy, full bhavcopy, F&O bhavcopy, index bhavcopy, bulk deals, and index constituents
- **Live market data:** standardized quotes, option chains
- **cli:** simple commands for quick downloads
- **resilient networking:** http/2, connection pooling, retries with exponential backoff, rate limiting, circuit breaker
- **batching & streaming:** adaptive concurrency and low-memory processing
- **comprehensive type hints:** full typing support for ide autocomplete
- **extensive test coverage:** robust test suite for reliability
- **streaming utilities:** chunked CSV/JSON/ZIP processing for larger files

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
from aynse import stock_df

df = stock_df(
    symbol="reliance",
    from_date="2024-01-01",
    to_date="2024-01-31",
)

print(df[["date", "symbol", "open", "close"]].head())
```

### archive datasets

```python
from aynse import bhavcopy_raw, bhavcopy_save

records = bhavcopy_raw("2024-07-26")
print(records[0])

path = bhavcopy_save("2024-07-26", "downloads/")
print(path)
```

### get live stock quote

fetch live price information for a stock:

```python
from aynse import NSELive

live = NSELive()
quote = live.stock_quote("INFY")

print(quote["symbol"])
print(quote["company_name"])
print(quote["price"]["last"])
print(quote["price"]["change_percent"])
```

### get option chain data

fetch option chain for index or equity:

```python
from aynse import NSELive, summarize_option_chain

live = NSELive()
chain = live.equities_option_chain("RELIANCE")
summary = summarize_option_chain(chain)

print(summary["at_the_money_strike"])
print(summary["put_call_ratio"])
```

### metadata

```python
from aynse import dataset_capabilities, supported_indices

print(dataset_capabilities()["historical"]["outputs"])
print(supported_indices()[:3])
```

## canonical contracts

### accepted inputs

All public date boundaries accept:

- `datetime.date`
- `datetime.datetime`
- `"YYYY-MM-DD"`

Symbols are normalized at the boundary, so `"reliance"` and `"RELIANCE"` resolve the same way for symbol-based APIs.

### historical record shape

`stock_raw(...)` returns rows like:

```python
{
    "date": date(2024, 1, 1),
    "symbol": "RELIANCE",
    "series": "EQ",
    "open": 2850.0,
    "high": 2875.0,
    "low": 2832.0,
    "close": 2868.0,
    "previous_close": 2844.0,
    "last_traded_price": 2867.5,
    "volume": 1234567,
}
```

Time-series datasets are returned in chronological ascending order.

### archive contract

Archive families follow the same triplet:

- `bhavcopy_raw(...)`, `bhavcopy_df(...)`, `bhavcopy_save(...)`
- `full_bhavcopy_raw(...)`, `full_bhavcopy_df(...)`, `full_bhavcopy_save(...)`
- `bhavcopy_fo_raw(...)`, `bhavcopy_fo_df(...)`, `bhavcopy_fo_save(...)`
- `bhavcopy_index_raw(...)`, `bhavcopy_index_df(...)`, `bhavcopy_index_save(...)`
- `bulk_deals_raw(...)`, `bulk_deals_df(...)`, `bulk_deals_save(...)`
- `index_constituent_raw(...)`, `index_constituent_df(...)`, `index_constituent_save(...)`

### live contract

live methods return stable top-level payloads. For example:

```python
{
    "symbol": "INFY",
    "company_name": "Infosys Limited",
    "price": {
        "last": 1520.5,
        "change": 12.4,
        "change_percent": 0.82,
    },
}
```

Option-chain methods return:

- `symbol`
- `market_type`
- `timestamp`
- `underlying_value`
- `expiry_dates`
- `strike_prices`
- `records`
- `summary`

## public API highlights

### historical + archives

- `stock_raw`, `stock_df`, `stock_csv`
- `index_raw`, `index_df`, `index_csv`
- `index_pe_raw`, `index_pe_df`
- `derivatives_raw`, `derivatives_df`, `derivatives_csv`
- `bhavcopy_*`, `full_bhavcopy_*`, `bhavcopy_fo_*`, `bhavcopy_index_*`
- `bulk_deals_*`
- `index_constituent_*`
- `expiry_dates`

### live + metadata

- `NSELive.stock_quote`, `stock_quote_fno`, `trade_info`, `market_status`
- `NSELive.index_option_chain`, `equities_option_chain`, `currency_option_chain`
- `NSELive.corporate_announcements`, `corporate_actions`, `results_calendar`
- `NSELive.metadata`
- `dataset_capabilities`, `supported_indices`, `supported_instruments`, `supported_event_categories`

### analytics

- `add_returns`
- `add_rolling_volatility`
- `add_drawdown`
- `add_gap_metrics`
- `add_volume_metrics`
- `summarize_option_chain`
- `analyze_event_window`

## CLI

```sh
# historical stock data
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -o reliance_q1.csv

# live quote
aynse quote -s RELIANCE

# archive download
aynse bhavcopy -d downloads/ -f 2024-07-26

# holidays
aynse holidays -y 2024
```

## testing

```sh
# deterministic/offline contracts
pytest -m offline -v --tb=short

# live NSE/RBI integration checks
pytest -m live -v --tb=short

# end-to-end integration checks
pytest -m e2e -v --tb=short
```

## documentation

- [Historical Data Guide](docs/historical.md)
- [Live Data Guide](docs/live.md)
- [API Reference](docs/api.md)
- [Data Calls Reference](docs/data_calls.md)

## contributing

contributions are welcome. Please add or update contract tests whenever you change a public schema, accepted input, or save behavior.

## license

this project uses a custom MIT-derived license with additional usage restrictions. See [LICENSE.md](LICENSE.md) for the exact terms.
