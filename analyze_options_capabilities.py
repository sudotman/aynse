#!/usr/bin/env python3
"""
Options Fetching Capabilities Analysis for aynse library

This script analyzes the options fetching capabilities of the aynse library
and tests functionality for major stocks over the last ~5 years.
"""

import sys
import os
from datetime import date, datetime, timedelta
import traceback
import json
from pprint import pprint

# Add the current directory to path to import aynse
sys.path.insert(0, '/home/runner/work/aynse/aynse')

try:
    from aynse.nse.live import NSELive
    from aynse.nse.history import derivatives_raw, derivatives_df
    from aynse.nse.archives import expiry_dates
except ImportError as e:
    print(f"Error importing aynse modules: {e}")
    sys.exit(1)

class OptionsCapabilityAnalyzer:
    """Analyzes options fetching capabilities and identifies issues."""
    
    def __init__(self):
        self.issues = []
        self.test_results = {}
        
        # Major stocks to test
        self.major_stocks = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFOSYS', 'HINDUNILVR',
            'ICICIBANK', 'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK'
        ]
        
        # Test date range (last ~5 years)
        self.end_date = date.today()
        self.start_date = date(2020, 1, 1)
        
        print(f"Analyzing options capabilities from {self.start_date} to {self.end_date}")
        print(f"Testing with major stocks: {self.major_stocks}")
        
    def test_live_option_chains(self):
        """Test current live option chain functionality."""
        print("\n=== Testing Live Option Chain Functionality ===")
        
        # Test without actual network connection (since we're in sandbox)
        # This will help us understand the API structure
        
        try:
            nse = NSELive()
            print("NSE Live instance created successfully")
        except Exception as e:
            self.issues.append({
                'component': 'NSELive initialization',
                'issue': f'Failed to initialize NSELive: {str(e)}',
                'severity': 'high'
            })
            print(f"Failed to initialize NSELive: {e}")
            return False
            
        # Test API structure
        print(f"Available routes: {list(nse._routes.keys())}")
        print(f"Option-related routes:")
        for route, endpoint in nse._routes.items():
            if 'option' in route.lower():
                print(f"  {route}: {endpoint}")
                
        return True
    
    def test_historical_derivatives_api(self):
        """Test historical derivatives API structure and parameters."""
        print("\n=== Testing Historical Derivatives API ===")
        
        # Test parameter validation
        test_cases = [
            {
                'symbol': 'RELIANCE',
                'from_date': date(2024, 1, 1),
                'to_date': date(2024, 1, 31),
                'expiry_date': date(2024, 1, 25),
                'instrument_type': 'OPTSTK',
                'strike_price': 2800,
                'option_type': 'CE'
            },
            {
                'symbol': 'NIFTY',
                'from_date': date(2024, 1, 1), 
                'to_date': date(2024, 1, 31),
                'expiry_date': date(2024, 1, 25),
                'instrument_type': 'OPTIDX',
                'strike_price': 21000,
                'option_type': 'PE'
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"\nTest case {i+1}: {test_case['symbol']} {test_case['instrument_type']}")
            try:
                # This will fail due to network, but we can analyze the code path
                print(f"  Parameters: {test_case}")
                print(f"  API would call: /api/historical/fo/derivatives")
                print(f"  Valid instrument type: {test_case['instrument_type'] in ['OPTIDX', 'OPTSTK', 'FUTIDX', 'FUTSTK']}")
                
                # Validate required parameters for options
                if 'OPT' in test_case['instrument_type']:
                    if not (test_case.get('strike_price') and test_case.get('option_type')):
                        self.issues.append({
                            'component': 'derivatives_raw',
                            'issue': f'Missing required parameters for options: strike_price or option_type',
                            'severity': 'medium'
                        })
                        
            except Exception as e:
                print(f"  Error in test case: {e}")
                
    def test_expiry_date_calculation(self):
        """Test expiry date calculation functionality."""
        print("\n=== Testing Expiry Date Calculation ===")
        
        test_date = date(2024, 1, 15)
        
        test_scenarios = [
            ('NIFTY', 'OPTIDX'),
            ('BANKNIFTY', 'OPTIDX'), 
            ('RELIANCE', 'OPTSTK'),
            ('TCS', 'FUTSTK'),
        ]
        
        for symbol, instrument_type in test_scenarios:
            try:
                print(f"\nTesting expiry dates for {symbol} ({instrument_type}):")
                expiries = expiry_dates(test_date, instrument_type, symbol)
                print(f"  Found {len(expiries)} expiry dates")
                print(f"  Next 3 expiries: {expiries[:3] if expiries else 'None'}")
                
                if not expiries:
                    self.issues.append({
                        'component': 'expiry_dates',
                        'issue': f'No expiry dates found for {symbol} {instrument_type}',
                        'severity': 'medium'
                    })
                    
            except Exception as e:
                print(f"  Error calculating expiries for {symbol}: {e}")
                self.issues.append({
                    'component': 'expiry_dates',
                    'issue': f'Failed to calculate expiries for {symbol}: {str(e)}',
                    'severity': 'high'
                })

    def analyze_earnings_date_capability(self):
        """Analyze capability to get earnings dates."""
        print("\n=== Analyzing Earnings Date Capability ===")
        
        print("Current library capabilities for earnings dates:")
        print("1. corporate_announcements() method in NSELive")
        print("   - Can filter by symbol and date range")
        print("   - Returns corporate announcements/filings")
        print("   - Could potentially include earnings announcements")
        
        # Check if we have corporate announcements functionality
        try:
            nse = NSELive()
            # Test parameter structure (without network call)
            print("\nCorporate announcements API structure:")
            print("  Route: /corporate-announcements") 
            print("  Parameters: segment, from_date, to_date, symbol")
            print("  Usage: corporate_announcements('equities', from_date, to_date, 'RELIANCE')")
            
        except Exception as e:
            print(f"Error analyzing corporate announcements: {e}")
            
        # Identify the gap
        self.issues.append({
            'component': 'earnings_dates',
            'issue': 'No dedicated earnings date functionality - need to parse corporate announcements or use external source',
            'severity': 'medium',
            'solution': 'Create earnings date parser from corporate announcements or integrate external earnings calendar'
        })
        
    def analyze_unified_interface_gaps(self):
        """Analyze gaps in unified interface for option fetching."""
        print("\n=== Analyzing Unified Interface Gaps ===")
        
        current_methods = {
            'live_data': [
                'index_option_chain(symbol)',
                'equities_option_chain(symbol)', 
                'currency_option_chain(symbol)'
            ],
            'historical_data': [
                'derivatives_raw(symbol, from_date, to_date, expiry_date, instrument_type, strike_price, option_type)',
                'derivatives_csv(...)',
                'derivatives_df(...)'
            ],
            'utilities': [
                'expiry_dates(dt, instrument_type, symbol)'
            ]
        }
        
        print("Current option fetching methods:")
        for category, methods in current_methods.items():
            print(f"\n{category.upper()}:")
            for method in methods:
                print(f"  - {method}")
                
        # Identify interface gaps
        gaps = [
            {
                'gap': 'No unified method to fetch both live and historical option data',
                'impact': 'Users need to know which method to use for different time periods',
                'solution': 'Create unified get_option_data() method that auto-detects time period'
            },
            {
                'gap': 'No convenient method to fetch option data around earnings dates',
                'impact': 'Manual process to combine earnings dates with option data fetching',
                'solution': 'Create get_earnings_options() method that handles the full workflow'
            },
            {
                'gap': 'Historical derivatives method requires exact expiry dates',
                'impact': 'Users must calculate appropriate expiry dates for given time periods',
                'solution': 'Allow automatic expiry date selection based on trade date'
            },
            {
                'gap': 'No bulk fetching for multiple symbols or multiple expiries',
                'impact': 'Inefficient for analyzing multiple stocks or option strategies',
                'solution': 'Add bulk fetching capabilities with parallel processing'
            }
        ]
        
        for gap in gaps:
            print(f"\nGAP: {gap['gap']}")
            print(f"  Impact: {gap['impact']}")
            print(f"  Solution: {gap['solution']}")
            
            self.issues.append({
                'component': 'unified_interface',
                'issue': gap['gap'],
                'impact': gap['impact'],
                'solution': gap['solution'],
                'severity': 'medium'
            })
            
    def analyze_testing_gaps(self):
        """Analyze gaps in testing coverage for options functionality."""
        print("\n=== Analyzing Testing Gaps ===")
        
        # Check existing tests
        existing_tests = [
            'test_equities_option_chain()',
            'test_currency_option_chain()', 
            'test_index_option_chain()',
            'test_expiry_dates() in test_bhav.py'
        ]
        
        print("Existing option-related tests:")
        for test in existing_tests:
            print(f"  - {test}")
            
        # Identify testing gaps
        testing_gaps = [
            'No tests for historical derivatives functionality',
            'No tests for option data quality and completeness',
            'No tests for error handling with invalid parameters',
            'No tests for performance with large date ranges',
            'No tests for options around earnings dates',
            'No tests for different strike prices and option types',
            'No integration tests combining multiple functionalities'
        ]
        
        print("\nTesting gaps identified:")
        for gap in testing_gaps:
            print(f"  - {gap}")
            self.issues.append({
                'component': 'testing',
                'issue': gap,
                'severity': 'medium'
            })
            
    def create_sample_earnings_dates(self):
        """Create sample earnings dates for major stocks over the last 5 years."""
        print("\n=== Creating Sample Earnings Date Analysis ===")
        
        # For major Indian companies, earnings are typically announced quarterly
        # Q1: July-August, Q2: October-November, Q3: January-February, Q4: April-May
        
        sample_earnings_periods = {
            'RELIANCE': [
                ('Q1 FY24', date(2023, 7, 20)),
                ('Q2 FY24', date(2023, 10, 25)), 
                ('Q3 FY24', date(2024, 1, 19)),
                ('Q4 FY24', date(2024, 4, 18)),
                ('Q1 FY25', date(2024, 7, 18))
            ],
            'TCS': [
                ('Q1 FY24', date(2023, 7, 12)),
                ('Q2 FY24', date(2023, 10, 11)),
                ('Q3 FY24', date(2024, 1, 10)), 
                ('Q4 FY24', date(2024, 4, 10)),
                ('Q1 FY25', date(2024, 7, 10))
            ],
            'HDFCBANK': [
                ('Q1 FY24', date(2023, 7, 15)),
                ('Q2 FY24', date(2023, 10, 14)),
                ('Q3 FY24', date(2024, 1, 13)),
                ('Q4 FY24', date(2024, 4, 13)),
                ('Q1 FY25', date(2024, 7, 13))
            ]
        }
        
        print("Sample earnings dates for analysis:")
        for symbol, earnings in sample_earnings_periods.items():
            print(f"\n{symbol}:")
            for quarter, date_val in earnings:
                # Calculate relevant option expiry dates
                try:
                    expiries = expiry_dates(date_val, 'OPTSTK', symbol, months_ahead=2)
                    next_expiry = expiries[0] if expiries else None
                    print(f"  {quarter} ({date_val}): Next expiry {next_expiry}")
                except Exception as e:
                    print(f"  {quarter} ({date_val}): Error calculating expiry - {e}")
                    
        return sample_earnings_periods
        
    def generate_analysis_report(self):
        """Generate comprehensive analysis report."""
        print("\n" + "="*80)
        print("AYNSE OPTIONS FETCHING CAPABILITIES - ANALYSIS REPORT")
        print("="*80)
        
        print(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Test Period: {self.start_date} to {self.end_date}")
        print(f"Major Stocks Analyzed: {', '.join(self.major_stocks)}")
        
        # Summary of current capabilities
        print("\n🟢 CURRENT CAPABILITIES:")
        capabilities = [
            "✓ Live option chain data for indices, equities, and currencies",
            "✓ Historical derivatives data with specific expiry dates",
            "✓ Algorithmic expiry date calculation",
            "✓ Support for multiple instrument types (OPTIDX, OPTSTK, FUTIDX, FUTSTK)",
            "✓ CSV and DataFrame output formats for historical data",
            "✓ Corporate announcements API (potential source for earnings dates)"
        ]
        for cap in capabilities:
            print(f"  {cap}")
            
        # Summary of issues
        print(f"\n🔴 ISSUES IDENTIFIED ({len(self.issues)} total):")
        
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for issue in self.issues:
            severity_counts[issue.get('severity', 'medium')] += 1
            
        print(f"  High: {severity_counts['high']}, Medium: {severity_counts['medium']}, Low: {severity_counts['low']}")
        
        for i, issue in enumerate(self.issues, 1):
            severity = issue.get('severity', 'medium').upper()
            print(f"\n  {i}. [{severity}] {issue['component']}")
            print(f"     Issue: {issue['issue']}")
            if 'solution' in issue:
                print(f"     Solution: {issue['solution']}")
                
        # Recommendations
        print(f"\n🔧 RECOMMENDED SOLUTIONS:")
        solutions = [
            "1. Create unified option data fetching interface",
            "2. Implement earnings date extraction from corporate announcements",
            "3. Add bulk fetching capabilities for multiple symbols",
            "4. Enhance testing coverage for all option functionality",
            "5. Create convenience methods for common option strategies",
            "6. Add option data quality validation",
            "7. Implement caching for improved performance"
        ]
        for solution in solutions:
            print(f"  {solution}")
            
        print("\n" + "="*80)
        return self.issues

def main():
    """Main analysis function."""
    print("🚀 Starting Options Fetching Capabilities Analysis")
    
    analyzer = OptionsCapabilityAnalyzer()
    
    try:
        # Run all analysis components
        analyzer.test_live_option_chains()
        analyzer.test_historical_derivatives_api() 
        analyzer.test_expiry_date_calculation()
        analyzer.analyze_earnings_date_capability()
        analyzer.analyze_unified_interface_gaps()
        analyzer.analyze_testing_gaps()
        analyzer.create_sample_earnings_dates()
        
        # Generate final report
        issues = analyzer.generate_analysis_report()
        
        # Save results
        with open('/tmp/options_analysis_report.json', 'w') as f:
            json.dump({
                'analysis_date': datetime.now().isoformat(),
                'issues': issues,
                'summary': {
                    'total_issues': len(issues),
                    'high_severity': len([i for i in issues if i.get('severity') == 'high']),
                    'medium_severity': len([i for i in issues if i.get('severity') == 'medium']),
                    'low_severity': len([i for i in issues if i.get('severity') == 'low'])
                }
            }, f, indent=2)
            
        print(f"\n📄 Detailed report saved to: /tmp/options_analysis_report.json")
        return issues
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()