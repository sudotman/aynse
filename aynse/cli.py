"""
Command-line interface for aynse.

This module provides CLI commands for downloading NSE data:
- bhavcopy: Download equity/F&O/index bhavcopies
- stock: Download historical stock data
- index: Download historical index data
- derivatives: Download derivatives data
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import click
import requests

from aynse import nse
from aynse import holidays as hol
from aynse.rbi import RBI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(package_name='aynse')
def cli() -> None:
    """
    aynse - A command line tool to download NSE stock market data.
    
    Use the various subcommands to download different types of data:
    
    \b
    - bhavcopy: Download daily bhavcopies (equity, F&O, index)
    - stock: Download historical stock data
    - index: Download historical index data  
    - derivatives: Download derivatives (futures/options) data
    
    Examples:
    
    \b
    # Download today's equity bhavcopy
    aynse bhavcopy -d /path/to/dir
    
    \b
    # Download historical stock data
    aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -o reliance.csv
    """
    pass


def _safe_download(
    downloader_func,
    dt: date,
    dest: str
) -> tuple[date, bool, Optional[str]]:
    """
    Safely execute a download function with error handling.
    
    Args:
        downloader_func: Function to call for download
        dt: Date to download
        dest: Destination directory
        
    Returns:
        Tuple of (date, success, error_message)
    """
    try:
        downloader_func(dt, dest)
        return (dt, True, None)
    except FileNotFoundError as e:
        return (dt, False, f"File not found: {e}")
    except requests.exceptions.Timeout as e:
        return (dt, False, f"Timeout: {e}")
    except requests.exceptions.RequestException as e:
        return (dt, False, f"Request error: {e}")
    except Exception as e:
        return (dt, False, f"Error: {e}")


@cli.command("bhavcopy")
@click.option(
    "--dest", "-d",
    help="Destination directory path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
@click.option(
    "--from", "-f", "from_date",
    help="From date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--to", "-t", "to_date",
    help="To date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--fo/--no-fo",
    help="Download F&O bhavcopy instead of equity",
    default=False
)
@click.option(
    "--idx/--no-idx",
    help="Download Index bhavcopy instead of equity",
    default=False
)
@click.option(
    "--full/--no-full",
    help="Download full bhavcopy (includes delivery info)",
    default=False
)
def bhavcopy(
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    dest: str,
    fo: bool,
    idx: bool,
    full: bool
) -> None:
    """
    Download bhavcopy from NSE's website.
    
    Downloads equity bhavcopy by default. Use flags to download other types:
    
    \b
    Examples:
    
    \b
    # Download today's equity bhavcopy
    aynse bhavcopy -d /path/to/dir
    
    \b
    # Download bhavcopy for a specific date
    aynse bhavcopy -d /path/to/dir -f 2024-01-15
    
    \b
    # Download bhavcopy for a date range
    aynse bhavcopy -d /path/to/dir -f 2024-01-01 -t 2024-01-31
    
    \b
    # Download F&O bhavcopy
    aynse bhavcopy -d /path/to/dir --fo
    
    \b
    # Download index bhavcopy
    aynse bhavcopy -d /path/to/dir --idx
    
    \b
    # Download full bhavcopy with delivery data
    aynse bhavcopy -d /path/to/dir --full
    """
    # Select the appropriate downloader function
    downloader = nse.bhavcopy_save
    bhavcopy_type = "Equity"
    
    if full:
        downloader = nse.full_bhavcopy_save
        bhavcopy_type = "Full Equity"
    elif idx:
        downloader = nse.bhavcopy_index_save
        bhavcopy_type = "Index"
    elif fo:
        downloader = nse.bhavcopy_fo_save
        bhavcopy_type = "F&O"

    # Single date download (today or specific date)
    if not from_date or (from_date and not to_date):
        dt = from_date.date() if from_date else date.today()
        
        click.echo(f"Downloading {bhavcopy_type} bhavcopy for {dt}...")
        
        try:
            path = downloader(dt, dest)
            click.echo(click.style(f"✓ Saved to: {path}", fg='green'))
        except FileNotFoundError:
            click.echo(
                click.style(
                    f"✗ No data available for {dt} (might be a holiday)",
                    fg='yellow'
                ),
                err=True
            )
            sys.exit(1)
        except requests.exceptions.Timeout:
            click.echo(
                click.style(
                    f"✗ Timeout while downloading. Check your internet connection "
                    f"or the date might be a holiday.",
                    fg='red'
                ),
                err=True
            )
            sys.exit(1)
        except Exception as e:
            click.echo(
                click.style(f"✗ Error: {e}", fg='red'),
                err=True
            )
            sys.exit(1)
        return

    # Date range download
    if from_date and to_date:
        start_dt = from_date.date() if isinstance(from_date, datetime) else from_date
        end_dt = to_date.date() if isinstance(to_date, datetime) else to_date
        
        # Build list of weekdays in range
        date_range = []
        delta = end_dt - start_dt
        for i in range(delta.days + 1):
            dt = start_dt + timedelta(days=i)
            if dt.weekday() < 5:  # Weekday
                date_range.append(dt)
        
        if not date_range:
            click.echo(
                click.style("No weekdays in the specified date range.", fg='yellow'),
                err=True
            )
            return
        
        click.echo(
            f"Downloading {bhavcopy_type} bhavcopies from {start_dt} to {end_dt} "
            f"({len(date_range)} days)..."
        )
        
        failed_downloads = []
        successful = 0
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_safe_download, downloader, dt, dest): dt
                for dt in date_range
            }
            
            with click.progressbar(
                length=len(futures),
                label="Downloading"
            ) as progress:
                for future in as_completed(futures):
                    dt, success, error = future.result()
                    if success:
                        successful += 1
                    else:
                        failed_downloads.append((dt, error))
                    progress.update(1)
        
        click.echo()
        click.echo(click.style(f"✓ Successfully downloaded: {successful}", fg='green'))
        click.echo(f"  Saved to: {dest}")
        
        if failed_downloads:
            click.echo(
                click.style(
                    f"\n✗ Failed downloads: {len(failed_downloads)} (likely holidays)",
                    fg='yellow'
                )
            )
            for dt, error in failed_downloads[:10]:  # Show first 10
                click.echo(f"  - {dt}")
            if len(failed_downloads) > 10:
                click.echo(f"  ... and {len(failed_downloads) - 10} more")


@cli.command("stock")
@click.option(
    "--symbol", "-s",
    required=True,
    help="Stock symbol (e.g., RELIANCE, TCS, INFY)"
)
@click.option(
    "--from", "-f", "from_date",
    required=True,
    help="From date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--to", "-t", "to_date",
    required=True,
    help="To date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--series", "-S",
    default="EQ",
    show_default=True,
    help="Series (EQ, BE, etc.)"
)
@click.option(
    "--output", "-o",
    default="",
    help="Output file path (default: SYMBOL-FROM-TO-SERIES.csv)"
)
def stock_command(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    series: str,
    output: str
) -> None:
    """
    Download historical stock data.
    
    Fetches OHLCV data for a stock symbol over a date range and saves to CSV.
    
    \b
    Examples:
    
    \b
    # Basic usage
    aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31
    
    \b
    # With custom output file
    aynse stock -s TCS -f 2024-01-01 -t 2024-03-31 -o tcs_q1_2024.csv
    
    \b
    # Different series
    aynse stock -s RELIANCE -f 2024-01-01 -t 2024-03-31 -S BE
    """
    from_dt = from_date.date()
    to_dt = to_date.date()
    
    click.echo(f"Fetching {symbol} data from {from_dt} to {to_dt}...")
    
    try:
        output_path = nse.stock_csv(
            symbol,
            from_dt,
            to_dt,
            series,
            output,
            show_progress=True
        )
        click.echo()
        click.echo(click.style(f"✓ Saved to: {output_path}", fg='green'))
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg='red'), err=True)
        logger.exception("Error downloading stock data")
        sys.exit(1)


@cli.command("index")
@click.option(
    "--symbol", "-s",
    required=True,
    help="Index symbol (e.g., 'NIFTY 50', 'NIFTY BANK')"
)
@click.option(
    "--from", "-f", "from_date",
    required=True,
    help="From date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--to", "-t", "to_date",
    required=True,
    help="To date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--output", "-o",
    default="",
    help="Output file path (default: SYMBOL-FROM-TO.csv)"
)
def index_command(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    output: str
) -> None:
    """
    Download historical index data.
    
    Fetches OHLC data for an index over a date range and saves to CSV.
    
    \b
    Examples:
    
    \b
    # Basic usage
    aynse index -s "NIFTY 50" -f 2024-01-01 -t 2024-03-31
    
    \b
    # Bank Nifty
    aynse index -s "NIFTY BANK" -f 2024-01-01 -t 2024-03-31 -o banknifty.csv
    """
    from_dt = from_date.date()
    to_dt = to_date.date()
    
    click.echo(f"Fetching {symbol} data from {from_dt} to {to_dt}...")
    
    try:
        output_path = nse.index_csv(
            symbol,
            from_dt,
            to_dt,
            output,
            show_progress=True
        )
        click.echo()
        click.echo(click.style(f"✓ Saved to: {output_path}", fg='green'))
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg='red'), err=True)
        logger.exception("Error downloading index data")
        sys.exit(1)


@cli.command("derivatives")
@click.option(
    "--symbol", "-s",
    required=True,
    help="Stock/Index symbol"
)
@click.option(
    "--from", "-f", "from_date",
    required=True,
    help="From date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--to", "-t", "to_date",
    required=True,
    help="To date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--expiry", "-e",
    required=True,
    help="Expiry date (YYYY-MM-DD)",
    type=click.DateTime(["%Y-%m-%d"])
)
@click.option(
    "--instru", "-i",
    required=True,
    type=click.Choice(["FUTSTK", "FUTIDX", "OPTSTK", "OPTIDX"]),
    help="Instrument type"
)
@click.option(
    "--price", "-p",
    type=float,
    help="Strike price (required for options)"
)
@click.option(
    "--ce/--pe",
    "is_call",
    default=None,
    help="Call option (--ce) or Put option (--pe)"
)
@click.option(
    "--output", "-o",
    default="",
    help="Output file path"
)
def derivatives_command(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    expiry: datetime,
    instru: str,
    price: Optional[float],
    is_call: Optional[bool],
    output: str
) -> None:
    """
    Download derivatives (futures/options) data.
    
    Fetches historical derivatives data and saves to CSV.
    
    \b
    Examples:
    
    \b
    # Stock futures
    aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i FUTSTK
    
    \b
    # Index futures
    aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i FUTIDX
    
    \b
    # Stock call options
    aynse derivatives -s SBIN -f 2024-01-01 -t 2024-01-30 -e 2024-01-25 -i OPTSTK -p 750 --ce
    
    \b
    # Index put options
    aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-25 -e 2024-01-25 -i OPTIDX -p 21000 --pe
    """
    from_dt = from_date.date()
    to_dt = to_date.date()
    expiry_dt = expiry.date()
    
    # Validate options parameters
    if "OPT" in instru:
        if price is None:
            raise click.UsageError(
                "Strike price (-p/--price) is required for options"
            )
        if is_call is None:
            raise click.UsageError(
                "Option type (--ce for call, --pe for put) is required for options"
            )
        option_type = "CE" if is_call else "PE"
    else:
        option_type = None
        price = None
    
    click.echo(
        f"Fetching {symbol} {instru} data from {from_dt} to {to_dt} "
        f"(expiry: {expiry_dt})..."
    )
    
    try:
        output_path = nse.derivatives_csv(
            symbol,
            from_dt,
            to_dt,
            expiry_dt,
            instru,
            price,
            option_type,
            output,
            show_progress=True
        )
        click.echo()
        click.echo(click.style(f"✓ Saved to: {output_path}", fg='green'))
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg='red'), err=True)
        logger.exception("Error downloading derivatives data")
        sys.exit(1)


@cli.command("holidays")
@click.option(
    "--year", "-y",
    type=int,
    default=None,
    help="Year to list holidays for (default: current year)"
)
def holidays_command(year: Optional[int]) -> None:
    """
    List trading holidays.
    
    Shows all trading holidays for the specified year.
    
    \b
    Examples:
    
    \b
    # List holidays for current year
    aynse holidays
    
    \b
    # List holidays for 2024
    aynse holidays -y 2024
    """
    if year is None:
        year = date.today().year
    
    holiday_list = hol.holidays(year=year)
    
    if not holiday_list:
        click.echo(f"No holiday data available for {year}")
        return
    
    click.echo(f"\nTrading holidays for {year}:")
    click.echo("-" * 30)
    
    for dt in sorted(holiday_list):
        weekday = dt.strftime("%A")
        click.echo(f"  {dt.strftime('%Y-%m-%d')} ({weekday})")
    
    click.echo(f"\nTotal: {len(holiday_list)} holidays")


@cli.command("quote")
@click.option(
    "--symbol", "-s",
    required=True,
    help="Stock symbol"
)
def quote_command(symbol: str) -> None:
    """
    Get live stock quote.
    
    Fetches and displays the current market quote for a stock.
    
    \b
    Example:
    
    \b
    aynse quote -s RELIANCE
    """
    from aynse.nse import NSELive
    
    click.echo(f"Fetching quote for {symbol}...")
    
    try:
        live = NSELive()
        quote = live.stock_quote(symbol)
        
        info = quote.get('info', {})
        price_info = quote.get('priceInfo', {})
        
        click.echo()
        click.echo(f"Symbol: {info.get('symbol', symbol)}")
        click.echo(f"Company: {info.get('companyName', 'N/A')}")
        click.echo()
        click.echo(f"Last Price: ₹{price_info.get('lastPrice', 'N/A')}")
        click.echo(f"Change: {price_info.get('change', 'N/A')} ({price_info.get('pChange', 'N/A')}%)")
        click.echo(f"Open: ₹{price_info.get('open', 'N/A')}")
        click.echo(f"High: ₹{price_info.get('intraDayHighLow', {}).get('max', 'N/A')}")
        click.echo(f"Low: ₹{price_info.get('intraDayHighLow', {}).get('min', 'N/A')}")
        click.echo(f"Prev Close: ₹{price_info.get('previousClose', 'N/A')}")
        
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg='red'), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
