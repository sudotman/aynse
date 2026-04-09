"""
Dataset metadata and discovery helpers for the standardized aynse API.
"""

from __future__ import annotations

from typing import Any

from .nse.archives import NSEIndices


SUPPORTED_DERIVATIVE_INSTRUMENTS = [
    {"code": "FUTIDX", "label": "Index futures", "market": "derivatives"},
    {"code": "FUTSTK", "label": "Stock futures", "market": "derivatives"},
    {"code": "OPTIDX", "label": "Index options", "market": "derivatives"},
    {"code": "OPTSTK", "label": "Stock options", "market": "derivatives"},
]


SUPPORTED_EVENT_TYPES = [
    "results",
    "dividend",
    "split",
    "bonus",
    "rights",
    "board_meeting",
    "compliance",
    "general",
]


def supported_indices() -> list[dict[str, str]]:
    def _label(code: str) -> str:
        return code.replace("nifty", "NIFTY ").replace("_", "").strip().upper()

    values = NSEIndices.get_indices_without_underscores() + NSEIndices.get_indices_with_underscores()
    return [
        {"code": value, "label": _label(value)}
        for value in sorted(values)
    ]


def supported_instruments() -> list[dict[str, str]]:
    return list(SUPPORTED_DERIVATIVE_INSTRUMENTS)


def supported_event_categories() -> list[str]:
    return list(SUPPORTED_EVENT_TYPES)


def dataset_capabilities() -> dict[str, Any]:
    return {
        "historical": {
            "datasets": ["stock", "index", "derivatives", "index_pe"],
            "accepted_dates": "date | datetime | 'YYYY-MM-DD'",
            "outputs": ["records", "dataframe", "save"],
        },
        "archives": {
            "datasets": [
                "bhavcopy",
                "full_bhavcopy",
                "bhavcopy_fo",
                "bhavcopy_index",
                "bulk_deals",
                "index_constituents",
            ],
            "outputs": ["records", "dataframe", "save"],
        },
        "live": {
            "datasets": [
                "quote",
                "trade_info",
                "market_status",
                "option_chain",
                "announcements",
                "corporate_actions",
                "results_calendar",
            ],
            "outputs": ["records", "summary", "dict"],
        },
        "analytics": {
            "datasets": [
                "returns",
                "rolling_volatility",
                "drawdown",
                "gap_metrics",
                "volume_metrics",
                "option_chain_summary",
                "event_window",
            ],
        },
        "metadata": {
            "supported_indices": supported_indices(),
            "supported_instruments": supported_instruments(),
            "supported_event_categories": supported_event_categories(),
        },
    }

