"""
    Implements functionality to download archival data such as Bhavcopy, bulk
    deals from NSE and NSEIndices website
"""
from datetime import datetime, date
import os
import io
import csv
import zipfile
import pprint
import json
import gzip
import pandas as pd
import requests
from io import StringIO
from .connection_pool import get_connection_pool
from .http_client import NSEHttpClient
def unzip(function):
    
    def unzipper(*args, **kwargs):
        r = function(*args, **kwargs)
        fp = io.BytesIO(r)
        with zipfile.ZipFile(file=fp) as zf:
            fname = zf.namelist()[0]
            with zf.open(fname) as fp_bh:
                return fp_bh.read().decode('utf-8')
    return unzipper


class NSEArchives:
    base_url = "https://nsearchives.nseindia.com/"
    nse_api_url = "https://www.nseindia.com/api"
    cutoff_date = date(2024, 7, 8)  # Date when NSE switched formats
    """Conventions
           d - 1, 12 (without leading zero)
          dd - 01, 21 (day of the month with leading zero)
          mm - 01, 12 (month with leading zero)
           m - 1, 12 (month without leading zero)
         MMM - JAN, DEC
          yy - 19, 20
        yyyy - 2020, 2030
    """
    timeout = 4 
       
    def __init__(self):
        # Centralized clients
        self.connection_pool = get_connection_pool()
        self.client_arch: NSEHttpClient = self.connection_pool.get_client(self.base_url)
        self.client_nse: NSEHttpClient = self.connection_pool.get_client("https://www.nseindia.com")

        self._routes = {
                "bhavcopy": "/content/historical/EQUITIES/{yyyy}/{MMM}/cm{dd}{MMM}{yyyy}bhav.csv.zip",
                "bhavcopy_full": "/products/content/sec_bhavdata_full_{dd}{mm}{yyyy}.csv",
                "bulk_deals": "/content/equities/bulk.csv",
                "bhavcopy_fo": "/content/historical/DERIVATIVES/{yyyy}/{MMM}/fo{dd}{MMM}{yyyy}bhav.csv.zip"
            }
        # Clients handle priming internally; no explicit setup required
        
    def _setup_nse_session(self):
        """Deprecated - retained for compatibility; clients self-prime."""
        return
        
    def get(self, rout, **params):
        """Make API request with automatic retry and session management"""
        path = self._routes[rout].format(**params)
        client_arch = self.connection_pool.get_client(self.base_url)
        self.r = client_arch._request_with_retry("GET", path)
        return self.r
    
    def _get_new_bhavcopy(self, dt):
        """Get bhavcopy using new NSE API (after July 8, 2024)"""
        date_str = dt.strftime('%d-%b-%Y')
        
        url = f"{self.nse_api_url}/reports"
        params = {
            'archives': '[{"name":"CM - Bhavcopy (PR.zip)","type":"archives","category":"capital-market","section":"equities"}]',
            'date': date_str,
            'type': 'Archives'
        }
        
        client_nse = self.connection_pool.get_client("https://www.nseindia.com")
        response = client_nse.get(url, params=params)
        return response
    
    def _get_old_bhavcopy(self, dt):
        """Get bhavcopy using new NSE API (before July 8, 2024)"""
        date_str = dt.strftime('%d-%b-%Y')
        
        url = f"{self.nse_api_url}/reports"
        params = {
            'archives': '[{"name":"CM - Bhavcopy(csv)","type":"archives","category":"capital-market","section":"equities"}]',
            'date': date_str,
            'type': 'Archives'
        }
        
        client_nse = self.connection_pool.get_client("https://www.nseindia.com")
        response = client_nse.get(url, params=params)
        return response

    def _get_new_bhavcopy_fo(self, dt):
        """Get F&O bhavcopy using new NSE API (after July 8, 2024)"""
        date_str = dt.strftime('%d-%b-%Y')
        
        url = f"{self.nse_api_url}/reports"
        params = {
            'archives': '[{"name":"F&O - UDiFF Common Bhavcopy Final (zip)","type":"archives","category":"derivatives","section":"equity"}]',
            'date': date_str,
            'type': 'equity',
            'mode': 'single'
        }

        client_nse = self.connection_pool.get_client("https://www.nseindia.com")
        response = client_nse.get(url, params=params)
        return response
    
    def _get_old_bhavcopy_fo(self, dt):
        """Get F&O bhavcopy using old NSE API (before July 8, 2024)"""
        date_str = dt.strftime('%d-%b-%Y')
        
        url = f"{self.nse_api_url}/reports"
        params = {
            'archives': '[{"name":"F&O - Bhavcopy(csv)","type":"archives","category":"derivatives","section":"equity"}]',
            'date': date_str,
            'type': 'Archives'
        }
        client_nse = self.connection_pool.get_client("https://www.nseindia.com")
        response = client_nse.get(url, params=params)
        return response

    def _handle_bhavcopy_response(self, response):
        """
        Handles the response from a bhavcopy request.
        It may be a JSON response with a download link, or a direct zip file.

        Issues identified:
        - Repeated session creation for file downloads
        - No connection reuse for multiple downloads
        - Error handling could be more specific
        - No retry logic for transient failures
        - Large response content loaded entirely into memory
        """
        # Check for direct file download first by inspecting headers
        content_type = response.headers.get('Content-Type', '')
        if 'zip' in content_type or 'octet-stream' in content_type:
            if response.status_code == 200:
                return response.content
            else:
                raise Exception(f"File download failed with status code {response.status_code}")

        # If not a direct file, try to parse as JSON
        try:
            response_data = response.json()
            if not response_data or len(response_data) == 0:
                raise Exception("Empty response from API")

            if 'file' not in response_data[0]:
                raise Exception("No download link found in API response")

            download_url = response_data[0]['file']

            # Use same session for file download (connection reuse)
            client_nse = self.connection_pool.get_client("https://www.nseindia.com")
            file_response = client_nse._request_with_retry("GET", download_url)
            if file_response.status_code != 200:
                raise Exception(f"File download failed with status code {file_response.status_code}")

            return file_response.content
        except json.JSONDecodeError:
            # If JSON parsing fails, and it wasn't identified as a zip,
            # it might still be a direct download without the right content-type.
            if response.status_code == 200 and response.content:
                 # Heuristic: Check for zip file signature
                if response.content.startswith(b'PK\x03\x04'):
                    return response.content

            # More specific error message
            error_msg = f"Failed to parse JSON response. Content-Type: {content_type}, Status: {response.status_code}"
            if response.text:
                error_msg += f", Response preview: {response.text[:200]}"
            raise Exception(error_msg)


    def bhavcopy_raw(self, dt, as_dataframe=False):
        """Downloads raw bhavcopy text for a specific date

        Uses new NSE API endpoints with date-based format switching.
        - Before July 8, 2024: Uses old CSV format API
        - After July 8, 2024: Uses new ZIP format API with different structure

        Issues identified:
        - Complex nested ZIP processing could be optimized
        - Large files loaded entirely into memory
        - No streaming for large files
        - Repeated file extension checks

        Args:
            dt (date): Date for bhavcopy
            as_dataframe (bool): If True, returns a pandas DataFrame. If False, returns CSV text.
        """
        if dt < self.cutoff_date:
            response = self._get_old_bhavcopy(dt)
        else:
            response = self._get_new_bhavcopy(dt)

        if response.status_code != 200:
            if "file not available" in response.text.lower():
                raise FileNotFoundError(f"Bhavcopy not available for {dt.strftime('%d-%m-%Y')}")
            raise Exception(f"API request failed with status code {response.status_code}: {response.text}")

        try:
            file_content = self._handle_bhavcopy_response(response)

            def extract_csv_from_zip(zip_content):
                """Helper function to extract CSV from potentially nested ZIP files"""
                with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                    # Check for nested ZIP files first
                    nested_zips = [f for f in zf.namelist() if f.lower().endswith('.zip')]

                    if nested_zips:
                        # Handle nested ZIP
                        with zf.open(nested_zips[0]) as nested_file:
                            nested_content = nested_file.read()
                            return extract_csv_from_zip(nested_content)
                    else:
                        # Extract CSV directly
                        csv_files = [f for f in zf.namelist() if f.lower().endswith('.csv')]
                        if not csv_files:
                            raise Exception("No CSV file found in ZIP archive")

                        with zf.open(csv_files[0]) as csv_file:
                            return csv_file.read().decode('utf-8')

            csv_text = extract_csv_from_zip(file_content)

            if as_dataframe:
                return pd.read_csv(StringIO(csv_text))
            return csv_text
        except Exception as e:
            raise Exception(f"Error processing bhavcopy data for {dt.strftime('%d-%m-%Y')}: {str(e)}")
    def bhavcopy_save(self, dt, dest, skip_if_present=True):
        """Downloads and saves raw bhavcopy csv file for a specific date
        
        Uses new NSE API endpoints with automatic fallback to old archives.
        """
        fmt = "cm%d%b%Ybhav.csv"
        fname = os.path.join(dest, dt.strftime(fmt))
        if os.path.isfile(fname) and skip_if_present:
            return fname
        
        # Use new method that handles both old and new formats
        text = self.bhavcopy_raw(dt)
          # Ensure we got string data
        if isinstance(text, bytes):
            text = text.decode('utf-8')
            
        with open(fname, 'w', newline='') as fp:
            fp.write(text)
            return fname
    
    def full_bhavcopy_raw(self, dt):
        """
        Downloads full raw bhavcopy text for a specific date.
        This uses the new API endpoint and works for all dates without a cutoff.
        The endpoint directly returns the CSV content.
        """
        date_str = dt.strftime('%d-%b-%Y')
        url = f"{self.nse_api_url}/reports"
        params = {
            'archives': '[{"name":"Full Bhavcopy and Security Deliverable data","type":"daily-reports","category":"capital-market","section":"equities"}]',
            'date': date_str,
            'type': 'equities',
            'mode': 'single'
        }
        
        client_nse = self.connection_pool.get_client("https://www.nseindia.com")
        response = client_nse.get(url, params=params)
        
        if response.status_code != 200:
            if "file not available" in response.text.lower():
                 raise FileNotFoundError(f"Full Bhavcopy not available for {dt.strftime('%d-%m-%Y')}")
            response.raise_for_status()

        # The response is expected to be the CSV content directly
        return response.text

    def full_bhavcopy_save(self, dt, dest, skip_if_present=True):
        fmt = "sec_bhavdata_full_%d%b%Y.csv"
        fname = os.path.join(dest, dt.strftime(fmt))
        if os.path.isfile(fname) and skip_if_present:
            return fname
        text = self.full_bhavcopy_raw(dt)
        with open(fname, 'w', newline='') as fp:
            fp.write(text)
        return fname

    def bulk_deals_raw(self, from_date: date, to_date: date):
        """
        Downloads bulk deals for a given date range.
        :param from_date: From date
        :param to_date: To date
        :return: JSON response from the API
        """
        from_date_str = from_date.strftime('%d-%m-%Y')
        to_date_str = to_date.strftime('%d-%m-%Y')
        
        url = f"{self.nse_api_url}/historicalOR/bulk-block-short-deals"
        params = {
            'optionType': 'bulk_deals',
            'from': from_date_str,
            'to': to_date_str,
        }
        
        data = self.client_nse.get_json(url, params=params)
        return data
    
    def bulk_deals_save(self, from_date: date, to_date: date, dest: str):
        """
        Saves bulk deals for a given date range to a JSON file.
        :param from_date: From date
        :param to_date: To date
        :param dest: Destination directory
        :return: Path to the saved file
        """
        data = self.bulk_deals_raw(from_date, to_date)
        fname = os.path.join(dest, f"bulk_deals_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.json")
        with open(fname, 'w') as fp:
            json.dump(data, fp)
        return fname

    def bhavcopy_fo_raw(self, dt):
        """Downloads raw F&O bhavcopy text for a specific date"""
        if dt < self.cutoff_date:
            response = self._get_old_bhavcopy_fo(dt)
        else:
            response = self._get_new_bhavcopy_fo(dt)

        if response.status_code != 200:
            if "file not available" in response.text.lower():
                 raise FileNotFoundError(f"F&O Bhavcopy not available for {dt.strftime('%d-%m-%Y')}")
            raise Exception(f"API request failed with status code {response.status_code}: {response.text}")

        try:
            file_content = self._handle_bhavcopy_response(response)
            
            fp = io.BytesIO(file_content)
            with zipfile.ZipFile(file=fp) as zf:
                # F&O bhavcopy is not expected to be nested, but we check anyway
                nested_zip_files = [f for f in zf.namelist() if f.lower().endswith('.zip')]
                
                if nested_zip_files:
                    nested_zip_filename = nested_zip_files[0]
                    with zf.open(nested_zip_filename) as nested_zip_file:
                        nested_zip_content = nested_zip_file.read()
                        nested_fp = io.BytesIO(nested_zip_content)
                        with zipfile.ZipFile(file=nested_fp) as nested_zf:
                            csv_files = [f for f in nested_zf.namelist() if f.lower().endswith('.csv')]
                            if not csv_files:
                                raise Exception("No CSV file found in nested ZIP archive")
                            
                            fname = csv_files[0]
                            with nested_zf.open(fname) as fp_bh:
                                return fp_bh.read().decode('utf-8')
                
                csv_files = [f for f in zf.namelist() if f.lower().endswith('.csv')]
                if not csv_files:
                    raise Exception("No CSV file found in the archive.")
                    
                fname = csv_files[0]
                with zf.open(fname) as fp_bh:
                    return fp_bh.read().decode('utf-8')
        except Exception as e:
            raise Exception(f"Error processing F&O bhavcopy data for {dt.strftime('%d-%m-%Y')}: {str(e)}")

    
    def bhavcopy_fo_save(self, dt, dest, skip_if_present=True):
        """ Saves Derivatives Bhavcopy to a directory """
        fmt = "fo%d%b%Ybhav.csv"
        fname = os.path.join(dest, dt.strftime(fmt))
        if os.path.isfile(fname) and skip_if_present:
            return fname
        text = self.bhavcopy_fo_raw(dt)
        with open(fname, 'w') as fp:
            fp.write(text)
        return fname

class NSEIndicesArchives(NSEArchives):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.niftyindices.com"
        self._routes = { 
                "bhavcopy": "/Daily_Snapshot/ind_close_all_{dd}{mm}{yyyy}.csv"
        }
        self.h = {
        "Host": "www.niftyindices.com",
        "Referer": "https://www.nseindia.com",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
       "Accept": "*/*",
       "Accept-Encoding": "gzip, deflate",
       "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
       "Cache-Control": "no-cache",
       "Connection": "keep-alive",
    }

        # Headers are handled by client; if customization is needed, consider extending NSEHttpClient

    def bhavcopy_index_raw(self, dt):
        """Downloads raw index bhavcopy text for a specific date"""
        dd = dt.strftime('%d')
        mm = dt.strftime('%m').upper()
        yyyy = dt.year
        r = self.get("bhavcopy", yyyy=yyyy, mm=mm, dd=dd)
        return r.text
   
    def bhavcopy_index_save(self, dt, dest, skip_if_present=True):
        """Downloads and saves index bhavcopy csv for a specific date"""
        fmt = "ind_close_all_%d%m%Y.csv"
        fname = os.path.join(dest, dt.strftime(fmt))
        if os.path.isfile(fname) and skip_if_present:
            return fname
        text = self.bhavcopy_index_raw(dt)
        with open(fname, 'w') as fp:
            fp.write(text)
        return fname

class NSEIndices:
    """List of NSE indices"""

    NIFTY_50 = "nifty50"
    NIFTY_100 = "nifty100"
    NIFTY_200 = "nifty200"
    NIFTY_500 = "nifty500"

    NIFTY_NEXT_50 = "niftynext50"

    NIFTY_MIDCAP_50 = "niftymidcap50"
    NIFTY_MIDCAP_100 = "niftymidcap100"
    NIFTY_MIDCAP_150 = "niftymidcap150"

    NIFTY_LARGEMIDCAP_250 = "niftylargemidcap250"
    NIFTY_MIDSMALLCAP_400 = "niftymidsmallcap400"

    NIFTY_SMALLCAP_50 = "niftysmallcap50"
    NIFTY_SMALLCAP_100 = "niftysmallcap100"
    NIFTY_SMALLCAP_250 = "niftysmallcap250"

    NIFTY_MICROCAP_250 = "niftymicrocap250_"
    NIFTY_MIDCAP_SELECT = "niftymidcapselect_"
    NIFTY_TOTALMARKET = "niftytotalmarket_"

    NIFTY_500_LARGEMIDSMALL_EQUALCAP_WEIGHTED = "nifty500LargeMidSmallEqualCapWeighted_"
    NIFTY_500_MULTICAP_502525 = "nifty500Multicap502525_"

    @classmethod
    def get_indices_without_underscores(cls):
        """Returns a list of indices without underscores"""
        return [v for k, v in vars(cls).items() if (isinstance(v, str) and
            v.startswith("nifty") and not v.startswith("__") and not v.endswith("_"))]

    @classmethod
    def get_indices_with_underscores(cls):
        """Returns a list of indices with underscores"""
        return [v for k, v in vars(cls).items() if (isinstance(v, str) and
            v.startswith("nifty") and not v.startswith("__") and v.endswith("_"))]

class NSEIndexConstituents(NSEArchives):
    """NSE Index constituents
    https://niftyindices.com/indices/equity/broad-based-indices/NIFTY--50
    Index constituent link
    https://niftyindices.com/IndexConstituent/ind_nifty50list.csv
    Args:
        NSEArchives (class): Base class
    """

    def __init__(self):
        super().__init__()

        self.base_url = "https://www.niftyindices.com"
        self._routes = self._build_routes()
        self.h = {
          "Host": "www.niftyindices.com",
          "Referer": "https://www.nseindia.com",
          "X-Requested-With": "XMLHttpRequest",
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
          "Accept": "*/*",
          "Accept-Encoding": "gzip, deflate",
          "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        }

        # Switch client to niftyindices host
        self.client_arch = self.connection_pool.get_client(self.base_url)

    def _build_routes(self) -> dict:
        routes = {}

        index_types = NSEIndices.get_indices_without_underscores(
          ) + NSEIndices.get_indices_with_underscores()
        for index_type in index_types:
            routes[index_type] = f"/IndexConstituent/{self._index_file_name(index_type)}"

        return routes

    def _index_file_name(self, index_type: str) -> str:
        index_types = NSEIndices.get_indices_without_underscores(
          ) + NSEIndices.get_indices_with_underscores()
        if index_type in index_types:
            return f"ind_{index_type}list.csv"

        raise ValueError(f"Invalid index type: {index_type}")

    def index_constituent_raw(self, index_type=str):
        """Downloads raw index constituent text for a specific index"""
        r = self.get(index_type)
        return r.text

    def index_constituent_save(self, index_type:str, dest, skip_if_present=True):
        """Downloads and saves index constituent csv for a specific index"""
        fname = self._index_file_name(index_type)
        fpath = os.path.join(dest, fname)
        if os.path.isfile(fpath) and skip_if_present:
            return fpath
        text = self.index_constituent_raw(index_type)
        with open(fpath, 'w') as fp:
            fp.write(text)

        return fpath

    def index_constituent_save_all(self, dest, skip_if_present=True):
        """Downloads and saves index constituent csv for all known indexes"""
        fpaths = []

        index_types = NSEIndices.get_indices_without_underscores(
            ) + NSEIndices.get_indices_with_underscores()
        for index_type in index_types:
            fpath = self.index_constituent_save(index_type, dest, skip_if_present)
            fpaths.append(fpath)

        return fpaths


a = NSEArchives()
bhavcopy_raw = a.bhavcopy_raw
bhavcopy_save = a.bhavcopy_save
full_bhavcopy_raw = a.full_bhavcopy_raw
full_bhavcopy_save = a.full_bhavcopy_save
bulk_deals_raw = a.bulk_deals_raw
bulk_deals_save = a.bulk_deals_save
bhavcopy_fo_raw = a.bhavcopy_fo_raw
bhavcopy_fo_save = a.bhavcopy_fo_save
ia = NSEIndicesArchives()
bhavcopy_index_raw = ia.bhavcopy_index_raw
bhavcopy_index_save = ia.bhavcopy_index_save

ic = NSEIndexConstituents()
index_constituent_raw = ic.index_constituent_raw
index_constituent_save = ic.index_constituent_save
index_constituent_save_all = ic.index_constituent_save_all


def expiry_dates(
    dt: date,
    instrument_type: str = "",
    symbol: str = "",
    contracts: int = 0,
    months_ahead: int = 6
) -> list:
    """
    Algorithmically calculate expiry dates based on NSE rules.
    
    Args:
        dt: Reference date for calculation
        instrument_type: Type of derivative instrument (e.g., "FUTIDX", "OPTIDX", "FUTSTK", "OPTSTK")
        symbol: Symbol name (used to determine contract cycle)
        contracts: Minimum open interest filter (deprecated in algorithmic approach)
        months_ahead: Number of months ahead to calculate expiries for
        
    Returns:
        List of expiry dates
    """
    from ..holidays import holidays
    import calendar
    
    def is_trading_day(date_obj):
        """Check if a date is a trading day (not weekend or holiday)"""
        # Skip weekends
        if date_obj.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        # Skip holidays
        year_holidays = holidays(year=date_obj.year)
        return date_obj not in year_holidays
    
    def get_expiry_weekday(trade_date):
        """Determine expiry weekday based on NSE policy calendar"""
        # Policy transition dates
        thursday_cutoff = date(2025, 4, 4)
        monday_cutoff = date(2025, 8, 29)
        
        if trade_date < thursday_cutoff:
            return 3  # Thursday (0=Monday, 1=Tuesday, ..., 6=Sunday)
        elif trade_date < monday_cutoff:
            return 0  # Monday
        else:
            return 1  # Tuesday
    
    def adjust_for_trading_day(candidate_date):
        """Adjust date to previous trading day if not a trading day"""
        while not is_trading_day(candidate_date):
            candidate_date = date(candidate_date.year, candidate_date.month, candidate_date.day - 1)
        return candidate_date
    
    def get_monthly_expiry(year, month, expiry_weekday):
        """Get the last occurrence of expiry_weekday in the given month"""
        # Get last day of month
        last_day = calendar.monthrange(year, month)[1]
        last_date = date(year, month, last_day)
        
        # Find the last occurrence of the target weekday
        days_back = (last_date.weekday() - expiry_weekday) % 7
        candidate = date(year, month, last_day - days_back)
        
        return adjust_for_trading_day(candidate)
    
    def get_weekly_expiry(year, month, week_number, expiry_weekday):
        """Get weekly expiry for a specific week in the month"""
        from datetime import timedelta
        
        # Find first occurrence of expiry_weekday in the month
        first_day = date(year, month, 1)
        days_ahead = (expiry_weekday - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_ahead)
        
        # Add weeks to get to the target week
        target_date = first_occurrence + timedelta(weeks=(week_number - 1))
        
        # Make sure we're still in the same month
        if target_date.month != month:
            return None
            
        return adjust_for_trading_day(target_date)
    
    def determine_contract_cycle(instrument_type, symbol):
        """Determine if symbol has weekly, monthly, quarterly, or half-yearly expiries"""
        # Major indices typically have weekly expiries
        weekly_symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
        
        # Bank Nifty and Nifty have weekly expiries
        if any(weekly_symbol in (symbol or '').upper() for weekly_symbol in weekly_symbols):
            return 'weekly'
        
        # Some special contracts might have quarterly expiries (Mar, Jun, Sep, Dec)
        quarterly_symbols = []  # Add symbols that have quarterly expiries if needed
        if symbol and symbol.upper() in quarterly_symbols:
            return 'quarterly'
        
        # Some contracts might have half-yearly expiries (Jun, Dec)
        half_yearly_symbols = []  # Add symbols that have half-yearly expiries if needed
        if symbol and symbol.upper() in half_yearly_symbols:
            return 'half_yearly'
        
        # Most stocks have monthly expiries
        if instrument_type and ('STK' in instrument_type.upper()):
            return 'monthly'
            
        # Default to monthly for unknown cases
        return 'monthly'
    
    expiry_weekday = get_expiry_weekday(dt)
    contract_cycle = determine_contract_cycle(instrument_type, symbol)
    expiries = []
    
    # Generate expiries for the specified months ahead
    current_month = dt.month
    current_year = dt.year
    
    for i in range(months_ahead):
        target_month = current_month + i
        target_year = current_year
        
        # Handle year rollover
        while target_month > 12:
            target_month -= 12
            target_year += 1
        
        if contract_cycle == 'weekly':
            # Generate weekly expiries for the month
            for week in range(1, 6):  # Up to 5 weeks in a month
                weekly_expiry = get_weekly_expiry(target_year, target_month, week, expiry_weekday)
                if weekly_expiry and weekly_expiry >= dt:
                    expiries.append(weekly_expiry)
        elif contract_cycle == 'quarterly':
            # Quarterly expiries (March, June, September, December)
            if target_month in [3, 6, 9, 12]:
                quarterly_expiry = get_monthly_expiry(target_year, target_month, expiry_weekday)
                if quarterly_expiry >= dt:
                    expiries.append(quarterly_expiry)
        elif contract_cycle == 'half_yearly':
            # Half-yearly expiries (June, December)
            if target_month in [6, 12]:
                half_yearly_expiry = get_monthly_expiry(target_year, target_month, expiry_weekday)
                if half_yearly_expiry >= dt:
                    expiries.append(half_yearly_expiry)
        else:
            # Monthly expiry (last occurrence of expiry weekday in month)
            monthly_expiry = get_monthly_expiry(target_year, target_month, expiry_weekday)
            if monthly_expiry >= dt:
                expiries.append(monthly_expiry)
    
    # Sort and remove duplicates
    expiries = sorted(list(set(expiries)))
    
    return expiries



if __name__ == "__main__":

    url = "https://www.niftyindices.com/Daily_Snapshot/ind_close_all_20082020.csv"
    headers = {
        "Host": "www.niftyindices.com",
        "Referer": "https://www.nseindia.com",
       "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36",
       "Accept": "*/*",
       "Accept-Encoding": "gzip, deflate",
       "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
       "Cache-Control": "no-cache",
       "Connection": "keep-alive",
       }
    d = requests.get(url, stream=True, timeout=10, headers=headers, verify=False)
    for chunk in d.iter_content(chunk_size=1024):
        print("Received")
        print(len(chunk))


