"""NSE IPO issues, subscription data, and listing-day backtests.

The module answers one practical question: *if you had applied to an IPO and
been allotted, what would selling on listing day (or holding a little longer)
have returned?*  It combines three NSE sources:

* ``/api/public-past-issues`` – every public issue listed on NSE with its
  issue price, price band, bidding window, and listing date.
* ``/api/ipo-detail`` – the category-wise subscription book, lot size, issue
  structure, and retail discount for one issue.
* ``/api/historicalOR/cm/equity`` – daily OHLC/VWAP from the listing session
  onward (the listing-day ``previous_close`` is NSE's base price, which equals
  the issue price and is used as a cross-check).

Returns are measured against the issue price and exclude brokerage, taxes, and
the (small) opportunity cost of blocked ASBA funds.  The listing-day high is an
*oracle* exit: nobody reliably sells the exact high, so treat it as an upper
bound and VWAP as the realistic "sold sometime during the day" price.

Retail allotment odds for mainboard issues are estimated as
``1 / retail subscription``.  Because some retail applicants bid for more than
one lot, the true lottery odds are at least this high, so the estimate is
conservative.  NSE does not publish the category reservation for SME issues,
so SME allotment odds are left unset rather than guessed.
"""

from __future__ import annotations

import logging
import math
import re
import statistics
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .standard import (
    DataUnavailableError,
    DateLike,
    InputValidationError,
    clean_text,
    coerce_date,
    coerce_optional_date,
    dataframe_from_records,
    normalize_symbol,
    parse_date_maybe,
    to_float,
    to_int,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

NSE_SOURCE = "NSE"

PAST_ISSUES_PATH = "/api/public-past-issues"
CURRENT_ISSUES_PATH = "/api/ipo-current-issue"
UPCOMING_ISSUES_PATH = "/api/all-upcoming-issues"
ISSUE_DETAIL_PATH = "/api/ipo-detail"
PRICE_HISTORY_PATH = "/api/historicalOR/cm/equity"

BOARD_MAINBOARD = "mainboard"
BOARD_SME = "sme"
BOARD_REIT = "reit"
BOARD_INVIT = "invit"
BOARD_DEBT = "debt"
EQUITY_BOARDS: Tuple[str, ...] = (BOARD_MAINBOARD, BOARD_SME)
IPO_BOARDS: Tuple[str, ...] = (BOARD_MAINBOARD, BOARD_SME, BOARD_REIT, BOARD_INVIT, BOARD_DEBT)

_SECURITY_TYPE_BOARDS = {
    "EQ": BOARD_MAINBOARD,
    "BE": BOARD_MAINBOARD,
    "BZ": BOARD_MAINBOARD,
    "SME": BOARD_SME,
    "SM": BOARD_SME,
    "ST": BOARD_SME,
    "RR": BOARD_REIT,
    "IV": BOARD_INVIT,
}
_HISTORY_SERIES = {
    BOARD_MAINBOARD: ("EQ", "BE", "BZ", "SM", "ST", "SZ"),
    BOARD_SME: ("EQ", "BE", "BZ", "SM", "ST", "SZ"),
    BOARD_REIT: ("RR",),
    BOARD_INVIT: ("IV",),
}

#: Holding horizons after listing, in calendar days.  ``d1`` is special: it is
#: the next trading session.  Every other horizon exits at the close of the
#: first session on or after ``listing_date + days`` (the day you could sell
#: once the holding period is over), which keeps exchange holidays from
#: shifting a "one year" hold by a week.
IPO_HORIZONS: Tuple[Tuple[str, int], ...] = (
    ("d1", 1),
    ("w1", 7),
    ("m1", 30),
    ("m3", 91),
    ("m6", 182),
    ("y1", 365),
)
_HORIZON_DAYS = dict(IPO_HORIZONS)

#: Listing-day exit prices.
LISTING_EXITS: Tuple[str, ...] = ("open", "high", "low", "close", "vwap")

#: Every exit understood by :func:`summarize_ipo_backtest`, mapped to its record field.
IPO_EXIT_FIELDS: Dict[str, str] = {
    **{name: f"return_{name}_pct" for name in LISTING_EXITS},
    **{name: f"return_{name}_pct" for name, _ in IPO_HORIZONS},
    "best_m1": "return_max_m1_pct",
    "worst_m1": "return_min_m1_pct",
}

IPO_EXIT_LABELS: Dict[str, str] = {
    "open": "Sell at listing open",
    "high": "Sell at listing-day high (oracle)",
    "low": "Sell at listing-day low (worst case)",
    "close": "Sell at listing-day close",
    "vwap": "Sell at listing-day VWAP",
    "d1": "Hold 1 session",
    "w1": "Hold 1 week",
    "m1": "Hold 1 month",
    "m3": "Hold 3 months",
    "m6": "Hold 6 months",
    "y1": "Hold 1 year",
    "best_m1": "Best high within first month (oracle)",
    "worst_m1": "Worst low within first month",
}

SUBSCRIPTION_BUCKETS: Tuple[Tuple[str, float, float], ...] = (
    ("<1x", 0.0, 1.0),
    ("1-3x", 1.0, 3.0),
    ("3-10x", 3.0, 10.0),
    ("10-30x", 10.0, 30.0),
    ("30-100x", 30.0, 100.0),
    ("100x+", 100.0, math.inf),
)

ISSUE_SIZE_BUCKETS: Tuple[Tuple[str, float, float], ...] = (
    ("<₹25 cr", 0.0, 25.0),
    ("₹25-100 cr", 25.0, 100.0),
    ("₹100-500 cr", 100.0, 500.0),
    ("₹500-2,000 cr", 500.0, 2000.0),
    ("₹2,000 cr+", 2000.0, math.inf),
)

# One historical request returns at most ~70 sessions, so 90 calendar days
# (≤ 64 sessions) keeps each chunk complete.
_HISTORY_CHUNK_DAYS = 90
# Enough calendar days to find the first session after the one-year mark.
_HISTORY_WINDOW_DAYS = 380
# After this long a record is final even if a horizon never printed
# (suspension, delisting, or symbol reuse).
_FINAL_AFTER_DAYS = 420
# Real IPOs list within days of bidding closing (T+3 today, ~T+12 a decade
# ago). NSE's past-issues feed also carries later listings of companies that
# already trade (SME-to-mainboard migrations, relistings, direct listings);
# those list months or years after the dates shown and are not IPO debuts.
_MAX_DEBUT_GAP_DAYS = 30
_RECORD_SCHEMA_VERSION = 1

_CATEGORY_HEADER = "category"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _numbers(text: Any) -> List[float]:
    raw = str(text or "").replace(",", "")
    return [float(value) for value in re.findall(r"\d+(?:\.\d+)?", raw)]


def _share_count(text: str) -> Optional[int]:
    """Parse an Indian-grouped share count such as ``45,98,400``."""
    digits = text.replace(",", "").strip()
    return int(digits) if digits.isdigit() else None


def _board_for(security_type: Optional[str], series: Optional[str] = None) -> str:
    key = (security_type or series or "").strip().upper()
    return _SECURITY_TYPE_BOARDS.get(key, BOARD_DEBT)


def _parse_price_band(raw: Any) -> Tuple[Optional[float], Optional[float]]:
    values = [value for value in _numbers(raw) if value > 0]
    if not values:
        return None, None
    return min(values), max(values)


def _parse_issue_price(raw_price: Any, band_high: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    text = str(raw_price or "").strip()
    if text and not set(text) <= {"#", "-", " "}:
        values = [value for value in _numbers(text) if value > 0]
        if len(values) == 1:
            return values[0], "issue_price"
        if values:
            return max(values), "price_band_upper"
    if band_high is not None:
        return band_high, "price_band_upper"
    return None, None


def _normalize_past_issue(row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = clean_text(row.get("symbol"))
    if not symbol:
        return None
    security_type = (clean_text(row.get("securityType")) or "").upper()
    band_low, band_high = _parse_price_band(row.get("priceRange"))
    issue_price, price_source = _parse_issue_price(row.get("issuePrice"), band_high)
    return {
        "symbol": normalize_symbol(symbol),
        "company_name": clean_text(row.get("companyName") or row.get("company")),
        "security_type": security_type or None,
        "board": _board_for(security_type),
        "issue_start_date": parse_date_maybe(clean_text(row.get("ipoStartDate"))),
        "issue_end_date": parse_date_maybe(clean_text(row.get("ipoEndDate"))),
        "listing_date": parse_date_maybe(clean_text(row.get("listingDate"))),
        "issue_price": issue_price,
        "issue_price_source": price_source,
        "price_band_low": band_low,
        "price_band_high": band_high,
        "price_band_text": clean_text(row.get("priceRange")),
    }


def _normalize_live_issue(row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = clean_text(row.get("symbol"))
    if not symbol:
        return None
    series = (clean_text(row.get("series")) or "").upper()
    band_text = row.get("issuePrice") or row.get("priceBand")
    band_low, band_high = _parse_price_band(band_text)
    return {
        "symbol": normalize_symbol(symbol),
        "company_name": clean_text(row.get("companyName")),
        "series": series or None,
        "board": BOARD_SME if series == "SME" else _board_for(series),
        "status": clean_text(row.get("status")),
        "issue_start_date": parse_date_maybe(clean_text(row.get("issueStartDate"))),
        "issue_end_date": parse_date_maybe(clean_text(row.get("issueEndDate"))),
        "price_band_low": band_low,
        "price_band_high": band_high,
        "price_band_text": clean_text(band_text),
        "shares_offered": to_int(row.get("issueSize") or row.get("noOfSharesOffered")),
        "shares_bid": to_int(row.get("noOfsharesBid")),
        "subscription_total_x": to_float(row.get("noOfTime")),
        "lot_size": to_int(row.get("lotSize")),
    }


def _category_key(category: str, sr_no: str) -> Optional[str]:
    name = category.casefold()
    sr = sr_no.strip()
    if name == "total":
        return "total"
    if "qualified institutional" in name or sr == "1":
        return "qib"
    if "more than ten lakh" in name or sr == "2.1":
        return "nii_big"
    if "more than two lakh" in name or sr == "2.2":
        return "nii_small"
    if name.startswith("non institutional") or sr == "2":
        return "nii"
    if "retail individual" in name or name.startswith("individual investors") or sr == "3":
        return "retail"
    if "employee" in name:
        return "employee"
    if "shareholder" in name:
        return "shareholder"
    if "policyholder" in name or "policy holder" in name:
        return "policyholder"
    return None


def _parse_book(rows: Any) -> Dict[str, Dict[str, Optional[float]]]:
    """Normalize NSE's category rows (both consolidated and NSE-only shapes)."""
    book: Dict[str, Dict[str, Optional[float]]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        category = clean_text(row.get("category")) or ""
        if category.casefold() == _CATEGORY_HEADER:
            continue
        sr_no = str(row.get("srNo") or "")
        # Sub-rows such as "1(a) FIIs" are informational breakdowns.
        if "(" in sr_no:
            continue
        key = _category_key(category, sr_no)
        if key is None or key in book:
            continue
        book[key] = {
            "shares_offered": to_float(row.get("noOfShareOffered") or row.get("noOfSharesOffered")),
            "shares_bid": to_float(row.get("noOfSharesBid") or row.get("noOfsharesBid") or row.get("noOfshareBid")),
            "times": to_float(row.get("noOfTotalMeant") or row.get("noOfTime")),
            "applications": to_float(row.get("noofapplication")),
        }
    return book


def _book_has_multiples(book: Mapping[str, Mapping[str, Optional[float]]]) -> bool:
    total = book.get("total") or {}
    return bool((total.get("times") or 0) > 0 and (total.get("shares_offered") or 0) > 0)


def _parse_issue_structure(text: Optional[str]) -> Dict[str, Optional[int]]:
    """Extract total, market-maker, and anchor share counts from issue-size prose."""
    if not text:
        return {"total_shares": None, "market_maker_shares": None, "anchor_shares": None}
    lowered = text.casefold()
    # "45,98,400 equity shares", "37,50,400 fresh equity shares"; the qualifier
    # list is closed so rupee amounts ("Rs. 1,000 crore of shares") never match.
    shares = r"([\d,]{3,})\s*(?:(?:fresh|new|equity|ordinary|fully|paid[- ]up)\s+){0,3}shares"
    total = None
    match = re.search(shares, lowered)
    if match:
        total = _share_count(match.group(1))
    market_maker = None
    match = re.search(r"market\s*maker[^\d\[]{0,60}?" + shares, lowered)
    if match:
        market_maker = _share_count(match.group(1))
    anchor = None
    match = re.search(r"anchor[^\d\[]{0,60}?" + shares, lowered)
    if match:
        anchor = _share_count(match.group(1))
    return {"total_shares": total, "market_maker_shares": market_maker, "anchor_shares": anchor}


def _parse_retail_discount(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"(?:rs\.?|₹|inr)\s*([\d.]+)[^;]*?retail", text, flags=re.IGNORECASE)
    if not match:
        return None
    value = to_float(match.group(1))
    return value if value and value > 0 else None


def _first_int(text: Optional[str]) -> Optional[int]:
    values = _numbers(text)
    return int(values[0]) if values and values[0] >= 1 else None


def _issue_info(payload: Mapping[str, Any]) -> Dict[str, str]:
    info = payload.get("issueInfo") if isinstance(payload, Mapping) else None
    rows = info.get("dataList") if isinstance(info, Mapping) else None
    values: Dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        title = clean_text(row.get("title"))
        value = clean_text(row.get("value"))
        if title and value is not None:
            values.setdefault(title.rstrip(":").strip().casefold(), value.strip('"').strip())
    return values


def _normalize_detail(symbol: str, payload: Mapping[str, Any], board_hint: Optional[str]) -> Dict[str, Any]:
    meta = payload.get("metaInfo") if isinstance(payload.get("metaInfo"), Mapping) else {}
    info = _issue_info(payload)
    segment = (clean_text(meta.get("segment")) or "").upper()
    board = board_hint or (BOARD_SME if segment == "SME" else BOARD_MAINBOARD)

    active = payload.get("activeCat") if isinstance(payload.get("activeCat"), Mapping) else {}
    consolidated = _parse_book(active.get("dataList"))
    nse_only = _parse_book(payload.get("bidDetails"))
    structure = _parse_issue_structure(info.get("issue size"))

    subscription: Dict[str, Optional[float]] = {}
    source: Optional[str] = None
    book_shares: Optional[float] = None
    if board != BOARD_SME and _book_has_multiples(consolidated):
        source = "consolidated"
        for key, row in consolidated.items():
            subscription[key] = row.get("times")
        book_shares = (consolidated.get("total") or {}).get("shares_offered")
    elif board != BOARD_SME and _book_has_multiples(nse_only):
        source = "nse_only"
        for key, row in nse_only.items():
            subscription[key] = row.get("times")
        book_shares = (nse_only.get("total") or {}).get("shares_offered")
    elif board == BOARD_SME:
        # SME books carry bid quantities but not the reservation per category.
        total_bid = (nse_only.get("total") or {}).get("shares_bid")
        if not total_bid:
            total_bid = sum((row.get("shares_bid") or 0.0) for key, row in nse_only.items() if key != "total") or None
        total_shares = structure["total_shares"]
        if total_shares:
            net = total_shares - (structure["market_maker_shares"] or 0) - (structure["anchor_shares"] or 0)
            if net > 0:
                book_shares = float(net)
        if total_bid and book_shares:
            subscription["total"] = total_bid / book_shares
            source = "nse_book_estimate"

    applications = {
        key: row.get("applications")
        for key, row in nse_only.items()
        if row.get("applications")
    }
    lot_size = _first_int(
        info.get("bid lot") or info.get("minimum order quantity") or info.get("lot size") or info.get("market lot")
    )
    lots_per_application = 1
    for row in payload.get("bidDetails") or []:
        if isinstance(row, Mapping) and "bidding for 2 lots" in str(row.get("category") or "").casefold():
            lots_per_application = 2
            break
    issue_type_text = (info.get("issue type") or "").casefold()
    issue_type = None
    if "book" in issue_type_text:
        issue_type = "book_building"
    elif "fixed" in issue_type_text:
        issue_type = "fixed_price"

    qib_offered = (consolidated.get("qib") or nse_only.get("qib") or {}).get("shares_offered")

    return {
        "symbol": normalize_symbol(symbol),
        "company_name": clean_text(payload.get("companyName") or meta.get("companyName")),
        "board": board,
        "industry": clean_text(meta.get("industry")),
        "isin": clean_text(meta.get("isin")),
        "listing_date": parse_date_maybe(meta.get("listingDate")),
        "active_series": list(meta.get("activeSeries") or []),
        "issue_type": issue_type,
        "issue_size_text": info.get("issue size"),
        "price_range_text": info.get("price range") or info.get("issue price"),
        "face_value_text": info.get("face value"),
        "discount_text": info.get("discount"),
        "retail_discount": _parse_retail_discount(info.get("discount")),
        "lot_size": lot_size,
        "lots_per_application": lots_per_application,
        "min_application_qty": lot_size * lots_per_application if lot_size else None,
        "lead_managers": info.get("book running lead managers"),
        "registrar": info.get("name of the registrar"),
        "subscription": subscription,
        "subscription_source": source,
        "book_shares": book_shares,
        "qib_book_shares": qib_offered,
        "structure": structure,
        "applications": applications,
        "categories": {
            "consolidated": consolidated,
            "nse": nse_only,
        },
        "source": NSE_SOURCE,
    }


def _history_row(row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    day = parse_date_maybe(row.get("CH_TIMESTAMP") or row.get("mTIMESTAMP"))
    close = to_float(row.get("CH_CLOSING_PRICE"))
    if day is None or close is None:
        return None
    return {
        "date": day,
        "series": clean_text(row.get("CH_SERIES")),
        "open": to_float(row.get("CH_OPENING_PRICE")),
        "high": to_float(row.get("CH_TRADE_HIGH_PRICE")),
        "low": to_float(row.get("CH_TRADE_LOW_PRICE")),
        "close": close,
        "previous_close": to_float(row.get("CH_PREVIOUS_CLS_PRICE")),
        "vwap": to_float(row.get("VWAP")),
        "volume": to_int(row.get("CH_TOT_TRADED_QTY")),
        "turnover": to_float(row.get("CH_TOT_TRADED_VAL")),
        "trades": to_int(row.get("CH_TOTAL_TRADES")),
    }


def _pct(price: Optional[float], base: Optional[float]) -> Optional[float]:
    if price is None or base is None or base <= 0:
        return None
    return round((price / base - 1.0) * 100.0, 4)


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = parse_date_maybe(value)
    return parsed.isoformat() if parsed else None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Listing performance
# ---------------------------------------------------------------------------

def analyze_listing_performance(
    rows: Sequence[Mapping[str, Any]],
    listing_date: DateLike,
    issue_price: Optional[float],
    *,
    fallback_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute listing-day and post-listing returns from daily rows.

    ``rows`` are chronological daily bars (``date/open/high/low/close/vwap``).
    The first bar on or after ``listing_date`` is the listing session.  If
    ``issue_price`` is missing, the listing session's ``previous_close`` (NSE's
    IPO base price) is used instead, then ``fallback_price``.
    """
    listed_on = coerce_date(listing_date, "listing_date")
    bars = sorted(
        (dict(row) for row in rows if parse_date_maybe(row.get("date")) and parse_date_maybe(row.get("date")) >= listed_on),
        key=lambda row: parse_date_maybe(row["date"]),
    )
    result: Dict[str, Any] = {
        "has_listing_data": False,
        "listing_session_date": None,
        "listing_series": None,
        "listing_base_price": None,
        "issue_price_used": issue_price,
        "sessions_observed": len(bars),
        "data_as_of": _iso(bars[-1]["date"]) if bars else None,
    }
    if not bars:
        return result
    first = bars[0]
    base_price = to_float(first.get("previous_close"))
    price = issue_price if issue_price and issue_price > 0 else (base_price if base_price and base_price > 0 else fallback_price)
    result.update(
        {
            "has_listing_data": True,
            "listing_session_date": _iso(first["date"]),
            "listing_series": first.get("series"),
            "listing_base_price": base_price,
            "issue_price_used": price,
        }
    )
    listing = {name: to_float(first.get(name)) for name in LISTING_EXITS}
    for name in LISTING_EXITS:
        result[f"listing_{name}"] = listing[name]
        result[f"return_{name}_pct"] = _pct(listing[name], price)
    result["listing_volume"] = to_int(first.get("volume"))
    result["listing_turnover"] = to_float(first.get("turnover"))
    result["listing_trades"] = to_int(first.get("trades"))
    result["close_vs_open_pct"] = _pct(listing["close"], listing["open"])
    result["high_vs_open_pct"] = _pct(listing["high"], listing["open"])
    result["low_vs_open_pct"] = _pct(listing["low"], listing["open"])
    high, low, close = listing["high"], listing["low"], listing["close"]
    result["closed_at_high"] = bool(high and close and close >= high * 0.999)
    result["closed_at_low"] = bool(low and close and close <= low * 1.001 and high and high > low)
    result["listing_range_pct"] = _pct(high, low)

    bar_dates = [parse_date_maybe(bar["date"]) for bar in bars]
    for name, days in IPO_HORIZONS:
        exit_bar: Optional[Mapping[str, Any]] = None
        if name == "d1":
            exit_bar = bars[1] if len(bars) > 1 else None
        else:
            target = listed_on + timedelta(days=days)
            exit_bar = next((bar for bar, day in zip(bars, bar_dates) if day >= target), None)
        close_at = to_float(exit_bar.get("close")) if exit_bar else None
        result[f"close_{name}"] = close_at
        result[f"return_{name}_pct"] = _pct(close_at, price)
        result[f"date_{name}"] = _iso(exit_bar["date"]) if exit_bar else None

    month_end = listed_on + timedelta(days=_HORIZON_DAYS["m1"])
    month = [bar for bar, day in zip(bars, bar_dates) if day <= month_end]
    highs = [to_float(bar.get("high")) for bar in month if to_float(bar.get("high")) is not None]
    lows = [to_float(bar.get("low")) for bar in month if to_float(bar.get("low")) is not None]
    result["return_max_m1_pct"] = _pct(max(highs), price) if highs else None
    result["return_min_m1_pct"] = _pct(min(lows), price) if lows else None
    return result


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NSEIpo:
    """Client for NSE's public-issue endpoints and IPO listing backtests."""

    def __init__(self, client: Any = None) -> None:
        # ``client`` only needs ``get_json(path, params=None)``; tests inject fakes.
        self._client = client
        self._client_lock = threading.Lock()

    @property
    def client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from .nse.connection_pool import get_connection_pool

                    self._client = get_connection_pool().get_client("https://www.nseindia.com")
        return self._client

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.client.get_json(path, params=params or {})

    # -- issue lists -------------------------------------------------------

    def past_issues(
        self,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        boards: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return listed public issues, newest listing first.

        ``from_date``/``to_date`` filter by listing date.  ``boards`` defaults
        to every board; pass ``("mainboard", "sme")`` for equity IPOs only.
        """
        start = coerce_optional_date(from_date, "from_date")
        end = coerce_optional_date(to_date, "to_date")
        if start and end and start > end:
            raise InputValidationError("from_date must be on or before to_date")
        wanted = _coerce_boards(boards, default=IPO_BOARDS)
        payload = self._get(PAST_ISSUES_PATH)
        if not isinstance(payload, list):
            raise DataUnavailableError("NSE past-issues response did not contain a list")
        issues: List[Dict[str, Any]] = []
        seen: set[Tuple[str, Optional[date]]] = set()
        for row in payload:
            if not isinstance(row, Mapping):
                continue
            issue = _normalize_past_issue(row)
            if issue is None or issue["board"] not in wanted:
                continue
            listed = issue["listing_date"]
            if start and (listed is None or listed < start):
                continue
            if end and (listed is None or listed > end):
                continue
            key = (issue["symbol"], listed)
            if key in seen:
                continue
            seen.add(key)
            issues.append(issue)
        issues.sort(key=lambda item: (item["listing_date"] or date.max, item["symbol"]), reverse=True)
        return issues

    def current_issues(self) -> List[Dict[str, Any]]:
        """Return issues open for bidding with NSE's live total subscription."""
        payload = self._get(CURRENT_ISSUES_PATH)
        rows = [_normalize_live_issue(row) for row in payload if isinstance(row, Mapping)] if isinstance(payload, list) else []
        return [row for row in rows if row]

    def upcoming_issues(self) -> List[Dict[str, Any]]:
        """Return open (``Active``) and announced (``Forthcoming``) IPOs."""
        payload = self._get(UPCOMING_ISSUES_PATH, {"category": "ipo"})
        rows = [_normalize_live_issue(row) for row in payload if isinstance(row, Mapping)] if isinstance(payload, list) else []
        return [row for row in rows if row]

    def live_issues(self) -> List[Dict[str, Any]]:
        """Merge open and forthcoming IPOs with live subscription where NSE has it.

        The two NSE feeds each omit fields the other carries (SME rows in the
        current-issue feed have no price band), so non-empty values win.
        """
        merged: Dict[str, Dict[str, Any]] = {}
        for row in [*self.upcoming_issues(), *self.current_issues()]:
            target = merged.setdefault(row["symbol"], {})
            for key, value in row.items():
                if value is not None or key not in target:
                    target[key] = value
        if any(row.get("price_band_high") is None for row in merged.values()):
            # Open SME issues often appear in neither feed with a band, but
            # the past-issues list already carries them (unlisted, with band).
            try:
                bands = {
                    issue["symbol"]: issue
                    for issue in self.past_issues()
                    if issue.get("price_band_high") is not None
                }
            except Exception as exc:  # the band is cosmetic; never fail the list
                logger.debug("ipo_band_backfill_failed", exc_info=exc)
                bands = {}
            for symbol, row in merged.items():
                source = bands.get(symbol)
                if source and row.get("price_band_high") is None:
                    row["price_band_low"] = source["price_band_low"]
                    row["price_band_high"] = source["price_band_high"]
                    row["price_band_text"] = row.get("price_band_text") or source.get("price_band_text")
        return sorted(
            merged.values(),
            key=lambda row: (
                (row.get("status") or "").casefold() != "active",
                row.get("issue_end_date") or date.max,
                row["symbol"],
            ),
        )

    # -- per issue ---------------------------------------------------------

    def issue_detail(self, symbol: str, board: Optional[str] = None) -> Dict[str, Any]:
        """Return the subscription book, lot size, and issue structure."""
        symbol_name = normalize_symbol(symbol)
        if board is not None and board not in IPO_BOARDS:
            raise InputValidationError(f"board must be one of {', '.join(IPO_BOARDS)}")
        series = "SME" if board == BOARD_SME else "EQ"
        payload = self._get(ISSUE_DETAIL_PATH, {"symbol": symbol_name, "series": series})
        if not isinstance(payload, Mapping) or not payload:
            raise DataUnavailableError(f"NSE has no issue detail for {symbol_name}")
        return _normalize_detail(symbol_name, payload, board)

    def price_history(
        self,
        symbol: str,
        from_date: DateLike,
        to_date: DateLike,
        board: str = BOARD_MAINBOARD,
    ) -> List[Dict[str, Any]]:
        """Return chronological daily bars across every series the stock traded in.

        IPOs often list in a trade-for-trade series (``BE``/``ST``) and move
        later, so the request covers all equity series and keeps the most
        traded row per date.
        """
        symbol_name = normalize_symbol(symbol)
        start = coerce_date(from_date, "from_date")
        end = coerce_date(to_date, "to_date")
        if start > end:
            raise InputValidationError("from_date must be on or before to_date")
        series = _HISTORY_SERIES.get(board, _HISTORY_SERIES[BOARD_MAINBOARD])
        series_param = "[" + ",".join(f'"{item}"' for item in series) + "]"
        by_date: Dict[date, Dict[str, Any]] = {}
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(end, chunk_start + timedelta(days=_HISTORY_CHUNK_DAYS - 1))
            payload = self._get(
                PRICE_HISTORY_PATH,
                {
                    "symbol": symbol_name,
                    "series": series_param,
                    "from": chunk_start.strftime("%d-%m-%Y"),
                    "to": chunk_end.strftime("%d-%m-%Y"),
                },
            )
            rows = payload.get("data") if isinstance(payload, Mapping) else payload
            for raw in rows if isinstance(rows, list) else []:
                bar = _history_row(raw) if isinstance(raw, Mapping) else None
                if bar is None:
                    continue
                current = by_date.get(bar["date"])
                if current is None or (bar.get("volume") or 0) > (current.get("volume") or 0):
                    by_date[bar["date"]] = bar
            chunk_start = chunk_end + timedelta(days=1)
        return [by_date[day] for day in sorted(by_date)]

    def listing_performance(
        self,
        symbol: str,
        listing_date: DateLike,
        issue_price: Optional[float] = None,
        *,
        board: str = BOARD_MAINBOARD,
        include_path: bool = False,
        today: Optional[date] = None,
        fallback_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Return listing-day and post-listing returns versus the issue price.

        Pass ``issue_price=None`` to measure against NSE's listing base price,
        with ``fallback_price`` used only when the base price is missing.
        """
        listed_on = coerce_date(listing_date, "listing_date")
        end = min(today or date.today(), listed_on + timedelta(days=_HISTORY_WINDOW_DAYS))
        if end < listed_on:
            raise DataUnavailableError(f"{normalize_symbol(symbol)} has not listed yet")
        bars = self.price_history(symbol, listed_on, end, board=board)
        result = analyze_listing_performance(bars, listed_on, issue_price, fallback_price=fallback_price)
        if include_path:
            result["path"] = [
                {**bar, "date": _iso(bar["date"])}
                for bar in bars
            ]
        return result

    def backtest_record(
        self,
        issue: Mapping[str, Any],
        *,
        include_detail: bool = True,
        previous: Optional[Mapping[str, Any]] = None,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Build one JSON-ready backtest record for a past issue.

        ``previous`` is an earlier record for the same issue; its subscription
        detail is reused when present because the book is final at listing.
        """
        return build_ipo_record(self, issue, include_detail=include_detail, previous=previous, today=today)

    def backtest(
        self,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        boards: Optional[Iterable[str]] = EQUITY_BOARDS,
        *,
        existing: Optional[Iterable[Mapping[str, Any]]] = None,
        include_detail: bool = True,
        max_workers: int = 4,
        progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        failure_burst: int = 8,
        cooldown_seconds: float = 45.0,
        max_cooldowns: int = 6,
        today: Optional[date] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> List[Dict[str, Any]]:
        """Build backtest records for every listed issue in the window.

        Pass the records from a previous run as ``existing``: final records
        are reused untouched and only new or still-maturing issues hit NSE,
        which turns a full rebuild (thousands of requests) into a handful.

        NSE throttles sustained scraping by resetting connections, which then
        trips the HTTP client's circuit breaker.  Work is therefore dispatched
        at most ``max_workers`` at a time; after ``failure_burst`` consecutive
        network failures the builder drains, waits ``cooldown_seconds`` (longer
        each time), and resumes.  Records that failed on network errors are
        retried once; after ``max_cooldowns`` pauses the remaining issues are
        skipped (previous records are kept) rather than hammering NSE.
        """
        today = today or date.today()
        issues = [
            issue
            for issue in self.past_issues(from_date, to_date, boards)
            if issue["listing_date"] is not None and issue["listing_date"] <= today
        ]
        previous_by_key = {
            str(record.get("key")): dict(record)
            for record in existing or []
            if isinstance(record, Mapping) and record.get("key")
        }
        results: Dict[str, Dict[str, Any]] = {}
        pending: List[Tuple[Mapping[str, Any], Optional[Dict[str, Any]]]] = []
        for issue in issues:
            key = ipo_record_key(issue["symbol"], issue["listing_date"])
            previous = previous_by_key.get(key)
            if previous is not None and not ipo_record_needs_refresh(previous, today=today):
                # Derived money fields are cheap; recomputing keeps old caches
                # consistent with the current formulas without a refetch.
                _derive_fields(previous)
                results[key] = previous
            else:
                pending.append((issue, previous))

        total = len(issues)
        done = len(results)
        if pending:
            done = self._run_backtest_queue(
                pending,
                results,
                done=done,
                total=total,
                include_detail=include_detail,
                max_workers=max_workers,
                progress=progress,
                failure_burst=failure_burst,
                cooldown_seconds=cooldown_seconds,
                max_cooldowns=max_cooldowns,
                today=today,
                sleep=sleep,
            )
            for issue, previous in pending:
                key = ipo_record_key(issue["symbol"], issue["listing_date"])
                if key not in results and previous is not None:
                    results[key] = previous
        return sorted(results.values(), key=lambda row: (row.get("listing_date") or "", row.get("symbol") or ""), reverse=True)

    def _run_backtest_queue(
        self,
        pending: Sequence[Tuple[Mapping[str, Any], Optional[Dict[str, Any]]]],
        results: Dict[str, Dict[str, Any]],
        *,
        done: int,
        total: int,
        include_detail: bool,
        max_workers: int,
        progress: Optional[Callable[[int, int, Dict[str, Any]], None]],
        failure_burst: int,
        cooldown_seconds: float,
        max_cooldowns: int,
        today: date,
        sleep: Callable[[float], None],
    ) -> int:
        workers = max(1, min(int(max_workers), 16))
        queue = deque(pending)
        retried: set[str] = set()
        in_flight: Dict[Future, Tuple[Mapping[str, Any], Optional[Dict[str, Any]]]] = {}
        consecutive_failures = 0
        cooldowns = 0
        stopping = False

        def finish(record: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> None:
            nonlocal done
            # A refresh that failed on the network must not replace good data.
            if record.get("transient_error") and previous is not None and previous.get("has_listing_data"):
                record = previous
            results[str(record["key"])] = record
            done += 1
            if progress is not None:
                progress(done, total, record)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="aynse-ipo") as executor:
            while in_flight or (queue and not stopping):
                while queue and not stopping and len(in_flight) < workers:
                    issue, previous = queue.popleft()
                    future = executor.submit(
                        build_ipo_record,
                        self,
                        issue,
                        include_detail=include_detail,
                        previous=previous,
                        today=today,
                    )
                    in_flight[future] = (issue, previous)
                completed, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
                for future in completed:
                    issue, previous = in_flight.pop(future)
                    key = ipo_record_key(issue["symbol"], issue["listing_date"])
                    try:
                        record = future.result()
                    except Exception as exc:  # pragma: no cover - build_ipo_record traps errors
                        logger.warning("ipo_record_failed", extra={"symbol": issue["symbol"], "error": str(exc)})
                        continue
                    if record.get("transient_error"):
                        consecutive_failures += 1
                        if key not in retried and not stopping:
                            retried.add(key)
                            queue.append((issue, previous))
                            continue
                    else:
                        consecutive_failures = 0
                    finish(record, previous)
                if failure_burst and consecutive_failures >= failure_burst and not stopping:
                    if cooldowns >= max_cooldowns:
                        logger.warning("ipo_backtest_stopped", extra={"remaining": len(queue)})
                        stopping = True
                        continue
                    # Let requests already on the wire finish (they fail fast
                    # while the circuit is open), then give NSE room.
                    for future in list(in_flight):
                        future.exception()
                    cooldowns += 1
                    logger.warning("ipo_backtest_cooldown", extra={"seconds": cooldown_seconds * cooldowns})
                    sleep(cooldown_seconds * cooldowns)
                    # Nothing is in flight now, so a fresh transport and cookie
                    # set can replace a connection NSE has started resetting.
                    reset = getattr(self.client, "reset_session", None)
                    if callable(reset):
                        try:
                            reset()
                        except Exception as exc:  # pragma: no cover - best effort
                            logger.debug("ipo_session_reset_failed", exc_info=exc)
                    consecutive_failures = 0
        return done

    def report(self, symbol: str, listing_date: Optional[DateLike] = None) -> Dict[str, Any]:
        """Return one issue's record plus its full post-listing price path."""
        symbol_name = normalize_symbol(symbol)
        wanted = coerce_optional_date(listing_date, "listing_date")
        matches = [
            issue
            for issue in self.past_issues()
            if issue["symbol"] == symbol_name and (wanted is None or issue["listing_date"] == wanted)
        ]
        if not matches:
            raise DataUnavailableError(f"{symbol_name} is not in NSE's list of past public issues")
        issue = matches[0]
        record = build_ipo_record(self, issue, include_detail=True, include_path=True)
        return record


# ---------------------------------------------------------------------------
# Record building and freshness
# ---------------------------------------------------------------------------

def ipo_record_key(symbol: str, listing_date: Any) -> str:
    return f"{normalize_symbol(symbol)}:{_iso(listing_date) or 'unlisted'}"


def _horizon_due(listing: date, name: str, today: date) -> bool:
    # A weekend plus a holiday can push the exit session a few days out.
    days = 1 if name == "d1" else _HORIZON_DAYS[name]
    return today >= listing + timedelta(days=days + 4)


def ipo_record_needs_refresh(
    record: Mapping[str, Any],
    *,
    today: Optional[date] = None,
    min_interval_hours: float = 20.0,
) -> bool:
    """Return True when an existing record can gain data from a re-fetch."""
    if record.get("schema_version") != _RECORD_SCHEMA_VERSION:
        return True
    if record.get("is_final"):
        return False
    if record.get("transient_error"):
        # A network failure says nothing about the data; retry at the next run.
        return True
    today = today or date.today()
    fetched_at = record.get("fetched_at")
    if fetched_at:
        try:
            fetched = datetime.fromisoformat(str(fetched_at))
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            if _utc_now() - fetched < timedelta(hours=min_interval_hours):
                return False
        except ValueError:
            return True
    listing = parse_date_maybe(record.get("listing_date"))
    if listing is None:
        return False
    if not record.get("has_listing_data"):
        return listing <= today
    if record.get("detail_error") or not record.get("detail_fetched"):
        return True
    for name, _ in IPO_HORIZONS:
        if record.get(f"return_{name}_pct") is None and _horizon_due(listing, name, today):
            return True
    return False


def build_ipo_record(
    api: NSEIpo,
    issue: Mapping[str, Any],
    *,
    include_detail: bool = True,
    include_path: bool = False,
    previous: Optional[Mapping[str, Any]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Combine issue metadata, subscription detail, and listing performance."""
    today = today or date.today()
    symbol = normalize_symbol(issue["symbol"])
    board = issue.get("board") or BOARD_MAINBOARD
    listing = parse_date_maybe(issue.get("listing_date"))
    issue_end = parse_date_maybe(issue.get("issue_end_date"))
    record: Dict[str, Any] = {
        "schema_version": _RECORD_SCHEMA_VERSION,
        "key": ipo_record_key(symbol, listing),
        "symbol": symbol,
        "company_name": issue.get("company_name"),
        "board": board,
        "security_type": issue.get("security_type"),
        "issue_start_date": _iso(issue.get("issue_start_date")),
        "issue_end_date": _iso(issue_end),
        "listing_date": _iso(listing),
        "listing_year": listing.year if listing else None,
        "days_to_listing": (listing - issue_end).days if listing and issue_end else None,
        "issue_price": issue.get("issue_price"),
        "issue_price_source": issue.get("issue_price_source"),
        "price_band_low": issue.get("price_band_low"),
        "price_band_high": issue.get("price_band_high"),
        "source": NSE_SOURCE,
    }
    errors: List[str] = []
    transient = False

    detail: Optional[Dict[str, Any]] = None
    reuse_detail = bool(previous is not None and previous.get("detail_fetched") and not previous.get("detail_error"))
    if include_detail and not reuse_detail:
        try:
            detail = api.issue_detail(symbol, board=board)
        except Exception as exc:
            errors.append(f"detail: {exc}")
            record["detail_error"] = str(exc)
            transient = transient or _is_transient(exc)
    record["detail_fetched"] = detail is not None or reuse_detail
    if detail is not None:
        subscription = detail.get("subscription") or {}
        record.update(
            {
                "company_name": record["company_name"] or detail.get("company_name"),
                "industry": detail.get("industry"),
                "isin": detail.get("isin"),
                "issue_type": detail.get("issue_type"),
                "lot_size": detail.get("lot_size"),
                "lots_per_application": detail.get("lots_per_application"),
                "min_application_qty": detail.get("min_application_qty"),
                "retail_discount": detail.get("retail_discount"),
                "subscription_source": detail.get("subscription_source"),
                "book_shares": detail.get("book_shares"),
                "qib_book_shares": detail.get("qib_book_shares"),
                "anchor_shares": (detail.get("structure") or {}).get("anchor_shares"),
                "market_maker_shares": (detail.get("structure") or {}).get("market_maker_shares"),
                "applications_total": (detail.get("applications") or {}).get("total"),
                "applications_retail": (detail.get("applications") or {}).get("retail"),
                "lead_managers": detail.get("lead_managers"),
                "registrar": detail.get("registrar"),
            }
        )
        for key in ("total", "qib", "nii", "nii_big", "nii_small", "retail", "employee", "shareholder", "policyholder"):
            value = subscription.get(key)
            record[f"subscription_{key}_x"] = round(value, 4) if value is not None else None
    elif reuse_detail and previous is not None:
        for key, value in previous.items():
            if key.startswith("subscription_") or key in _DETAIL_FIELDS:
                record[key] = value

    performance: Dict[str, Any] = {}
    # A band-derived price is a guess; NSE's listing base price is the real one.
    known_price = None if record.get("issue_price_source") == "price_band_upper" else to_float(record.get("issue_price"))
    path: List[Dict[str, Any]] = []
    if listing is not None and listing <= today:
        try:
            performance = api.listing_performance(
                symbol,
                listing,
                known_price,
                board=board,
                include_path=True,
                today=today,
                fallback_price=to_float(record.get("issue_price")),
            )
            path = performance.pop("path", None) or []
        except Exception as exc:
            errors.append(f"history: {exc}")
            transient = transient or _is_transient(exc)

    base = performance.get("listing_base_price")
    if (
        base
        and known_price is not None
        and (record.get("days_to_listing") is None or record["days_to_listing"] <= _MAX_DEBUT_GAP_DAYS)
        and not _in_band(known_price, record)
        and _in_band(base, record)
    ):
        # The issue list's price is a clerical error (it sits outside the
        # issue's own band) while NSE's base price is in it: measure again.
        record["issue_price"] = base
        record["issue_price_source"] = "listing_base_price"
        performance = analyze_listing_performance(path, listing, base)
    record.update({key: value for key, value in performance.items() if key != "issue_price_used"})
    record.setdefault("has_listing_data", False)
    if include_path:
        record["path"] = path

    if record.get("issue_price") is None and base:
        record["issue_price"] = base
        record["issue_price_source"] = "listing_base_price"
    elif record.get("issue_price_source") == "price_band_upper" and base:
        record["issue_price"] = base
        record["issue_price_source"] = "listing_base_price"
    issue_price = to_float(record.get("issue_price"))
    record["issue_price_mismatch"] = bool(
        issue_price and base and abs(base / issue_price - 1.0) > 0.005
    )
    _derive_fields(record)

    record["errors"] = errors
    record["transient_error"] = transient
    record["attempts"] = int((previous or {}).get("attempts") or 0) + (0 if transient else 1)
    record["fetched_at"] = _utc_now().isoformat(timespec="seconds")
    record["is_final"] = _is_final(record, today, detail_required=include_detail)
    return record


_DETAIL_FIELDS = {
    "industry",
    "isin",
    "issue_type",
    "lot_size",
    "lots_per_application",
    "min_application_qty",
    "retail_discount",
    "book_shares",
    "qib_book_shares",
    "anchor_shares",
    "market_maker_shares",
    "applications_total",
    "applications_retail",
    "lead_managers",
    "registrar",
}


def _in_band(price: Optional[float], record: Mapping[str, Any], tolerance: float = 0.02) -> bool:
    low = to_float(record.get("price_band_low"))
    high = to_float(record.get("price_band_high"))
    if price is None or not low or not high:
        return True  # no band to contradict the price
    return low * (1 - tolerance) <= price <= high * (1 + tolerance)


def _classify_listing(record: Dict[str, Any]) -> None:
    """Tag records that are not IPO debuts so analytics can leave them out."""
    kind, reason = "ipo", None
    gap = record.get("days_to_listing")
    if isinstance(gap, int) and gap > _MAX_DEBUT_GAP_DAYS:
        kind = "later_listing"
        reason = f"listed {gap} days after bidding closed (SME migration, relisting, or direct listing)"
    elif record.get("has_listing_data") and not _in_band(to_float(record.get("issue_price")), record):
        kind = "unverified"
        reason = "issue price lies outside the issue's own price band"
    record["listing_kind"] = kind
    record["listing_kind_reason"] = reason


def _derive_fields(record: Dict[str, Any]) -> None:
    """Recompute every field derivable without NSE (cheap; runs on reuse too)."""
    _classify_listing(record)
    _derive_money_fields(record)


def _derive_money_fields(record: Dict[str, Any]) -> None:
    issue_price = to_float(record.get("issue_price"))
    qty = to_int(record.get("min_application_qty"))
    record["min_application_value"] = round(qty * issue_price, 2) if qty and issue_price else None

    book = to_float(record.get("book_shares"))
    anchor = to_float(record.get("anchor_shares"))
    market_maker = to_float(record.get("market_maker_shares"))
    qib_book = to_float(record.get("qib_book_shares"))
    size_basis = None
    total_shares = None
    if book:
        if anchor:
            total_shares = book + anchor + (market_maker or 0.0)
            size_basis = "book_plus_anchor"
        elif record.get("board") == BOARD_MAINBOARD and record.get("issue_type") == "book_building" and qib_book:
            # Anchors take up to 60% of the QIB portion, i.e. 1.5x the QIB book.
            total_shares = book + 1.5 * qib_book
            size_basis = "book_plus_anchor_estimate"
        else:
            total_shares = book + (market_maker or 0.0)
            size_basis = "book_only"
    record["issue_size_cr"] = round(total_shares * issue_price / 1e7, 2) if total_shares and issue_price else None
    record["issue_size_basis"] = size_basis

    retail_x = to_float(record.get("subscription_retail_x"))
    probability = None
    basis = None
    if record.get("board") == BOARD_MAINBOARD and retail_x is not None and retail_x > 0:
        probability = min(1.0, 1.0 / retail_x)
        basis = "inverse_retail_subscription"
    record["allotment_probability"] = round(probability, 6) if probability is not None else None
    record["allotment_probability_basis"] = basis

    for name in LISTING_EXITS:
        price = to_float(record.get(f"listing_{name}"))
        profit = round(qty * (price - issue_price), 2) if qty and price is not None and issue_price else None
        record[f"profit_{name}"] = profit
        record[f"expected_profit_{name}"] = round(profit * probability, 2) if profit is not None and probability is not None else None


def _is_transient(exc: BaseException) -> bool:
    """Network trouble worth retrying later, as opposed to data NSE lacks."""
    if isinstance(exc, (OSError, TimeoutError)):
        return True
    module = type(exc).__module__ or ""
    if module.startswith(("httpx", "httpcore", "h2", "h11", "tenacity")):
        return True
    return type(exc).__name__ in {"CircuitOpenError", "_RetryableContentError", "RetryError"}


def _is_final(record: Mapping[str, Any], today: date, *, detail_required: bool = True) -> bool:
    """A record is final once nothing more can be learned by re-fetching it.

    Complete records are final immediately.  Old issues with a permanent gap
    (a delisting before the one-year mark, a book NSE never published) become
    final after a few attempts so they stop costing requests.
    """
    listing = parse_date_maybe(record.get("listing_date"))
    if listing is None:
        return False
    detail_ok = bool(record.get("detail_fetched")) or not detail_required
    complete = (
        bool(record.get("has_listing_data"))
        and detail_ok
        and all(record.get(f"return_{name}_pct") is not None for name, _ in IPO_HORIZONS)
    )
    if complete:
        return True
    if record.get("transient_error"):
        return False
    return (today - listing).days >= _FINAL_AFTER_DAYS and int(record.get("attempts") or 0) >= 3


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def return_distribution(values: Iterable[Optional[float]]) -> Dict[str, Any]:
    """Summarize percentage returns: centre, spread, and hit rate."""
    clean = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not clean:
        return {"count": 0}
    wins = [value for value in clean if value > 0]
    losses = [value for value in clean if value < 0]

    def _r(value: float) -> float:
        return round(value, 4)

    return {
        "count": len(clean),
        "mean_pct": _r(statistics.fmean(clean)),
        "median_pct": _r(_quantile(clean, 0.5)),
        "p10_pct": _r(_quantile(clean, 0.10)),
        "p25_pct": _r(_quantile(clean, 0.25)),
        "p75_pct": _r(_quantile(clean, 0.75)),
        "p90_pct": _r(_quantile(clean, 0.90)),
        "min_pct": _r(clean[0]),
        "max_pct": _r(clean[-1]),
        "stdev_pct": _r(statistics.stdev(clean)) if len(clean) > 1 else 0.0,
        "win_rate_pct": _r(len(wins) / len(clean) * 100.0),
        "loss_rate_pct": _r(len(losses) / len(clean) * 100.0),
        "avg_win_pct": _r(statistics.fmean(wins)) if wins else None,
        "avg_loss_pct": _r(statistics.fmean(losses)) if losses else None,
    }


def _bucket(value: Optional[float], buckets: Sequence[Tuple[str, float, float]]) -> Optional[str]:
    if value is None:
        return None
    for label, low, high in buckets:
        if low <= value < high:
            return label
    return None


def subscription_bucket(value: Optional[float]) -> Optional[str]:
    return _bucket(value, SUBSCRIPTION_BUCKETS)


def issue_size_bucket(value: Optional[float]) -> Optional[str]:
    return _bucket(value, ISSUE_SIZE_BUCKETS)


def _coerce_boards(boards: Optional[Iterable[str]], default: Sequence[str]) -> set[str]:
    if boards is None:
        return set(default)
    if isinstance(boards, str):
        boards = [part for part in re.split(r"[,\s]+", boards) if part]
    wanted = {str(board).strip().lower() for board in boards if str(board).strip()}
    if "all" in wanted:
        return set(default) | set(EQUITY_BOARDS)
    unknown = wanted - set(IPO_BOARDS)
    if unknown:
        raise InputValidationError(f"Unknown board(s): {', '.join(sorted(unknown))}; expected {', '.join(IPO_BOARDS)}")
    return wanted


def filter_ipo_records(
    records: Iterable[Mapping[str, Any]],
    *,
    boards: Optional[Iterable[str]] = None,
    from_date: Optional[DateLike] = None,
    to_date: Optional[DateLike] = None,
    min_subscription: Optional[float] = None,
    max_subscription: Optional[float] = None,
    include_later_listings: bool = False,
) -> List[Dict[str, Any]]:
    """Filter backtest records by board, listing window, and total subscription.

    Records that are not IPO debuts (``listing_kind`` other than ``"ipo"``:
    SME migrations, relistings, contradictory prices) are left out unless
    ``include_later_listings`` is true.
    """
    wanted = _coerce_boards(boards, default=IPO_BOARDS)
    start = coerce_optional_date(from_date, "from_date")
    end = coerce_optional_date(to_date, "to_date")
    selected = []
    for record in records:
        if record.get("board") not in wanted:
            continue
        if not include_later_listings and record.get("listing_kind", "ipo") != "ipo":
            continue
        listed = parse_date_maybe(record.get("listing_date"))
        if start and (listed is None or listed < start):
            continue
        if end and (listed is None or listed > end):
            continue
        subscription = to_float(record.get("subscription_total_x"))
        if min_subscription is not None and (subscription is None or subscription < min_subscription):
            continue
        if max_subscription is not None and (subscription is None or subscription >= max_subscription):
            continue
        selected.append(dict(record))
    return selected


def summarize_ipo_backtest(
    records: Iterable[Mapping[str, Any]],
    exit: str = "open",
    *,
    boards: Optional[Iterable[str]] = None,
    from_date: Optional[DateLike] = None,
    to_date: Optional[DateLike] = None,
    min_subscription: Optional[float] = None,
    max_subscription: Optional[float] = None,
    top: int = 10,
) -> Dict[str, Any]:
    """Aggregate backtest records into strategy, cohort, and P&L statistics.

    ``exit`` selects the headline strategy (see :data:`IPO_EXIT_FIELDS`).
    The response always includes every strategy side by side so the "sell at
    open vs close vs hold" question can be answered from one call.
    """
    if exit not in IPO_EXIT_FIELDS:
        raise InputValidationError(f"exit must be one of {', '.join(IPO_EXIT_FIELDS)}")
    field = IPO_EXIT_FIELDS[exit]
    selected = [
        record
        for record in filter_ipo_records(
            records,
            boards=boards if boards is not None else EQUITY_BOARDS,
            from_date=from_date,
            to_date=to_date,
            min_subscription=min_subscription,
            max_subscription=max_subscription,
        )
        if record.get("has_listing_data")
    ]
    selected.sort(key=lambda row: (row.get("listing_date") or "", row.get("symbol") or ""))

    strategies = {
        name: {"label": IPO_EXIT_LABELS[name], **return_distribution(row.get(record_field) for row in selected)}
        for name, record_field in IPO_EXIT_FIELDS.items()
    }

    def _group(key_fn: Callable[[Mapping[str, Any]], Optional[str]], order: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Mapping[str, Any]]] = {}
        for row in selected:
            key = key_fn(row) or "unknown"
            groups.setdefault(key, []).append(row)
        keys = list(order or sorted(groups))
        if "unknown" in groups and "unknown" not in keys:
            keys.append("unknown")
        output = []
        for key in keys:
            rows = groups.get(key)
            if not rows:
                continue
            output.append(
                {
                    "group": key,
                    **return_distribution(row.get(field) for row in rows),
                    "median_close_vs_open_pct": return_distribution(row.get("close_vs_open_pct") for row in rows).get("median_pct"),
                    "median_subscription_x": _median(row.get("subscription_total_x") for row in rows),
                }
            )
        return output

    by_year = _group(lambda row: str(row.get("listing_year") or "") or None)
    by_board = _group(lambda row: row.get("board"), order=EQUITY_BOARDS)
    by_subscription = _group(
        lambda row: subscription_bucket(to_float(row.get("subscription_total_x"))),
        order=[label for label, _, _ in SUBSCRIPTION_BUCKETS],
    )
    by_size = _group(
        lambda row: issue_size_bucket(to_float(row.get("issue_size_cr"))),
        order=[label for label, _, _ in ISSUE_SIZE_BUCKETS],
    )

    both = [row for row in selected if row.get("return_open_pct") is not None and row.get("return_close_pct") is not None]
    close_beats_open = sum(1 for row in both if row["return_close_pct"] > row["return_open_pct"])
    intraday = {
        "count": len(both),
        "close_above_open_pct": round(close_beats_open / len(both) * 100.0, 4) if both else None,
        "close_vs_open": return_distribution(row.get("close_vs_open_pct") for row in both),
        "high_vs_open": return_distribution(row.get("high_vs_open_pct") for row in both),
        "low_vs_open": return_distribution(row.get("low_vs_open_pct") for row in both),
        "closed_at_high_pct": round(sum(1 for row in both if row.get("closed_at_high")) / len(both) * 100.0, 4) if both else None,
    }

    listing_exit = exit if exit in LISTING_EXITS else "open"
    profit_field = f"profit_{listing_exit}"
    expected_field = f"expected_profit_{listing_exit}"
    with_profit = [row for row in selected if row.get(profit_field) is not None]
    with_expected = [row for row in with_profit if row.get(expected_field) is not None]
    cumulative = 0.0
    cumulative_expected = 0.0
    curve = []
    for row in with_profit:
        cumulative += float(row[profit_field])
        if row.get(expected_field) is not None:
            cumulative_expected += float(row[expected_field])
        curve.append(
            {
                "date": row.get("listing_date"),
                "symbol": row.get("symbol"),
                "profit": row[profit_field],
                "cumulative_profit": round(cumulative, 2),
                "cumulative_expected_profit": round(cumulative_expected, 2),
            }
        )
    capital = [float(row["min_application_value"]) for row in with_profit if row.get("min_application_value")]
    pnl = {
        "exit": listing_exit,
        "applications": len(with_profit),
        "total_profit_if_always_allotted": round(cumulative, 2),
        "mean_profit_per_allotment": round(cumulative / len(with_profit), 2) if with_profit else None,
        "median_application_value": _median(capital),
        "expected_profit_applications": len(with_expected),
        "total_expected_profit": round(sum(float(row[expected_field]) for row in with_expected), 2) if with_expected else None,
        "mean_expected_profit_per_application": (
            round(sum(float(row[expected_field]) for row in with_expected) / len(with_expected), 2) if with_expected else None
        ),
        "mean_allotment_probability": _mean(row.get("allotment_probability") for row in with_expected),
        "curve": curve,
    }

    ranked = [row for row in selected if row.get(field) is not None]
    ranked.sort(key=lambda row: float(row[field]))

    def compact(row: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": row.get("symbol"),
            "company_name": row.get("company_name"),
            "board": row.get("board"),
            "listing_date": row.get("listing_date"),
            "issue_price": row.get("issue_price"),
            "subscription_total_x": row.get("subscription_total_x"),
            "return_pct": row.get(field),
        }

    return {
        "exit": exit,
        "exit_label": IPO_EXIT_LABELS[exit],
        "count": len(selected),
        "from_date": selected[0].get("listing_date") if selected else None,
        "to_date": selected[-1].get("listing_date") if selected else None,
        "headline": strategies[exit],
        "strategies": strategies,
        "by_year": by_year,
        "by_board": by_board,
        "by_subscription": by_subscription,
        "by_issue_size": by_size,
        "intraday": intraday,
        "pnl": pnl,
        "best": [compact(row) for row in reversed(ranked[-top:])],
        "worst": [compact(row) for row in ranked[:top]],
        "basis": (
            "Returns versus issue price, before brokerage and taxes. The listing-day high is an "
            "oracle exit; VWAP approximates an average execution. Mainboard allotment odds use "
            "1 / retail subscription (conservative)."
        ),
        "source": NSE_SOURCE,
    }


def _median(values: Iterable[Any]) -> Optional[float]:
    clean = sorted(float(value) for value in values if to_float(value) is not None)
    return round(_quantile(clean, 0.5), 4) if clean else None


def _mean(values: Iterable[Any]) -> Optional[float]:
    clean = [float(value) for value in values if to_float(value) is not None]
    return round(statistics.fmean(clean), 6) if clean else None


# ---------------------------------------------------------------------------
# Module-level convenience API
# ---------------------------------------------------------------------------

_DEFAULT_CLIENT: Optional[NSEIpo] = None
_DEFAULT_CLIENT_LOCK = threading.Lock()


def _default_client() -> NSEIpo:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        with _DEFAULT_CLIENT_LOCK:
            if _DEFAULT_CLIENT is None:
                _DEFAULT_CLIENT = NSEIpo()
    return _DEFAULT_CLIENT


def ipo_past_issues(
    from_date: Optional[DateLike] = None,
    to_date: Optional[DateLike] = None,
    boards: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return NSE-listed public issues (IPOs, SME IPOs, REITs, InvITs, NCDs)."""
    return _default_client().past_issues(from_date, to_date, boards)


def ipo_current_issues() -> List[Dict[str, Any]]:
    """Return IPOs currently open for bidding with live total subscription."""
    return _default_client().current_issues()


def ipo_upcoming_issues() -> List[Dict[str, Any]]:
    """Return open and forthcoming IPOs announced on NSE."""
    return _default_client().upcoming_issues()


def ipo_live_issues() -> List[Dict[str, Any]]:
    """Return open and forthcoming IPOs merged with live subscription."""
    return _default_client().live_issues()


def ipo_detail(symbol: str, board: Optional[str] = None) -> Dict[str, Any]:
    """Return one issue's subscription book, lot size, and issue structure."""
    return _default_client().issue_detail(symbol, board=board)


def ipo_listing_performance(
    symbol: str,
    listing_date: DateLike,
    issue_price: Optional[float] = None,
    *,
    board: str = BOARD_MAINBOARD,
    include_path: bool = False,
) -> Dict[str, Any]:
    """Return listing-day and post-listing returns for one issue."""
    return _default_client().listing_performance(
        symbol, listing_date, issue_price, board=board, include_path=include_path
    )


def ipo_report(symbol: str, listing_date: Optional[DateLike] = None) -> Dict[str, Any]:
    """Return a full backtest record, including the daily path, for one issue."""
    return _default_client().report(symbol, listing_date)


def ipo_backtest(
    from_date: Optional[DateLike] = None,
    to_date: Optional[DateLike] = None,
    boards: Optional[Iterable[str]] = EQUITY_BOARDS,
    *,
    existing: Optional[Iterable[Mapping[str, Any]]] = None,
    include_detail: bool = True,
    max_workers: int = 4,
    progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    """Build JSON-ready listing backtest records for every IPO in the window."""
    return _default_client().backtest(
        from_date,
        to_date,
        boards,
        existing=existing,
        include_detail=include_detail,
        max_workers=max_workers,
        progress=progress,
    )


def ipo_backtest_df(records: Sequence[Mapping[str, Any]]):
    """Return backtest records as a pandas DataFrame."""
    return dataframe_from_records([dict(record) for record in records])


__all__ = [
    "BOARD_MAINBOARD",
    "BOARD_SME",
    "EQUITY_BOARDS",
    "IPO_BOARDS",
    "IPO_EXIT_FIELDS",
    "IPO_EXIT_LABELS",
    "IPO_HORIZONS",
    "ISSUE_SIZE_BUCKETS",
    "LISTING_EXITS",
    "NSEIpo",
    "SUBSCRIPTION_BUCKETS",
    "analyze_listing_performance",
    "build_ipo_record",
    "filter_ipo_records",
    "ipo_backtest",
    "ipo_backtest_df",
    "ipo_current_issues",
    "ipo_detail",
    "ipo_listing_performance",
    "ipo_live_issues",
    "ipo_past_issues",
    "ipo_record_key",
    "ipo_record_needs_refresh",
    "ipo_report",
    "ipo_upcoming_issues",
    "issue_size_bucket",
    "return_distribution",
    "subscription_bucket",
    "summarize_ipo_backtest",
]
