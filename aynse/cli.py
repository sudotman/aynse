"""
Command-line interface for aynse.

This module provides CLI commands for downloading NSE data:
- bhavcopy: Download equity/F&O/index bhavcopies
- stock: Download historical stock data
- index: Download historical index data
- derivatives: Download derivatives data
- ipo: List NSE IPOs and backtest listing-day exits
"""

from __future__ import annotations

import os
import sys
import logging
import json
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import click
import requests

from aynse import nse
from aynse.holidays import holidays as list_holidays
from aynse.rbi import RBI
from aynse.mutual_funds import (
    mutual_fund_history_raw,
    mutual_fund_search,
    mutual_fund_summary,
)
from aynse.ipo import (
    EQUITY_BOARDS,
    IPO_EXIT_FIELDS,
    ipo_backtest,
    ipo_live_issues,
    ipo_past_issues,
    ipo_report,
    summarize_ipo_backtest,
)
from aynse.standard import write_records_csv

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
    
    holiday_list = list_holidays(year=year)
    
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
        price_info = quote.get('price', {})
        
        click.echo()
        click.echo(f"Symbol: {quote.get('symbol', symbol)}")
        click.echo(f"Company: {quote.get('company_name', 'N/A')}")
        click.echo()
        click.echo(f"Last Price: ₹{price_info.get('last', 'N/A')}")
        click.echo(f"Change: {price_info.get('change', 'N/A')} ({price_info.get('change_percent', 'N/A')}%)")
        click.echo(f"Open: ₹{price_info.get('open', 'N/A')}")
        click.echo(f"High: ₹{price_info.get('high', 'N/A')}")
        click.echo(f"Low: ₹{price_info.get('low', 'N/A')}")
        click.echo(f"Prev Close: ₹{price_info.get('previous_close', 'N/A')}")
        
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.group("mutual-fund")
def mutual_fund_group() -> None:
    """Search and analyze official AMFI mutual-fund NAV data."""


@mutual_fund_group.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=20, show_default=True, type=click.IntRange(1, 100))
def mutual_fund_search_command(query: str, limit: int) -> None:
    """Search current AMFI schemes by name, code, ISIN, or fund house."""
    try:
        records = mutual_fund_search(query, limit=limit)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if not records:
        click.echo("No current AMFI schemes matched the query.")
        return
    click.echo("SCHEME CODE\tLATEST NAV\tNAV DATE\tSCHEME")
    for row in records:
        click.echo(
            f"{row.get('scheme_code', '')}\t{row.get('latest_nav', '')}\t"
            f"{row.get('latest_nav_date', '')}\t{row.get('scheme_name', '')}"
        )


@mutual_fund_group.command("history")
@click.option("--scheme-code", "-s", required=True, help="Numeric AMFI scheme code")
@click.option(
    "--from", "-f", "from_date", required=True, type=click.DateTime(["%Y-%m-%d"]),
    help="From date (YYYY-MM-DD)",
)
@click.option(
    "--to", "-t", "to_date", required=True, type=click.DateTime(["%Y-%m-%d"]),
    help="To date (YYYY-MM-DD)",
)
@click.option("--limit", "-n", default=20, show_default=True, type=click.IntRange(1, 1000))
@click.option("--output", "-o", default="", type=click.Path(dir_okay=False), help="Optional CSV path")
def mutual_fund_history_command(
    scheme_code: str,
    from_date: datetime,
    to_date: datetime,
    limit: int,
    output: str,
) -> None:
    """Fetch daily NAV history for one AMFI scheme."""
    try:
        records = mutual_fund_history_raw(scheme_code, from_date.date(), to_date.date())
        if output:
            path = write_records_csv(output, records)
            click.echo(click.style(f"✓ Saved {len(records)} NAV records to: {path}", fg="green"))
            return
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if not records:
        click.echo("AMFI returned no NAV observations for this period.")
        return
    click.echo(f"{records[-1].get('scheme_name', scheme_code)} ({scheme_code})")
    click.echo("DATE\tNAV")
    for row in records[-limit:]:
        nav_date = row.get("date")
        click.echo(f"{nav_date.isoformat() if isinstance(nav_date, date) else nav_date}\t{row.get('nav', '')}")


@mutual_fund_group.command("analyze")
@click.option("--scheme-code", "-s", required=True, help="Numeric AMFI scheme code")
@click.option(
    "--from", "-f", "from_date", required=True, type=click.DateTime(["%Y-%m-%d"]),
    help="From date (YYYY-MM-DD)",
)
@click.option(
    "--to", "-t", "to_date", required=True, type=click.DateTime(["%Y-%m-%d"]),
    help="To date (YYYY-MM-DD)",
)
@click.option("--json-output", is_flag=True, help="Print the complete summary as JSON")
def mutual_fund_analyze_command(
    scheme_code: str,
    from_date: datetime,
    to_date: datetime,
    json_output: bool,
) -> None:
    """Calculate NAV return, volatility, and drawdown metrics."""
    try:
        summary = mutual_fund_summary(scheme_code, from_date.date(), to_date.date())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        click.echo(json.dumps(summary, default=str, indent=2))
        return
    scheme = summary.get("scheme") or {}
    metrics = summary.get("metrics") or {}
    click.echo(f"{scheme.get('scheme_name', scheme_code)} ({scheme_code})")
    click.echo(f"Plan / option: {scheme.get('plan') or 'N/A'} / {scheme.get('option') or 'N/A'}")
    click.echo(f"AMFI NAV as of: {summary.get('as_of_date') or 'N/A'}")
    click.echo(f"Observations: {metrics.get('observations', 0)}")
    click.echo(f"Absolute NAV return: {metrics.get('absolute_return_percent')}")
    click.echo(f"CAGR (>= 365 days only): {metrics.get('cagr_percent')}")
    click.echo(f"Annualized volatility: {metrics.get('annualized_volatility_percent')}")
    click.echo(f"Maximum drawdown: {metrics.get('max_drawdown_percent')}")
    click.echo("Basis: NAV return; IDCW cash distributions, loads, taxes, and cash flows are excluded.")


def _fmt_pct(value: object) -> str:
    return f"{float(value):+.1f}%" if isinstance(value, (int, float)) else "n/a"


def _fmt_x(value: object) -> str:
    return f"{float(value):.1f}x" if isinstance(value, (int, float)) else "n/a"


def _ipo_boards(board: str) -> tuple:
    return EQUITY_BOARDS if board == "equity" else (board,)


@cli.group("ipo")
def ipo_group() -> None:
    """List NSE IPOs and backtest selling on listing day."""


@ipo_group.command("list")
@click.option("--board", "-b", default="equity", show_default=True,
              type=click.Choice(["equity", "mainboard", "sme", "reit", "invit", "debt"]))
@click.option("--from", "-f", "from_date", default=None, type=click.DateTime(["%Y-%m-%d"]), help="Listed on or after")
@click.option("--to", "-t", "to_date", default=None, type=click.DateTime(["%Y-%m-%d"]), help="Listed on or before")
@click.option("--limit", "-n", default=30, show_default=True, type=click.IntRange(1, 5000))
def ipo_list_command(board: str, from_date: Optional[datetime], to_date: Optional[datetime], limit: int) -> None:
    """List past public issues, newest listing first."""
    try:
        issues = ipo_past_issues(
            from_date.date() if from_date else None,
            to_date.date() if to_date else None,
            _ipo_boards(board),
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("LISTED\tSYMBOL\tBOARD\tISSUE PRICE\tCOMPANY")
    for issue in issues[:limit]:
        listed = issue.get("listing_date")
        click.echo(
            f"{listed.isoformat() if listed else 'pending'}\t{issue['symbol']}\t{issue['board']}\t"
            f"{issue.get('issue_price') or 'n/a'}\t{issue.get('company_name') or ''}"
        )


@ipo_group.command("current")
def ipo_current_command() -> None:
    """Show IPOs open for bidding (with live subscription) and forthcoming ones."""
    try:
        rows = ipo_live_issues()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("STATUS\tSYMBOL\tBOARD\tCLOSES\tBAND\tSUBSCRIBED")
    for row in rows:
        closes = row.get("issue_end_date")
        click.echo(
            f"{row.get('status') or ''}\t{row['symbol']}\t{row['board']}\t"
            f"{closes.isoformat() if closes else ''}\t{row.get('price_band_text') or ''}\t"
            f"{_fmt_x(row.get('subscription_total_x'))}"
        )


@ipo_group.command("show")
@click.argument("symbol")
@click.option("--json-output", is_flag=True, help="Print the full record, including the daily path, as JSON")
def ipo_show_command(symbol: str, json_output: bool) -> None:
    """Show subscription and listing performance for one IPO."""
    try:
        record = ipo_report(symbol)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        click.echo(json.dumps(record, default=str, indent=2))
        return
    click.echo(f"{record.get('company_name') or record['symbol']} ({record['symbol']}, {record['board']})")
    click.echo(f"Issue price: {record.get('issue_price')}  listed: {record.get('listing_date') or 'pending'}")
    click.echo(
        f"Subscription: total {_fmt_x(record.get('subscription_total_x'))}, "
        f"retail {_fmt_x(record.get('subscription_retail_x'))}, QIB {_fmt_x(record.get('subscription_qib_x'))}"
    )
    if not record.get("has_listing_data"):
        click.echo("No listing-day trades yet.")
        return
    listing = ", ".join(
        f"{name} {_fmt_pct(record.get(f'return_{name}_pct'))}" for name in ("open", "high", "low", "close", "vwap")
    )
    held = ", ".join(f"{name} {_fmt_pct(record.get(f'return_{name}_pct'))}" for name in ("w1", "m1", "m3", "m6", "y1"))
    click.echo(f"Listing day vs issue: {listing}")
    click.echo(f"Held: {held}")
    if record.get("allotment_probability") is not None:
        click.echo(
            f"Retail allotment odds ~{record['allotment_probability'] * 100:.1f}%; "
            f"expected profit per application at open: {record.get('expected_profit_open')}"
        )


@ipo_group.command("backtest")
@click.option("--board", "-b", default="equity", show_default=True,
              type=click.Choice(["equity", "mainboard", "sme"]))
@click.option("--from", "-f", "from_date", default=None, type=click.DateTime(["%Y-%m-%d"]), help="Listed on or after")
@click.option("--to", "-t", "to_date", default=None, type=click.DateTime(["%Y-%m-%d"]), help="Listed on or before")
@click.option("--exit", "-e", "exit_name", default="open", show_default=True, type=click.Choice(list(IPO_EXIT_FIELDS)))
@click.option("--cache", "cache_path", default="", type=click.Path(dir_okay=False),
              help="JSON file of previous records; only new or maturing IPOs are re-fetched")
@click.option("--output", "-o", default="", type=click.Path(dir_okay=False), help="Optional CSV path for all records")
@click.option("--workers", "-w", default=4, show_default=True, type=click.IntRange(1, 16))
@click.option("--json-output", is_flag=True, help="Print the summary as JSON")
def ipo_backtest_command(
    board: str,
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    exit_name: str,
    cache_path: str,
    output: str,
    workers: int,
    json_output: bool,
) -> None:
    """Backtest buying IPOs at the issue price and selling on or after listing."""
    # A full build makes thousands of requests; per-request INFO logs drown the progress line.
    logging.getLogger("aynse.nse.http_client").setLevel(logging.WARNING)
    existing = []
    if cache_path and os.path.isfile(cache_path):
        with open(cache_path, encoding="utf-8") as handle:
            existing = json.load(handle)

    def progress(done: int, total: int, record: dict) -> None:
        if not json_output:
            click.echo(f"\r  fetched {done}/{total} ({record.get('symbol')})".ljust(60), nl=False, err=True)

    try:
        records = ipo_backtest(
            from_date.date() if from_date else None,
            to_date.date() if to_date else None,
            _ipo_boards(board),
            existing=existing,
            max_workers=workers,
            progress=progress,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if not json_output:
        click.echo("", err=True)
    if cache_path:
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(records, handle, default=str)
    if output:
        path = write_records_csv(output, records)
        click.echo(click.style(f"Saved {len(records)} IPO records to: {path}", fg="green"), err=True)

    summary = summarize_ipo_backtest(records, exit_name)
    if json_output:
        pnl = {key: value for key, value in summary["pnl"].items() if key != "curve"}
        click.echo(json.dumps({**summary, "pnl": pnl}, default=str, indent=2))
        return
    click.echo(f"{summary['count']} listed IPOs, {summary['from_date']} to {summary['to_date']}")
    click.echo("STRATEGY\tN\tMEDIAN\tMEAN\tWIN RATE")
    for stats in summary["strategies"].values():
        if stats.get("count"):
            click.echo(
                f"{stats['label']}\t{stats['count']}\t{_fmt_pct(stats['median_pct'])}\t"
                f"{_fmt_pct(stats['mean_pct'])}\t{stats['win_rate_pct']:.0f}%"
            )
    for title, groups in (
        (f"By total subscription ({summary['exit_label']})", summary["by_subscription"]),
        ("By listing year", summary["by_year"]),
    ):
        click.echo(f"\n{title}:")
        for group in groups:
            click.echo(
                f"  {group['group']:>8}\tn={group['count']}\tmedian {_fmt_pct(group.get('median_pct'))}\t"
                f"win {group.get('win_rate_pct', 0):.0f}%"
            )
    pnl = summary["pnl"]
    if pnl.get("mean_expected_profit_per_application") is not None:
        click.echo(
            f"\nMainboard retail, one minimum application each: "
            f"~Rs.{pnl['mean_expected_profit_per_application']:,.0f} expected per application after "
            f"allotment odds (Rs.{pnl['mean_profit_per_allotment']:,.0f} if allotted)."
        )
    click.echo(f"Basis: {summary['basis']}")


# Concise alias for interactive use while retaining a descriptive help entry.
cli.add_command(mutual_fund_group, "mf")


if __name__ == "__main__":
    cli()
