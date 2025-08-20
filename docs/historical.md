# Historical Data

## Download Bhavcopies

You can download bhavcopies for stocks, indices, and futures & options using `aynse`. The example below shows how to download different bhavcopies for January 1, 2024, and save them to a directory in CSV format.

```python
from datetime import date
from aynse.nse import bhavcopy_save, full_bhavcopy_save, bhavcopy_fo_save, bhavcopy_index_save

bhavcopy_save(date(2024, 1, 1), "/path/to/directory")
full_bhavcopy_save(date(2024, 1, 1), "/path/to/directory")
bhavcopy_fo_save(date(2024, 1, 1), "/path/to/directory")
bhavcopy_index_save(date(2024, 1, 1), "/path/to/directory")
```

> **Note:** The difference between `bhavcopy_save` and `full_bhavcopy_save` is that the full bhavcopy also includes the percentage of volume that was for delivery.

## Download Index Constituents

Download the constituent stocks of various NSE indices.

```python
from aynse.nse import index_constituent_save, index_constituent_save_all, index_constituent_raw

# Download constituents for a specific index
index_constituent_save("nifty50", "/path/to/directory")

# Download raw constituents data as string
raw_data = index_constituent_raw("nifty50")
print(raw_data)

# Download constituents for all available indices
index_constituent_save_all("/path/to/directory")
```

## Download Bulk Deals Data

Download bulk deals data for specific date ranges using the new bulk deals API.

```python
from datetime import date
from aynse.nse import bulk_deals_raw, bulk_deals_save

# Download bulk deals data as JSON for a date range
bulk_data = bulk_deals_raw(from_date=date(2024, 7, 1), 
                          to_date=date(2024, 7, 31))
print(f"Found {len(bulk_data['data'])} bulk deals")

# Save bulk deals data to a JSON file
bulk_deals_save(from_date=date(2024, 7, 1), 
               to_date=date(2024, 7, 31), 
               dest="/path/to/directory")
```

## Download Historical Stock Data

```python
from datetime import date
from aynse.nse import stock_csv, stock_df

# Download as pandas dataframe
df = stock_df(symbol="RELIANCE", from_date=date(2024, 1, 1),
              to_date=date(2024, 1, 31), series="EQ")
print(df.head())

# Download data and save to a CSV file
stock_csv(symbol="RELIANCE", from_date=date(2024, 1, 1),
          to_date=date(2024, 1, 31), series="EQ", output="/path/to/file.csv")
```

## Download Historical Index Data

```python
from aynse.nse import index_csv, index_df, index_pe_df

# Download as pandas dataframe
df = index_df(symbol="NIFTY 50", from_date=date(2024, 1, 1),
              to_date=date(2024, 1, 31))
print(df.head())

# Download as a CSV file
index_csv(symbol="NIFTY 50", from_date=date(2024, 1, 1),
          to_date=date(2024, 1, 31), output="/path/to/file.csv")

# Download index P/E ratio data
pe_df = index_pe_df(symbol="NIFTY 50", from_date=date(2024, 1, 1),
                   to_date=date(2024, 1, 31))
print(pe_df.head())
```

## Download Historical Derivatives Data

### Get Expiry Dates

For a given day, fetch expiry dates of all active contracts.

```python
from datetime import date
from aynse.nse import expiry_dates

expiries = expiry_dates(date(2024, 1, 1))
print(expiries)
```

You can filter it further based on the contract type (e.g., `OPTIDX`, `FUTSTK`).

```python
from datetime import date
from aynse.nse import expiry_dates

expiries = expiry_dates(date(2024, 1, 1), "FUTSTK")
print(expiries)
```

### Master Functions for Derivatives Data

Use `derivatives_df` to download historical data for a given contract into a pandas DataFrame.

```python
def derivatives_df(symbol, from_date, to_date, expiry_date, instrument_type, option_type, strike_price):
    """
    Downloads historical data for a given contract into a pandas dataframe.

    Args:
        symbol (str): Stock symbol (e.g., "SBIN" or "NIFTY").
        from_date (datetime.date): Start date.
        to_date (datetime.date): End date.
        expiry_date (datetime.date): Expiry date.
        instrument_type (str): "FUTSTK", "FUTIDX", "OPTSTK", or "OPTIDX".
        option_type (str): "CE" for call or "PE" for put (required for options).
        strike_price (float): Strike price (required for options).
    """
```

To download as a CSV file, use `derivatives_csv` and provide an `output` path.

### Stock Futures

```python
from aynse.nse import derivatives_df

df = derivatives_df(symbol="RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 1, 31),
                    expiry_date=date(2024, 1, 25), instrument_type="FUTSTK")
print(df.head())
```

### Stock Options

```python
from aynse.nse import derivatives_df

df = derivatives_df(symbol="RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 1, 31),
                    expiry_date=date(2024, 1, 25), instrument_type="OPTSTK", 
                    option_type="CE", strike_price=2800)
print(df.head())
```

### Index Futures

```python
from aynse.nse import derivatives_df

df = derivatives_df(symbol="NIFTY", from_date=date(2024, 1, 1), to_date=date(2024, 1, 31),
                    expiry_date=date(2024, 1, 25), instrument_type="FUTIDX")
print(df.head())
```

### Index Options

```python
from aynse.nse import derivatives_df

df = derivatives_df(symbol="NIFTY", from_date=date(2024, 1, 1), to_date=date(2024, 1, 31),
                    expiry_date=date(2024, 1, 25), instrument_type="OPTIDX", 
                    option_type="CE", strike_price=21000)
print(df.head())
```

## Bulk Derivatives Operations

For advanced users who need to fetch data for multiple derivatives contracts concurrently, `aynse` provides bulk fetching capabilities through the `NSEHistory` class.

### Bulk Historical Derivatives Data

```python
from datetime import date
from aynse.nse.history import NSEHistory

# Create NSEHistory instance
nse_history = NSEHistory()

# Define multiple derivatives requests
requests_list = [
    {
        'symbol': 'RELIANCE',
        'from_date': date(2024, 1, 1),
        'to_date': date(2024, 1, 31),
        'expiry_date': date(2024, 1, 25),
        'instrument_type': 'FUTSTK'
    },
    {
        'symbol': 'TCS',
        'from_date': date(2024, 1, 1), 
        'to_date': date(2024, 1, 31),
        'expiry_date': date(2024, 1, 25),
        'instrument_type': 'FUTSTK'
    },
    {
        'symbol': 'NIFTY',
        'from_date': date(2024, 1, 1),
        'to_date': date(2024, 1, 31), 
        'expiry_date': date(2024, 1, 25),
        'instrument_type': 'FUTIDX'
    }
]

# Fetch all contracts concurrently
bulk_results = nse_history.bulk_derivatives_raw(requests_list, max_workers=3)

# Process results
for result in bulk_results:
    if 'error' in result:
        print(f"Error for {result['request']['symbol']}: {result['error']}")
    else:
        print(f"Downloaded {len(result['data'])} records for {result['request']['symbol']}")
```

### Historical Options Analysis Around Earnings

```python
from datetime import date
from aynse.nse.history import NSEHistory

# Create NSEHistory instance
nse_history = NSEHistory()

# Analyze options around earnings announcement
earnings_analysis = nse_history.get_earnings_options_historical(
    symbol='RELIANCE',
    earnings_date=date(2024, 1, 19),
    expiry_date=date(2024, 1, 25),
    strike_prices=[2800, 2850, 2900, 2950, 3000],  # List of strike prices
    days_around=7  # Days before/after earnings
)

print(f"Analyzed {len(earnings_analysis)} strike prices")
for strike, data in earnings_analysis.items():
    print(f"Strike {strike}: {len(data['CE'])} CE records, {len(data['PE'])} PE records")
```
