# `aynse`

`aynse` is a lean, modern Python library for fetching data from the National Stock Exchange (NSE) of India. It is a fork of the unmaintained `jugaad-data` library, aiming to provide a robust and regularly updated tool for financial data analysis.

This library fetches data from the new NSE website and is future-proof. Many other libraries still rely on the old website and may eventually stop working.

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

You can optionally install `pandas` library in case you are interested in fetching data directly into pandas dataframes, in which case you can run:

```sh
pip install aynse pandas
```

## Quick Start

### Download Bhavcopies and Historical Data

```python
from datetime import date
from aynse.nse import bhavcopy_save, bhavcopy_fo_save

# Download bhavcopy
bhavcopy_save(date(2024, 1, 1), "./")

# Download bhavcopy for futures and options
bhavcopy_fo_save(date(2024, 1, 1), "./")
```

### Fetch Live Quotes

```python
from aynse.nse import NSELive
from pprint import pprint

n = NSELive()
q = n.stock_quote("INFY")
pprint(q)
```
