# Command-Line Interface

`aynse` provides a comprehensive command-line interface for downloading NSE data without writing any code.

## Installation

The CLI is automatically installed with the package:

```bash
pip install aynse
```

Verify installation:

```bash
aynse --version
aynse --help
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `bhavcopy` | Download daily bhavcopies (equity, F&O, index) |
| `stock` | Download historical stock data |
| `index` | Download historical index data |
| `derivatives` | Download derivatives (futures/options) data |
| `quote` | Get live stock quote |
| `holidays` | List trading holidays |

## Bhavcopy Downloads

Download daily bhavcopies for equity, F&O, or indices.

```bash
aynse bhavcopy --help
```

### Download Today's Bhavcopy

```bash
# Equity bhavcopy (works only after market hours)
aynse bhavcopy -d /path/to/directory

# F&O bhavcopy
aynse bhavcopy -d /path/to/directory --fo

# Index bhavcopy
aynse bhavcopy -d /path/to/directory --idx

# Full bhavcopy (with delivery data)
aynse bhavcopy -d /path/to/directory --full
```

### Download for Specific Date

```bash
aynse bhavcopy -d /path/to/directory -f 2024-01-15
```

### Download Date Range

```bash
# Equity bhavcopies for January 2024
aynse bhavcopy -d /path/to/directory -f 2024-01-01 -t 2024-01-31

# F&O bhavcopies for Q1 2024
aynse bhavcopy -d /path/to/directory -f 2024-01-01 -t 2024-03-31 --fo
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dest` | `-d` | Destination directory (required) |
| `--from` | `-f` | From date (YYYY-MM-DD) |
| `--to` | `-t` | To date (YYYY-MM-DD) |
| `--fo` | | Download F&O bhavcopy |
| `--idx` | | Download index bhavcopy |
| `--full` | | Download full bhavcopy with delivery data |

## Historical Stock Data

Download historical OHLCV data for stocks.

```bash
aynse stock --help
```

### Examples

```bash
# Basic usage
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31

# With custom output file
aynse stock -s TCS -f 2024-01-01 -t 2024-03-31 -o tcs_q1_2024.csv

# Different series (BE = trade-to-trade)
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -S BE
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--symbol` | `-s` | Stock symbol (required) |
| `--from` | `-f` | From date (required) |
| `--to` | `-t` | To date (required) |
| `--series` | `-S` | Series: EQ (default), BE, etc. |
| `--output` | `-o` | Output file path |

### Output Format

The CSV file contains:

```
DATE,SERIES,OPEN,HIGH,LOW,PREV. CLOSE,LTP,CLOSE,VWAP,52W H,52W L,VOLUME,VALUE,NO OF TRADES,SYMBOL
```

## Historical Index Data

Download historical OHLC data for indices.

```bash
aynse index --help
```

### Examples

```bash
# NIFTY 50
aynse index -s "NIFTY 50" -f 2024-01-01 -t 2024-03-31

# Bank Nifty
aynse index -s "NIFTY BANK" -f 2024-01-01 -t 2024-03-31 -o banknifty.csv
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--symbol` | `-s` | Index symbol (required) |
| `--from` | `-f` | From date (required) |
| `--to` | `-t` | To date (required) |
| `--output` | `-o` | Output file path |

## Derivatives Data

Download historical data for futures and options.

```bash
aynse derivatives --help
```

### Stock Futures

```bash
aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i FUTSTK
```

### Index Futures

```bash
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i FUTIDX
```

### Stock Options

```bash
# Call option
aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i OPTSTK -p 750 --ce

# Put option
aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i OPTSTK -p 700 --pe
```

### Index Options

```bash
# Call option
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-25 -e 2024-01-25 -i OPTIDX -p 21000 --ce

# Put option
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-25 -e 2024-01-25 -i OPTIDX -p 21000 --pe
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--symbol` | `-s` | Stock/Index symbol (required) |
| `--from` | `-f` | From date (required) |
| `--to` | `-t` | To date (required) |
| `--expiry` | `-e` | Expiry date (required) |
| `--instru` | `-i` | Instrument: FUTSTK, FUTIDX, OPTSTK, OPTIDX (required) |
| `--price` | `-p` | Strike price (required for options) |
| `--ce` | | Call option |
| `--pe` | | Put option |
| `--output` | `-o` | Output file path |

## Live Quote

Get real-time stock quote from the terminal.

```bash
aynse quote --help
```

### Example

```bash
aynse quote -s RELIANCE
```

### Output

```
Fetching quote for RELIANCE...

Symbol: RELIANCE
Company: Reliance Industries Limited

Last Price: ₹2530.00
Change: 40.00 (1.61%)
Open: ₹2500.00
High: ₹2550.00
Low: ₹2480.00
Prev Close: ₹2490.00
```

## Trading Holidays

List NSE trading holidays.

```bash
aynse holidays --help
```

### Examples

```bash
# Current year
aynse holidays

# Specific year
aynse holidays -y 2024
```

### Output

```
Trading holidays for 2024:
------------------------------
  2024-01-22 (Monday)
  2024-01-26 (Friday)
  2024-03-08 (Friday)
  ...

Total: 16 holidays
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid arguments, API error, etc.) |

## Error Handling

The CLI provides helpful error messages:

```bash
# File not found (holiday)
$ aynse bhavcopy -d /tmp -f 2024-01-26
✗ No data available for 2024-01-26 (might be a holiday)

# Invalid symbol
$ aynse quote -s INVALID
✗ Error: No data found for symbol

# Network timeout
$ aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31
✗ Timeout while downloading. Check your internet connection.
```

## Tips

1. **Use date ranges wisely**: Large date ranges are automatically chunked, but smaller ranges are faster.

2. **Check holidays first**: Use `aynse holidays -y YYYY` to see which dates might fail.

3. **Specify output files**: Use `-o` to save to specific locations instead of auto-generated names.

4. **Progress indication**: Long operations show progress bars for tracking.

5. **Batch downloads**: Date range downloads run in parallel for speed.
