# `aynse`

`aynse` is a lean, modern Python library for fetching data from the National Stock Exchange (NSE) of India. It is a fork of the unmaintained `jugaad-data` library, aiming to provide a robust and regularly updated tool for financial data analysis.

This library fetches data from the new NSE website and is future-proof. Many other libraries still rely on the old website and may eventually stop working.

## Features

-   **Historical Data:** Fetch historical stock and index data.
-   **Derivatives Data:** Download futures and options data.
-   **Bhavcopy:** Download daily bhavcopy reports for equity, F&O, and indices.
-   **Bulk Deals:** Download bulk deals data for date ranges.
-   **Live Market Data:** Get real-time stock quotes and market information.
-   **Option Chains:** Fetch option chain data for stocks, indices, and currencies.
-   **Bulk Operations:** Concurrent fetching of data for multiple symbols or contracts.
-   **Earnings Analysis:** Specialized tools for analyzing options around earnings dates.
-   **RBI Data:** Access to RBI policy rates and historical data.
-   **Holiday Information:** Retrieve trading holidays for any year.
-   **Command-Line Interface:** A simple CLI for quick data downloads.
-   **Pandas Integration:** Returns data as Pandas DataFrames for easy analysis.

## Installation

You can install `aynse` directly from PyPI:

```sh
pip install aynse
```

You can optionally install `pandas` library in case you are interested in fetching data directly into pandas dataframes, in which case you can run:

```sh
pip install aynse pandas
```

## Quick Start

### Download Bhavcopies and Historical Data

```python
from datetime import date
from aynse.nse import bhavcopy_save, bhavcopy_fo_save, bulk_deals_save

# Download bhavcopy
bhavcopy_save(date(2024, 1, 1), "./")

# Download bhavcopy for futures and options
bhavcopy_fo_save(date(2024, 1, 1), "./")

# Download bulk deals for a date range
bulk_deals_save(date(2024, 1, 1), date(2024, 1, 31), "./")
```

### Fetch Live Quotes

```python
from aynse.nse import NSELive
from pprint import pprint

n = NSELive()
q = n.stock_quote("INFY")
pprint(q)
```

### Bulk Options Analysis

```python
from aynse.nse import NSELive

n = NSELive()

# Fetch option chains for multiple stocks
symbols = ['RELIANCE', 'TCS', 'HDFCBANK']
bulk_options = n.bulk_equities_option_chain(symbols)

for symbol in bulk_options['success']:
    print(f"{symbol}: {len(bulk_options['success'][symbol]['records']['data'])} contracts")
```

### RBI Data

```python
from aynse.rbi import policy_rate_archive

# Get recent RBI policy rates
rates = policy_rate_archive(n=5)
print(f"Latest repo rate: {rates[0]}")
```
