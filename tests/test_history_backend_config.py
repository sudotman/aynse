from datetime import date

import pytest

from aynse.nse.history import (
    NSEHistory,
    get_stock_history_backend,
    register_stock_history_provider,
    set_stock_history_backend,
)


@pytest.fixture(autouse=True)
def reset_history_backend_config():
    """Keep backend/provider globals isolated between tests."""
    original_backend = get_stock_history_backend()
    register_stock_history_provider(None)
    set_stock_history_backend("auto")
    try:
        yield
    finally:
        register_stock_history_provider(None)
        set_stock_history_backend(original_backend)


def test_set_get_stock_history_backend():
    set_stock_history_backend("bhavcopy")
    assert get_stock_history_backend() == "bhavcopy"

    set_stock_history_backend("nse")
    assert get_stock_history_backend() == "nse"

    with pytest.raises(ValueError):
        set_stock_history_backend("invalid")


def test_custom_provider_backend():
    def provider(symbol, from_date, to_date, series):
        return [{
            "CH_TIMESTAMP": "2024-01-31",
            "CH_SERIES": series,
            "CH_OPENING_PRICE": 100.0,
            "CH_TRADE_HIGH_PRICE": 110.0,
            "CH_TRADE_LOW_PRICE": 95.0,
            "CH_PREVIOUS_CLS_PRICE": 99.0,
            "CH_LAST_TRADED_PRICE": 105.0,
            "CH_CLOSING_PRICE": 106.0,
            "VWAP": 104.0,
            "CH_52WEEK_HIGH_PRICE": 120.0,
            "CH_52WEEK_LOW_PRICE": 80.0,
            "CH_TOT_TRADED_QTY": 1000,
            "CH_TOT_TRADED_VAL": 104000.0,
            "CH_TOTAL_TRADES": 10,
            "CH_SYMBOL": symbol,
        }]

    register_stock_history_provider(provider)
    set_stock_history_backend("custom")

    h = NSEHistory()
    rows = h.stock_raw("abc", date(2024, 1, 1), date(2024, 1, 31), "eq")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "ABC"
    assert rows[0]["series"] == "EQ"
    assert rows[0]["date"] == date(2024, 1, 31)


def test_custom_backend_without_provider_raises():
    set_stock_history_backend("custom")
    h = NSEHistory()
    with pytest.raises(RuntimeError):
        h.stock_raw("RELIANCE", date(2024, 1, 1), date(2024, 1, 31), "EQ")


def test_auto_fallback_to_bhavcopy_when_nse_empty(monkeypatch):
    h = NSEHistory()
    set_stock_history_backend("auto")

    monkeypatch.setattr(h, "_stock_from_nse_api", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        h,
        "_stock_from_bhavcopy",
        lambda *args, **kwargs: [{
            "CH_TIMESTAMP": "2024-01-31",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 1.0,
            "CH_TRADE_HIGH_PRICE": 1.0,
            "CH_TRADE_LOW_PRICE": 1.0,
            "CH_PREVIOUS_CLS_PRICE": 1.0,
            "CH_LAST_TRADED_PRICE": 1.0,
            "CH_CLOSING_PRICE": 1.0,
            "VWAP": 1.0,
            "CH_52WEEK_HIGH_PRICE": 1.0,
            "CH_52WEEK_LOW_PRICE": 1.0,
            "CH_TOT_TRADED_QTY": 1,
            "CH_TOT_TRADED_VAL": 1.0,
            "CH_TOTAL_TRADES": 1,
            "CH_SYMBOL": "RELIANCE",
        }],
    )

    rows = h.stock_raw("RELIANCE", date(2024, 1, 1), date(2024, 1, 31), "EQ")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "RELIANCE"
    assert rows[0]["close"] == 1.0
