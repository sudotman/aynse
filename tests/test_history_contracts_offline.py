"""Deterministic contracts for historical public APIs."""

from __future__ import annotations

from datetime import date

import pytest

from aynse.nse import history
from aynse.nse.archives import expiry_dates
from aynse.nse.history import NSEHistory
from aynse.standard import UpstreamResponseError


def _history_without_network() -> NSEHistory:
    instance = NSEHistory.__new__(NSEHistory)
    instance.show_progress = False
    instance.workers = 1
    return instance


def test_derivatives_raw_futures_does_not_require_option_arguments(monkeypatch):
    instance = _history_without_network()
    monkeypatch.setattr(history.ut, "break_dates", lambda start, end: [(start, end)])
    monkeypatch.setattr(
        history.ut,
        "pool",
        lambda function, params, max_workers: [function(*item) for item in params],
    )
    monkeypatch.setattr(
        instance,
        "_derivatives",
        lambda *args: [
            {
                "FH_TIMESTAMP": "2026-07-15",
                "FH_SYMBOL": "NIFTY",
                "FH_INSTRUMENT": "FUTIDX",
                "FH_EXPIRY_DT": "2026-07-28",
                "FH_OPENING_PRICE": "24000",
                "FH_TRADE_HIGH_PRICE": "24200",
                "FH_TRADE_LOW_PRICE": "23900",
                "FH_CLOSING_PRICE": "24100",
                "FH_LAST_TRADED_PRICE": "24095.5",
                "FH_SETTLE_PRICE": "24110",
                "FH_MARKET_LOT": "75",
            }
        ],
    )

    rows = instance.derivatives_raw(
        "nifty",
        "2026-07-01",
        "2026-07-15",
        "2026-07-28",
        "futidx",
    )

    assert rows[0]["symbol"] == "NIFTY"
    assert rows[0]["instrument_type"] == "FUTIDX"
    assert rows[0]["option_type"] is None
    assert rows[0]["date"] == date(2026, 7, 15)
    assert rows[0]["expiry_date"] == rows[0]["expiry"] == date(2026, 7, 28)
    assert rows[0]["last_traded_price"] == rows[0]["last_price"] == 24095.5
    assert rows[0]["settlement_price"] == rows[0]["settle_price"] == 24110.0
    assert rows[0]["lot_size"] == rows[0]["market_lot"] == 75


def test_stock_records_expose_documented_key_and_legacy_alias():
    instance = _history_without_network()

    row = instance._canonical_stock_record(
        {
            "CH_TIMESTAMP": "2026-07-15",
            "CH_SYMBOL": "RELIANCE",
            "CH_SERIES": "EQ",
            "CH_LAST_TRADED_PRICE": "1500.25",
        }
    )

    assert row["last_traded_price"] == 1500.25
    assert row["last_price"] == row["last_traded_price"]


def test_bhavcopy_fallback_skips_known_exchange_holidays(
    monkeypatch,
    tmp_path,
):
    instance = _history_without_network()
    requested_dates = []

    def capture_pool(function, params, max_workers):
        requested_dates.extend(item[0] for item in params)
        return []

    monkeypatch.setenv("J_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(history.ut, "pool", capture_pool)

    rows = instance._stock_from_bhavcopy(
        "RELIANCE",
        date(2026, 1, 14),
        date(2026, 1, 16),
    )

    assert rows == []
    assert requested_dates == [date(2026, 1, 14), date(2026, 1, 16)]


@pytest.mark.parametrize(
    ("strike_price", "option_type", "message"),
    [
        (None, None, "required for options"),
        (24000, "CALL", "either 'CE' or 'PE'"),
        (0, "CE", "positive finite"),
        (float("nan"), "CE", "positive finite"),
        (float("inf"), "CE", "positive finite"),
        ("not-a-strike", "CE", "positive finite"),
    ],
)
def test_derivatives_raw_rejects_invalid_option_contract(
    strike_price,
    option_type,
    message,
):
    instance = _history_without_network()

    with pytest.raises(ValueError, match=message):
        instance.derivatives_raw(
            "NIFTY",
            "2026-07-01",
            "2026-07-15",
            "2026-07-28",
            "OPTIDX",
            strike_price,
            option_type,
        )


def test_derivatives_chunk_requires_data_list(monkeypatch):
    instance = _history_without_network()

    class Response:
        def json(self):
            return {"unexpected": []}

    monkeypatch.setattr(instance, "_get", lambda *args, **kwargs: Response())

    with pytest.raises(UpstreamResponseError, match="data list"):
        instance._derivatives(
            "NIFTY",
            date(2026, 7, 1),
            date(2026, 7, 15),
            date(2026, 7, 28),
            "FUTIDX",
        )


@pytest.mark.parametrize("function", [history.index_raw, history.index_pe_raw])
def test_index_history_rejects_reversed_ranges(function):
    with pytest.raises(ValueError, match="from_date"):
        function("NIFTY 50", "2026-07-15", "2026-07-01")


def test_expiry_dates_respect_the_2025_thursday_to_tuesday_transition():
    april = expiry_dates(
        date(2025, 4, 1),
        "OPTIDX",
        "NIFTY",
        months_ahead=1,
    )
    transition = expiry_dates(
        date(2025, 8, 25),
        "OPTIDX",
        "NIFTY",
        months_ahead=2,
    )

    assert april == [
        date(2025, 4, 3),
        date(2025, 4, 9),
        date(2025, 4, 17),
        date(2025, 4, 24),
    ]
    assert date(2025, 8, 28) in transition
    assert date(2025, 9, 2) in transition
    assert date(2025, 9, 4) not in transition


def test_expiry_dates_do_not_generate_weekly_futures_or_retired_weeklies():
    nifty_futures = expiry_dates(
        date(2026, 8, 1),
        "FUTIDX",
        "NIFTY",
        months_ahead=1,
    )
    banknifty_options = expiry_dates(
        date(2026, 8, 1),
        "OPTIDX",
        "BANKNIFTY",
        months_ahead=1,
    )

    assert nifty_futures == [date(2026, 8, 25)]
    assert banknifty_options == [date(2026, 8, 25)]


def test_expiry_dates_use_the_previous_trading_day_for_holidays():
    assert expiry_dates(
        date(2026, 3, 1),
        "FUTSTK",
        "RELIANCE",
        months_ahead=1,
    ) == [date(2026, 3, 30)]


@pytest.mark.parametrize("months_ahead", [0, -1, 1.5, True])
def test_expiry_dates_reject_invalid_horizon(months_ahead):
    with pytest.raises(ValueError, match="positive integer"):
        expiry_dates(date(2026, 1, 1), months_ahead=months_ahead)
