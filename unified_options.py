"""
Unified Options Interface for aynse library

This module provides a unified interface for fetching option data,
addressing the gaps identified in the options capabilities analysis:

1. Unified method to fetch both live and historical option data
2. Convenient method to fetch option data around earnings dates  
3. Automatic expiry date selection based on trade date
4. Bulk fetching capabilities for multiple symbols
5. Enhanced error handling and data validation
"""

import sys
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Union, Tuple
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import warnings

# Add project root to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from aynse.nse.live import NSELive
from aynse.nse.history import derivatives_raw, derivatives_df
from aynse.nse.archives import expiry_dates


class UnifiedOptionsInterface:
    """
    Unified interface for fetching option data from NSE.
    
    Provides simplified methods for common option data fetching scenarios,
    automatic expiry date selection, and bulk processing capabilities.
    """
    
    def __init__(self):
        """Initialize the unified options interface."""
        self.live_client = None
        self._initialize_live_client()
        
    def _initialize_live_client(self):
        """Initialize NSE Live client with error handling."""
        try:
            self.live_client = NSELive()
        except Exception as e:
            warnings.warn(f"Failed to initialize NSE Live client: {e}")
            self.live_client = None
            
    def get_option_data(self, 
                       symbol: str,
                       start_date: Optional[date] = None,
                       end_date: Optional[date] = None,
                       expiry_date: Optional[date] = None,
                       instrument_type: str = 'OPTSTK',
                       strike_price: Optional[float] = None,
                       option_type: Optional[str] = None,
                       auto_expiry: bool = True) -> Dict:
        """
        Unified method to fetch option data (live or historical).
        
        Automatically determines whether to fetch live or historical data
        based on the date parameters provided.
        
        Args:
            symbol: Stock/Index symbol (e.g., 'RELIANCE', 'NIFTY')
            start_date: Start date for historical data (if None, fetches live data)
            end_date: End date for historical data
            expiry_date: Specific expiry date (if None and auto_expiry=True, selects automatically)
            instrument_type: 'OPTSTK', 'OPTIDX', 'FUTSTK', 'FUTIDX'
            strike_price: Strike price for options
            option_type: 'CE' or 'PE' for options
            auto_expiry: Automatically select appropriate expiry date
            
        Returns:
            Dictionary containing option data
        """
        
        # Validate parameters
        self._validate_parameters(symbol, instrument_type, strike_price, option_type)
        
        # Determine if this is a live or historical request
        if start_date is None:
            return self._get_live_option_data(symbol, instrument_type)
        else:
            # Historical data request
            if end_date is None:
                end_date = start_date
                
            # Auto-select expiry date if not provided
            if expiry_date is None and auto_expiry:
                expiry_date = self._select_appropriate_expiry(start_date, instrument_type, symbol)
                
            if expiry_date is None:
                raise ValueError("Expiry date required for historical options data")
                
            return self._get_historical_option_data(
                symbol, start_date, end_date, expiry_date, 
                instrument_type, strike_price, option_type
            )
            
    def get_earnings_options(self,
                           symbol: str,
                           earnings_dates: List[date],
                           days_before: int = 30,
                           days_after: int = 7,
                           strike_range: Optional[List[float]] = None,
                           option_types: List[str] = ['CE', 'PE']) -> Dict:
        """
        Fetch option data around earnings dates.
        
        Args:
            symbol: Stock symbol
            earnings_dates: List of earnings announcement dates
            days_before: Days before earnings to start data collection
            days_after: Days after earnings to end data collection  
            strike_range: List of strike prices to fetch (if None, uses default range)
            option_types: List of option types to fetch ('CE', 'PE')
            
        Returns:
            Dictionary with earnings dates as keys and option data as values
        """
        
        results = {}
        
        for earnings_date in earnings_dates:
            print(f"Processing earnings date: {earnings_date}")
            
            # Calculate date range around earnings
            start_date = earnings_date - timedelta(days=days_before)
            end_date = earnings_date + timedelta(days=days_after)
            
            # Find appropriate expiry date
            expiry_date = self._select_appropriate_expiry(earnings_date, 'OPTSTK', symbol)
            
            if expiry_date is None:
                warnings.warn(f"No appropriate expiry found for {symbol} earnings on {earnings_date}")
                continue
                
            # Generate strike prices if not provided
            if strike_range is None:
                strike_range = self._generate_strike_range(symbol)
                
            # Fetch option data for each strike and type
            earnings_data = {
                'earnings_date': earnings_date,
                'expiry_date': expiry_date,
                'data_period': (start_date, end_date),
                'options': {}
            }
            
            for strike in strike_range:
                for option_type in option_types:
                    key = f"{strike}_{option_type}"
                    
                    try:
                        option_data = self.get_option_data(
                            symbol=symbol,
                            start_date=start_date,
                            end_date=end_date,
                            expiry_date=expiry_date,
                            instrument_type='OPTSTK',
                            strike_price=strike,
                            option_type=option_type
                        )
                        
                        earnings_data['options'][key] = option_data
                        
                    except Exception as e:
                        warnings.warn(f"Failed to fetch {key} for {symbol}: {e}")
                        
            results[earnings_date] = earnings_data
            
        return results
        
    def bulk_fetch_options(self,
                          symbols: List[str],
                          start_date: date,
                          end_date: date,
                          instrument_type: str = 'OPTSTK',
                          strike_prices: Optional[List[float]] = None,
                          option_types: List[str] = ['CE', 'PE'],
                          max_workers: int = 5) -> Dict:
        """
        Bulk fetch option data for multiple symbols.
        
        Args:
            symbols: List of symbols to fetch
            start_date: Start date for historical data
            end_date: End date for historical data
            instrument_type: Instrument type
            strike_prices: List of strike prices (if None, generates default)
            option_types: List of option types
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary with symbols as keys and option data as values
        """
        
        results = {}
        
        # Generate tasks for parallel processing
        tasks = []
        
        for symbol in symbols:
            # Auto-select expiry date for each symbol
            expiry_date = self._select_appropriate_expiry(start_date, instrument_type, symbol)
            
            if expiry_date is None:
                warnings.warn(f"No appropriate expiry found for {symbol}")
                continue
                
            # Generate strike prices if not provided
            if strike_prices is None:
                symbol_strikes = self._generate_strike_range(symbol)
            else:
                symbol_strikes = strike_prices
                
            # Create tasks for each combination
            for strike in symbol_strikes:
                for option_type in option_types:
                    if 'OPT' in instrument_type:  # Only add option type for options
                        task = (symbol, start_date, end_date, expiry_date, 
                               instrument_type, strike, option_type)
                        tasks.append(task)
                    else:  # Futures don't need strike/option_type
                        task = (symbol, start_date, end_date, expiry_date,
                               instrument_type, None, None)
                        tasks.append(task)
                        break  # Only one task needed for futures
                        
        # Execute tasks in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(self._fetch_single_option, *task): task 
                for task in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                symbol = task[0]
                
                try:
                    data = future.result()
                    
                    if symbol not in results:
                        results[symbol] = {}
                        
                    # Create key for this option
                    if task[5] is not None and task[6] is not None:  # Has strike and option_type
                        key = f"{task[5]}_{task[6]}"
                    else:
                        key = instrument_type
                        
                    results[symbol][key] = data
                    
                except Exception as e:
                    warnings.warn(f"Failed to fetch data for {task}: {e}")
                    
        return results
        
    def _get_live_option_data(self, symbol: str, instrument_type: str) -> Dict:
        """Fetch live option data."""
        
        if self.live_client is None:
            raise ConnectionError("NSE Live client not available")
            
        if instrument_type in ['OPTSTK']:
            return self.live_client.equities_option_chain(symbol)
        elif instrument_type in ['OPTIDX']:
            return self.live_client.index_option_chain(symbol)
        else:
            raise ValueError(f"Live data not available for instrument type: {instrument_type}")
            
    def _get_historical_option_data(self, 
                                   symbol: str,
                                   start_date: date,
                                   end_date: date,
                                   expiry_date: date,
                                   instrument_type: str,
                                   strike_price: Optional[float],
                                   option_type: Optional[str]) -> Dict:
        """Fetch historical option data."""
        
        raw_data = derivatives_raw(
            symbol=symbol,
            from_date=start_date,
            to_date=end_date,
            expiry_date=expiry_date,
            instrument_type=instrument_type,
            strike_price=strike_price,
            option_type=option_type
        )
        
        return {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'expiry_date': expiry_date,
            'instrument_type': instrument_type,
            'strike_price': strike_price,
            'option_type': option_type,
            'data': raw_data,
            'record_count': len(raw_data) if raw_data else 0
        }
        
    def _fetch_single_option(self, *args) -> Dict:
        """Fetch single option data for parallel processing."""
        return self._get_historical_option_data(*args)
        
    def _select_appropriate_expiry(self, 
                                 reference_date: date,
                                 instrument_type: str,
                                 symbol: str) -> Optional[date]:
        """
        Select appropriate expiry date based on reference date.
        
        For earnings analysis, selects the expiry closest to but after the reference date.
        """
        
        try:
            expiries = expiry_dates(reference_date, instrument_type, symbol, months_ahead=3)
            
            # Find the first expiry on or after the reference date
            for expiry in expiries:
                if expiry >= reference_date:
                    return expiry
                    
            return None
            
        except Exception as e:
            warnings.warn(f"Failed to calculate expiry dates for {symbol}: {e}")
            return None
            
    def _generate_strike_range(self, symbol: str) -> List[float]:
        """
        Generate reasonable strike price range for a symbol.
        
        In a production system, this would use current market price.
        For now, uses common ranges for major stocks.
        """
        
        # Default strike ranges for major stocks (approximate)
        default_ranges = {
            'RELIANCE': [2600, 2700, 2800, 2900, 3000],
            'TCS': [3000, 3200, 3400, 3600, 3800],
            'HDFCBANK': [1400, 1500, 1600, 1700, 1800],
            'INFOSYS': [1400, 1500, 1600, 1700, 1800],
            'ITC': [400, 450, 500, 550, 600],
            'NIFTY': [20000, 21000, 22000, 23000, 24000]
        }
        
        return default_ranges.get(symbol.upper(), [2800, 3000, 3200])  # Default range
        
    def _validate_parameters(self,
                           symbol: str,
                           instrument_type: str,
                           strike_price: Optional[float],
                           option_type: Optional[str]):
        """Validate input parameters."""
        
        if not symbol:
            raise ValueError("Symbol is required")
            
        valid_instruments = ['OPTIDX', 'OPTSTK', 'FUTIDX', 'FUTSTK']
        if instrument_type not in valid_instruments:
            raise ValueError(f"Invalid instrument type. Must be one of: {valid_instruments}")
            
        # For options, validate strike price and option type
        if 'OPT' in instrument_type:
            if strike_price is None:
                raise ValueError("Strike price is required for options")
            if option_type not in ['CE', 'PE']:
                raise ValueError("Option type must be 'CE' or 'PE'")
                
    def get_option_chain_analysis(self, 
                                symbol: str,
                                analysis_date: date = None) -> Dict:
        """
        Get comprehensive option chain analysis for a symbol.
        
        Args:
            symbol: Symbol to analyze
            analysis_date: Date for analysis (if None, uses current date)
            
        Returns:
            Dictionary with option chain analysis
        """
        
        if analysis_date is None:
            analysis_date = date.today()
            
        try:
            # Get live option chain if available
            if symbol in ['RELIANCE', 'TCS', 'HDFCBANK']:  # Major stocks
                live_data = self.get_option_data(symbol, instrument_type='OPTSTK')
            else:
                live_data = self.get_option_data(symbol, instrument_type='OPTIDX')
                
            analysis = {
                'symbol': symbol,
                'analysis_date': analysis_date,
                'live_data_available': True,
                'live_data': live_data
            }
            
        except Exception as e:
            analysis = {
                'symbol': symbol,
                'analysis_date': analysis_date,
                'live_data_available': False,
                'error': str(e)
            }
            
        # Add expiry dates analysis
        try:
            if symbol in ['NIFTY', 'BANKNIFTY']:
                expiries = expiry_dates(analysis_date, 'OPTIDX', symbol)
            else:
                expiries = expiry_dates(analysis_date, 'OPTSTK', symbol)
                
            analysis['expiry_analysis'] = {
                'total_expiries': len(expiries),
                'next_expiry': expiries[0] if expiries else None,
                'near_term_expiries': expiries[:5] if expiries else [],
                'expiry_type': 'weekly' if len(expiries) > 10 else 'monthly'
            }
            
        except Exception as e:
            analysis['expiry_analysis'] = {'error': str(e)}
            
        return analysis


# Sample earnings dates for major Indian companies (for demonstration)
SAMPLE_EARNINGS_DATES = {
    'RELIANCE': [
        date(2023, 7, 20),   # Q1 FY24
        date(2023, 10, 25),  # Q2 FY24  
        date(2024, 1, 19),   # Q3 FY24
        date(2024, 4, 18),   # Q4 FY24
        date(2024, 7, 18),   # Q1 FY25
    ],
    'TCS': [
        date(2023, 7, 12),   # Q1 FY24
        date(2023, 10, 11),  # Q2 FY24
        date(2024, 1, 10),   # Q3 FY24
        date(2024, 4, 10),   # Q4 FY24
        date(2024, 7, 10),   # Q1 FY25
    ],
    'HDFCBANK': [
        date(2023, 7, 15),   # Q1 FY24
        date(2023, 10, 14),  # Q2 FY24
        date(2024, 1, 13),   # Q3 FY24
        date(2024, 4, 13),   # Q4 FY24
        date(2024, 7, 13),   # Q1 FY25
    ]
}


def demo_unified_interface():
    """Demonstrate the unified options interface."""
    
    print("🚀 Demonstrating Unified Options Interface")
    print("=" * 60)
    
    # Initialize interface
    options_api = UnifiedOptionsInterface()
    
    # Demo 1: Get live option data
    print("\n1. Live Option Data (would fail due to network in sandbox):")
    try:
        live_data = options_api.get_option_data('RELIANCE', instrument_type='OPTSTK')
        print(f"   ✓ Live data fetched for RELIANCE")
    except Exception as e:
        print(f"   ✗ Live data failed (expected in sandbox): {e}")
        
    # Demo 2: Get historical option data with auto-expiry
    print("\n2. Historical Option Data with Auto-Expiry:")
    try:
        historical_data = options_api.get_option_data(
            symbol='RELIANCE',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            instrument_type='OPTSTK',
            strike_price=2800.0,
            option_type='CE',
            auto_expiry=True
        )
        print(f"   ✓ Historical data structure created for RELIANCE")
        print(f"   ✓ Expiry auto-selected: {historical_data.get('expiry_date')}")
    except Exception as e:
        print(f"   ✗ Historical data failed (expected without network): {e}")
        
    # Demo 3: Earnings options analysis
    print("\n3. Earnings Options Analysis:")
    earnings_dates = SAMPLE_EARNINGS_DATES.get('RELIANCE', [])[:2]  # First 2 dates
    
    try:
        earnings_analysis = options_api.get_earnings_options(
            symbol='RELIANCE',
            earnings_dates=earnings_dates,
            strike_range=[2700, 2800, 2900]
        )
        print(f"   ✓ Earnings analysis structure created")
        print(f"   ✓ Processed {len(earnings_analysis)} earnings dates")
        
        for earnings_date, data in earnings_analysis.items():
            print(f"     - {earnings_date}: expiry {data.get('expiry_date')}")
            
    except Exception as e:
        print(f"   ✗ Earnings analysis failed: {e}")
        
    # Demo 4: Bulk fetching
    print("\n4. Bulk Options Fetching:")
    try:
        bulk_data = options_api.bulk_fetch_options(
            symbols=['RELIANCE', 'TCS'],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 20),
            strike_prices=[2800],
            option_types=['CE'],
            max_workers=2
        )
        print(f"   ✓ Bulk fetch structure created")
        print(f"   ✓ Processed {len(bulk_data)} symbols")
        
    except Exception as e:
        print(f"   ✗ Bulk fetch failed: {e}")
        
    # Demo 5: Option chain analysis
    print("\n5. Option Chain Analysis:")
    try:
        analysis = options_api.get_option_chain_analysis('RELIANCE')
        print(f"   ✓ Option chain analysis completed")
        
        if 'expiry_analysis' in analysis:
            exp_analysis = analysis['expiry_analysis']
            print(f"     - Total expiries: {exp_analysis.get('total_expiries', 'N/A')}")
            print(f"     - Next expiry: {exp_analysis.get('next_expiry', 'N/A')}")
            print(f"     - Expiry type: {exp_analysis.get('expiry_type', 'N/A')}")
            
    except Exception as e:
        print(f"   ✗ Option chain analysis failed: {e}")
        
    print("\n" + "=" * 60)
    print("✅ Unified Options Interface demonstration complete!")
    print("\nKey Features Demonstrated:")
    print("• Automatic live vs historical data detection")
    print("• Auto-expiry date selection") 
    print("• Earnings-focused option data fetching")
    print("• Bulk processing with parallel execution")
    print("• Comprehensive option chain analysis")
    print("• Enhanced error handling and validation")


if __name__ == "__main__":
    demo_unified_interface()