# Live Data

`aynse` provides comprehensive live market data functionality through the `NSELive` class. This includes real-time stock quotes, option chains, market status, and advanced bulk operations for concurrent data fetching.

## Basic Live Data

### Stock Quotes

```python
from aynse.nse import NSELive

n = NSELive()

# Get live stock quote
quote = n.stock_quote("RELIANCE")
print(quote['priceInfo'])

# Get F&O stock quote
fno_quote = n.stock_quote_fno("RELIANCE")
print(fno_quote)

# Get detailed trade information
trade_info = n.trade_info("RELIANCE")
print(trade_info)
```

### Market Information

```python
# Check market status
status = n.market_status()
print(f"Market is: {status['marketState'][0]['marketStatus']}")

# Get market turnover
turnover = n.market_turnover()
print(turnover)

# Get equity derivative turnover
eq_turnover = n.eq_derivative_turnover(type="allcontracts")
print(eq_turnover)

# Get pre-open market data
pre_open = n.pre_open_market(key="NIFTY")
print(pre_open)
```

### Index Data

```python
# Get all available indices
all_indices = n.all_indices()
print(f"Total indices: {len(all_indices['data'])}")

# Get live index data
nifty_data = n.live_index("NIFTY 50")
print(nifty_data)

# Get live F&O securities
fno_securities = n.live_fno()
print(f"F&O securities count: {len(fno_securities['data'])}")
```

### Chart and Tick Data

```python
# Get chart data for stock
chart_data = n.chart_data("RELIANCE", indices=False)
print(chart_data)

# Get chart data for index
index_chart = n.chart_data("NIFTY 50", indices=True)
print(index_chart)

# Get tick data
tick_data = n.tick_data("RELIANCE", indices=False)
print(tick_data)
```

## Option Chains

### Individual Option Chains

```python
# Equity option chain
equity_options = n.equities_option_chain("RELIANCE")
print(f"Total contracts: {len(equity_options['records']['data'])}")

# Index option chain
index_options = n.index_option_chain("NIFTY")
print(f"Total contracts: {len(index_options['records']['data'])}")

# Currency option chain
currency_options = n.currency_option_chain("USDINR")
print(f"Total contracts: {len(currency_options['records']['data'])}")
```

### Bulk Option Chains

For concurrent fetching of multiple option chains:

```python
# Fetch option chains for multiple stocks concurrently
symbols = ['RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'HINDUNILVR']
bulk_options = n.bulk_equities_option_chain(symbols, max_workers=3)

# Check successful fetches
for symbol in bulk_options['success']:
    contracts_count = len(bulk_options['success'][symbol]['records']['data'])
    print(f"{symbol}: {contracts_count} option contracts")

# Check any errors
for symbol, error in bulk_options['errors'].items():
    print(f"Error fetching {symbol}: {error}")

# Summary
summary = bulk_options['summary']
print(f"Successfully fetched: {summary['successful']}/{summary['total_requested']}")
```

## Advanced Analytics

### Options Around Specific Dates

Perfect for earnings analysis or event-driven trading:

```python
from datetime import date

# Analyze options around a target date (e.g., earnings date)
earnings_date = date(2024, 1, 19)
options_analysis = n.get_options_around_date(
    symbol='RELIANCE',
    target_date=earnings_date,
    days_before=5,
    days_after=5
)

print(f"Current price: {options_analysis['current_price']}")
print(f"Relevant expiries: {options_analysis['relevant_expiries']}")
print(f"ATM strike: {options_analysis['atm_strike']}")

# Analyze option concentrations
for expiry, analysis in options_analysis['expiry_analysis'].items():
    print(f"Expiry {expiry}: {analysis['contracts_count']} contracts")
```

### Bulk Earnings Analysis

Analyze multiple stocks and their earnings dates simultaneously:

```python
# Define stocks with their earnings dates
symbols_and_dates = [
    ('RELIANCE', date(2024, 1, 19)),
    ('TCS', date(2024, 1, 11)), 
    ('HDFCBANK', date(2024, 1, 20)),
    ('ICICIBANK', date(2024, 1, 24)),
    ('HINDUNILVR', date(2024, 1, 26))
]

# Perform bulk earnings analysis
earnings_analysis = n.analyze_earnings_options(symbols_and_dates, max_workers=3)

# Review results
for symbol in earnings_analysis['successful']:
    analysis = earnings_analysis['successful'][symbol]
    print(f"\\n{symbol} Earnings Analysis:")
    print(f"  Current Price: {analysis['current_price']}")
    print(f"  ATM Strike: {analysis['atm_strike']}")
    print(f"  Days to Earnings: {analysis['days_to_earnings']}")
    print(f"  Relevant Expiries: {len(analysis['relevant_expiries'])}")
    
    # Show implied volatility insights if available
    if 'iv_analysis' in analysis:
        iv_data = analysis['iv_analysis']
        print(f"  Avg Call IV: {iv_data.get('avg_call_iv', 'N/A')}")
        print(f"  Avg Put IV: {iv_data.get('avg_put_iv', 'N/A')}")

# Check for any failures
for symbol, error in earnings_analysis['failed'].items():
    print(f"Failed to analyze {symbol}: {error}")
```

## Corporate Data

### Corporate Announcements

```python
from datetime import date

# Get corporate announcements for all equities
announcements = n.corporate_announcements(
    segment='equities',
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)
print(f"Total announcements: {len(announcements)}")

# Filter for a specific symbol
reliance_announcements = n.corporate_announcements(
    segment='equities',
    symbol='RELIANCE',
    from_date=date(2024, 1, 1),
    to_date=date(2024, 1, 31)
)
print(f"RELIANCE announcements: {len(reliance_announcements)}")
```

### Holiday Information

```python
# Get trading holidays
holidays = n.holiday_list()
print("Upcoming holidays:")
for holiday in holidays['CM']:  # Capital Market holidays
    print(f"  {holiday['tradingDate']}: {holiday['description']}")
```

## Performance Tips

1. **Use bulk operations** when fetching data for multiple symbols to improve performance
2. **Adjust max_workers** parameter based on your system and network capacity (default: 3)
3. **Cache results** when possible, as live data has built-in caching mechanisms
4. **Handle errors gracefully** - bulk operations return separate success/error results
5. **Respect rate limits** - NSE may throttle requests if too many are made too quickly

## Error Handling

```python
# Example of robust error handling for bulk operations
try:
    bulk_result = n.bulk_equities_option_chain(['RELIANCE', 'INVALID_SYMBOL'])
    
    # Process successful results
    for symbol, data in bulk_result['success'].items():
        print(f"Successfully fetched {symbol}")
    
    # Handle errors
    for symbol, error in bulk_result['errors'].items():
        print(f"Failed to fetch {symbol}: {error}")
        
except Exception as e:
    print(f"Bulk operation failed entirely: {e}")
```
