"""High-value analytics contracts for option positioning and event studies."""

from __future__ import annotations

from datetime import date

import pytest

from aynse.analytics import analyze_event_window, summarize_option_chain
from aynse.standard import InputValidationError


def test_option_chain_summary_calculates_positioning_and_max_pain() -> None:
    chain = {
        "symbol": "NIFTY",
        "underlying_value": 111,
        "records": [
            {
                "strike_price": 100,
                "call": {
                    "open_interest": 100,
                    "change_in_open_interest": 10,
                    "volume": 1_000,
                    "implied_volatility": 12,
                },
                "put": {
                    "open_interest": 10,
                    "change_in_open_interest": -2,
                    "volume": 500,
                    "implied_volatility": 14,
                },
            },
            {
                "strike_price": 110,
                "call": {
                    "open_interest": 50,
                    "change_in_open_interest": -5,
                    "volume": 800,
                    "implied_volatility": 10,
                },
                "put": {
                    "open_interest": 80,
                    "change_in_open_interest": 20,
                    "volume": 900,
                    "implied_volatility": 14,
                },
            },
            {
                "strike_price": 120,
                "call": {
                    "open_interest": 10,
                    "change_in_open_interest": 1,
                    "volume": 300,
                },
                "put": {
                    "open_interest": 100,
                    "change_in_open_interest": 30,
                    "volume": 1_100,
                },
            },
        ],
    }

    summary = summarize_option_chain(chain)

    assert summary["total_call_open_interest"] == 160
    assert summary["total_put_open_interest"] == 190
    assert summary["total_call_change_in_open_interest"] == 6
    assert summary["total_put_change_in_open_interest"] == 48
    assert summary["total_call_volume"] == 2_100
    assert summary["total_put_volume"] == 2_500
    assert summary["put_call_ratio"] == pytest.approx(190 / 160)
    assert summary["at_the_money_strike"] == 110
    assert summary["at_the_money_implied_volatility"] == 12
    assert summary["max_pain"] == 110
    assert summary["max_pain_payout"] == 2_000
    assert summary["strongest_call_wall"] == {
        "strike_price": 100.0,
        "open_interest": 100,
    }
    assert summary["strongest_put_wall"] == {
        "strike_price": 120.0,
        "open_interest": 100,
    }


def test_option_chain_summary_handles_empty_and_non_finite_values() -> None:
    summary = summarize_option_chain(
        {
            "symbol": "NIFTY",
            "underlying_value": float("inf"),
            "records": [{"strike_price": "bad", "call": None, "put": None}],
        }
    )

    assert summary["underlying_value"] is None
    assert summary["max_pain"] is None
    assert summary["at_the_money_strike"] is None
    assert summary["strongest_call_wall"] is None
    assert summary["strongest_put_wall"] is None


def test_event_window_accepts_iso_dates_and_aligns_weekend_to_next_session() -> None:
    prices = [
        {"date": "2026-07-10", "close": 100},  # Friday
        {"date": "2026-07-13", "close": 110},  # Monday
        {"date": "2026-07-14", "close": 121},
    ]
    events = [
        {
            "symbol": "RELIANCE",
            "event_type": "results",
            "event_date": "2026-07-11",  # Saturday
            "headline": "Quarterly results",
        }
    ]

    result = analyze_event_window(
        prices,
        events,
        window_before=1,
        window_after=1,
    )

    assert len(result) == 1
    event = result[0]
    assert event["event_date"] == date(2026, 7, 11)
    assert event["aligned_trading_date"] == date(2026, 7, 13)
    assert event["alignment"] == "next"
    assert event["headline"] == "Quarterly results"
    assert event["event_day_return_percent"] == pytest.approx(10)
    assert event["post_event_return_percent"] == pytest.approx(10)
    assert [row["date"] for row in event["records"]] == [
        "2026-07-10",
        "2026-07-13",
        "2026-07-14",
    ]


@pytest.mark.parametrize(
    ("alignment", "expected"),
    [
        ("exact", None),
        ("previous", date(2026, 7, 10)),
        ("nearest", date(2026, 7, 10)),
        ("next", date(2026, 7, 13)),
    ],
)
def test_event_window_alignment_modes(alignment, expected) -> None:
    result = analyze_event_window(
        [
            {"date": date(2026, 7, 10), "close": 100},
            {"date": date(2026, 7, 13), "close": 101},
        ],
        [{"event_date": date(2026, 7, 11)}],
        window_before=0,
        window_after=0,
        alignment=alignment,
    )

    if expected is None:
        assert result == []
    else:
        assert result[0]["aligned_trading_date"] == expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window_before": -1},
        {"window_after": True},
        {"alignment": "sometimes"},
    ],
)
def test_event_window_rejects_invalid_configuration(kwargs) -> None:
    with pytest.raises(InputValidationError):
        analyze_event_window(
            [{"date": "2026-07-10", "close": 100}],
            [{"event_date": "2026-07-10"}],
            **kwargs,
        )
