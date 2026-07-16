"""Deterministic contracts for dependency-free market indicators."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from math import sqrt

import pytest

import aynse
from aynse.analytics import (
    add_atr,
    add_bollinger_bands,
    add_moving_average,
    add_rolling_volatility,
    add_rsi,
    add_volume_metrics,
)
from aynse.catalog import dataset_capabilities
from aynse.standard import InputValidationError


pytestmark = pytest.mark.offline


def _price_records(prices: list[float]) -> list[dict[str, object]]:
    start = date(2024, 1, 1)
    return [
        {"date": start + timedelta(days=index), "close": price}
        for index, price in enumerate(prices)
    ]


def test_simple_moving_average_sorts_copies_and_has_full_window_warmup():
    source = list(reversed(_price_records([1.0, 2.0, 3.0, 4.0, 5.0])))
    snapshot = deepcopy(source)

    enriched = add_moving_average(source, window=3)

    assert [record["date"] for record in enriched] == sorted(
        record["date"] for record in source
    )
    assert [record["moving_average"] for record in enriched] == [
        None,
        None,
        2.0,
        3.0,
        4.0,
    ]
    assert source == snapshot
    assert not any(output is original for output in enriched for original in source)


def test_exponential_moving_average_uses_sma_seed_and_custom_field():
    enriched = add_moving_average(
        _price_records([10.0, 11.0, 12.0, 20.0, 19.0]),
        window=3,
        kind="exponential",
        output_field="ema_3",
    )

    assert [record["ema_3"] for record in enriched] == [
        None,
        None,
        11.0,
        15.5,
        17.25,
    ]


def test_rsi_uses_wilder_smoothing_and_handles_directional_edge_cases():
    mixed = add_rsi(_price_records([1.0, 2.0, 1.0, 2.0, 1.0]), window=2)
    assert [record["rsi"] for record in mixed] == [None, None, 50.0, 75.0, 37.5]

    rising = add_rsi(_price_records([1.0, 2.0, 3.0]), window=2)
    falling = add_rsi(_price_records([3.0, 2.0, 1.0]), window=2)
    flat = add_rsi(_price_records([2.0, 2.0, 2.0]), window=2)
    assert rising[-1]["rsi"] == 100.0
    assert falling[-1]["rsi"] == 0.0
    assert flat[-1]["rsi"] == 50.0


def test_atr_uses_true_range_then_wilder_smoothing():
    records = [
        {"date": date(2024, 1, 1), "high": 10.0, "low": 8.0, "close": 9.0},
        {"date": date(2024, 1, 2), "high": 12.0, "low": 9.0, "close": 11.0},
        {"date": date(2024, 1, 3), "high": 13.0, "low": 10.0, "close": 12.0},
        {"date": date(2024, 1, 4), "high": 14.0, "low": 13.0, "close": 13.5},
    ]

    enriched = add_atr(records, window=3)

    assert [record["atr"] for record in enriched[:2]] == [None, None]
    assert enriched[2]["atr"] == pytest.approx(8.0 / 3.0)
    assert enriched[3]["atr"] == pytest.approx(22.0 / 9.0)


def test_bollinger_bands_use_population_standard_deviation():
    enriched = add_bollinger_bands(_price_records([1.0, 2.0, 3.0, 4.0]), window=3)
    width = 2.0 * sqrt(2.0 / 3.0)

    for field in ("bollinger_middle", "bollinger_upper", "bollinger_lower"):
        assert [record[field] for record in enriched[:2]] == [None, None]
    assert enriched[2]["bollinger_middle"] == 2.0
    assert enriched[2]["bollinger_upper"] == pytest.approx(2.0 + width)
    assert enriched[2]["bollinger_lower"] == pytest.approx(2.0 - width)
    assert enriched[3]["bollinger_middle"] == 3.0


def test_rolling_volatility_uses_explicit_annualization_period():
    records = _price_records([100.0, 110.0, 99.0])

    custom = add_rolling_volatility(records, window=2, annualization_period=4)
    default = add_rolling_volatility(records, window=2)

    assert [record["rolling_volatility"] for record in custom[:2]] == [None, None]
    assert custom[-1]["rolling_volatility"] == pytest.approx(0.2)
    assert default[-1]["rolling_volatility"] == pytest.approx(0.1 * sqrt(252))


def test_volume_metrics_validates_window_and_preserves_partial_average_contract():
    records = [
        {"date": date(2024, 1, 1), "volume": 10},
        {"date": date(2024, 1, 2), "volume": 30},
        {"date": date(2024, 1, 3), "volume": 20},
    ]

    enriched = add_volume_metrics(records, window=2)

    assert [record["average_volume"] for record in enriched] == [10.0, 20.0, 25.0]
    assert [record["volume_ratio"] for record in enriched] == [1.0, 1.5, 0.8]


@pytest.mark.parametrize("window", [0, -1, True, 1.5, "2", None])
@pytest.mark.parametrize(
    "helper",
    [
        add_moving_average,
        add_rsi,
        add_atr,
        add_bollinger_bands,
        add_rolling_volatility,
        add_volume_metrics,
    ],
)
def test_indicator_windows_must_be_positive_integers(helper, window):
    with pytest.raises(InputValidationError, match="positive integer"):
        helper([], window=window)


@pytest.mark.parametrize("kind", [None, "", "weighted", 1])
def test_moving_average_rejects_unknown_kinds(kind):
    with pytest.raises(InputValidationError, match="simple.*exponential"):
        add_moving_average([], kind=kind)


def test_moving_average_rejects_blank_output_field():
    with pytest.raises(InputValidationError, match="output_field"):
        add_moving_average([], output_field="  ")


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "252"])
def test_volatility_rejects_invalid_annualization_period(value):
    with pytest.raises(InputValidationError, match="annualization_period"):
        add_rolling_volatility([], annualization_period=value)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "2"])
def test_bollinger_bands_reject_invalid_standard_deviations(value):
    with pytest.raises(InputValidationError, match="standard_deviations"):
        add_bollinger_bands([], standard_deviations=value)


@pytest.mark.parametrize(
    "enricher",
    [
        lambda rows: add_moving_average(rows, window=2),
        lambda rows: add_rsi(rows, window=2),
        lambda rows: add_atr(rows, window=2),
        lambda rows: add_bollinger_bands(rows, window=2),
    ],
    ids=["moving-average", "rsi", "atr", "bollinger-bands"],
)
def test_new_indicators_preserve_input_records_and_sort_output(enricher):
    source = [
        {"date": date(2024, 1, 2), "high": 3.0, "low": 1.0, "close": 2.0},
        {"date": date(2024, 1, 1), "high": 2.0, "low": 0.5, "close": 1.0},
        {"date": date(2024, 1, 3), "high": 4.0, "low": 2.0, "close": 3.0},
    ]
    snapshot = deepcopy(source)

    enriched = enricher(source)

    assert source == snapshot
    assert [record["date"] for record in enriched] == sorted(
        record["date"] for record in source
    )
    assert not any(output is original for output in enriched for original in source)


def test_indicator_exports_and_capability_catalog_are_discoverable():
    assert aynse.add_moving_average is add_moving_average
    assert aynse.add_rsi is add_rsi
    assert aynse.add_atr is add_atr
    assert aynse.add_bollinger_bands is add_bollinger_bands

    analytics = dataset_capabilities()["analytics"]["datasets"]
    assert {"moving_average", "rsi", "atr", "bollinger_bands"}.issubset(analytics)
