"""
Canonical live-data client for NSE endpoints.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any, Dict, Iterable, Optional
import time

from ..standard import (
    DateLike,
    InputValidationError,
    clean_text,
    coerce_date,
    normalize_name,
    normalize_symbol,
    parse_date_maybe,
    parse_datetime_maybe,
    to_bool,
    to_float,
    to_int,
)
from ..analytics import summarize_option_chain
from ..catalog import supported_event_categories, supported_indices, supported_instruments
from ..util import live_cache
from .connection_pool import get_connection_pool
from .http_client import NSEHttpClient


def _normalize_option_leg(leg: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not leg:
        return None
    return {
        "identifier": clean_text(leg.get("identifier")),
        "expiry_date": parse_date_maybe(leg.get("expiryDate")),
        "strike_price": to_float(leg.get("strikePrice")),
        "last_price": to_float(leg.get("lastPrice")),
        "change": to_float(leg.get("change")),
        "change_percent": to_float(leg.get("pchange")),
        "open_interest": to_int(leg.get("openInterest")),
        "change_in_open_interest": to_int(leg.get("changeinOpenInterest")),
        "change_in_open_interest_percent": to_float(leg.get("pchangeinOpenInterest")),
        "volume": to_int(leg.get("totalTradedVolume")),
        "implied_volatility": to_float(leg.get("impliedVolatility")),
        "best_bid_price": to_float(leg.get("buyPrice1")),
        "best_bid_quantity": to_int(leg.get("buyQuantity1")),
        "best_ask_price": to_float(leg.get("sellPrice1")),
        "best_ask_quantity": to_int(leg.get("sellQuantity1")),
        "total_buy_quantity": to_int(leg.get("totalBuyQuantity")),
        "total_sell_quantity": to_int(leg.get("totalSellQuantity")),
        "underlying_value": to_float(leg.get("underlyingValue")),
    }


def _infer_event_type(text: str) -> str:
    lowered = text.lower()
    patterns = [
        ("dividend", "dividend"),
        ("split", "split"),
        ("bonus", "bonus"),
        ("rights", "rights"),
        ("financial results", "results"),
        ("result", "results"),
        ("earnings", "results"),
        ("board meeting", "board_meeting"),
        ("certificate", "compliance"),
        ("regulation", "compliance"),
    ]
    for needle, label in patterns:
        if needle in lowered:
            return label
    return "general"


class NSELive:
    time_out = 5
    base_url = "https://www.nseindia.com/api"
    page_url = "https://www.nseindia.com/get-quotes/equity?symbol=LT"
    _routes = {
        "stock_meta": "/equity-meta-info",
        "stock_quote": "/quote-equity",
        "market_status": "/marketStatus",
        "chart_data": "/chart-databyindex",
        "market_turnover": "/market-turnover",
        "equity_derivative_turnover": "/equity-stock",
        "all_indices": "/allIndices",
        "live_index": "/equity-stockIndices",
        "index_option_chain": "/option-chain-indices",
        "equity_option_chain": "/option-chain-equities",
        "currency_option_chain": "/option-chain-currency",
        "pre_open_market": "/market-data-pre-open",
        "holiday_list": "/holiday-master?type=trading",
        "corporate_announcements": "/corporate-announcements",
    }

    def __init__(self):
        self.connection_pool = get_connection_pool()
        self.client: NSEHttpClient = self.connection_pool.get_client("https://www.nseindia.com")

    def get(self, route, payload=None):
        payload = payload or {}
        path = "/api" + self._routes[route]
        return self.client.get_json(path, params=payload)

    def _normalize_quote(self, payload: Dict[str, Any], quote_type: str = "equity") -> Dict[str, Any]:
        info = payload.get("info", {})
        price = payload.get("priceInfo", {})
        day_range = price.get("intraDayHighLow", {}) if isinstance(price, dict) else {}
        week_range = price.get("weekHighLow", {}) if isinstance(price, dict) else {}
        return {
            "quote_type": quote_type,
            "symbol": normalize_symbol(info.get("symbol") or payload.get("symbol") or ""),
            "company_name": clean_text(info.get("companyName")),
            "isin": clean_text(info.get("isin")),
            "industry": clean_text(info.get("industry")),
            "listing_date": parse_date_maybe(info.get("listingDate")),
            "is_fno": bool(info.get("isFNOSec")),
            "identifier": clean_text(info.get("identifier")),
            "price": {
                "last": to_float(price.get("lastPrice")),
                "change": to_float(price.get("change")),
                "change_percent": to_float(price.get("pChange")),
                "open": to_float(price.get("open")),
                "high": to_float(day_range.get("max")),
                "low": to_float(day_range.get("min")),
                "close": to_float(price.get("close")),
                "previous_close": to_float(price.get("previousClose")),
                "vwap": to_float(price.get("vwap")),
                "lower_circuit": to_float(price.get("lowerCP")),
                "upper_circuit": to_float(price.get("upperCP")),
            },
            "week_range": {
                "high": to_float(week_range.get("max")),
                "high_date": parse_date_maybe(week_range.get("maxDate")),
                "low": to_float(week_range.get("min")),
                "low_date": parse_date_maybe(week_range.get("minDate")),
            },
            "metadata": {
                "market_type": clean_text(payload.get("currentMarketType")),
                "active_series": info.get("activeSeries") or [],
                "segment": clean_text(info.get("segment")),
                "pre_open": payload.get("preOpenMarket") or {},
                "security_info": payload.get("securityInfo") or {},
            },
        }

    @live_cache
    def stock_quote(self, symbol):
        data = {"symbol": normalize_symbol(symbol)}
        return self._normalize_quote(self.get("stock_quote", data))

    @live_cache
    def stock_quote_fno(self, symbol):
        """Return the equity quote plus the symbol's available F&O contracts."""
        symbol_name = normalize_symbol(symbol)
        quote = dict(self.stock_quote(symbol_name))
        contract_info = self.option_chain_contract_info(symbol_name)
        # Preserve the established response shape even though NSE removed the
        # old /quote-derivative endpoint.
        quote["quote_type"] = "derivative"
        quote["derivative_details"] = {
            "stocks": [],
            "strike_prices": contract_info["strike_prices"],
            "expiry_dates": contract_info["expiry_dates"],
        }
        return quote

    @live_cache
    def trade_info(self, symbol):
        data = {"symbol": normalize_symbol(symbol), "section": "trade_info"}
        payload = self.get("stock_quote", data)
        return {
            "symbol": normalize_symbol(symbol),
            "bulk_block_deals": payload.get("bulkBlockDeals") or [],
            "market_depth": payload.get("marketDeptOrderBook") or {},
            "security_wise_dp": payload.get("securityWiseDP") or {},
            "metadata": payload.get("securityInfo") or {},
        }

    @live_cache
    def market_status(self):
        payload = self.get("market_status", {})
        markets = []
        for row in payload.get("marketState", []) if isinstance(payload, dict) else []:
            markets.append(
                {
                    "market": clean_text(row.get("market")),
                    "status": clean_text(row.get("marketStatus")),
                    "message": clean_text(row.get("marketStatusMessage")),
                    "trade_date": clean_text(row.get("tradeDate")),
                    "index": clean_text(row.get("index")),
                    "last": to_float(row.get("last")),
                    "variation": to_float(row.get("variation")),
                    "percent_change": to_float(row.get("percentChange")),
                    "expiry_date": parse_date_maybe(row.get("expiryDate")),
                    "underlying": clean_text(row.get("underlying")),
                }
            )
        return {
            "markets": markets,
            "market_cap": payload.get("marketcap"),
            "gift_nifty": payload.get("giftnifty"),
            "indicative_nifty_50": payload.get("indicativenifty50"),
        }

    @live_cache
    def chart_data(self, symbol, indices=False, flag="1D"):
        symbol_name = normalize_name(symbol) if indices else normalize_symbol(symbol)
        if indices:
            params = {
                "functionName": "getGraphChart",
                "type": symbol_name,
                "flag": flag,
            }
            resp = self.client.get_json("/api/NextApi/apiClient", params=params)
            payload = resp.get("data", resp) if isinstance(resp, dict) else resp
        else:
            identifier = symbol_name if symbol_name.endswith("EQN") else f"{symbol_name}EQN"
            params = {
                "functionName": "getSymbolChartData",
                "symbol": identifier,
                "days": flag,
            }
            payload = self.client.get_json("/api/NextApi/apiClient/GetQuoteApi", params=params)
        return {
            "symbol": symbol_name,
            "is_index": bool(indices),
            "range": flag,
            "points": payload.get("grapthData") or payload.get("graphData") or [],
            "timestamp": payload.get("timestamp"),
            "open": payload.get("open"),
            "high": payload.get("high"),
            "low": payload.get("low"),
            "close": payload.get("close"),
        }

    @live_cache
    def tick_data(self, symbol, indices=False, flag="1D"):
        return self.chart_data(symbol, indices, flag)

    @live_cache
    def market_turnover(self):
        payload = self.get("market_turnover")
        return {
            "records": payload.get("data", []) if isinstance(payload, dict) else [],
            "source": "nse_market_turnover",
        }

    @live_cache
    def eq_derivative_turnover(self, type="allcontracts"):
        data = {"index": type}
        payload = self.get("equity_derivative_turnover", data)
        return {
            "category": type,
            "value": payload.get("value") if isinstance(payload, dict) else None,
            "volume": payload.get("volume") if isinstance(payload, dict) else None,
        }

    @live_cache
    def all_indices(self):
        payload = self.get("all_indices")
        return {
            "advances": to_int(payload.get("advances")) if isinstance(payload, dict) else None,
            "declines": to_int(payload.get("declines")) if isinstance(payload, dict) else None,
            "unchanged": to_int(payload.get("unchanged")) if isinstance(payload, dict) else None,
            "indices": payload.get("data", []) if isinstance(payload, dict) else [],
            "timestamp": payload.get("timestamp") if isinstance(payload, dict) else None,
        }

    def live_index(self, symbol="NIFTY 50"):
        data = {"index": normalize_name(symbol)}
        payload = self.get("live_index", data)
        return {
            "name": clean_text(payload.get("name")) if isinstance(payload, dict) else normalize_name(symbol),
            "advance": to_int(payload.get("advance")) if isinstance(payload, dict) else None,
            "decline": to_int(payload.get("decline")) if isinstance(payload, dict) else None,
            "unchanged": to_int(payload.get("unchanged")) if isinstance(payload, dict) else None,
            "data": payload.get("data", []) if isinstance(payload, dict) else [],
        }

    def _prime_option_chain(self, indices: bool = True) -> None:
        try:
            path = "/option-chain" if indices else "/option-chain-equities"
            self.client.get(path)
        except Exception:
            pass

    @staticmethod
    def _contract_info_values(payload: Dict[str, Any], *keys: str) -> list[Any]:
        """Extract a contract-info list across NSE's known response wrappers."""
        sources = [payload]
        for wrapper in ("records", "data"):
            wrapped = payload.get(wrapper)
            if isinstance(wrapped, dict):
                sources.append(wrapped)

        for source in sources:
            for key in keys:
                value = source.get(key)
                if value in (None, ""):
                    continue
                if isinstance(value, (list, tuple)):
                    if value:
                        return list(value)
                    continue
                return [value]
        return []

    @live_cache
    def option_chain_contract_info(self, symbol: str) -> Dict[str, Any]:
        """Return normalized expiries and strikes available for a symbol."""
        symbol_name = normalize_symbol(symbol)
        payload = self.client.get_json(
            "/api/option-chain-contract-info",
            params={"symbol": symbol_name},
        )
        if not isinstance(payload, dict):
            payload = {}

        expiry_values = self._contract_info_values(
            payload,
            "expiryDates",
            "expiryDate",
            "expiry_dates",
        )
        strike_values = self._contract_info_values(
            payload,
            "strikePrice",
            "strikePrices",
            "strike_prices",
        )

        expiry_dates = []
        for value in expiry_values:
            if isinstance(value, dict):
                value = value.get("expiryDate") or value.get("expiryDates")
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                parsed = parse_date_maybe(item)
                if parsed is not None and parsed not in expiry_dates:
                    expiry_dates.append(parsed)

        strike_prices = []
        for value in strike_values:
            if isinstance(value, dict):
                value = value.get("strikePrice") or value.get("strikePrices")
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                parsed = to_float(item)
                if parsed is not None and parsed not in strike_prices:
                    strike_prices.append(parsed)

        return {
            "symbol": symbol_name,
            "expiry_dates": expiry_dates,
            "strike_prices": strike_prices,
        }

    def _select_option_chain_expiry(
        self,
        symbol: str,
        expiry: Optional[DateLike],
    ) -> date:
        contract_info = self.option_chain_contract_info(symbol)
        available = contract_info["expiry_dates"]
        if not available:
            raise InputValidationError(
                f"No option-chain expiries are available for {symbol}"
            )

        selected = available[0] if expiry is None else coerce_date(expiry, "expiry")
        if selected not in available:
            choices = ", ".join(item.isoformat() for item in available)
            raise InputValidationError(
                f"Expiry {selected.isoformat()} is not available for {symbol}; "
                f"available expiries: {choices}"
            )
        return selected

    @staticmethod
    def _format_option_chain_expiry(expiry: date) -> str:
        """Format a date for NSE's option-chain-v3 query parameter."""
        months = (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        )
        return f"{expiry.day:02d}-{months[expiry.month - 1]}-{expiry.year:04d}"

    def _get_first_expiry(self, symbol: str) -> str:
        """Backward-compatible internal helper for the nearest expiry."""
        selected = self._select_option_chain_expiry(normalize_symbol(symbol), None)
        return self._format_option_chain_expiry(selected)

    def _normalize_option_chain(
        self,
        payload: Dict[str, Any],
        symbol: str,
        market_type: str,
        selected_expiry: Optional[date] = None,
    ) -> Dict[str, Any]:
        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        rows = []
        for row in records.get("data", []) if isinstance(records, dict) else []:
            expiry = parse_date_maybe(row.get("expiryDate") or row.get("expiryDates"))
            rows.append(
                {
                    "strike_price": to_float(row.get("strikePrice")),
                    "expiry_date": expiry,
                    "call": _normalize_option_leg(row.get("CE")),
                    "put": _normalize_option_leg(row.get("PE")),
                }
            )
        chain = {
            "symbol": normalize_symbol(symbol),
            "market_type": market_type,
            "timestamp": clean_text(records.get("timestamp")),
            "underlying_value": to_float(records.get("underlyingValue")),
            "selected_expiry": selected_expiry,
            "expiry_dates": [parse_date_maybe(item) for item in records.get("expiryDates", [])],
            "strike_prices": [to_float(item) for item in records.get("strikePrices", [])],
            "records": rows,
        }
        chain["summary"] = summarize_option_chain(chain)
        return chain

    @live_cache
    def index_option_chain(
        self,
        symbol="NIFTY",
        expiry: Optional[DateLike] = None,
    ):
        """Return an index option chain, optionally for a validated expiry."""
        symbol_name = normalize_symbol(symbol)
        self._prime_option_chain(indices=True)
        selected_expiry = self._select_option_chain_expiry(symbol_name, expiry)
        params = {
            "type": "Indices",
            "symbol": symbol_name,
            "expiry": self._format_option_chain_expiry(selected_expiry),
        }
        payload = self.client.get_json("/api/option-chain-v3", params=params)
        return self._normalize_option_chain(
            payload,
            symbol_name,
            "index",
            selected_expiry,
        )

    @live_cache
    def equities_option_chain(
        self,
        symbol,
        expiry: Optional[DateLike] = None,
    ):
        """Return an equity option chain, optionally for a validated expiry."""
        symbol_name = normalize_symbol(symbol)
        self._prime_option_chain(indices=False)
        selected_expiry = self._select_option_chain_expiry(symbol_name, expiry)
        params = {
            "type": "Stocks",
            "symbol": symbol_name,
            "expiry": self._format_option_chain_expiry(selected_expiry),
        }
        payload = self.client.get_json("/api/option-chain-v3", params=params)
        return self._normalize_option_chain(
            payload,
            symbol_name,
            "equity",
            selected_expiry,
        )

    @live_cache
    def currency_option_chain(self, symbol="USDINR"):
        symbol_name = normalize_symbol(symbol)
        payload = self.get("currency_option_chain", {"symbol": symbol_name})
        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        rows = []
        for row in records.get("data", []):
            rows.append(
                {
                    "strike_price": to_float(row.get("strikePrice")),
                    "expiry_date": parse_date_maybe(row.get("expiryDate")),
                    "call": _normalize_option_leg(row.get("CE")),
                    "put": _normalize_option_leg(row.get("PE")),
                }
            )
        chain = {
            "symbol": symbol_name,
            "market_type": "currency",
            "timestamp": clean_text(records.get("timestamp")),
            "underlying_value": to_float(records.get("underlyingValue")),
            "expiry_dates": [parse_date_maybe(item) for item in records.get("expiryDates", [])],
            "strike_prices": [to_float(item) for item in records.get("strikePrices", [])],
            "records": rows,
        }
        chain["summary"] = summarize_option_chain(chain)
        return chain

    @live_cache
    def live_fno(self):
        return self.live_index("SECURITIES IN F&O")

    @live_cache
    def pre_open_market(self, key="NIFTY"):
        payload = self.get("pre_open_market", {"key": normalize_name(key)})
        return {
            "key": normalize_name(key),
            "advances": to_int(payload.get("advances")) if isinstance(payload, dict) else None,
            "declines": to_int(payload.get("declines")) if isinstance(payload, dict) else None,
            "unchanged": to_int(payload.get("unchanged")) if isinstance(payload, dict) else None,
            "data": payload.get("data", []) if isinstance(payload, dict) else [],
        }

    @live_cache
    def holiday_list(self):
        payload = self.get("holiday_list", {})
        markets = []
        for market_name, rows in payload.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                markets.append(
                    {
                        "market": clean_text(market_name),
                        "date": parse_date_maybe(row.get("tradingDate")),
                        "weekday": clean_text(row.get("weekDay")),
                        "description": clean_text(row.get("description")),
                    }
                )
        return {"markets": markets}

    def corporate_announcements(self, segment='equities', from_date=None, to_date=None, symbol=None):
        payload = {"index": segment}
        if from_date and to_date:
            payload['from_date'] = coerce_date(from_date, "from_date").strftime("%d-%m-%Y")
            payload['to_date'] = coerce_date(to_date, "to_date").strftime("%d-%m-%Y")
        elif from_date or to_date:
            raise ValueError("Please provide both from_date and to_date")
        if symbol:
            payload['symbol'] = normalize_symbol(symbol)
        rows = self.get("corporate_announcements", payload)
        normalized = []
        for row in rows if isinstance(rows, list) else []:
            text = clean_text(row.get("desc") or row.get("attchmntText") or "")
            event_type = _infer_event_type(text or "")
            symbol_value = clean_text(row.get("symbol"))
            normalized.append(
                {
                    "symbol": normalize_symbol(symbol_value) if symbol_value else None,
                    "company_name": clean_text(row.get("sm_name")),
                    "isin": clean_text(row.get("sm_isin")),
                    "event_type": event_type,
                    "headline": clean_text(row.get("desc")),
                    "summary": clean_text(row.get("attchmntText")),
                    "event_date": parse_datetime_maybe(row.get("an_dt")),
                    "exchange_received_at": parse_datetime_maybe(row.get("exchdisstime")),
                    "attachment_url": clean_text(row.get("attchmntFile")),
                    "attachment_size": clean_text(row.get("attFileSize") or row.get("fileSize")),
                    "segment": clean_text(segment),
                    "has_xbrl": to_bool(row.get("hasXbrl")),
                }
            )
        return normalized

    def corporate_actions(
        self,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        symbol: Optional[str] = None,
        event_types: Optional[Iterable[str]] = None,
    ) -> list[dict[str, Any]]:
        allowed = set(event_types or ["dividend", "split", "bonus", "rights", "board_meeting"])
        events = self.corporate_announcements(from_date=from_date, to_date=to_date, symbol=symbol)
        return [event for event in events if event["event_type"] in allowed]

    def results_calendar(
        self,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        symbol: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        events = self.corporate_announcements(from_date=from_date, to_date=to_date, symbol=symbol)
        return [event for event in events if event["event_type"] == "results"]

    def bulk_equities_option_chain(self, symbols, max_workers=3) -> Dict[str, Any]:
        def fetch_single_option_chain(symbol):
            try:
                result = self.equities_option_chain(symbol)
                return symbol, result, None
            except Exception as exc:
                return symbol, None, str(exc)

        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {executor.submit(fetch_single_option_chain, symbol): symbol for symbol in symbols}
            for future in as_completed(future_to_symbol):
                symbol, data, error = future.result()
                if error:
                    errors[symbol] = error
                else:
                    results[symbol] = data
                time.sleep(0.1)

        return {
            "success": results,
            "errors": errors,
            "summary": {
                "total_requested": len(symbols),
                "successful": len(results),
                "failed": len(errors),
            },
        }

    def get_options_around_date(self, symbol, target_date, days_before=5, days_after=5) -> Dict[str, Any]:
        for name, value in (
            ("days_before", days_before),
            ("days_after", days_after),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InputValidationError(
                    f"{name} must be a non-negative integer"
                )

        target = coerce_date(target_date, "target_date")
        option_data = self.equities_option_chain(symbol)
        relevant_expiries = []
        for expiry_date in option_data.get("expiry_dates", []):
            if expiry_date is None:
                continue
            delta = (expiry_date - target).days
            if -days_before <= delta <= days_after:
                relevant_expiries.append(
                    {
                        "date": expiry_date,
                        "days_from_target": delta,
                    }
                )

        relevant_expiries.sort(key=lambda item: item["days_from_target"])
        primary_expiry = None
        for expiry in relevant_expiries:
            if expiry["days_from_target"] >= 0:
                primary_expiry = expiry
                break

        return {
            "symbol": normalize_symbol(symbol),
            "target_date": target,
            "option_chain": option_data,
            "relevant_expiries": relevant_expiries,
            "primary_expiry": primary_expiry,
            "analysis": {
                "record_count": len(option_data.get("records", [])),
                "expiry_count": len(relevant_expiries),
                "summary": option_data.get("summary"),
            },
        }

    def analyze_earnings_options(self, symbols_and_dates, max_workers=3) -> Dict[str, Any]:
        def analyze_single_stock(symbol_date_tuple):
            symbol, earnings_date = symbol_date_tuple
            return symbol, self.get_options_around_date(symbol, earnings_date)

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {executor.submit(analyze_single_stock, item): item[0] for item in symbols_and_dates}
            for future in as_completed(future_to_symbol):
                symbol, analysis = future.result()
                results[symbol] = analysis
        return results

    def metadata(self) -> dict[str, Any]:
        return {
            "supported_indices": supported_indices(),
            "supported_instruments": supported_instruments(),
            "supported_event_categories": supported_event_categories(),
        }
