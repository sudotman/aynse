"""
End-to-end contract tests for core aynse output schemas.

These tests focus on deterministic schema/sanity checks and avoid
depending on live market data endpoints.
"""

from __future__ import annotations

from datetime import date

from aynse.holidays import holidays, is_trading_day, get_trading_days
from aynse.nse.streaming_processor import StreamingProcessor, StreamConfig


def test_stock_contract_schema(sample_stock_data):
    """Validate stock payload schema + basic price sanity."""
    required_fields = {
        "CH_TIMESTAMP",
        "CH_SYMBOL",
        "CH_OPENING_PRICE",
        "CH_TRADE_HIGH_PRICE",
        "CH_TRADE_LOW_PRICE",
        "CH_CLOSING_PRICE",
    }
    for row in sample_stock_data:
        assert required_fields.issubset(row.keys())
    latest = sample_stock_data[0]
    assert latest["CH_SYMBOL"]
    assert latest["CH_TRADE_LOW_PRICE"] <= latest["CH_OPENING_PRICE"] <= latest["CH_TRADE_HIGH_PRICE"]
    assert latest["CH_TRADE_LOW_PRICE"] <= latest["CH_CLOSING_PRICE"] <= latest["CH_TRADE_HIGH_PRICE"]
    assert latest["CH_TOT_TRADED_QTY"] > 0


def test_index_contract_schema(sample_index_data):
    """Validate index payload schema + chronological data formatting."""
    required_fields = {"INDEX_NAME", "OPEN", "HIGH", "LOW", "CLOSE"}
    for row in sample_index_data:
        assert required_fields.issubset(row.keys())
    assert sample_index_data[0]["INDEX_NAME"] == "NIFTY 50"
    assert isinstance(sample_index_data[0]["OPEN"], float)
    assert isinstance(sample_index_data[0]["CLOSE"], float)


def test_bhavcopy_csv_contract(sample_bhavcopy_csv):
    """Validate CSV output contains required headers and data rows."""
    expected_headers = ["SYMBOL", "SERIES", "OPEN", "CLOSE", "TIMESTAMP"]
    header_line = sample_bhavcopy_csv.strip().split("\n", maxsplit=1)[0]
    headers = [h.strip() for h in header_line.split(",")]
    for key in expected_headers:
        assert key in headers
    rows = [line for line in sample_bhavcopy_csv.strip().split("\n") if line]
    assert len(rows) >= 2


def test_live_quote_contract_schema(sample_live_quote):
    """Validate live quote structure and numeric sanity."""
    info = sample_live_quote["info"]
    price = sample_live_quote["priceInfo"]

    assert info["symbol"]
    assert info["isin"].startswith("INE")
    assert isinstance(price["lastPrice"], (int, float))
    assert isinstance(price["pChange"], (int, float))
    assert price["intraDayHighLow"]["min"] <= price["lastPrice"] <= price["intraDayHighLow"]["max"]


def test_holidays_trading_days_contract():
    """Validate holidays and trading-day utilities remain internally consistent."""
    holidays_2024 = holidays(year=2024)
    assert len(holidays_2024) > 0
    assert date(2024, 1, 26) in holidays_2024
    assert is_trading_day(date(2024, 1, 15)) is True

    trading_days = get_trading_days(date(2024, 1, 15), date(2024, 1, 19))
    assert trading_days[0] == date(2024, 1, 15)
    assert trading_days[-1] == date(2024, 1, 19)
    assert len(trading_days) == 5


def test_streaming_contract_sanity():
    """Validate streaming processor contract on representative CSV input."""
    processor = StreamingProcessor(StreamConfig(chunk_size=2))
    csv_data = """symbol,date,open,high,low,close,volume
RELIANCE,2024-01-15,2500,2550,2480,2530,5000000
TCS,2024-01-15,3800,3850,3780,3820,2000000
INFY,2024-01-15,1550,1580,1540,1570,3500000
"""

    total_rows = processor.process_csv_string(csv_data, lambda chunk: len(chunk))
    assert total_rows == 3
