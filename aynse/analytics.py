"""
Higher-level analytics helpers built on canonical aynse records.
"""

from __future__ import annotations

from math import sqrt
from statistics import pstdev
from typing import Any, Iterable, Optional

from .standard import sort_by_date, to_float, parse_date_maybe


def _copy_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def add_returns(records: Iterable[dict[str, Any]], price_field: str = "close") -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    previous = None
    for record in ordered:
        price = to_float(record.get(price_field))
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
) -> list[dict[str, Any]]:
    ordered = add_returns(records, price_field=price_field)
    returns: list[float] = []
    for record in ordered:
        value = record.get("return")
        if isinstance(value, (int, float)):
            returns.append(float(value))
        if len(returns) >= window:
            record["rolling_volatility"] = pstdev(returns[-window:]) * sqrt(window)
        else:
            record["rolling_volatility"] = None
    return ordered


def add_drawdown(records: Iterable[dict[str, Any]], price_field: str = "close") -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    peak: Optional[float] = None
    for record in ordered:
        price = to_float(record.get(price_field))
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
        open_price = to_float(record.get("open"))
        if open_price is None or previous_close in (None, 0):
            record["gap"] = None
            record["gap_percent"] = None
        else:
            gap = open_price - previous_close
            record["gap"] = gap
            record["gap_percent"] = (gap / previous_close) * 100.0
        close_price = to_float(record.get("close"))
        if close_price is not None:
            previous_close = close_price
    return ordered


def add_volume_metrics(records: Iterable[dict[str, Any]], window: int = 20) -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(records))
    volumes: list[float] = []
    for record in ordered:
        volume = to_float(record.get("volume"))
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
    records = chain.get("records", [])
    if not isinstance(records, list):
        records = []

    total_call_oi = 0
    total_put_oi = 0
    strongest_call = None
    strongest_put = None
    underlying = to_float(chain.get("underlying_value"))

    for record in records:
        strike = to_float(record.get("strike_price"))
        call = record.get("call") or {}
        put = record.get("put") or {}
        call_oi = to_int_like(call.get("open_interest"))
        put_oi = to_int_like(put.get("open_interest"))
        total_call_oi += call_oi or 0
        total_put_oi += put_oi or 0

        if strongest_call is None or (call_oi or 0) > (strongest_call["open_interest"] or 0):
            strongest_call = {"strike_price": strike, "open_interest": call_oi}
        if strongest_put is None or (put_oi or 0) > (strongest_put["open_interest"] or 0):
            strongest_put = {"strike_price": strike, "open_interest": put_oi}

    atm = None
    if underlying is not None and records:
        candidates = [to_float(row.get("strike_price")) for row in records]
        candidates = [strike for strike in candidates if strike is not None]
        if candidates:
            atm = min(candidates, key=lambda strike: abs(strike - underlying))

    return {
        "symbol": chain.get("symbol"),
        "underlying_value": underlying,
        "record_count": len(records),
        "total_call_open_interest": total_call_oi,
        "total_put_open_interest": total_put_oi,
        "put_call_ratio": (total_put_oi / total_call_oi) if total_call_oi else None,
        "at_the_money_strike": atm,
        "strongest_call_wall": strongest_call,
        "strongest_put_wall": strongest_put,
    }


def analyze_event_window(
    price_records: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    window_before: int = 5,
    window_after: int = 5,
) -> list[dict[str, Any]]:
    ordered = sort_by_date(_copy_records(price_records))
    if not ordered:
        return []

    indexed = {record.get("date"): i for i, record in enumerate(ordered)}
    results: list[dict[str, Any]] = []

    for event in events:
        event_date = parse_date_maybe(event.get("event_date") or event.get("date"))
        if event_date is None or event_date not in indexed:
            continue
        idx = indexed[event_date]
        window = ordered[max(0, idx - window_before): idx + window_after + 1]
        enriched = add_returns(window)
        results.append(
            {
                "symbol": event.get("symbol"),
                "event_type": event.get("event_type"),
                "event_date": event_date,
                "window_before": window_before,
                "window_after": window_after,
                "records": enriched,
                "pre_event_return_percent": _compound_return_percent(enriched[:window_before]),
                "post_event_return_percent": _compound_return_percent(enriched[window_before + 1 :]),
            }
        )
    return results


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

