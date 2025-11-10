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

## Tips
- Large ranges are chunked month-by-month for reliability
- Retries with backoff are applied under the hood
- For many symbols, use the request batcher

## Download Historical Index Data

```python
from aynse.nse import index_csv, index_df

# Download as pandas dataframe
df = index_df(symbol="NIFTY 50", from_date=date(2024, 1, 1),
              to_date=date(2024, 1, 31))
print(df.head())

# Download as a CSV file
index_csv(symbol="NIFTY 50", from_date=date(2024, 1, 1),
          to_date=date(2024, 1, 31), output="/path/to/file.csv")
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
