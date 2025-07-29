# `aynse`

[![build status](https://github.com/a-y-n/aynse/actions/workflows/run-tests.yml/badge.svg)](https://github.com/a-y-n/aynse/actions/workflows/run-tests.yml)
[![PyPI version](https://badge.fury.io/py/aynse.svg)](https://badge.fury.io/py/aynse)
[![license: mit](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

`aynse` is a lean, modern python library for fetching data from the national stock exchange (NSE) of india. it is a fork of the unmaintained `jugaad-data` library, aiming to provide a robust and regularly updated tool for financial data analysis.

## features

-   **historical data:** fetch historical stock and index data.
-   **derivatives data:** download futures and options data.
-   **bhavcopy:** download daily bhavcopy reports for equity, f&o, and indices.
-   **live market data:** get real-time stock quotes.
-   **holiday information:** retrieve a list of trading holidays for a given year.
-   **command-line interface:** a simple cli for quick data downloads.
-   **pandas integration:** returns data as pandas dataframes for easy analysis.

## etymology / musings
aynse is a portmanteau of "ayn" from miss ayn rand and "nse" from national stock exchange. ayn rand was a russian-american writer and philosopher known for her philosophy of objectivism, which emphasizes individualism and rational self-interest and among other things, she was a strong advocate for laissez-faire capitalism. the name serves as a fun ironical reminder of the library's purpose: to provide a tool for individuals to access and analyze financial data independently, without relying on large institutions or complex systems. in a cruel twist of fate, this open source library wouldn't exist under ayn rand's philosophy, as she was against altruism and believed in the pursuit of one's own happiness as the highest moral purpose. and as the final act of irony, we gather to use this library to analyze financial markets while generating zero (and possibly, negative) intrinsic value for humans or human kind as a whole - this is capitalism.


## installation

you can install `aynse` directly from PyPI:

```sh
pip install aynse
```

## usage

here are a few examples of how to use `aynse` to fetch data.

### get historical stock data

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

### download daily bhavcopy

download the daily bhavcopy for a specific date to a local directory.

```python
from datetime import date
from aynse.nse import bhavcopy_save

# download equity bhavcopy for july 26, 2024, into the "tmp" directory
bhavcopy_save(date(2024, 7, 26), "tmp")
```

### get live stock quote

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

## command-line interface

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

## contributing

contributions are welcome! if you find a bug or have a feature request, please open an issue on the [github repository](https://github.com/a-y-n/aynse/issues).

## license

this project is in the public domain. see the [license](LICENSE.YOLO.md) file for more details.
