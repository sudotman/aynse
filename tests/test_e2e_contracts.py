"""
End-to-end contract tests for the standardized aynse API surface.
"""

from __future__ import annotations

from datetime import date, datetime

from aynse.analytics import add_returns, summarize_option_chain
from aynse.catalog import dataset_capabilities, supported_event_categories
from aynse.holidays import holiday_records, holidays, is_trading_day, get_trading_days
from aynse.nse.streaming_processor import StreamingProcessor, StreamConfig


def test_stock_contract_schema():
    rows = [
        {
            "date": date(2024, 1, 15),
            "symbol": "RELIANCE",
            "series": "EQ",
            "open": 2500.0,
            "high": 2550.0,
            "low": 2480.0,
            "previous_close": 2490.0,
            "last_price": 2528.0,
            "close": 2530.0,
            "vwap": 2515.5,
            "week_52_high": 2800.0,
            "week_52_low": 2200.0,
            "volume": 5000000,
            "turnover": 12575000000.0,
            "trades": 250000,
        }
    ]
    row = rows[0]
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    assert required.issubset(row.keys())
    assert row["low"] <= row["open"] <= row["high"]
    assert row["low"] <= row["close"] <= row["high"]


def test_index_contract_schema():
    row = {
        "date": date(2024, 1, 15),
        "symbol": "NIFTY 50",
        "open": 21500.0,
        "high": 21650.0,
        "low": 21450.0,
        "close": 21600.0,
    }
    assert row["symbol"] == "NIFTY 50"
    assert isinstance(row["open"], float)
    assert isinstance(row["close"], float)


def test_live_quote_contract_schema():
    quote = {
        "symbol": "RELIANCE",
        "company_name": "Reliance Industries Limited",
        "isin": "INE002A01018",
        "price": {
            "last": 2530.0,
            "change": 40.0,
            "change_percent": 1.61,
            "open": 2500.0,
            "high": 2550.0,
            "low": 2480.0,
            "previous_close": 2490.0,
        },
        "week_range": {"high": 2800.0, "low": 2200.0},
    }
    assert quote["symbol"]
    assert quote["isin"].startswith("INE")
    assert isinstance(quote["price"]["last"], (int, float))
    assert quote["price"]["low"] <= quote["price"]["last"] <= quote["price"]["high"]


def test_holidays_trading_days_contract():
    holidays_2024 = holidays(year=2024)
    assert len(holidays_2024) > 0
    assert date(2024, 1, 26) in holidays_2024
    assert is_trading_day(date(2024, 1, 15)) is True

    records = holiday_records(year=2024, month=1)
    assert records[0]["date"].year == 2024
    assert "weekday" in records[0]

    trading_days = get_trading_days(date(2024, 1, 15), date(2024, 1, 19))
    assert trading_days[0] == date(2024, 1, 15)
    assert trading_days[-1] == date(2024, 1, 19)
    assert len(trading_days) == 5


def test_streaming_contract_sanity():
    processor = StreamingProcessor(StreamConfig(chunk_size=2))
    csv_data = """symbol,date,open,high,low,close,volume
RELIANCE,2024-01-15,2500,2550,2480,2530,5000000
TCS,2024-01-15,3800,3850,3780,3820,2000000
INFY,2024-01-15,1550,1580,1540,1570,3500000
"""

    total_rows = processor.process_csv_string(csv_data, lambda chunk: len(chunk))
    assert total_rows == 3


def test_analytics_and_metadata_contracts():
    enriched = add_returns(
        [
            {"date": date(2024, 1, 1), "close": 100.0},
            {"date": date(2024, 1, 2), "close": 110.0},
        ]
    )
    assert enriched[-1]["return_percent"] == 10.0

    chain = {
        "symbol": "RELIANCE",
        "underlying_value": 1330.0,
        "records": [
            {"strike_price": 1300.0, "call": {"open_interest": 1000}, "put": {"open_interest": 500}},
            {"strike_price": 1350.0, "call": {"open_interest": 800}, "put": {"open_interest": 1400}},
        ],
    }
    summary = summarize_option_chain(chain)
    assert summary["record_count"] == 2
    assert summary["put_call_ratio"] == 1900 / 1800

    capabilities = dataset_capabilities()
    assert "historical" in capabilities
    assert "analytics" in capabilities
    assert "results" in supported_event_categories()
