# `aynse`

[![build status](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml/badge.svg)](https://github.com/sudotman/aynse/actions/workflows/run-tests.yml)
[![PyPI version](https://badge.fury.io/py/aynse.svg)](https://badge.fury.io/py/aynse)
[![license: CMIT](https://img.shields.io/badge/license-*CMIT-black.svg)](LICENSE.md)
[![misc badge](https://img.shields.io/badge/ayn-nse-black)](https://en.wikipedia.org/wiki/Ayn_Rand)

`aynse` is a lean, modern python library for fetching data from the National Stock Exchange (NSE) of India. It includes a resilient HTTP client (HTTP/2, retries with jitter, connection pooling), adaptive batching, and efficient streaming utilities.

## Features

- **Historical data:** stocks, indices, derivatives
- **Bhavcopy:** equity, F&O, index downloads
- **Live market data:** real-time quotes
- **CLI:** simple commands for quick downloads
- **Resilient networking:** HTTP/2, pooling, retries, rate limit, circuit breaker
- **Batching & streaming:** adaptive concurrency and low-memory processing

## etymology / musings
aynse is a portmanteau of "ayn" from miss ayn rand and "nse" from national stock exchange. ayn rand was a russian-american writer and philosopher known for her philosophy of objectivism, which emphasizes individualism and rational self-interest and among other things, she was a strong advocate for laissez-faire capitalism. the name serves as a fun ironical reminder of the library's purpose: to provide a tool for individuals to access and analyze financial data independently, without relying on large institutions or complex systems. in a cruel twist of fate, this open source library wouldn't be encouraged under ayn rand's philosophy, as she discouraged altruism and believed in the pursuit of one's own happiness as the highest moral purpose. and as the final act of irony, we gather to use this library to analyze financial markets while generating zero (and possibly, negative) intrinsic value for humans or human kind as a whole - this is capitalism.


## Installation

you can install `aynse` directly from PyPI:

```sh
pip install aynse
```

## Usage

here are a few examples of how to use `aynse` to fetch data.

### Get historical stock data

retrieve historical data for a stock as a pandas dataframe.

```python
from datetime import date
import pandas as pd
from aynse.nse import stock_df

# set pandas display options to view all columns
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

# fetch data for reliance from january 1, 2024, to january 31, 2024
df = stock_df(symbol="RELIANCE",
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 31))

print(df.head())
```

### Download daily bhavcopy

download the daily bhavcopy for a specific date to a local directory.

```python
from datetime import date
from aynse.nse import bhavcopy_save

# download equity bhavcopy for july 26, 2024, into the "tmp" directory
bhavcopy_save(date(2024, 7, 26), "tmp")
```

### Get live stock quote

fetch live price information for a stock.

```python
from aynse.nse import NSELive

n = NSELive()
quote = n.stock_quote("INFY")
print(quote['priceInfo'])
```

### get trading holidays

get the list of trading holidays for a specific year.

```python
from aynse.holidays import holidays

# get trading holidays for the year 2024
trading_holidays = holidays(2024)
print(trading_holidays)
```

## Command-line interface

`aynse` also comes with a simple command-line tool for quick downloads.

**download today's bhavcopy:**

```sh
aynse bhavcopy -d /path/to/your/directory
```

**download bhavcopy for a specific date range:**

```sh
aynse bhavcopy -d /path/to/your/directory -f 2024-01-01 -t 2024-01-31
```

**download historical stock data:**

```sh
aynse stock --symbol RELIANCE -f 2024-01-01 -t 2024-01-31 -o reliance_data.csv
```

## Migration notes (breaking changes)

- Networking is centralized via a connection pool and resilient clients.
- If you previously managed `requests.Session` manually, prefer:
  ```python
  from aynse.nse.connection_pool import get_connection_pool
  client = get_connection_pool().get_client("https://www.nseindia.com")
  data = client.get_json("/api/marketStatus")
  ```
- Legacy behavior is preserved via `get_session(url)` shim on the pool.

## Contributing

contributions are welcome! if you find a bug or have a feature request, please open an issue on the [github repository](https://github.com/a-y-n/aynse/issues).

## License

this project has a (custom) MIT* license but extends limitations. if you're a agency/corporate with >2 employees alongside of you, you cannot wrap this project or use it without prior written permission from me. if you're an individual, you can use it freely for personal projects. this project is not intended for commercial use without prior permission. if caught using this project in violation of the license, it may result in automated reporting and/or legal action. please see the [license file](LICENSE.md) for more details.