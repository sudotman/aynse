"""Deterministic contracts for historical public APIs."""

from __future__ import annotations

from datetime import date

import pytest

from aynse.nse import history
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
