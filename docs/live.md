# Live Data

The `NSELive` class exposes standardized live-market payloads instead of raw endpoint-shaped dicts. Quotes, option chains, market status, and announcements all use canonical top-level keys.

## Getting Started

```python
from aynse import NSELive

live = NSELive()
```

## Stock Quotes

### Basic Quote

```python
quote = live.stock_quote("RELIANCE")

price = quote["price"]
print(f"Last Price: ₹{price['last']}")
print(f"Change: {price['change']} ({price['change_percent']}%)")
print(f"Open: ₹{price['open']}")
print(f"Day High: ₹{price['high']}")
print(f"Day Low: ₹{price['low']}")
print(f"Previous Close: ₹{price['previous_close']}")

print(f"Company: {quote['company_name']}")
print(f"Industry: {quote['industry']}")
print(f"ISIN: {quote['isin']}")
```

### F&O Quote

Get quote with F&O details:

```python
fno_quote = live.stock_quote_fno("RELIANCE")

details = fno_quote["derivative_details"]
print(f"Available Strike Prices: {details['strike_prices'][:5]}")
print(f"Available Expiries: {details['expiry_dates'][:3]}")
```

### Trade Info

Get detailed trading information:

```python
trade_info = live.trade_info("RELIANCE")

print(f"Bulk Deals: {trade_info['bulk_block_deals']}")
print(trade_info["metadata"])
```

## Market Status

```python
status = live.market_status()

for market in status['markets']:
    print(f"{market['market']}: {market['status']}")
```

## Option Chains

### Index Option Chain (v3)

```python
# NIFTY option chain (uses option-chain-v3; auto-selects first expiry)
chain = live.index_option_chain("NIFTY")

print(f"Expiry Dates: {chain['expiry_dates'][:3]}")
print(f"Strike Prices: {chain['strike_prices'][:5]}")
print(chain["summary"])

for strike in chain["records"][:5]:
    ce = strike.get("call") or {}
    pe = strike.get("put") or {}
    print(f"Strike {strike['strike_price']}: CE OI={ce.get('open_interest', 0)}, PE OI={pe.get('open_interest', 0)}")
```

### Equity Option Chain (v3)

```python
# RELIANCE option chain (uses option-chain-v3; auto-selects first expiry)
chain = live.equities_option_chain("RELIANCE")

for strike_data in chain["records"][:5]:
    print(f"Strike: {strike_data['strike_price']}")
```

### Currency Option Chain

```python
chain = live.currency_option_chain("USDINR")
print(f"Expiry Dates: {chain['expiry_dates']}")
```

## Indices Data

### All Indices

```python
indices = live.all_indices()

print(f"Advances: {indices['advances']}")
print(f"Declines: {indices['declines']}")

for idx in indices['indices'][:5]:
    print(f"{idx['index']}: {idx['last']} ({idx['percentChange']}%)")
```

### Live Index Data

```python
nifty = live.live_index("NIFTY 50")

print(f"NIFTY 50: {nifty['data'][0]['last']}")
print(f"Advances: {nifty['advance']}")
print(f"Declines: {nifty['decline']}")

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

for stock in preopen['data'][:5]:
    meta = stock['metadata']
    print(f"{meta['symbol']}: ₹{meta['lastPrice']} ({meta['pChange']}%)")
```

## Chart/Tick Data

Get intraday tick data for charting. The canonical response exposes chart points directly under `points`.

```python
ticks = live.tick_data("RELIANCE")
print(ticks["points"][:5])

index_ticks = live.tick_data("NIFTY 50", indices=True)
print(index_ticks["points"][:5])

week_ticks = live.tick_data("RELIANCE", flag="5D")
```

## Market Turnover

```python
turnover = live.market_turnover()
print(turnover["records"][:2])
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
print(announcements[:2])

# Filter by date range
announcements = live.corporate_announcements(
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)

# Filter by symbol
announcements = live.corporate_announcements(symbol="RELIANCE")
actions = live.corporate_actions(symbol="RELIANCE")
results = live.results_calendar(symbol="RELIANCE")

print(actions[:1])
print(results[:1])
```

## Trading Holidays

```python
holidays = live.holiday_list()

for holiday in holidays["markets"][:5]:
    print(f"{holiday['date']}: {holiday['description']}")
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
    print(f"{symbol}: {len(data['records'])} strikes")
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
print(analysis["analysis"]["summary"])
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
    print(f"{symbol}: {analysis['analysis']['record_count']} strikes")
```

## Metadata

```python
metadata = live.metadata()
print(metadata["supported_instruments"])
print(metadata["supported_event_categories"])
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
