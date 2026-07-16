"""
Higher-level analytics helpers built on canonical aynse records.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date
from math import isfinite, sqrt
from numbers import Real
from statistics import pstdev
from typing import Any, Iterable, Literal, Optional

from .standard import InputValidationError, parse_date_maybe, sort_by_date, to_float


def _copy_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def _to_finite_float(value: Any) -> Optional[float]:
    number = to_float(value)
    if number is None or not isfinite(number):
        return None
    return number


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise InputValidationError("window must be a positive integer")


def _validate_field_name(value: str, parameter: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError(f"{parameter} must be a non-empty string")
    return value.strip()


def _validate_positive_number(value: float, parameter: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InputValidationError(f"{parameter} must be a positive finite number")
    number = float(value)
    if not isfinite(number) or number <= 0:
        raise InputValidationError(f"{parameter} must be a positive finite number")
    return number


def add_returns(records: Iterable[dict[str, Any]], price_field: str = "close") -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    previous = None
    for record in ordered:
        price = _to_finite_float(record.get(price_field))
        if price is None or previous in (None, 0):
            record["return"] = None
            record["return_percent"] = None
        else:
            value = (price - previous) / previous
            record["return"] = value
            record["return_percent"] = value * 100.0
        if price is not None:
            previous = price
    return ordered


def add_rolling_volatility(
    records: Iterable[dict[str, Any]],
    window: int = 20,
    price_field: str = "close",
    annualization_period: float = 252,
) -> list[dict[str, Any]]:
    """Add annualized population volatility of the trailing simple returns.

    ``window`` counts returns, so at least ``window + 1`` valid prices are
    needed. ``annualization_period`` is normally 252 for daily market data,
    52 for weekly data, or 12 for monthly data.
    """
    _validate_window(window)
    price_field = _validate_field_name(price_field, "price_field")
    annualization = _validate_positive_number(
        annualization_period,
        "annualization_period",
    )

    ordered = add_returns(records, price_field=price_field)
    returns: list[float] = []
    for record in ordered:
        value = record.get("return")
        if isinstance(value, (int, float)):
            returns.append(float(value))
        if value is not None and len(returns) >= window:
            record["rolling_volatility"] = pstdev(returns[-window:]) * sqrt(annualization)
        else:
            record["rolling_volatility"] = None
    return ordered


def add_moving_average(
    records: Iterable[dict[str, Any]],
    window: int = 20,
    price_field: str = "close",
    kind: Literal["simple", "exponential"] = "simple",
    output_field: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Add a simple or exponential moving average to chronological records.

    Exponential averages use ``2 / (window + 1)`` as the smoothing factor and
    are seeded with the first full-window simple average. The default output
    field is ``moving_average``; provide ``output_field`` to keep multiple
    averages on the same records.
    """
    _validate_window(window)
    price_field = _validate_field_name(price_field, "price_field")
    if (
        not isinstance(kind, str)
        or kind.strip().lower() not in {"simple", "exponential"}
    ):
        raise InputValidationError("kind must be 'simple' or 'exponential'")
    normalized_kind = kind.strip().lower()
    field = _validate_field_name(
        "moving_average" if output_field is None else output_field,
        "output_field",
    )

    ordered = sort_by_date(_copy_records(records))
    prices: list[float] = []

    if normalized_kind == "simple":
        for record in ordered:
            price = _to_finite_float(record.get(price_field))
            if price is not None:
                prices.append(price)
            record[field] = (
                sum(prices[-window:]) / window
                if price is not None and len(prices) >= window
                else None
            )
        return ordered

    alpha = 2.0 / (window + 1.0)
    exponential_average: Optional[float] = None
    for record in ordered:
        price = _to_finite_float(record.get(price_field))
        if price is None:
            record[field] = None
            continue
        if exponential_average is None:
            prices.append(price)
            if len(prices) < window:
                record[field] = None
                continue
            exponential_average = sum(prices[-window:]) / window
        else:
            exponential_average = alpha * price + (1.0 - alpha) * exponential_average
        record[field] = exponential_average
    return ordered


def add_rsi(
    records: Iterable[dict[str, Any]],
    window: int = 14,
    price_field: str = "close",
) -> list[dict[str, Any]]:
    """Add Wilder's Relative Strength Index (RSI) in the range 0 to 100.

    The first RSI requires ``window`` price changes (``window + 1`` prices).
    A flat window is reported as the neutral value 50.
    """
    _validate_window(window)
    price_field = _validate_field_name(price_field, "price_field")

    ordered = sort_by_date(_copy_records(records))
    previous_price: Optional[float] = None
    gains: list[float] = []
    losses: list[float] = []
    average_gain: Optional[float] = None
    average_loss: Optional[float] = None

    for record in ordered:
        price = _to_finite_float(record.get(price_field))
        if price is None:
            record["rsi"] = None
            continue
        if previous_price is None:
            previous_price = price
            record["rsi"] = None
            continue

        change = price - previous_price
        previous_price = price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if average_gain is None or average_loss is None:
            gains.append(gain)
            losses.append(loss)
            if len(gains) < window:
                record["rsi"] = None
                continue
            average_gain = sum(gains[-window:]) / window
            average_loss = sum(losses[-window:]) / window
        else:
            average_gain = ((window - 1) * average_gain + gain) / window
            average_loss = ((window - 1) * average_loss + loss) / window

        record["rsi"] = _rsi_value(average_gain, average_loss)
    return ordered


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_gain == 0.0 and average_loss == 0.0:
        return 50.0
    if average_loss == 0.0:
        return 100.0
    if average_gain == 0.0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def add_atr(
    records: Iterable[dict[str, Any]],
    window: int = 14,
) -> list[dict[str, Any]]:
    """Add Wilder's Average True Range (ATR) from ``high``, ``low``, and ``close``.

    The initial ATR is the mean of the first ``window`` true ranges. Later
    values use Wilder smoothing.
    """
    _validate_window(window)

    ordered = sort_by_date(_copy_records(records))
    previous_close: Optional[float] = None
    true_ranges: list[float] = []
    average_true_range: Optional[float] = None

    for record in ordered:
        high = _to_finite_float(record.get("high"))
        low = _to_finite_float(record.get("low"))
        close = _to_finite_float(record.get("close"))

        if high is None or low is None:
            record["atr"] = None
            if close is not None:
                previous_close = close
            continue

        candidates = [abs(high - low)]
        if previous_close is not None:
            candidates.extend((abs(high - previous_close), abs(low - previous_close)))
        true_range = max(candidates)

        if average_true_range is None:
            true_ranges.append(true_range)
            if len(true_ranges) < window:
                record["atr"] = None
            else:
                average_true_range = sum(true_ranges[-window:]) / window
                record["atr"] = average_true_range
        else:
            average_true_range = (
                (window - 1) * average_true_range + true_range
            ) / window
            record["atr"] = average_true_range

        if close is not None:
            previous_close = close
    return ordered


def add_bollinger_bands(
    records: Iterable[dict[str, Any]],
    window: int = 20,
    standard_deviations: float = 2.0,
    price_field: str = "close",
) -> list[dict[str, Any]]:
    """Add middle, upper, and lower Bollinger Bands.

    The middle band is a simple moving average. Band width uses population
    standard deviation over the same trailing window.
    """
    _validate_window(window)
    deviations = _validate_positive_number(
        standard_deviations,
        "standard_deviations",
    )
    price_field = _validate_field_name(price_field, "price_field")

    ordered = sort_by_date(_copy_records(records))
    prices: list[float] = []
    for record in ordered:
        price = _to_finite_float(record.get(price_field))
        if price is not None:
            prices.append(price)
        if price is None or len(prices) < window:
            record["bollinger_middle"] = None
            record["bollinger_upper"] = None
            record["bollinger_lower"] = None
            continue

        trailing = prices[-window:]
        middle = sum(trailing) / window
        width = pstdev(trailing) * deviations
        record["bollinger_middle"] = middle
        record["bollinger_upper"] = middle + width
        record["bollinger_lower"] = middle - width
    return ordered


def add_drawdown(records: Iterable[dict[str, Any]], price_field: str = "close") -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    peak: Optional[float] = None
    for record in ordered:
        price = _to_finite_float(record.get(price_field))
        if price is None:
            record["drawdown"] = None
            record["drawdown_percent"] = None
            continue
        peak = price if peak is None else max(peak, price)
        drawdown = price - peak
        record["drawdown"] = drawdown
        record["drawdown_percent"] = (drawdown / peak * 100.0) if peak else None
    return ordered


def add_gap_metrics(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    previous_close = None
    for record in ordered:
        open_price = _to_finite_float(record.get("open"))
        if open_price is None or previous_close in (None, 0):
            record["gap"] = None
            record["gap_percent"] = None
        else:
            gap = open_price - previous_close
            record["gap"] = gap
            record["gap_percent"] = (gap / previous_close) * 100.0
        close_price = _to_finite_float(record.get("close"))
        if close_price is not None:
            previous_close = close_price
    return ordered


def add_volume_metrics(records: Iterable[dict[str, Any]], window: int = 20) -> list[dict[str, Any]]:
    """Add trailing average volume and the current-volume ratio."""
    _validate_window(window)

    ordered = sort_by_date(_copy_records(records))
    volumes: list[float] = []
    for record in ordered:
        volume = _to_finite_float(record.get("volume"))
        if volume is not None and volume < 0:
            volume = None
        if volume is not None:
            volumes.append(volume)
        trailing = volumes[-window:] if volumes else []
        if trailing:
            average = sum(trailing) / len(trailing)
            record["average_volume"] = average
            record["volume_ratio"] = (volume / average) if volume is not None and average else None
        else:
            record["average_volume"] = None
            record["volume_ratio"] = None
    return ordered


def summarize_option_chain(chain: dict[str, Any]) -> dict[str, Any]:
    """Summarize positioning, liquidity, ATM volatility, and max pain.

    Max pain is the candidate strike with the lowest aggregate intrinsic-value
    payout at expiry, weighted by open interest. The calculation assumes the
    supplied records belong to one expiry, as canonical live chain responses do.
    """
    records = chain.get("records", [])
    if not isinstance(records, list):
        records = []

    total_call_oi = 0
    total_put_oi = 0
    total_call_change_oi = 0
    total_put_change_oi = 0
    total_call_volume = 0
    total_put_volume = 0
    strongest_call = None
    strongest_put = None
    underlying = _to_finite_float(chain.get("underlying_value"))
    normalized_rows: list[dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        strike = _to_finite_float(record.get("strike_price"))
        call = record.get("call") if isinstance(record.get("call"), dict) else {}
        put = record.get("put") if isinstance(record.get("put"), dict) else {}
        call_oi = to_int_like(call.get("open_interest"))
        put_oi = to_int_like(put.get("open_interest"))
        call_change_oi = to_int_like(call.get("change_in_open_interest"))
        put_change_oi = to_int_like(put.get("change_in_open_interest"))
        call_volume = to_int_like(call.get("volume"))
        put_volume = to_int_like(put.get("volume"))
        total_call_oi += call_oi or 0
        total_put_oi += put_oi or 0
        total_call_change_oi += call_change_oi or 0
        total_put_change_oi += put_change_oi or 0
        total_call_volume += call_volume or 0
        total_put_volume += put_volume or 0

        if call_oi is not None and (
            strongest_call is None
            or call_oi > strongest_call["open_interest"]
        ):
            strongest_call = {"strike_price": strike, "open_interest": call_oi}
        if put_oi is not None and (
            strongest_put is None
            or put_oi > strongest_put["open_interest"]
        ):
            strongest_put = {"strike_price": strike, "open_interest": put_oi}

        if strike is not None:
            normalized_rows.append(
                {
                    "strike_price": strike,
                    "call_open_interest": max(call_oi or 0, 0),
                    "put_open_interest": max(put_oi or 0, 0),
                    "call_implied_volatility": _to_finite_float(
                        call.get("implied_volatility")
                    ),
                    "put_implied_volatility": _to_finite_float(
                        put.get("implied_volatility")
                    ),
                }
            )

    atm = None
    atm_implied_volatility = None
    if underlying is not None and normalized_rows:
        candidates = [row["strike_price"] for row in normalized_rows]
        if candidates:
            atm = min(candidates, key=lambda strike: abs(strike - underlying))
            atm_row = next(
                row for row in normalized_rows if row["strike_price"] == atm
            )
            atm_ivs = [
                value
                for value in (
                    atm_row["call_implied_volatility"],
                    atm_row["put_implied_volatility"],
                )
                if value is not None and value >= 0
            ]
            if atm_ivs:
                atm_implied_volatility = sum(atm_ivs) / len(atm_ivs)

    max_pain = None
    max_pain_payout = None
    if normalized_rows:
        payouts: list[tuple[float, float]] = []
        for settlement in sorted(
            {row["strike_price"] for row in normalized_rows}
        ):
            payout = 0.0
            for row in normalized_rows:
                strike = row["strike_price"]
                payout += row["call_open_interest"] * max(
                    settlement - strike,
                    0.0,
                )
                payout += row["put_open_interest"] * max(
                    strike - settlement,
                    0.0,
                )
            payouts.append((payout, settlement))
        max_pain_payout, max_pain = min(payouts)

    return {
        "symbol": chain.get("symbol"),
        "underlying_value": underlying,
        "record_count": len(records),
        "total_call_open_interest": total_call_oi,
        "total_put_open_interest": total_put_oi,
        "total_call_change_in_open_interest": total_call_change_oi,
        "total_put_change_in_open_interest": total_put_change_oi,
        "total_call_volume": total_call_volume,
        "total_put_volume": total_put_volume,
        "put_call_ratio": (total_put_oi / total_call_oi) if total_call_oi else None,
        "at_the_money_strike": atm,
        "at_the_money_implied_volatility": atm_implied_volatility,
        "max_pain": max_pain,
        "max_pain_payout": max_pain_payout,
        "strongest_call_wall": strongest_call,
        "strongest_put_wall": strongest_put,
    }


def analyze_event_window(
    price_records: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    window_before: int = 5,
    window_after: int = 5,
    alignment: Literal["exact", "next", "previous", "nearest"] = "next",
) -> list[dict[str, Any]]:
    """Measure returns around events, aligned to observable trading sessions.

    ``alignment="next"`` maps weekend/holiday events to the next available
    trading record. Use ``exact`` for the legacy exact-date behavior.
    """
    for value, name in (
        (window_before, "window_before"),
        (window_after, "window_after"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InputValidationError(f"{name} must be a non-negative integer")
    if alignment not in {"exact", "next", "previous", "nearest"}:
        raise InputValidationError(
            "alignment must be 'exact', 'next', 'previous', or 'nearest'"
        )

    ordered = sort_by_date(_copy_records(price_records))
    dated_records = [
        (parsed, record)
        for record in ordered
        if (parsed := parse_date_maybe(record.get("date"))) is not None
    ]
    if not dated_records:
        return []

    trading_dates = [item[0] for item in dated_records]
    ordered = [item[1] for item in dated_records]
    results: list[dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        event_date = parse_date_maybe(event.get("event_date") or event.get("date"))
        if event_date is None:
            continue
        idx = _aligned_trading_index(trading_dates, event_date, alignment)
        if idx is None:
            continue
        start = max(0, idx - window_before)
        stop = min(len(ordered), idx + window_after + 1)
        event_offset = idx - start
        window = ordered[start:stop]
        enriched = add_returns(window)
        results.append(
            {
                "symbol": event.get("symbol"),
                "event_type": event.get("event_type"),
                "event_date": event_date,
                "aligned_trading_date": trading_dates[idx],
                "alignment": alignment,
                "headline": event.get("headline") or event.get("subject"),
                "window_before": window_before,
                "window_after": window_after,
                "records": enriched,
                "event_day_return_percent": enriched[event_offset].get(
                    "return_percent"
                ),
                "pre_event_return_percent": _compound_return_percent(
                    enriched[:event_offset]
                ),
                "post_event_return_percent": _compound_return_percent(
                    enriched[event_offset + 1 :]
                ),
            }
        )
    return results


def _aligned_trading_index(
    trading_dates: list[date],
    event_date: date,
    alignment: str,
) -> Optional[int]:
    left = bisect_left(trading_dates, event_date)
    if left < len(trading_dates) and trading_dates[left] == event_date:
        return left
    if alignment == "exact":
        return None
    if alignment == "next":
        return left if left < len(trading_dates) else None
    previous = bisect_right(trading_dates, event_date) - 1
    if alignment == "previous":
        return previous if previous >= 0 else None
    if previous < 0:
        return left if left < len(trading_dates) else None
    if left >= len(trading_dates):
        return previous
    previous_distance = event_date - trading_dates[previous]
    next_distance = trading_dates[left] - event_date
    return previous if previous_distance < next_distance else left


def _compound_return_percent(records: list[dict[str, Any]]) -> Optional[float]:
    returns = [record.get("return") for record in records if isinstance(record.get("return"), (int, float))]
    if not returns:
        return None
    value = 1.0
    for item in returns:
        value *= 1.0 + float(item)
    return (value - 1.0) * 100.0


def to_int_like(value: Any) -> Optional[int]:
    if value in (None, "", "-", "--"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
