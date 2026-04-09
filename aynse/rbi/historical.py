"""
Canonical RBI policy-rate helpers.
"""

from __future__ import annotations

import logging
from datetime import date
from io import StringIO
from typing import Any, Dict, List

import pandas as pd
import requests

from ..standard import UpstreamResponseError, clean_text, snake_case, to_float

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def policy_rate_archive(n: int = 10) -> List[Dict[str, Any]]:
    """
    Return canonical RBI policy-rate snapshots.

    RBI's public policy-rate page now exposes a current snapshot instead of the
    older paginated archive used by the legacy implementation. We normalize that
    snapshot into a stable list-of-records contract.
    """
    url = "https://website.rbi.org.in/web/rbi/policy-rate-archive"
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}

    try:
        response = session.get(url, timeout=30, headers=headers)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to fetch RBI policy-rate page: %s", exc)
        raise UpstreamResponseError(f"Unable to fetch RBI policy-rate page: {exc}") from exc

    try:
        tables = pd.read_html(StringIO(response.text))
    except ValueError as exc:
        raise UpstreamResponseError("RBI policy-rate page did not contain readable tables") from exc

    if not tables:
        raise UpstreamResponseError("RBI policy-rate page returned no tables")

    rate_snapshot = _table_to_mapping(tables[0])
    liquidity_snapshot = _table_to_mapping(tables[1]) if len(tables) > 1 else {}

    record = {
        "snapshot_date": date.today(),
        "policy_repo_rate": to_float(rate_snapshot.get("policy_repo_rate")),
        "standing_deposit_facility_rate": to_float(rate_snapshot.get("standing_deposit_facility_rate")),
        "marginal_standing_facility_rate": to_float(rate_snapshot.get("marginal_standing_facility_rate")),
        "bank_rate": to_float(rate_snapshot.get("bank_rate")),
        "fixed_reverse_repo_rate": to_float(rate_snapshot.get("fixed_reverse_repo_rate")),
        "cash_reserve_ratio": to_float(liquidity_snapshot.get("crr")),
        "statutory_liquidity_ratio": to_float(liquidity_snapshot.get("slr")),
        "source": "rbi_policy_rate_page",
    }

    records = [record]
    return records[: max(1, int(n))]


def _table_to_mapping(frame: pd.DataFrame) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    for row in frame.itertuples(index=False):
        values = list(row)
        if len(values) < 2:
            continue
        key = snake_case(clean_text(values[0]) or "")
        value = clean_text(values[1])
        if not key:
            continue
        if value and value.startswith(":"):
            value = clean_text(value[1:])
        mapping[key] = value
    return mapping

