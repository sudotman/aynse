# Live Data

The `NSELive` class provides real-time market data from NSE including stock quotes, option chains, market status, and more.

## Getting Started

```python
from aynse import NSELive

live = NSELive()
```

## Stock Quotes

### Basic Quote

```python
quote = live.stock_quote("RELIANCE")

# Access price information
price_info = quote['priceInfo']
print(f"Last Price: ₹{price_info['lastPrice']}")
print(f"Change: {price_info['change']} ({price_info['pChange']}%)")
print(f"Open: ₹{price_info['open']}")
print(f"Day High: ₹{price_info['intraDayHighLow']['max']}")
print(f"Day Low: ₹{price_info['intraDayHighLow']['min']}")
print(f"Previous Close: ₹{price_info['previousClose']}")

# Access company info
info = quote['info']
print(f"Company: {info['companyName']}")
print(f"Industry: {info['industry']}")
print(f"ISIN: {info['isin']}")
```

### F&O Quote

Get quote with F&O details:

```python
fno_quote = live.stock_quote_fno("RELIANCE")

print(f"Available Strike Prices: {fno_quote['strikePrices']}")
print(f"Available Expiries: {fno_quote['expiryDates']}")
```

### Trade Info

Get detailed trading information:

```python
trade_info = live.trade_info("RELIANCE")

# Bulk/Block deals
print(f"Bulk Deals: {trade_info['bulkBlockDeals']}")

# Order book
order_book = trade_info['marketDeptOrderBook']
print(f"Total Buy Qty: {order_book['totalBuyQuantity']}")
print(f"Total Sell Qty: {order_book['totalSellQuantity']}")
```

## Market Status

```python
status = live.market_status()

for market in status['marketState']:
    print(f"{market['market']}: {market['marketStatus']}")
```

## Option Chains

### Index Option Chain

```python
# NIFTY option chain
chain = live.index_option_chain("NIFTY")

records = chain['records']
print(f"Expiry Dates: {records['expiryDates']}")
print(f"Strike Prices: {records['strikePrices']}")

# Get ATM (at-the-money) data
atm = chain['filtered']['data']
for strike in atm[:5]:
    ce = strike.get('CE', {})
    pe = strike.get('PE', {})
    print(f"Strike {strike['strikePrice']}: CE OI={ce.get('openInterest', 0)}, PE OI={pe.get('openInterest', 0)}")
```

### Equity Option Chain

```python
# RELIANCE option chain
chain = live.equities_option_chain("RELIANCE")

records = chain['records']
for strike_data in records['data'][:5]:
    print(f"Strike: {strike_data['strikePrice']}")
```

### Currency Option Chain

```python
chain = live.currency_option_chain("USDINR")
print(f"Expiry Dates: {chain['records']['expiryDates']}")
```

## Indices Data

### All Indices

```python
indices = live.all_indices()

print(f"Advances: {indices['advances']}")
print(f"Declines: {indices['declines']}")

for idx in indices['data'][:5]:
    print(f"{idx['index']}: {idx['last']} ({idx['percentChange']}%)")
```

### Live Index Data

```python
# Get NIFTY 50 data with all constituents
nifty = live.live_index("NIFTY 50")

print(f"NIFTY 50: {nifty['data'][0]['last']}")
print(f"Advances: {nifty['advance']['advances']}")
print(f"Declines: {nifty['advance']['declines']}")

# Top gainers/losers
for stock in nifty['data'][1:6]:
    print(f"{stock['symbol']}: {stock['pChange']}%")
```

### F&O Securities

```python
fno = live.live_fno()
print(f"Total F&O Securities: {len(fno['data'])}")
```

## Pre-Open Market

```python
preopen = live.pre_open_market("NIFTY")

print(f"Advances: {preopen['advances']}")
print(f"Declines: {preopen['declines']}")
print(f"Unchanged: {preopen['unchanged']}")

# Pre-open prices
for stock in preopen['data'][:5]:
    meta = stock['metadata']
    print(f"{meta['symbol']}: ₹{meta['lastPrice']} ({meta['pChange']}%)")
```

## Chart/Tick Data

Get intraday tick data for charting:

```python
# Stock tick data
ticks = live.tick_data("RELIANCE")
chart_data = ticks['grapthData']  # Note: NSE typo in response

# Index tick data
index_ticks = live.tick_data("NIFTY 50", indices=True)
```

## Market Turnover

```python
turnover = live.market_turnover()
print(turnover)
```

## Derivatives Turnover

```python
# All contracts
turnover = live.eq_derivative_turnover()
print(f"Value: {turnover['value']}")
print(f"Volume: {turnover['volume']}")

# Specific segment
nifty_turnover = live.eq_derivative_turnover(type="fu_nifty50")
```

## Corporate Announcements

```python
from datetime import date

# All announcements
announcements = live.corporate_announcements()

# Filter by date range
announcements = live.corporate_announcements(
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)

# Filter by symbol
announcements = live.corporate_announcements(symbol="RELIANCE")
```

## Trading Holidays

```python
holidays = live.holiday_list()

# CM (Capital Market) holidays
for holiday in holidays.get('CM', []):
    print(f"{holiday['tradingDate']}: {holiday['description']}")
```

## Bulk Operations

### Multiple Option Chains

Fetch option chains for multiple stocks concurrently:

```python
symbols = ["RELIANCE", "TCS", "INFY", "HDFC", "SBIN"]
results = live.bulk_equities_option_chain(symbols, max_workers=3)

print(f"Successful: {results['summary']['successful']}")
print(f"Failed: {results['summary']['failed']}")

for symbol, data in results['success'].items():
    print(f"{symbol}: {len(data['records']['data'])} strikes")
```

### Options Around Earnings

Analyze options around earnings dates:

```python
from datetime import date

analysis = live.get_options_around_date(
    symbol="RELIANCE",
    target_date=date(2024, 1, 19),  # Earnings date
    days_before=5,
    days_after=5
)

print(f"Primary Expiry: {analysis['primary_expiry']}")
print(f"Relevant Expiries: {len(analysis['relevant_expiries'])}")
```

### Bulk Earnings Analysis

```python
stocks_and_dates = [
    ("RELIANCE", date(2024, 1, 19)),
    ("TCS", date(2024, 1, 11)),
    ("INFY", date(2024, 1, 12)),
]

results = live.analyze_earnings_options(stocks_and_dates, max_workers=3)

for symbol, analysis in results.items():
    if 'error' not in analysis:
        print(f"{symbol}: {analysis['analysis']['total_strikes']} strikes")
```

## Caching Behavior

Live data methods use time-based caching to prevent excessive API calls:

- Default cache timeout: 5 seconds
- Cache is per-method and per-arguments
- Cache automatically expires and refreshes

```python
# First call - fetches from API
quote1 = live.stock_quote("RELIANCE")

# Within 5 seconds - returns cached data
quote2 = live.stock_quote("RELIANCE")  # Same object

# After 5 seconds - fetches fresh data
import time
time.sleep(6)
quote3 = live.stock_quote("RELIANCE")  # Fresh fetch
```

You can customize the timeout:

```python
live = NSELive()
live.time_out = 10  # Cache for 10 seconds
```

## Error Handling

```python
from aynse import NSELive
from aynse.nse.http_client import CircuitOpenError

live = NSELive()

try:
    quote = live.stock_quote("INVALID_SYMBOL")
except Exception as e:
    print(f"Error fetching quote: {e}")

# Circuit breaker opens after repeated failures
try:
    # After many failures...
    quote = live.stock_quote("RELIANCE")
except CircuitOpenError:
    print("Circuit breaker is open, wait before retrying")
```

## Notes

- Live endpoints are automatically rate-limited
- The HTTP client handles retries with exponential backoff
- Session cookies are managed automatically (NSE requires specific cookies)
- All responses are cached briefly to reduce API load
