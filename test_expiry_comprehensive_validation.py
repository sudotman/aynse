#!/usr/bin/env python3
"""
Additional comprehensive tests for the new algorithmic expiry_dates function
"""

import pytest
from datetime import date
from aynse.nse.archives import expiry_dates

def test_expiry_dates_return_format():
    """Test that expiry_dates returns proper format and types"""
    dt = date(2025, 1, 15)
    
    # Test return type
    result = expiry_dates(dt)
    assert isinstance(result, list), "expiry_dates should return a list"
    
    # Test that all items are date objects
    for expiry in result:
        assert isinstance(expiry, date), f"All expiries should be date objects, got {type(expiry)}"
    
    # Test that dates are sorted
    assert result == sorted(result), "Expiry dates should be sorted in ascending order"
    
    # Test that all dates are in the future (relative to input date)
    for expiry in result:
        assert expiry >= dt, f"All expiry dates should be >= input date {dt}, got {expiry}"

def test_expiry_dates_no_duplicates():
    """Test that expiry_dates doesn't return duplicate dates"""
    dt = date(2025, 1, 15)
    
    # Test with weekly expiries (more likely to have duplicates)
    result = expiry_dates(dt, "FUTIDX", "NIFTY", months_ahead=3)
    assert len(result) == len(set(result)), "Expiry dates should not contain duplicates"
    
    # Test with monthly expiries
    result = expiry_dates(dt, "FUTSTK", "RELIANCE", months_ahead=6)
    assert len(result) == len(set(result)), "Expiry dates should not contain duplicates"

def test_expiry_dates_contract_cycles():
    """Test different contract cycles work correctly"""
    dt = date(2025, 6, 15)
    
    # Weekly contracts should have more expiries than monthly
    weekly_expiries = expiry_dates(dt, "FUTIDX", "NIFTY", months_ahead=2)
    monthly_expiries = expiry_dates(dt, "FUTSTK", "RELIANCE", months_ahead=2)
    
    assert len(weekly_expiries) > len(monthly_expiries), \
        "Weekly contracts should have more expiries than monthly contracts"
    
    # Test known weekly symbols
    weekly_symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
    for symbol in weekly_symbols:
        result = expiry_dates(dt, "FUTIDX", symbol, months_ahead=1)
        assert len(result) >= 3, f"Weekly symbol {symbol} should have at least 3 expiries per month"

def test_expiry_dates_policy_transitions():
    """Test that policy transitions work correctly"""
    
    # Before April 4, 2025 (Thursday rules)
    dt1 = date(2025, 3, 15)
    expiry1 = expiry_dates(dt1, "FUTSTK", "RELIANCE", months_ahead=1)[0]
    assert expiry1.weekday() == 3, f"Before Apr 4, 2025 should use Thursday (3), got {expiry1.weekday()}"
    
    # Between April 4 and August 28, 2025 (Monday rules)
    dt2 = date(2025, 6, 15)
    expiry2 = expiry_dates(dt2, "FUTSTK", "RELIANCE", months_ahead=1)[0]
    assert expiry2.weekday() == 0, f"Between Apr-Aug 2025 should use Monday (0), got {expiry2.weekday()}"
    
    # After August 29, 2025 (Tuesday rules)
    dt3 = date(2025, 10, 15)
    expiry3 = expiry_dates(dt3, "FUTSTK", "RELIANCE", months_ahead=1)[0]
    assert expiry3.weekday() == 1, f"After Aug 29, 2025 should use Tuesday (1), got {expiry3.weekday()}"

def test_expiry_dates_edge_cases():
    """Test edge cases and boundary conditions"""
    
    # Test with months_ahead=0 (should still return valid expiries)
    dt = date(2025, 6, 15)
    result = expiry_dates(dt, months_ahead=0)
    # Should return empty list since we're looking 0 months ahead from mid-month
    assert isinstance(result, list)
    
    # Test with very large months_ahead
    result = expiry_dates(dt, months_ahead=24)
    assert len(result) > 10, "Should return many expiries for 24 months ahead"
    
    # Test year boundary crossing
    dt_year_end = date(2025, 12, 15)
    result = expiry_dates(dt_year_end, months_ahead=3)
    assert any(exp.year == 2026 for exp in result), "Should handle year boundary crossing"

def test_expiry_dates_parameter_validation():
    """Test that function handles various parameter combinations"""
    dt = date(2025, 6, 15)
    
    # Test with empty/None instrument_type and symbol
    result1 = expiry_dates(dt, "", "")
    result2 = expiry_dates(dt, None, None)
    
    assert isinstance(result1, list) and isinstance(result2, list)
    
    # Test case sensitivity
    result_upper = expiry_dates(dt, "FUTIDX", "NIFTY")
    result_lower = expiry_dates(dt, "futidx", "nifty")  # Should still work due to .upper() in code
    
    assert len(result_upper) > 0 and len(result_lower) > 0

def test_expiry_dates_weekend_holiday_handling():
    """Test that expiry dates avoid weekends and holidays"""
    from aynse.holidays import holidays
    
    dt = date(2025, 1, 15)
    result = expiry_dates(dt, months_ahead=12)
    
    # Get all holidays for 2025 and 2026
    all_holidays = holidays(year=2025) + holidays(year=2026)
    
    for expiry in result:
        # Check not a weekend
        assert expiry.weekday() < 5, f"Expiry {expiry} falls on weekend (weekday: {expiry.weekday()})"
        
        # Check not a holiday
        assert expiry not in all_holidays, f"Expiry {expiry} falls on a holiday"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
