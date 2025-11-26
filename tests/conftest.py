"""
Pytest configuration and shared fixtures for aynse tests.

This module provides:
- Common fixtures for test setup/teardown
- Mock server fixtures for offline testing
- Test data generators
- Helper functions for test assertions
"""

from __future__ import annotations

import os
import json
import tempfile
from datetime import date, datetime, timedelta
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# Test configuration
TEST_CACHE_DIR = tempfile.mkdtemp(prefix="aynse_test_cache_")


@pytest.fixture(autouse=True)
def set_test_cache_dir(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Set test cache directory to avoid polluting user's cache."""
    monkeypatch.setenv("J_CACHE_DIR", TEST_CACHE_DIR)
    yield
    # Cleanup is handled by temp directory


@pytest.fixture
def sample_stock_data() -> List[Dict[str, Any]]:
    """Generate sample stock data for testing."""
    return [
        {
            "CH_TIMESTAMP": "2024-01-15",
            "CH_SERIES": "EQ",
            "CH_SYMBOL": "RELIANCE",
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2550.0,
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2530.0,
            "CH_LAST_TRADED_PRICE": 2528.0,
            "CH_PREVIOUS_CLS_PRICE": 2490.0,
            "VWAP": 2515.5,
            "CH_52WEEK_HIGH_PRICE": 2800.0,
            "CH_52WEEK_LOW_PRICE": 2200.0,
            "CH_TOT_TRADED_QTY": 5000000,
            "CH_TOT_TRADED_VAL": 12575000000.0,
            "CH_TOTAL_TRADES": 250000,
        },
        {
            "CH_TIMESTAMP": "2024-01-14",
            "CH_SERIES": "EQ",
            "CH_SYMBOL": "RELIANCE",
            "CH_OPENING_PRICE": 2480.0,
            "CH_TRADE_HIGH_PRICE": 2510.0,
            "CH_TRADE_LOW_PRICE": 2470.0,
            "CH_CLOSING_PRICE": 2490.0,
            "CH_LAST_TRADED_PRICE": 2488.0,
            "CH_PREVIOUS_CLS_PRICE": 2475.0,
            "VWAP": 2495.0,
            "CH_52WEEK_HIGH_PRICE": 2800.0,
            "CH_52WEEK_LOW_PRICE": 2200.0,
            "CH_TOT_TRADED_QTY": 4500000,
            "CH_TOT_TRADED_VAL": 11227500000.0,
            "CH_TOTAL_TRADES": 225000,
        },
    ]


@pytest.fixture
def sample_index_data() -> List[Dict[str, Any]]:
    """Generate sample index data for testing."""
    return [
        {
            "INDEX_NAME": "NIFTY 50",
            "Index Name": "Nifty 50",
            "HistoricalDate": "15 Jan 2024",
            "OPEN": 21500.0,
            "HIGH": 21650.0,
            "LOW": 21450.0,
            "CLOSE": 21600.0,
        },
        {
            "INDEX_NAME": "NIFTY 50",
            "Index Name": "Nifty 50",
            "HistoricalDate": "14 Jan 2024",
            "OPEN": 21400.0,
            "HIGH": 21550.0,
            "LOW": 21380.0,
            "CLOSE": 21500.0,
        },
    ]


@pytest.fixture
def sample_derivatives_data() -> List[Dict[str, Any]]:
    """Generate sample derivatives data for testing."""
    return [
        {
            "FH_TIMESTAMP": "2024-01-15",
            "FH_EXPIRY_DT": "2024-01-25",
            "FH_SYMBOL": "NIFTY",
            "FH_INSTRUMENT": "FUTIDX",
            "FH_OPENING_PRICE": 21500.0,
            "FH_TRADE_HIGH_PRICE": 21650.0,
            "FH_TRADE_LOW_PRICE": 21450.0,
            "FH_CLOSING_PRICE": 21600.0,
            "FH_LAST_TRADED_PRICE": 21595.0,
            "FH_SETTLE_PRICE": 21600.0,
            "FH_TOT_TRADED_QTY": 1000000,
            "FH_MARKET_LOT": 50,
            "FH_TOT_TRADED_VAL": 1080000000.0,
            "FH_OPEN_INT": 5000000,
            "FH_CHANGE_IN_OI": 250000,
        },
    ]


@pytest.fixture
def sample_bhavcopy_csv() -> str:
    """Generate sample bhavcopy CSV content for testing."""
    return """SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN
RELIANCE,EQ,2500.00,2550.00,2480.00,2530.00,2528.00,2490.00,5000000,12575000000.00,15-JAN-2024,250000,INE002A01018
TCS,EQ,3800.00,3850.00,3780.00,3820.00,3818.00,3790.00,2000000,7640000000.00,15-JAN-2024,100000,INE467B01029
INFY,EQ,1550.00,1580.00,1540.00,1570.00,1568.00,1545.00,3500000,5495000000.00,15-JAN-2024,175000,INE009A01021
"""


@pytest.fixture
def sample_live_quote() -> Dict[str, Any]:
    """Generate sample live quote data for testing."""
    return {
        "info": {
            "symbol": "RELIANCE",
            "companyName": "Reliance Industries Limited",
            "industry": "REFINERIES",
            "isin": "INE002A01018",
        },
        "priceInfo": {
            "lastPrice": 2530.0,
            "change": 40.0,
            "pChange": 1.61,
            "open": 2500.0,
            "previousClose": 2490.0,
            "intraDayHighLow": {
                "min": 2480.0,
                "max": 2550.0,
            },
            "weekHighLow": {
                "min": 2200.0,
                "max": 2800.0,
            },
        },
    }


@pytest.fixture
def mock_nse_response(sample_stock_data: List[Dict[str, Any]]) -> MagicMock:
    """Create a mock NSE API response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"data": sample_stock_data}
    mock.text = json.dumps({"data": sample_stock_data})
    return mock


@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory(prefix="aynse_test_output_") as tmpdir:
        yield tmpdir


@pytest.fixture
def trading_date() -> date:
    """Return a known trading date for testing."""
    return date(2024, 1, 15)  # Monday, not a holiday


@pytest.fixture
def holiday_date() -> date:
    """Return a known holiday date for testing."""
    return date(2024, 1, 26)  # Republic Day


@pytest.fixture
def weekend_date() -> date:
    """Return a weekend date for testing."""
    return date(2024, 1, 13)  # Saturday


# Helper functions for assertions
def assert_stock_data_valid(data: List[Dict[str, Any]]) -> None:
    """Assert that stock data has required fields."""
    required_fields = [
        "CH_TIMESTAMP",
        "CH_SYMBOL",
        "CH_OPENING_PRICE",
        "CH_TRADE_HIGH_PRICE",
        "CH_TRADE_LOW_PRICE",
        "CH_CLOSING_PRICE",
    ]
    
    for record in data:
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"


def assert_index_data_valid(data: List[Dict[str, Any]]) -> None:
    """Assert that index data has required fields."""
    required_fields = ["INDEX_NAME", "OPEN", "HIGH", "LOW", "CLOSE"]
    
    for record in data:
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"


def assert_csv_valid(csv_content: str, expected_headers: List[str]) -> None:
    """Assert that CSV content has expected headers."""
    lines = csv_content.strip().split('\n')
    assert len(lines) > 0, "CSV is empty"
    
    headers = lines[0].split(',')
    for expected in expected_headers:
        assert expected in headers, f"Missing header: {expected}"


# Skip markers for different test categories
requires_network = pytest.mark.skipif(
    os.environ.get("AYNSE_SKIP_NETWORK_TESTS", "0") == "1",
    reason="Network tests disabled"
)

requires_nse_access = pytest.mark.skipif(
    os.environ.get("AYNSE_SKIP_NSE_TESTS", "0") == "1",
    reason="NSE access tests disabled"
)

slow_test = pytest.mark.skipif(
    os.environ.get("AYNSE_SKIP_SLOW_TESTS", "0") == "1",
    reason="Slow tests disabled"
)


# Register custom markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "network: marks tests as requiring network access"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow-running"
    )
    config.addinivalue_line(
        "markers", "nse: marks tests as requiring NSE API access"
    )

