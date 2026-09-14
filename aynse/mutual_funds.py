"""Official AMFI mutual-fund NAV data and NAV-based analytics.

The Association of Mutual Funds in India (AMFI) publishes a complete latest-
NAV feed and a historical NAV report.  AMFI changed both report layouts in
2026, so this module discovers columns from the report header instead of
depending on a fixed column order.

Return calculations in this module are NAV returns.  They are not total
returns: cash distributions from IDCW options, loads, taxes, and investor cash
flows are intentionally outside the scope of the public AMFI NAV reports.
"""

from __future__ import annotations

import csv
import html
import json
import logging
import math
import re
import statistics
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .standard import (
    DateLike,
    DataUnavailableError,
    InputValidationError,
    UpstreamResponseError,
    coerce_date,
    dataframe_from_records,
    snake_case,
    sort_by_date,
    to_float,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

AMFI_LATEST_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
AMFI_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
AMFI_NAV_DOWNLOAD_PAGE_URL = "https://www.amfiindia.com/net-asset-value/nav-download"
AMFI_SOURCE = "AMFI"
AMFI_MAX_HISTORY_WINDOW_DAYS = 90

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 45.0)
_DEFAULT_USER_AGENT = "aynse/2.x (+https://github.com/sudotman/aynse)"
# The AMFI download page is the source of truth for these IDs.  A small local
# copy keeps history usable if the website shell is temporarily unavailable;
# the page is still refreshed and merged when reachable so newly added AMCs do
# not require a library release.  Historical/renamed fund houses are retained
# because older scheme records can refer to them.
_KNOWN_AMC_IDS: Dict[str, str] = {
    "360 ONE Mutual Fund": "62",
    "Abakkus Mutual Fund": "85",
    "Aditya Birla Sun Life Mutual Fund": "3",
    "AlphaGrep Mutual Fund": "86",
    "Angel One Mutual Fund": "80",
    "ASK MUTUAL FUND": "87",
    "Axis Mutual Fund": "53",
    "Bajaj Finserv Mutual Fund": "75",
    "Bandhan Mutual Fund": "48",
    "Bank of India Mutual Fund": "46",
    "Baroda BNP Paribas Mutual Fund": "4",
    "Canara Robeco Mutual Fund": "32",
    "Capitalmind Mutual Fund": "81",
    "Choice Mutual Fund": "84",
    "DSP Mutual Fund": "6",
    "Edelweiss Mutual Fund": "47",
    "Franklin Templeton Mutual Fund": "27",
    "Groww Mutual Fund": "63",
    "HDFC Mutual Fund": "9",
    "Helios Mutual Fund": "76",
    "HSBC Mutual Fund": "37",
    "ICICI Prudential Mutual Fund": "20",
    "IL&FS Mutual Fund (IDF)": "65",
    "Invesco Mutual Fund": "42",
    "ITI Mutual Fund": "70",
    "Jio BlackRock Mutual Fund": "82",
    "JM Financial Mutual Fund": "16",
    "Kotak Mahindra Mutual Fund": "17",
    "LIC Mutual Fund": "18",
    "Mahindra Manulife Mutual Fund": "69",
    "Mirae Asset Mutual Fund": "45",
    "Monarch Mutual Fund": "89",
    "Motilal Oswal Mutual Fund": "55",
    "Navi Mutual Fund": "54",
    "Nippon India Mutual Fund": "21",
    "NJ Mutual Fund": "73",
    "Old Bridge Mutual Fund": "78",
    "PGIM India Mutual Fund": "58",
    "PPFAS Mutual Fund": "64",
    "quant Mutual Fund": "13",
    "Quantum Mutual Fund": "41",
    "Samco Mutual Fund": "74",
    "SBI Mutual Fund": "22",
    "Shriram Mutual Fund": "67",
    "Sundaram Mutual Fund": "33",
    "Tata Mutual Fund": "25",
    "Taurus Mutual Fund": "26",
    "The Wealth Company Mutual Fund": "83",
    "Trust Mutual Fund": "72",
    "Unifi Mutual Fund": "79",
    "Union Mutual Fund": "61",
    "UTI Mutual Fund": "28",
    "WhiteOak Capital Mutual Fund": "71",
    "Zerodha Mutual Fund": "77",
}


def _normalized_lookup(value: Any) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _clean_optional_text(value: Any) -> Optional[str]:
    text = " ".join(str(value or "").replace("\ufeff", "").strip().split())
    if not text or text in {"-", "--"}:
        return None
    return text


def _clean_header(value: str) -> str:
    cleaned = value.replace("/", " ").replace("-", " ")
    return snake_case(cleaned)


def _section_metadata(line: str) -> Optional[Tuple[str, Optional[str]]]:
    match = re.match(
        r"^\s*(Open\s+Ended|Close\s+Ended|Interval\s+Fund)\s+Schemes?\s*\((.*?)\)\s*$",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    scheme_type = " ".join(match.group(1).split()).title()
    if scheme_type == "Open Ended":
        scheme_type = "Open Ended"
    elif scheme_type == "Close Ended":
        scheme_type = "Close Ended"
    else:
        scheme_type = "Interval Fund"
    category = _clean_optional_text(match.group(2))
    return scheme_type, category


def _display_name(raw_name: str, plan: Optional[str], option: Optional[str], *, is_nav_name: bool) -> str:
    name = " ".join(raw_name.split())
    if is_nav_name:
        return name
    additions: List[str] = []
    lowered = name.casefold()
    for value in (plan, option):
        if value and value.casefold() not in lowered:
            additions.append(value)
    return " - ".join([name] + additions)


def _parse_amfi_records(
    lines: Iterable[str],
    *,
    scheme_code: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Parse either current or legacy AMFI latest/history text layouts."""
    records: List[Dict[str, Any]] = []
    headers: Optional[List[str]] = None
    current_type: Optional[str] = None
    current_category: Optional[str] = None
    current_fund_house: Optional[str] = None
    target_code = str(scheme_code) if scheme_code is not None else None
    saw_header = False

    for raw_line in lines:
        line = str(raw_line).replace("\ufeff", "").replace("\r", "").strip()
        if not line:
            continue
        if line.casefold().startswith("scheme code;"):
            raw_headers = next(csv.reader([line], delimiter=";"))
            headers = [_clean_header(value) for value in raw_headers]
            saw_header = "scheme_code" in headers
            continue

        section = _section_metadata(line)
        if section is not None:
            current_type, current_category = section
            continue

        if headers is None:
            continue

        values = next(csv.reader([line], delimiter=";"))
        if not values or not values[0].strip().isdigit():
            # Non-data lines between a section heading and its records identify
            # the fund house.  HTML error pages never reach this branch because
            # they do not contain a recognized report header.
            if ";" not in line and "mutual fund" in line.casefold():
                current_fund_house = _clean_optional_text(html.unescape(line))
            continue

        row = {headers[index]: value.strip() for index, value in enumerate(values) if index < len(headers)}
        code = str(row.get("scheme_code") or "").strip()
        if target_code is not None and code != target_code:
            continue

        raw_name = _clean_optional_text(row.get("nav_name")) or _clean_optional_text(row.get("scheme_name"))
        nav = to_float(row.get("net_asset_value"))
        raw_date = _clean_optional_text(row.get("date"))
        if not code or raw_name is None or nav is None or nav <= 0 or raw_date is None:
            continue
        try:
            nav_date = coerce_date(raw_date, field_name="AMFI NAV date")
        except InputValidationError:
            continue

        plan = _clean_optional_text(row.get("plan"))
        option = _clean_optional_text(row.get("option"))
        is_nav_name = bool(_clean_optional_text(row.get("nav_name")))
        base_name = _clean_optional_text(row.get("scheme_name")) or raw_name
        records.append(
            {
                "scheme_code": code,
                "scheme_name": _display_name(raw_name, plan, option, is_nav_name=is_nav_name),
                "scheme_base_name": base_name,
                "fund_house": current_fund_house,
                "scheme_type": current_type,
                "scheme_category": current_category,
                "plan": plan,
                "option": option,
                "isin_growth": _clean_optional_text(
                    row.get("isin_div_payout_isin_growth")
                    or row.get("isin_div_payout_isin_growthisin_div_reinvestment")
                ),
                "isin_div_reinvestment": _clean_optional_text(row.get("isin_div_reinvestment")),
                "nav": float(nav),
                "date": nav_date,
                "source": AMFI_SOURCE,
            }
        )

    return records, saw_header


def _history_windows(from_date: date, to_date: date) -> List[Tuple[date, date]]:
    if from_date > to_date:
        raise InputValidationError("from_date must be on or before to_date")
    windows: List[Tuple[date, date]] = []
    cursor = from_date
    while cursor <= to_date:
        window_end = min(cursor + timedelta(days=AMFI_MAX_HISTORY_WINDOW_DAYS - 1), to_date)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def _build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session = requests.Session()
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "text/plain,text/html;q=0.8,*/*;q=0.5",
        }
    )
    return session


class AMFIMutualFunds:
    """Client for AMFI's official latest and historical NAV reports."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        *,
        timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
        latest_cache_seconds: int = 60 * 60,
        amc_cache_seconds: int = 24 * 60 * 60,
    ) -> None:
        self.session = session or _build_session()
        self.timeout = timeout
        self.latest_cache_seconds = max(0, int(latest_cache_seconds))
        self.amc_cache_seconds = max(0, int(amc_cache_seconds))
        # Cache state belongs to the client.  This matters for callers that use
        # a custom session (including tests) and prevents one client's response
        # from being returned through another client's transport or TTL policy.
        self._cache_lock = threading.Lock()
        self._latest_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
        self._amc_id_cache: Optional[Tuple[float, Dict[str, str]]] = None

    def _response_lines(self, url: str, *, params: Optional[Mapping[str, str]] = None) -> Iterable[str]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, stream=True)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UpstreamResponseError(f"Unable to fetch AMFI data: {exc}") from exc

        try:
            for raw_line in response.iter_lines(decode_unicode=False):
                if isinstance(raw_line, bytes):
                    yield raw_line.decode("utf-8-sig", errors="replace")
                else:
                    yield str(raw_line)
        except requests.RequestException as exc:
            raise UpstreamResponseError(f"Unable to read AMFI data: {exc}") from exc
        finally:
            response.close()

    def _fetch_latest(self) -> List[Dict[str, Any]]:
        records, saw_header = _parse_amfi_records(self._response_lines(AMFI_LATEST_NAV_URL))
        if not saw_header:
            raise UpstreamResponseError("AMFI latest-NAV response did not contain a recognized header")
        if not records:
            raise UpstreamResponseError("AMFI latest-NAV report contained no usable scheme records")
        return records

    def latest(self) -> List[Dict[str, Any]]:
        now = time.monotonic()
        with self._cache_lock:
            if self._latest_cache is not None and now < self._latest_cache[0]:
                return [dict(row) for row in self._latest_cache[1]]

        records = self._fetch_latest()
        with self._cache_lock:
            self._latest_cache = (time.monotonic() + self.latest_cache_seconds, records)
        return [dict(row) for row in records]

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        raw_query = " ".join(str(query or "").strip().split())
        if not raw_query:
            raise InputValidationError("query cannot be empty")
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise InputValidationError("limit must be an integer between 1 and 1000") from exc
        if not 1 <= normalized_limit <= 1000:
            raise InputValidationError("limit must be between 1 and 1000")

        normalized_query = _normalized_lookup(raw_query)
        query_tokens = [_normalized_lookup(token) for token in raw_query.split() if _normalized_lookup(token)]
        matches: List[Tuple[int, str, Dict[str, Any]]] = []
        for row in self.latest():
            code = str(row.get("scheme_code") or "")
            scheme_name = str(row.get("scheme_name") or "")
            searchable = " ".join(
                str(row.get(key) or "")
                for key in (
                    "scheme_code",
                    "scheme_name",
                    "scheme_base_name",
                    "fund_house",
                    "scheme_category",
                    "plan",
                    "option",
                    "isin_growth",
                    "isin_div_reinvestment",
                )
            )
            normalized_searchable = _normalized_lookup(searchable)
            if not query_tokens or not all(token in normalized_searchable for token in query_tokens):
                continue
            normalized_name = _normalized_lookup(scheme_name)
            if code == raw_query:
                rank = 0
            elif normalized_name.startswith(normalized_query):
                rank = 1
            elif normalized_query in normalized_name:
                rank = 2
            else:
                rank = 3
            item = _scheme_metadata(row)
            item["latest_nav"] = row.get("nav")
            item["latest_nav_date"] = _iso_date(row.get("date"))
            item["source"] = AMFI_SOURCE
            matches.append((rank, scheme_name.casefold(), item))

        matches.sort(key=lambda value: (value[0], value[1], value[2]["scheme_code"]))
        return [item for _, _, item in matches[:normalized_limit]]

    def _amc_ids(self) -> Dict[str, str]:
        now = time.monotonic()
        with self._cache_lock:
            if self._amc_id_cache is not None and now < self._amc_id_cache[0]:
                return dict(self._amc_id_cache[1])

        mappings = {_normalized_lookup(name): identifier for name, identifier in _KNOWN_AMC_IDS.items()}
        try:
            response = self.session.get(AMFI_NAV_DOWNLOAD_PAGE_URL, timeout=self.timeout)
            response.raise_for_status()
            page = response.text
            patterns = (
                r'\\"mfId\\":\\"(?P<id>\d+)\\",\\"mfName\\":\\"(?P<name>.*?)\\"',
                r'"mfId":"(?P<id>\d+)","mfName":"(?P<name>(?:[^"\\]|\\.)*)"',
            )
            for pattern in patterns:
                for match in re.finditer(pattern, page):
                    escaped_name = match.group("name")
                    try:
                        name = json.loads(f'"{escaped_name}"')
                    except (ValueError, TypeError):
                        name = escaped_name.replace(r"\u0026", "&")
                    mappings[_normalized_lookup(html.unescape(name))] = match.group("id")
        except requests.RequestException as exc:
            logger.warning("Unable to refresh AMFI AMC identifiers: %s", exc)

        with self._cache_lock:
            self._amc_id_cache = (time.monotonic() + self.amc_cache_seconds, mappings)
        return dict(mappings)

    def _latest_scheme(self, scheme_code: str) -> Dict[str, Any]:
        for row in self.latest():
            if row.get("scheme_code") == scheme_code:
                return row
        raise DataUnavailableError(
            f"Mutual-fund scheme {scheme_code} is not present in AMFI's current NAV report"
        )

    def history(
        self,
        scheme_code: Any,
        from_date: DateLike,
        to_date: DateLike,
    ) -> List[Dict[str, Any]]:
        code = _coerce_scheme_code(scheme_code)
        start = coerce_date(from_date, field_name="from_date")
        end = coerce_date(to_date, field_name="to_date")
        windows = _history_windows(start, end)
        latest_scheme = self._latest_scheme(code)
        fund_house = str(latest_scheme.get("fund_house") or "").strip()
        amc_id = self._amc_ids().get(_normalized_lookup(fund_house))
        if amc_id is None:
            # A newly launched AMC can appear in NAVAll before the AMFI download
            # page publishes its identifier.  Omitting ``mf`` asks the same
            # official endpoint for the all-AMC report, preserving correctness
            # at the cost of a larger streamed response.
            logger.warning(
                "AMFI AMC identifier unavailable for %s; using the all-AMC history report",
                fund_house or "the selected scheme",
            )

        records: List[Dict[str, Any]] = []
        for window_start, window_end in windows:
            params = {
                "frmdt": window_start.strftime("%d-%b-%Y"),
                "todt": window_end.strftime("%d-%b-%Y"),
            }
            if amc_id is not None:
                params["mf"] = amc_id
            chunk, saw_header = _parse_amfi_records(
                self._response_lines(AMFI_HISTORY_URL, params=params),
                scheme_code=code,
            )
            if not saw_header:
                raise UpstreamResponseError(
                    "AMFI historical-NAV response did not contain a recognized header"
                )
            records.extend(
                row
                for row in chunk
                if window_start <= coerce_date(row["date"], field_name="AMFI NAV date") <= window_end
            )

        # AMFI occasionally repeats a boundary record.  Date-key de-duplication
        # gives deterministic chronological output while preserving the newest
        # copy returned by the upstream report.
        by_date = {coerce_date(row["date"]).isoformat(): row for row in records}
        normalized = sort_by_date(by_date.values())
        for row in normalized:
            for key, value in latest_scheme.items():
                if key not in {"nav", "date", "source"} and value is not None:
                    row[key] = value
        return normalized

    def summary(
        self,
        scheme_code: Any,
        from_date: DateLike,
        to_date: DateLike,
    ) -> Dict[str, Any]:
        code = _coerce_scheme_code(scheme_code)
        start = coerce_date(from_date, field_name="from_date")
        end = coerce_date(to_date, field_name="to_date")
        records = self.history(code, start, end)
        if records:
            scheme = _scheme_metadata(records[-1])
        else:
            scheme = _scheme_metadata(self._latest_scheme(code))
        latest_date = max((_iso_date(row.get("date")) for row in records), default=None)
        return {
            "scheme": scheme,
            "nav_points": [
                {"date": _iso_date(row.get("date")), "nav": row.get("nav")}
                for row in records
            ],
            "metrics": analyze_mutual_fund(records),
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
            "as_of_date": latest_date,
            "source": AMFI_SOURCE,
            "analytics_basis": "NAV return; IDCW cash distributions, loads, taxes, and investor cash flows are excluded",
        }


def _coerce_scheme_code(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise InputValidationError("scheme_code must be a positive AMFI numeric code")
    return str(int(raw))


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return coerce_date(value).isoformat()
    except InputValidationError:
        return str(value)


def _scheme_metadata(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "scheme_code": str(record.get("scheme_code") or ""),
        "scheme_name": record.get("scheme_name"),
        "scheme_base_name": record.get("scheme_base_name"),
        "fund_house": record.get("fund_house"),
        "scheme_type": record.get("scheme_type"),
        "scheme_category": record.get("scheme_category"),
        "plan": record.get("plan"),
        "option": record.get("option"),
        "isin_growth": record.get("isin_growth"),
        "isin_div_reinvestment": record.get("isin_div_reinvestment"),
    }


def analyze_mutual_fund(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Calculate NAV return, volatility, and drawdown metrics.

    ``cagr_percent`` is deliberately omitted (``None``) for periods shorter
    than 365 days, where annualizing a short NAV move is usually misleading.
    """
    usable: List[Tuple[date, float]] = []
    for row in records:
        nav = to_float(row.get("nav"))
        try:
            nav_date = coerce_date(row.get("date"), field_name="NAV date")
        except InputValidationError:
            continue
        if nav is not None and nav > 0:
            usable.append((nav_date, float(nav)))
    usable.sort(key=lambda item: item[0])
    if not usable:
        return {
            "start_nav": None,
            "end_nav": None,
            "absolute_return_percent": None,
            "cagr_percent": None,
            "annualized_volatility_percent": None,
            "max_drawdown_percent": None,
            "observations": 0,
            "period_days": 0,
        }

    # De-duplicate dates before computing daily changes.
    unique = sorted(dict(usable).items())
    start_date, start_nav = unique[0]
    end_date, end_nav = unique[-1]
    period_days = (end_date - start_date).days
    absolute_return = ((end_nav / start_nav) - 1.0) * 100.0
    cagr: Optional[float] = None
    if period_days >= 365:
        cagr = ((end_nav / start_nav) ** (365.25 / period_days) - 1.0) * 100.0

    daily_returns = [
        (unique[index][1] / unique[index - 1][1]) - 1.0
        for index in range(1, len(unique))
        if unique[index - 1][1] > 0
    ]
    volatility: Optional[float] = None
    if len(daily_returns) >= 2:
        volatility = statistics.stdev(daily_returns) * math.sqrt(252.0) * 100.0

    peak = unique[0][1]
    max_drawdown = 0.0
    for _, nav in unique:
        peak = max(peak, nav)
        max_drawdown = min(max_drawdown, ((nav / peak) - 1.0) * 100.0)

    def _rounded(value: Optional[float]) -> Optional[float]:
        return round(value, 6) if value is not None and math.isfinite(value) else None

    return {
        "start_nav": start_nav,
        "end_nav": end_nav,
        "absolute_return_percent": _rounded(absolute_return),
        "cagr_percent": _rounded(cagr),
        "annualized_volatility_percent": _rounded(volatility),
        "max_drawdown_percent": _rounded(max_drawdown),
        "observations": len(unique),
        "period_days": period_days,
    }


_DEFAULT_CLIENT: Optional[AMFIMutualFunds] = None
_DEFAULT_CLIENT_LOCK = threading.Lock()


def _default_client() -> AMFIMutualFunds:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        with _DEFAULT_CLIENT_LOCK:
            if _DEFAULT_CLIENT is None:
                _DEFAULT_CLIENT = AMFIMutualFunds()
    return _DEFAULT_CLIENT


def mutual_fund_latest_raw() -> List[Dict[str, Any]]:
    """Return all schemes from AMFI's latest end-of-day NAV report."""
    return _default_client().latest()


def mutual_fund_search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search current AMFI schemes by name, code, ISIN, fund house, or category."""
    return _default_client().search(query, limit=limit)


def mutual_fund_history_raw(
    scheme_code: Any,
    from_date: DateLike,
    to_date: DateLike,
) -> List[Dict[str, Any]]:
    """Return chronological daily NAV records for one current AMFI scheme."""
    return _default_client().history(scheme_code, from_date, to_date)


def mutual_fund_history_df(scheme_code: Any, from_date: DateLike, to_date: DateLike):
    """Return historical mutual-fund NAV records as a pandas DataFrame."""
    return dataframe_from_records(mutual_fund_history_raw(scheme_code, from_date, to_date))


def mutual_fund_summary(
    scheme_code: Any,
    from_date: DateLike,
    to_date: DateLike,
) -> Dict[str, Any]:
    """Return scheme metadata, NAV points, and NAV-based risk/return metrics."""
    return _default_client().summary(scheme_code, from_date, to_date)


def compare_mutual_funds(
    scheme_codes: Sequence[Any],
    from_date: DateLike,
    to_date: DateLike,
) -> Dict[str, Any]:
    """Return comparable NAV summaries for multiple AMFI scheme codes."""
    if isinstance(scheme_codes, (str, bytes)):
        raise InputValidationError("scheme_codes must be a sequence of at least two codes")
    try:
        raw_codes = list(scheme_codes)
    except TypeError as exc:
        raise InputValidationError("scheme_codes must be a sequence of at least two codes") from exc
    codes = list(dict.fromkeys(_coerce_scheme_code(code) for code in raw_codes))
    if len(codes) < 2:
        raise InputValidationError("scheme_codes must contain at least two distinct codes")
    start = coerce_date(from_date, field_name="from_date")
    end = coerce_date(to_date, field_name="to_date")
    _history_windows(start, end)
    funds = [_default_client().summary(code, start, end) for code in codes]

    # Rebase every metric to NAV dates present for every selected fund.  Using
    # each scheme's independently available first/last date can create an
    # apples-to-oranges comparison (especially around launches and missing
    # observations), even when the requested range is identical.
    common_dates: Optional[set[str]] = None
    for fund in funds:
        dates = {
            str(point.get("date"))
            for point in fund.get("nav_points", [])
            if point.get("date") and to_float(point.get("nav")) is not None
        }
        if not dates:
            code = (fund.get("scheme") or {}).get("scheme_code", "unknown")
            raise DataUnavailableError(
                f"AMFI returned no NAV observations for scheme {code} in the requested period"
            )
        common_dates = dates if common_dates is None else common_dates & dates

    if not common_dates:
        raise DataUnavailableError("The selected schemes have no common NAV observation dates")

    common_start = min(common_dates)
    common_end = max(common_dates)
    aligned_funds: List[Dict[str, Any]] = []
    for fund in funds:
        points = [
            point
            for point in fund.get("nav_points", [])
            if str(point.get("date")) in common_dates
        ]
        aligned = dict(fund)
        aligned["nav_points"] = points
        aligned["metrics"] = analyze_mutual_fund(points)
        aligned["from_date"] = common_start
        aligned["to_date"] = common_end
        aligned["as_of_date"] = common_end
        aligned_funds.append(aligned)

    return {
        "funds": aligned_funds,
        "from_date": common_start,
        "to_date": common_end,
        "requested_from_date": start.isoformat(),
        "requested_to_date": end.isoformat(),
        "source": AMFI_SOURCE,
        "comparison_basis": "Paths and metrics use NAV observation dates shared by every selected scheme",
        "analytics_basis": "NAV return; IDCW cash distributions, loads, taxes, and investor cash flows are excluded",
    }


__all__ = [
    "AMFI_LATEST_NAV_URL",
    "AMFI_HISTORY_URL",
    "AMFI_MAX_HISTORY_WINDOW_DAYS",
    "AMFI_SOURCE",
    "AMFIMutualFunds",
    "analyze_mutual_fund",
    "compare_mutual_funds",
    "mutual_fund_history_df",
    "mutual_fund_history_raw",
    "mutual_fund_latest_raw",
    "mutual_fund_search",
    "mutual_fund_summary",
]
