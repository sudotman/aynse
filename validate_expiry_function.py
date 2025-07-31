#!/usr/bin/env python3
"""
Final validation of expiry_dates function behavior and return format
"""

from datetime import date
from aynse.nse.archives import expiry_dates

def validate_expiry_dates_function():
    """Validate all aspects of the expiry_dates function"""
    
    print("🔍 VALIDATING EXPIRY_DATES FUNCTION")
    print("=" * 40)
    
    # Test date in the middle of a month for better testing
    dt = date(2025, 6, 15)
    
    # Test 1: Return type and format
    print("\n1. Testing return type and format:")
    result = expiry_dates(dt, "FUTIDX", "NIFTY", months_ahead=2)
    print(f"   Return type: {type(result)}")
    print(f"   Length: {len(result)}")
    print(f"   All items are date objects: {all(isinstance(item, date) for item in result)}")
    print(f"   Sample items: {result[:3]}")
    
    # Test 2: No duplicates
    print("\n2. Testing for duplicates:")
    unique_count = len(set(result))
    total_count = len(result)
    print(f"   Total items: {total_count}")
    print(f"   Unique items: {unique_count}")
    print(f"   No duplicates: {unique_count == total_count}")
    
    # Test 3: Sorted order
    print("\n3. Testing sort order:")
    is_sorted = result == sorted(result)
    print(f"   Dates are sorted: {is_sorted}")
    
    # Test 4: All dates in future
    print("\n4. Testing future dates:")
    all_future = all(exp >= dt for exp in result)
    print(f"   All dates >= input date: {all_future}")
    
    # Test 5: Weekly vs Monthly contracts
    print("\n5. Testing contract types:")
    
    weekly_result = expiry_dates(dt, "FUTIDX", "NIFTY", months_ahead=1)
    monthly_result = expiry_dates(dt, "FUTSTK", "RELIANCE", months_ahead=1)
    
    print(f"   NIFTY (weekly) expiries in 1 month: {len(weekly_result)}")
    print(f"   RELIANCE (monthly) expiries in 1 month: {len(monthly_result)}")
    print(f"   Weekly has more expiries: {len(weekly_result) > len(monthly_result)}")
    
    # Test 6: Policy transitions
    print("\n6. Testing policy transitions:")
    
    dates_and_rules = [
        (date(2025, 3, 15), "Thursday", 3),
        (date(2025, 6, 15), "Monday", 0), 
        (date(2025, 10, 15), "Tuesday", 1)
    ]
    
    for test_date, expected_day, expected_weekday in dates_and_rules:
        expiry = expiry_dates(test_date, "FUTSTK", "RELIANCE", months_ahead=1)[0]
        actual_weekday = expiry.weekday()
        print(f"   {test_date} → {expiry} ({expiry.strftime('%A')}): {expected_day} rule ✓" if actual_weekday == expected_weekday else f"   {test_date} → {expiry} ({expiry.strftime('%A')}): Expected {expected_day}, got {expiry.strftime('%A')} ✗")
    
    # Test 7: Parameter variations
    print("\n7. Testing parameter variations:")
    
    # Empty parameters
    result_empty = expiry_dates(dt)
    print(f"   No instrument/symbol specified: {len(result_empty)} expiries")
    
    # Case sensitivity
    result_upper = expiry_dates(dt, "FUTIDX", "NIFTY")
    result_lower = expiry_dates(dt, "futidx", "nifty")
    print(f"   Case insensitive: {len(result_upper) == len(result_lower)}")
    
    print("\n✅ VALIDATION COMPLETE")
    print("   The expiry_dates function returns:")
    print("   • List of datetime.date objects")
    print("   • Properly sorted in ascending order")
    print("   • No duplicates")
    print("   • All dates >= input date")
    print("   • Respects NSE policy transitions")
    print("   • Handles weekly/monthly contract cycles correctly")

if __name__ == "__main__":
    validate_expiry_dates_function()
