# `aynse`

[![Build Status](https://github.com/a-y-n/aynse/actions/workflows/run-tests.yml/badge.svg)](https://github.com/a-y-n/aynse/actions/workflows/run-tests.yml)
[![PyPI version](https://badge.fury.io/py/aynse.svg)](https://badge.fury.io/py/aynse)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

`aynse` is a lean, modern Python library for fetching data from the National Stock Exchange (NSE) of India. It is a fork of the unmaintained `jugaad-data` library, aiming to provide a robust and regularly updated tool for financial data analysis.

## Features

-   **Historical Data:** Fetch historical stock and index data.
-   **Derivatives Data:** Download futures and options data.
-   **Bhavcopy:** Download daily bhavcopy reports for equity, F&O, and indices.
-   **Live Market Data:** Get real-time stock quotes.
-   **Holiday Information:** Retrieve a list of trading holidays for a given year.
-   **Command-Line Interface:** A simple CLI for quick data downloads.
-   **Pandas Integration:** Returns data as Pandas DataFrames for easy analysis.

## Installation

You can install `aynse` directly from PyPI:

```sh
pip install aynse
```

## Usage

Here are a few examples of how to use `aynse` to fetch data.

### Get Historical Stock Data

Retrieve historical data for a stock as a Pandas DataFrame.

```python
from datetime import date
import pandas as pd
from aynse.nse import stock_df

# Set pandas display options to view all columns
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

# Fetch data for Reliance from January 1, 2024, to January 31, 2024
df = stock_df(symbol="RELIANCE",
              from_date=date(2024, 1, 1),
              to_date=date(2024, 1, 31))

print(df.head())
```

### Download Daily Bhavcopy

Download the daily bhavcopy for a specific date to a local directory.

```python
from datetime import date
from aynse.nse import bhavcopy_save

# Download equity bhavcopy for July 26, 2024, into the "tmp" directory
bhavcopy_save(date(2024, 7, 26), "tmp")
```

### Get Live Stock Quote

Fetch live price information for a stock.

```python
from aynse.nse import NSELive

n = NSELive()
quote = n.stock_quote("INFY")
print(quote['priceInfo'])
```

### Get Trading Holidays

Get the list of trading holidays for a specific year.

```python
from aynse.holidays import holidays

# Get trading holidays for the year 2024
trading_holidays = holidays(2024)
print(trading_holidays)
```

## Command-Line Interface

`aynse` also comes with a simple command-line tool for quick downloads.

**Download today's bhavcopy:**

```sh
aynse bhavcopy -d /path/to/your/directory
```

**Download bhavcopy for a specific date range:**

```sh
aynse bhavcopy -d /path/to/your/directory -f 2024-01-01 -t 2024-01-31
```

**Download historical stock data:**

```sh
aynse stock --symbol RELIANCE -f 2024-01-01 -t 2024-01-31 -o reliance_data.csv
```

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue on the [GitHub repository](https://github.com/a-y-n/aynse/issues).

## License

This project is in the public domain. See the [LICENSE](LICENSE.YOLO.md) file for more details.
