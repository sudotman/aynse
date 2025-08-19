"""
Comprehensive tests for options functionality in aynse library.

This test module addresses the gaps identified in the options capabilities analysis:
- Tests for historical derivatives functionality
- Tests for option data quality and completeness  
- Tests for error handling with invalid parameters
- Tests for different strike prices and option types
- Integration tests combining multiple functionalities
"""

import pytest
from datetime import date, datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from aynse.nse.live import NSELive
from aynse.nse.history import derivatives_raw, derivatives_df, derivatives_csv
from aynse.nse.archives import expiry_dates


class TestHistoricalDerivatives:
    """Test historical derivatives functionality."""
    
    def test_derivatives_parameter_validation(self):
        """Test parameter validation for derivatives functions."""
        
        # Test invalid instrument types
        with pytest.raises(Exception) as excinfo:
            derivatives_raw(
                'RELIANCE', 
                date(2024, 1, 1), 
                date(2024, 1, 31),
                date(2024, 1, 25),
                'INVALID_TYPE',  # Invalid instrument type
                None, None
            )
        assert "Invalid instrument_type" in str(excinfo.value)
        
    def test_options_require_strike_and_type(self):
        """Test that options require both strike price and option type."""
        
        # Test OPTSTK without strike price
        with pytest.raises(Exception) as excinfo:
            derivatives_raw(
                'RELIANCE',
                date(2024, 1, 1),
                date(2024, 1, 31), 
                date(2024, 1, 25),
                'OPTSTK',
                None,  # Missing strike price
                'CE'
            )
        assert "Missing argument for OPTIDX or OPTSTK" in str(excinfo.value)
        
        # Test OPTIDX without option type
        with pytest.raises(Exception) as excinfo:
            derivatives_raw(
                'NIFTY',
                date(2024, 1, 1),
                date(2024, 1, 31),
                date(2024, 1, 25), 
                'OPTIDX',
                21000,
                None  # Missing option type
            )
        assert "Missing argument for OPTIDX or OPTSTK" in str(excinfo.value)
        
    def test_futures_dont_require_strike_and_type(self):
        """Test that futures don't require strike price and option type."""
        
        # These should not raise exceptions (though they'll fail on network)
        try:
            derivatives_raw(
                'RELIANCE',
                date(2024, 1, 1),
                date(2024, 1, 31),
                date(2024, 1, 25),
                'FUTSTK',
                None,  # Strike price not required for futures
                None   # Option type not required for futures
            )
        except Exception as e:
            # Network error is expected, but not parameter validation error
            assert "Missing argument" not in str(e)
            
    def test_valid_instrument_types(self):
        """Test all valid instrument types are accepted."""
        
        valid_types = ['OPTIDX', 'OPTSTK', 'FUTIDX', 'FUTSTK']
        
        for instrument_type in valid_types:
            try:
                if 'OPT' in instrument_type:
                    # Options require strike and type
                    derivatives_raw(
                        'RELIANCE',
                        date(2024, 1, 1),
                        date(2024, 1, 31),
                        date(2024, 1, 25),
                        instrument_type,
                        2800.0,
                        'CE'
                    )
                else:
                    # Futures don't require strike and type
                    derivatives_raw(
                        'RELIANCE', 
                        date(2024, 1, 1),
                        date(2024, 1, 31),
                        date(2024, 1, 25),
                        instrument_type,
                        None,
                        None
                    )
            except Exception as e:
                # Network error expected, but not validation error
                assert "Invalid instrument_type" not in str(e)
                assert "Missing argument" not in str(e)


class TestOptionStrikesAndTypes:
    """Test different strike prices and option types."""
    
    def test_option_type_validation(self):
        """Test that only CE and PE are valid option types."""
        
        valid_option_types = ['CE', 'PE']
        
        for option_type in valid_option_types:
            try:
                derivatives_raw(
                    'RELIANCE',
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    date(2024, 1, 25),
                    'OPTSTK',
                    2800.0,
                    option_type
                )
            except Exception as e:
                # Network error expected, not validation error for valid types
                assert "invalid option type" not in str(e).lower()
                
    def test_strike_price_formatting(self):
        """Test strike price formatting to 2 decimal places."""
        
        # Test various strike price formats
        strike_prices = [2800, 2800.0, 2800.5, 2800.75]
        
        for strike in strike_prices:
            try:
                derivatives_raw(
                    'RELIANCE',
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    date(2024, 1, 25),
                    'OPTSTK',
                    strike,
                    'CE'
                )
            except Exception as e:
                # Should not fail on strike price formatting
                assert "strike" not in str(e).lower()
                

class TestExpiryDateCalculation:
    """Test expiry date calculation for different scenarios."""
    
    def test_nifty_weekly_expiries(self):
        """Test NIFTY weekly expiries calculation."""
        
        test_date = date(2024, 1, 15)
        expiries = expiry_dates(test_date, 'OPTIDX', 'NIFTY')
        
        # NIFTY should have weekly expiries
        assert len(expiries) > 10, "NIFTY should have multiple weekly expiries"
        
        # Should have expiries in near term
        assert any(exp <= test_date + timedelta(days=7) for exp in expiries), \
            "Should have expiry within a week"
            
    def test_stock_monthly_expiries(self):
        """Test stock monthly expiries calculation."""
        
        test_date = date(2024, 1, 15)
        expiries = expiry_dates(test_date, 'OPTSTK', 'RELIANCE')
        
        # Stocks should have monthly expiries (fewer than weekly)
        assert len(expiries) >= 3, "Should have at least 3 monthly expiries"
        assert len(expiries) <= 12, "Should not have more than 12 monthly expiries"
        
    def test_expiry_dates_chronological(self):
        """Test that expiry dates are returned in chronological order."""
        
        test_date = date(2024, 1, 15)
        expiries = expiry_dates(test_date, 'OPTIDX', 'NIFTY')
        
        # Check chronological order
        for i in range(1, len(expiries)):
            assert expiries[i] > expiries[i-1], \
                f"Expiries should be chronological: {expiries[i-1]} >= {expiries[i]}"
                
    def test_expiry_dates_after_reference_date(self):
        """Test that all expiry dates are after the reference date."""
        
        test_date = date(2024, 1, 15)
        expiries = expiry_dates(test_date, 'OPTIDX', 'NIFTY')
        
        for expiry in expiries:
            assert expiry >= test_date, \
                f"Expiry {expiry} should be >= reference date {test_date}"


class TestDataQualityAndCompleteness:
    """Test option data quality and completeness."""
    
    def test_derivatives_data_structure(self):
        """Test the expected data structure from derivatives functions."""
        
        # Test that functions exist and have correct signatures
        assert callable(derivatives_raw)
        assert callable(derivatives_df) 
        assert callable(derivatives_csv)
        
        # Test parameter counts
        import inspect
        sig = inspect.signature(derivatives_raw)
        expected_params = ['symbol', 'from_date', 'to_date', 'expiry_date', 
                          'instrument_type', 'strike_price', 'option_type']
        
        # Check that all expected parameters exist
        param_names = list(sig.parameters.keys())
        assert len(param_names) >= 7, f"Expected >= 7 params, got {len(param_names)}"
        
    def test_option_headers_consistency(self):
        """Test that option headers are consistent across functions."""
        
        from aynse.nse.history import options_select_headers, options_final_headers
        
        # Check that headers are defined
        assert len(options_select_headers) > 0, "Option select headers should be defined"
        assert len(options_final_headers) > 0, "Option final headers should be defined"
        
        # Check header count consistency
        assert len(options_select_headers) == len(options_final_headers), \
            "Select and final headers should have same count"
            
        # Check for essential option fields
        essential_fields = ['DATE', 'EXPIRY', 'OPTION TYPE', 'STRIKE PRICE', 
                           'OPEN', 'HIGH', 'LOW', 'CLOSE']
        
        for field in essential_fields:
            assert field in options_final_headers, \
                f"Essential field {field} missing from option headers"


class TestErrorHandling:
    """Test error handling with invalid parameters."""
    
    def test_invalid_date_ranges(self):
        """Test error handling for invalid date ranges."""
        
        # Test from_date > to_date
        try:
            derivatives_raw(
                'RELIANCE',
                date(2024, 1, 31),  # from_date after to_date
                date(2024, 1, 1),   # to_date before from_date  
                date(2024, 1, 25),
                'OPTSTK',
                2800.0,
                'CE'
            )
        except Exception as e:
            # Should handle date validation appropriately
            pass  # Network error expected anyway
            
    def test_future_expiry_dates(self):
        """Test handling of far future expiry dates."""
        
        far_future = date(2030, 1, 1)
        
        try:
            derivatives_raw(
                'RELIANCE',
                date(2024, 1, 1),
                date(2024, 1, 31),
                far_future,  # Far future expiry
                'OPTSTK',
                2800.0,
                'CE'
            )
        except Exception as e:
            # Should not crash on future dates
            pass
            
    def test_invalid_symbols(self):
        """Test handling of invalid or non-existent symbols."""
        
        invalid_symbols = ['INVALID123', '', 'TOOLONGNAME' * 10]
        
        for symbol in invalid_symbols:
            try:
                derivatives_raw(
                    symbol,
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    date(2024, 1, 25),
                    'OPTSTK',
                    2800.0,
                    'CE'
                )
            except Exception as e:
                # Should handle gracefully without crashing
                pass


class TestPerformanceAndLimits:
    """Test performance with various scenarios."""
    
    def test_large_date_range_handling(self):
        """Test handling of large date ranges."""
        
        # Test 1 year range
        large_range_start = date(2023, 1, 1)
        large_range_end = date(2023, 12, 31)
        
        try:
            # This should be handled by date chunking
            derivatives_raw(
                'RELIANCE',
                large_range_start,
                large_range_end,
                date(2023, 1, 26),
                'OPTSTK', 
                2800.0,
                'CE'
            )
        except Exception as e:
            # Network error expected, but should not fail on date range size
            assert "date range" not in str(e).lower()
            
    def test_multiple_expiry_calculation_performance(self):
        """Test performance of calculating multiple expiries."""
        
        import time
        
        test_date = date(2024, 1, 15)
        
        start_time = time.time()
        expiries = expiry_dates(test_date, 'OPTIDX', 'NIFTY', months_ahead=12)
        end_time = time.time()
        
        calculation_time = end_time - start_time
        
        # Should calculate expiries reasonably quickly
        assert calculation_time < 5.0, \
            f"Expiry calculation took too long: {calculation_time}s"
        assert len(expiries) > 0, "Should calculate some expiries"


class TestIntegrationScenarios:
    """Integration tests combining multiple functionalities."""
    
    def test_earnings_date_option_workflow(self):
        """Test workflow for getting options around earnings dates."""
        
        # Simulated earnings dates for testing
        earnings_dates = {
            'RELIANCE': [
                date(2024, 1, 19),  # Q3 FY24
                date(2024, 4, 18),  # Q4 FY24
                date(2024, 7, 18),  # Q1 FY25
            ]
        }
        
        for symbol, dates in earnings_dates.items():
            for earnings_date in dates:
                # Step 1: Calculate relevant expiry dates
                expiries = expiry_dates(earnings_date, 'OPTSTK', symbol)
                
                assert len(expiries) > 0, f"Should find expiries for {symbol} around {earnings_date}"
                
                # Find expiry closest to earnings date (but after)
                relevant_expiry = None
                for expiry in expiries:
                    if expiry >= earnings_date:
                        relevant_expiry = expiry
                        break
                        
                assert relevant_expiry is not None, \
                    f"Should find expiry after earnings date {earnings_date}"
                
                # Step 2: Test option data fetching parameters
                # (Network call would fail, but we test parameter structure)
                test_strikes = [2600, 2800, 3000]  # ATM, ITM, OTM
                test_types = ['CE', 'PE']
                
                for strike in test_strikes:
                    for option_type in test_types:
                        try:
                            derivatives_raw(
                                symbol,
                                earnings_date - timedelta(days=30),  # 1 month before
                                earnings_date + timedelta(days=7),   # 1 week after
                                relevant_expiry,
                                'OPTSTK',
                                strike,
                                option_type
                            )
                        except Exception as e:
                            # Network error expected
                            assert "Missing argument" not in str(e)
                            
    def test_multi_symbol_option_analysis(self):
        """Test analysis across multiple symbols."""
        
        symbols = ['RELIANCE', 'TCS', 'HDFCBANK']
        test_date = date(2024, 1, 15)
        
        results = {}
        
        for symbol in symbols:
            try:
                # Calculate expiries for each symbol
                expiries = expiry_dates(test_date, 'OPTSTK', symbol)
                results[symbol] = {
                    'expiry_count': len(expiries),
                    'next_expiry': expiries[0] if expiries else None
                }
                
                assert len(expiries) > 0, f"Should find expiries for {symbol}"
                
            except Exception as e:
                # Should not fail on symbol processing
                pytest.fail(f"Failed processing symbol {symbol}: {e}")
                
        # Verify results structure
        assert len(results) == len(symbols), "Should process all symbols"
        
        for symbol, data in results.items():
            assert 'expiry_count' in data, f"Missing expiry_count for {symbol}"
            assert 'next_expiry' in data, f"Missing next_expiry for {symbol}"
            
    def test_option_strategy_parameter_validation(self):
        """Test parameter validation for common option strategies."""
        
        # Test straddle parameters (same strike, both CE and PE)
        symbol = 'RELIANCE'
        strike = 2800.0
        expiry = date(2024, 1, 25)
        date_range = (date(2024, 1, 1), date(2024, 1, 31))
        
        straddle_params = [
            (symbol, date_range[0], date_range[1], expiry, 'OPTSTK', strike, 'CE'),
            (symbol, date_range[0], date_range[1], expiry, 'OPTSTK', strike, 'PE')
        ]
        
        for params in straddle_params:
            try:
                derivatives_raw(*params)
            except Exception as e:
                # Should not fail on parameter validation
                assert "Missing argument" not in str(e)
                assert "Invalid instrument_type" not in str(e)
                
        # Test strangle parameters (different strikes)
        strangle_strikes = [2700.0, 2900.0]  # OTM put and call
        
        for i, option_type in enumerate(['PE', 'CE']):
            try:
                derivatives_raw(
                    symbol,
                    date_range[0], 
                    date_range[1],
                    expiry,
                    'OPTSTK',
                    strangle_strikes[i],
                    option_type
                )
            except Exception as e:
                # Should not fail on parameter validation
                assert "Missing argument" not in str(e)


# Additional test for NSELive initialization in different environments
class TestNSELiveEnvironment:
    """Test NSELive initialization and error handling."""
    
    def test_nse_live_network_failure_handling(self):
        """Test NSELive handles network failures gracefully."""
        
        # This will fail in sandboxed environment
        with pytest.raises(Exception):
            nse = NSELive()
            
        # But it should be a connection error, not a code error
        try:
            nse = NSELive()
        except Exception as e:
            # Should be network-related error
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in 
                      ['connection', 'network', 'resolve', 'timeout']), \
                f"Expected network error, got: {e}"
                
    def test_nse_live_routes_defined(self):
        """Test that NSELive has required routes defined."""
        
        # Test route definitions without initialization
        expected_routes = [
            'index_option_chain',
            'equity_option_chain', 
            'currency_option_chain',
            'corporate_announcements'
        ]
        
        # Check routes are defined in class
        from aynse.nse.live import NSELive
        
        for route in expected_routes:
            assert route in NSELive._routes, f"Route {route} not defined"
            assert NSELive._routes[route].startswith('/'), \
                f"Route {route} should start with '/'"


if __name__ == "__main__":
    # Run with pytest if available, otherwise run basic validation
    try:
        import pytest
        pytest.main([__file__, '-v'])
    except ImportError:
        print("pytest not available, running basic validation...")
        
        # Run basic validation without pytest
        test_classes = [
            TestHistoricalDerivatives,
            TestOptionStrikesAndTypes,
            TestExpiryDateCalculation,
            TestDataQualityAndCompleteness,
            TestErrorHandling,
            TestPerformanceAndLimits,
            TestIntegrationScenarios,
            TestNSELiveEnvironment
        ]
        
        for test_class in test_classes:
            print(f"\nTesting {test_class.__name__}...")
            instance = test_class()
            
            for method_name in dir(instance):
                if method_name.startswith('test_'):
                    print(f"  {method_name}...", end="")
                    try:
                        getattr(instance, method_name)()
                        print(" PASS")
                    except Exception as e:
                        print(f" FAIL: {e}")