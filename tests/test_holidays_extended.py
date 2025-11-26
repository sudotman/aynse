"""
Extended tests for the holidays module.

Tests cover:
- Holiday list retrieval
- is_holiday function
- is_trading_day function
- Trading day utilities
- Edge cases and boundary conditions
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from aynse.holidays import (
    holidays,
    is_holiday,
    is_trading_day,
    get_trading_days,
    count_trading_days,
    add_holiday,
    clear_holiday_cache,
)


class TestHolidays:
    """Tests for the holidays function."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_holiday_cache()
    
    def test_holidays_returns_list(self):
        """Test that holidays returns a list."""
        result = holidays()
        assert isinstance(result, list)
    
    def test_holidays_all_are_dates(self):
        """Test that all items are date objects."""
        result = holidays()
        for item in result:
            assert isinstance(item, date)
    
    def test_holidays_filter_by_year(self):
        """Test filtering holidays by year."""
        holidays_2024 = holidays(year=2024)
        
        assert len(holidays_2024) > 0
        for dt in holidays_2024:
            assert dt.year == 2024
    
    def test_holidays_filter_by_month(self):
        """Test filtering holidays by year and month."""
        holidays_jan_2024 = holidays(year=2024, month=1)
        
        assert len(holidays_jan_2024) > 0
        for dt in holidays_jan_2024:
            assert dt.year == 2024
            assert dt.month == 1
    
    def test_holidays_sorted(self):
        """Test that holidays are returned sorted."""
        result = holidays(year=2024)
        
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]
    
    def test_known_holidays_present(self):
        """Test that known holidays are in the list."""
        # Republic Day 2024
        assert date(2024, 1, 26) in holidays(year=2024)
        
        # Independence Day 2024
        assert date(2024, 8, 15) in holidays(year=2024)
        
        # Gandhi Jayanti 2024
        assert date(2024, 10, 2) in holidays(year=2024)
        
        # Christmas 2024
        assert date(2024, 12, 25) in holidays(year=2024)


class TestIsHoliday:
    """Tests for is_holiday function."""
    
    def test_known_holiday(self):
        """Test that known holidays return True."""
        assert is_holiday(date(2024, 1, 26)) is True  # Republic Day
        assert is_holiday(date(2024, 8, 15)) is True  # Independence Day
    
    def test_regular_weekday(self):
        """Test that regular weekdays return False."""
        # 2024-01-15 is a Monday, not a holiday
        assert is_holiday(date(2024, 1, 15)) is False
    
    def test_weekend_not_holiday(self):
        """Test that weekends are not considered holidays in this function."""
        # This function only checks the holiday list, not weekends
        assert is_holiday(date(2024, 1, 13)) is False  # Saturday


class TestIsTradingDay:
    """Tests for is_trading_day function."""
    
    def test_regular_weekday_is_trading_day(self):
        """Test that regular weekdays are trading days."""
        # 2024-01-15 is Monday
        assert is_trading_day(date(2024, 1, 15)) is True
    
    def test_weekend_not_trading_day(self):
        """Test that weekends are not trading days."""
        assert is_trading_day(date(2024, 1, 13)) is False  # Saturday
        assert is_trading_day(date(2024, 1, 14)) is False  # Sunday
    
    def test_holiday_not_trading_day(self):
        """Test that holidays are not trading days."""
        assert is_trading_day(date(2024, 1, 26)) is False  # Republic Day
    
    def test_friday_is_trading_day(self):
        """Test that Fridays are trading days."""
        assert is_trading_day(date(2024, 1, 12)) is True


class TestGetTradingDays:
    """Tests for get_trading_days function."""
    
    def test_returns_list_of_dates(self):
        """Test that function returns list of date objects."""
        result = get_trading_days(date(2024, 1, 1), date(2024, 1, 10))
        
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, date)
    
    def test_excludes_weekends(self):
        """Test that weekends are excluded."""
        result = get_trading_days(date(2024, 1, 1), date(2024, 1, 31))
        
        for dt in result:
            assert dt.weekday() < 5  # 0-4 are Mon-Fri
    
    def test_excludes_holidays(self):
        """Test that holidays are excluded."""
        # January 2024 has Jan 26 (Republic Day) as holiday
        result = get_trading_days(date(2024, 1, 1), date(2024, 1, 31))
        
        assert date(2024, 1, 26) not in result
    
    def test_sorted_result(self):
        """Test that results are sorted."""
        result = get_trading_days(date(2024, 1, 1), date(2024, 1, 31))
        
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1]
    
    def test_invalid_date_range(self):
        """Test error on invalid date range."""
        with pytest.raises(ValueError):
            get_trading_days(date(2024, 1, 31), date(2024, 1, 1))
    
    def test_single_day_range(self):
        """Test single day range."""
        # A trading day
        result = get_trading_days(date(2024, 1, 15), date(2024, 1, 15))
        assert result == [date(2024, 1, 15)]
        
        # A weekend
        result = get_trading_days(date(2024, 1, 13), date(2024, 1, 13))
        assert result == []


class TestCountTradingDays:
    """Tests for count_trading_days function."""
    
    def test_week_count(self):
        """Test counting trading days in a week."""
        # Monday to Friday (5 weekdays)
        count = count_trading_days(date(2024, 1, 15), date(2024, 1, 19))
        
        # Should be 5 trading days (no holidays in this range)
        assert count == 5
    
    def test_month_count(self):
        """Test counting trading days in a month."""
        # January 2024
        count = count_trading_days(date(2024, 1, 1), date(2024, 1, 31))
        
        # January 2024 has 23 weekdays, minus holidays
        # Holidays: Jan 22, Jan 26 = 2 holidays
        # Expected: 23 - 2 = 21 trading days
        assert count == 21
    
    def test_weekend_only(self):
        """Test weekend-only range returns 0."""
        count = count_trading_days(date(2024, 1, 13), date(2024, 1, 14))
        assert count == 0


class TestAddHoliday:
    """Tests for add_holiday function."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_holiday_cache()
    
    def test_add_custom_holiday(self):
        """Test adding a custom holiday."""
        custom_date = date(2099, 12, 31)
        
        # Should not be a holiday initially
        assert is_holiday(custom_date) is False
        
        # Add it
        add_holiday(custom_date)
        
        # Now should be a holiday
        assert is_holiday(custom_date) is True
    
    def test_add_holiday_affects_trading_day(self):
        """Test that added holiday affects is_trading_day."""
        # Find a weekday that's not a holiday
        custom_date = date(2099, 1, 2)  # Thursday
        
        assert is_trading_day(custom_date) is True
        
        add_holiday(custom_date)
        
        assert is_trading_day(custom_date) is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_year(self):
        """Test year with no holidays in database."""
        # Very old year
        result = holidays(year=1990)
        assert result == []
    
    def test_future_year(self):
        """Test future year (may have holidays if added)."""
        result = holidays(year=2025)
        # Should have holidays for 2025
        assert len(result) > 0
    
    def test_year_boundary(self):
        """Test trading days across year boundary."""
        result = get_trading_days(date(2023, 12, 28), date(2024, 1, 5))
        
        # Should include days from both years
        assert any(d.year == 2023 for d in result)
        assert any(d.year == 2024 for d in result)

