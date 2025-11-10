"""
    Implements live data fetch functionality
"""
from datetime import datetime
from ..util import live_cache
from .connection_pool import get_connection_pool
from .http_client import NSEHttpClient

class NSELive:
    time_out = 5
    base_url = "https://www.nseindia.com/api"
    page_url = "https://www.nseindia.com/get-quotes/equity?symbol=LT"
    _routes = {
            "stock_meta": "/equity-meta-info",
            "stock_quote": "/quote-equity",
            "stock_derivative_quote": "/quote-derivative",
            "market_status": "/marketStatus",
            "chart_data": "/chart-databyindex",
            "market_turnover": "/market-turnover",
            "equity_derivative_turnover": "/equity-stock",
            "all_indices": "/allIndices",
            "live_index": "/equity-stockIndices",
            "index_option_chain": "/option-chain-indices",
            "equity_option_chain": "/option-chain-equities",
            "currency_option_chain": "/option-chain-currency",
            "pre_open_market": "/market-data-pre-open",
            "holiday_list": "/holiday-master?type=trading",
            "corporate_announcements": "/corporate-announcements"
    }
    
    def __init__(self):
        """Initialize NSELive with centralized HTTP client"""
        self.connection_pool = get_connection_pool()
        # http client is keyed by host, not path
        self.client: NSEHttpClient = self.connection_pool.get_client("https://www.nseindia.com")

    def get(self, route, payload={}):
        """Make API request using centralized client with retries and validation"""
        path = "/api" + self._routes[route]
        return self.client.get_json(path, params=payload)

    @live_cache
    def stock_quote(self, symbol):
        data = {"symbol": symbol}
        return self.get("stock_quote", data) 

    @live_cache
    def stock_quote_fno(self, symbol):
        data = {"symbol": symbol}
        return self.get("stock_derivative_quote", data)

    @live_cache
    def trade_info(self, symbol):
        data = {"symbol": symbol, "section": "trade_info"}
        return self.get("stock_quote", data) 

    @live_cache
    def market_status(self):
        return self.get("market_status", {})

    @live_cache
    def chart_data(self, symbol, indices=False):
        data = {"index" : symbol + "EQN"}
        if indices:
            data["index"] = symbol
            data["indices"] = "true"
        return self.get("chart_data", data)
    
    @live_cache
    def tick_data(self, symbol, indices=False):
        return self.chart_data(symbol, indices)

    @live_cache
    def market_turnover(self):
        return self.get("market_turnover")

    @live_cache
    def eq_derivative_turnover(self, type="allcontracts"):
        data = {"index": type}
        return self.get("equity_derivative_turnover", data)
    
    @live_cache
    def all_indices(self):
        return self.get("all_indices")

    def live_index(self, symbol="NIFTY 50"):
        data = {"index" : symbol}
        return self.get("live_index", data)
    
    @live_cache
    def index_option_chain(self, symbol="NIFTY"):
        data = {"symbol": symbol}
        return self.get("index_option_chain", data)

    @live_cache
    def equities_option_chain(self, symbol):
        data = {"symbol": symbol}
        return self.get("equity_option_chain", data)

    @live_cache
    def currency_option_chain(self, symbol="USDINR"):
        data = {"symbol": symbol}
        return self.get("currency_option_chain", data)

    @live_cache
    def live_fno(self):
        return self.live_index("SECURITIES IN F&O")
    
    @live_cache
    def pre_open_market(self, key="NIFTY"):
        data = {"key": key}
        return self.get("pre_open_market", data)
    
    @live_cache
    def holiday_list(self):
        return self.get("holiday_list", {})

    def corporate_announcements(self, segment='equities', from_date=None, to_date=None, symbol=None):
        """
            This function returns the corporate annoucements 
            (https://www.nseindia.com/companies-listing/corporate-filings-announcements)
        """

        #from_date: 02-12-2024
        #to_date: 06-12-2024
        #symbol: 
        payload = {"index": segment}

        if from_date and to_date:
            payload['from_date'] = from_date.strftime("%d-%m-%Y")
            payload['to_date']   = to_date.strftime("%d-%m-%Y")
        elif from_date or to_date:
            raise Exception("Please provide both from_date and to_date")
        if symbol:
            payload['symbol'] = symbol
        return self.get("corporate_announcements", payload)
    
    def bulk_equities_option_chain(self, symbols, max_workers=3):
        """
        Fetch option chains for multiple equity symbols concurrently.
        
        Args:
            symbols (list): List of equity symbols
            max_workers (int): Maximum number of concurrent requests
            
        Returns:
            dict: Dictionary with symbol as key and option chain data as value
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        def fetch_single_option_chain(symbol):
            try:
                result = self.equities_option_chain(symbol)
                return symbol, result, None
            except Exception as e:
                return symbol, None, str(e)
        
        results = {}
        errors = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {executor.submit(fetch_single_option_chain, symbol): symbol 
                              for symbol in symbols}
            
            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                symbol, data, error = future.result()
                if error:
                    errors[symbol] = error
                else:
                    results[symbol] = data
                
                # Small delay to be respectful to the API
                time.sleep(0.1)
        
        return {
            'success': results,
            'errors': errors,
            'summary': {
                'total_requested': len(symbols),
                'successful': len(results),
                'failed': len(errors)
            }
        }
    
    def get_options_around_date(self, symbol, target_date, days_before=5, days_after=5):
        """
        Get option chain data and analyze it in context of a target date (like earnings).
        
        Args:
            symbol (str): Equity symbol
            target_date (date): Target date (e.g., earnings date)
            days_before (int): Days before target date to consider
            days_after (int): Days after target date to consider
            
        Returns:
            dict: Analysis of options around the target date
        """
        from datetime import timedelta
        
        try:
            # Get current option chain
            option_data = self.equities_option_chain(symbol)
            
            if not option_data or 'records' not in option_data:
                return {'error': 'No option data available'}
            
            records = option_data['records']
            
            # Parse expiry dates and find relevant ones
            relevant_expiries = []
            if 'expiryDates' in records:
                from datetime import datetime
                for expiry_str in records['expiryDates']:
                    try:
                        expiry_date = datetime.strptime(expiry_str, '%d-%b-%Y').date()
                        days_from_target = (expiry_date - target_date).days
                        
                        # Include expiries that are after the target date within our window
                        if days_from_target >= -days_before and days_from_target <= 45:  # Include up to 45 days out
                            relevant_expiries.append({
                                'date': expiry_date,
                                'date_str': expiry_str,
                                'days_from_target': days_from_target
                            })
                    except ValueError:
                        continue
            
            # Find the most relevant expiry (first one after target date)
            primary_expiry = None
            for exp in sorted(relevant_expiries, key=lambda x: x['days_from_target']):
                if exp['days_from_target'] >= 0:
                    primary_expiry = exp
                    break
            
            return {
                'symbol': symbol,
                'target_date': target_date,
                'option_data': option_data,
                'relevant_expiries': relevant_expiries,
                'primary_expiry': primary_expiry,
                'analysis': {
                    'total_strikes': len(records.get('data', [])),
                    'expiries_count': len(relevant_expiries),
                    'has_weekly_options': len(records.get('expiryDates', [])) > 4
                }
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_earnings_options(self, symbols_and_dates, max_workers=3):
        """
        Analyze option chains for multiple stocks around their earnings dates.
        
        Args:
            symbols_and_dates (list): List of tuples (symbol, earnings_date)
            max_workers (int): Maximum concurrent requests
            
        Returns:
            dict: Analysis results for each symbol
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def analyze_single_stock(symbol_date_tuple):
            symbol, earnings_date = symbol_date_tuple
            return symbol, self.get_options_around_date(symbol, earnings_date)
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {executor.submit(analyze_single_stock, item): item[0] 
                              for item in symbols_and_dates}
            
            for future in as_completed(future_to_symbol):
                symbol, analysis = future.result()
                results[symbol] = analysis
        
        return results

