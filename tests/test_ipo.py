from datetime import date, datetime, timedelta, timezone

import pytest

from aynse import (
    NSEIpo,
    analyze_listing_performance,
    ipo_record_needs_refresh,
    summarize_ipo_backtest,
)
from aynse.ipo import (
    ISSUE_DETAIL_PATH,
    PAST_ISSUES_PATH,
    PRICE_HISTORY_PATH,
    _parse_issue_structure,
    _parse_retail_discount,
    build_ipo_record,
    filter_ipo_records,
    return_distribution,
    subscription_bucket,
)
from aynse.standard import InputValidationError


def _bar(day, open_, high, low, close, *, series="EQ", previous=None, vwap=None, volume=1000):
    return {
        "CH_TIMESTAMP": day,
        "CH_SERIES": series,
        "CH_OPENING_PRICE": open_,
        "CH_TRADE_HIGH_PRICE": high,
        "CH_TRADE_LOW_PRICE": low,
        "CH_CLOSING_PRICE": close,
        "CH_PREVIOUS_CLS_PRICE": previous,
        "VWAP": vwap,
        "CH_TOT_TRADED_QTY": volume,
    }


PAST_ISSUES = [
    {"symbol": "ALPHA", "companyName": "Alpha Limited", "securityType": "EQ", "issuePrice": "  100",
     "priceRange": "Rs.95 to Rs.100", "ipoStartDate": "01-JAN-2024", "ipoEndDate": "03-JAN-2024",
     "listingDate": "08-JAN-2024"},
    {"symbol": "BETA", "company": "Beta Limited", "securityType": "SME", "issuePrice": "######",
     "priceRange": "Rs.51 to Rs.54", "ipoStartDate": "02-Feb-2024", "ipoEndDate": "06-Feb-2024",
     "listingDate": "09-Feb-2024"},
    {"symbol": "GAMMA", "company": "Gamma Trust", "securityType": "IV", "issuePrice": "100",
     "priceRange": "Rs.99 to Rs.100", "ipoStartDate": "02-Mar-2024", "ipoEndDate": "06-Mar-2024",
     "listingDate": "11-Mar-2024"},
    {"symbol": "NCD1", "company": "Some NCD", "securityType": "N0", "issuePrice": "######",
     "priceRange": "Rs.1000", "ipoStartDate": "02-Mar-2024", "ipoEndDate": "06-Mar-2024",
     "listingDate": "11-Mar-2024"},
    {"symbol": "OPEN", "company": "Open Limited", "securityType": "EQ", "issuePrice": "-",
     "priceRange": "Rs.10 to Rs.12", "ipoStartDate": "20-Sep-2026", "ipoEndDate": "22-Sep-2026",
     "listingDate": "-"},
    # A duplicate row NSE sometimes repeats for the same listing.
    {"symbol": "ALPHA", "companyName": "Alpha Limited", "securityType": "EQ", "issuePrice": "100",
     "priceRange": "Rs.95 to Rs.100", "ipoStartDate": "01-JAN-2024", "ipoEndDate": "03-JAN-2024",
     "listingDate": "08-JAN-2024"},
]

MAINBOARD_DETAIL = {
    "companyName": "Alpha Limited",
    "metaInfo": {"symbol": "ALPHA", "industry": "Widgets", "isin": "INE000A01010", "segment": "EQUITY",
                 "listingDate": "2024-01-08", "activeSeries": ["EQ"]},
    "bidDetails": [
        {"category": "Qualified Institutional Buyers(QIBs)", "noOfSharesOffered": "100", "noOfTime": "1", "noOfsharesBid": "100", "srNo": "1"},
        {"category": "Total", "noOfSharesOffered": "500", "noOfTime": "2", "noOfsharesBid": "1000", "srNo": None},
    ],
    "activeCat": {"dataList": [
        {"category": "Category", "noOfShareOffered": "No.of shares", "noOfSharesBid": "No. of shares bid", "noOfTotalMeant": "No. of times", "srNo": "Sr.No."},
        {"category": "Qualified Institutional Buyers(QIBs)", "noOfShareOffered": "200", "noOfSharesBid": "4000", "noOfTotalMeant": "20", "srNo": "1"},
        {"category": "Foreign Institutional Investors(FIIs)", "noOfShareOffered": "", "noOfSharesBid": "3000", "noOfTotalMeant": "", "srNo": "1(a)"},
        {"category": "Non Institutional Investors", "noOfShareOffered": "150", "noOfSharesBid": "1500", "noOfTotalMeant": "10", "srNo": "2"},
        {"category": "Non Institutional Investors(Bid amount of more than Ten Lakh Rupees)", "noOfShareOffered": "100", "noOfSharesBid": "1200", "noOfTotalMeant": "12", "srNo": "2.1"},
        {"category": "Non Institutional Investors(Bid amount of more than Two Lakh Rupees upto Ten Lakh Rupees)", "noOfShareOffered": "50", "noOfSharesBid": "300", "noOfTotalMeant": "6", "srNo": "2.2"},
        {"category": "Retail Individual Investors(RIIs)", "noOfShareOffered": "350", "noOfSharesBid": "1400", "noOfTotalMeant": "4", "srNo": "3"},
        {"category": "Total", "noOfShareOffered": "7.0E2", "noOfSharesBid": "6900", "noOfTotalMeant": "9.857", "srNo": None},
    ]},
    "issueInfo": {"dataList": [
        {"title": "Issue Size", "value": "\"Initial Public offer of [.] equity shares (including Anchor portion of 300 Equity Shares)\""},
        {"title": "Issue Type", "value": "Book Building"},
        {"title": "Discount", "value": "Rs.5 per Equity Share to Retail and Eligible Employee Categories"},
        {"title": "Bid Lot", "value": "150 Equity Shares and in multiples thereof"},
    ]},
}

SME_DETAIL = {
    "companyName": "Beta Limited",
    "metaInfo": {"symbol": "BETA", "segment": "SME"},
    "bidDetails": [
        {"category": "Qualified Institutional Buyers(QIBs)", "noOfshareBid": "200000", "noofapplication": "4", "srNo": "1"},
        {"category": "Non Institutional Investors", "noOfshareBid": "300000", "noofapplication": "30", "srNo": "2"},
        {"category": "Individual Investors (IND category bidding for 2 Lots)", "noOfshareBid": "500000", "noofapplication": "200", "srNo": "3"},
        {"category": "Total", "noOfshareBid": "1000000", "noofapplication": "234", "srNo": None},
    ],
    "activeCat": {"dataList": [
        {"category": "Total", "noOfShareOffered": "0.0", "noOfSharesBid": "0", "noOfTotalMeant": "0.00", "srNo": None},
    ]},
    "issueInfo": {"dataList": [
        {"title": "Issue Size", "value": "\"Initial Public Offer of upto 1,20,000 Equity Shares (including Market Maker portion of 10,000 Equity Shares and Anchor Allocation 10,000 Equity Shares)\""},
        {"title": "Lot Size", "value": "1000 Equity Shares"},
        {"title": "Issue Type", "value": "Book Building"},
    ]},
}


class FakeClient:
    def __init__(self, history=None, details=None, fail_history=False, flaky=0):
        self.history = history or {}
        self.details = details or {}
        self.fail_history = fail_history
        # Number of history calls that fail like a reset NSE connection.
        self.flaky = flaky
        self.calls = []

    def get_json(self, path, params=None):
        params = params or {}
        self.calls.append((path, dict(params)))
        if path == PAST_ISSUES_PATH:
            return PAST_ISSUES
        if path == ISSUE_DETAIL_PATH:
            return self.details.get(params["symbol"], {})
        if path == PRICE_HISTORY_PATH:
            if self.fail_history:
                raise RuntimeError("NSE unavailable")
            if self.flaky:
                self.flaky -= 1
                raise ConnectionResetError("connection reset by peer")
            start = datetime.strptime(params["from"], "%d-%m-%Y").date()
            end = datetime.strptime(params["to"], "%d-%m-%Y").date()
            rows = [
                row for row in self.history.get(params["symbol"], [])
                if start <= date.fromisoformat(row["CH_TIMESTAMP"]) <= end
            ]
            return {"data": rows}
        raise AssertionError(f"unexpected path {path}")


def _daily_bars(start, count, *, first=None, base=100.0, step=1.0, series="EQ"):
    bars = []
    day = start
    price = base
    while len(bars) < count:
        if day.weekday() < 5:
            if not bars and first is not None:
                bars.append(first)
            else:
                bars.append(_bar(day.isoformat(), price, price + 2, price - 2, price + 1, series=series, vwap=price + 0.5))
                price += step
        day += timedelta(days=1)
    return bars


@pytest.mark.offline
def test_past_issues_classify_boards_and_repair_prices() -> None:
    api = NSEIpo(client=FakeClient())

    issues = api.past_issues()
    by_symbol = {issue["symbol"]: issue for issue in issues}

    assert [issue["symbol"] for issue in issues].count("ALPHA") == 1
    assert by_symbol["ALPHA"]["board"] == "mainboard"
    assert by_symbol["ALPHA"]["issue_price"] == 100.0
    assert by_symbol["ALPHA"]["issue_price_source"] == "issue_price"
    assert by_symbol["ALPHA"]["listing_date"] == date(2024, 1, 8)
    assert by_symbol["BETA"]["board"] == "sme"
    assert by_symbol["BETA"]["issue_price"] == 54.0
    assert by_symbol["BETA"]["issue_price_source"] == "price_band_upper"
    assert by_symbol["GAMMA"]["board"] == "invit"
    assert by_symbol["NCD1"]["board"] == "debt"
    # Unlisted issues sort first (newest), then listing date descending.
    assert issues[0]["symbol"] == "OPEN"
    assert issues[0]["listing_date"] is None

    equity = api.past_issues(boards=("mainboard", "sme"), from_date="2024-01-01", to_date="2024-12-31")
    assert [issue["symbol"] for issue in equity] == ["BETA", "ALPHA"]
    assert [issue["symbol"] for issue in api.past_issues(boards="sme")] == ["BETA"]

    with pytest.raises(InputValidationError):
        api.past_issues(boards=("crypto",))
    with pytest.raises(InputValidationError):
        api.past_issues(from_date="2024-02-01", to_date="2024-01-01")


@pytest.mark.offline
def test_mainboard_detail_prefers_consolidated_book() -> None:
    api = NSEIpo(client=FakeClient(details={"ALPHA": MAINBOARD_DETAIL}))

    detail = api.issue_detail("alpha", board="mainboard")

    assert detail["subscription_source"] == "consolidated"
    assert detail["subscription"]["total"] == pytest.approx(9.857)
    assert detail["subscription"]["qib"] == 20
    assert detail["subscription"]["nii_big"] == 12
    assert detail["subscription"]["nii_small"] == 6
    assert detail["subscription"]["retail"] == 4
    assert detail["book_shares"] == 700
    assert detail["qib_book_shares"] == 200
    assert detail["lot_size"] == 150
    assert detail["min_application_qty"] == 150
    assert detail["retail_discount"] == 5
    assert detail["issue_type"] == "book_building"
    assert detail["structure"]["anchor_shares"] == 300


@pytest.mark.offline
def test_sme_detail_estimates_subscription_from_issue_structure() -> None:
    api = NSEIpo(client=FakeClient(details={"BETA": SME_DETAIL}))

    detail = api.issue_detail("BETA", board="sme")

    # Net book = 1,20,000 - 10,000 market maker - 10,000 anchor.
    assert detail["book_shares"] == 100000
    assert detail["subscription_source"] == "nse_book_estimate"
    assert detail["subscription"] == {"total": 10.0}
    assert detail["lots_per_application"] == 2
    assert detail["min_application_qty"] == 2000
    assert detail["applications"]["total"] == 234
    assert detail["applications"]["retail"] == 200


@pytest.mark.offline
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Initial Public offer of 55,80,000 Equity Shares (including Market Maker portion of 3,00,000 Equity Shares)",
         {"total_shares": 5580000, "market_maker_shares": 300000, "anchor_shares": None}),
        ("Initial Public offer of [.] Equity Shares comprising a Fresh Issue of Rs 405.40 Million (including anchor portion of 56,25,415 Equity Shares)",
         {"total_shares": 5625415, "market_maker_shares": None, "anchor_shares": 5625415}),
        ("Initial Public Offering of upto 37,50,400 fresh equity shares (including market maker portion of 1,88,800 equity shares)",
         {"total_shares": 3750400, "market_maker_shares": 188800, "anchor_shares": None}),
        ("Offer of Rs. 1,000 crore of equity shares", {"total_shares": None, "market_maker_shares": None, "anchor_shares": None}),
        ("Fresh issue aggregating up to Rs. 6,000 million and an Offer for sale aggregating up to Rs. 4,000 million",
         {"total_shares": None, "market_maker_shares": None, "anchor_shares": None}),
        (None, {"total_shares": None, "market_maker_shares": None, "anchor_shares": None}),
    ],
)
def test_issue_structure_parsing(text, expected) -> None:
    assert _parse_issue_structure(text) == expected


@pytest.mark.offline
def test_retail_discount_only_counts_retail() -> None:
    assert _parse_retail_discount("Rs.45 per Equity Share to Retail and Eligible Employee Categories") == 45
    assert _parse_retail_discount("Rs.15/- per Equity Share for Eligible Employees category") is None
    assert _parse_retail_discount(None) is None


@pytest.mark.offline
def test_price_history_chunks_and_keeps_the_most_traded_series() -> None:
    rows = [
        _bar("2024-01-08", 110, 120, 105, 118, series="BE", previous=100, volume=500),
        _bar("2024-01-08", 111, 121, 104, 117, series="EQ", previous=100, volume=50),
        _bar("2024-05-08", 150, 151, 149, 150, series="EQ", volume=10),
    ]
    client = FakeClient(history={"ALPHA": rows})
    api = NSEIpo(client=client)

    bars = api.price_history("ALPHA", "2024-01-08", "2024-06-30")

    assert [bar["date"] for bar in bars] == [date(2024, 1, 8), date(2024, 5, 8)]
    assert bars[0]["series"] == "BE"
    history_calls = [params for path, params in client.calls if path == PRICE_HISTORY_PATH]
    assert len(history_calls) == 2
    for params in history_calls:
        span = datetime.strptime(params["to"], "%d-%m-%Y") - datetime.strptime(params["from"], "%d-%m-%Y")
        assert span.days < 90
        assert '"ST"' in params["series"] and '"EQ"' in params["series"]


@pytest.mark.offline
def test_listing_performance_uses_calendar_horizons_and_base_price_fallback() -> None:
    listing = date(2024, 1, 8)
    first = _bar("2024-01-08", 150, 180, 140, 170, previous=100, vwap=160)
    rows = [
        {"date": date.fromisoformat(bar["CH_TIMESTAMP"]), "open": bar["CH_OPENING_PRICE"], "high": bar["CH_TRADE_HIGH_PRICE"],
         "low": bar["CH_TRADE_LOW_PRICE"], "close": bar["CH_CLOSING_PRICE"], "vwap": bar["VWAP"],
         "previous_close": bar["CH_PREVIOUS_CLS_PRICE"], "series": "EQ", "volume": 1}
        for bar in _daily_bars(listing, 60, first=first, base=160.0, step=1.0)
    ]

    result = analyze_listing_performance(rows, listing, None)

    assert result["has_listing_data"] is True
    assert result["issue_price_used"] == 100  # from NSE's listing base price
    assert result["return_open_pct"] == 50
    assert result["return_high_pct"] == 80
    assert result["return_low_pct"] == 40
    assert result["return_close_pct"] == 70
    assert result["return_vwap_pct"] == 60
    assert result["close_vs_open_pct"] == pytest.approx(13.3333, abs=1e-4)
    assert result["date_d1"] == "2024-01-09"
    # 7 calendar days after a Monday listing is the next Monday.
    assert result["date_w1"] == "2024-01-15"
    assert result["date_m1"] == "2024-02-07"
    assert result["return_m3_pct"] is None  # 60 sessions end before listing + 91 days
    # Highs climb 1/day: the 22nd session after listing (Feb 7) peaks at 183.
    assert result["return_max_m1_pct"] == 83
    assert result["return_min_m1_pct"] == 40


@pytest.mark.offline
def test_listing_performance_without_bars_is_empty() -> None:
    result = analyze_listing_performance([], "2024-01-08", 100)
    assert result["has_listing_data"] is False
    assert result["sessions_observed"] == 0


@pytest.mark.offline
def test_backtest_record_derives_money_fields() -> None:
    listing = date(2024, 1, 8)
    first = _bar("2024-01-08", 150, 180, 140, 170, previous=100, vwap=160)
    client = FakeClient(
        history={"ALPHA": _daily_bars(listing, 300, first=first, base=160.0, step=0.5)},
        details={"ALPHA": MAINBOARD_DETAIL},
    )
    api = NSEIpo(client=client)
    issue = next(issue for issue in api.past_issues() if issue["symbol"] == "ALPHA")

    record = build_ipo_record(api, issue, today=date(2025, 6, 1))

    assert record["key"] == "ALPHA:2024-01-08"
    assert record["days_to_listing"] == 5
    assert record["min_application_value"] == 15000
    assert record["profit_open"] == 150 * 50
    assert record["allotment_probability"] == 0.25  # 1 / 4x retail
    assert record["expected_profit_open"] == 150 * 50 * 0.25
    # Book (700) + parsed anchor (300) shares at Rs.100.
    assert record["issue_size_cr"] == pytest.approx(0.01)
    assert record["issue_size_basis"] == "book_plus_anchor"
    assert record["issue_price_mismatch"] is False
    assert record["return_y1_pct"] is not None
    assert record["is_final"] is True
    assert record["errors"] == []
    assert ipo_record_needs_refresh(record, today=date(2025, 6, 1)) is False


@pytest.mark.offline
def test_band_price_is_replaced_by_listing_base_price() -> None:
    listing = date(2024, 2, 9)
    first = _bar("2024-02-09", 60, 63, 57, 62, series="ST", previous=51, vwap=61)
    client = FakeClient(history={"BETA": _daily_bars(listing, 20, first=first, series="ST")}, details={"BETA": SME_DETAIL})
    api = NSEIpo(client=client)
    issue = next(issue for issue in api.past_issues() if issue["symbol"] == "BETA")
    assert issue["issue_price"] == 54

    record = build_ipo_record(api, issue, today=date(2024, 3, 1))

    assert record["issue_price"] == 51
    assert record["issue_price_source"] == "listing_base_price"
    # Returns are measured on the same (base) price that the record reports.
    assert record["return_open_pct"] == pytest.approx((60 / 51 - 1) * 100, abs=1e-3)
    assert record["allotment_probability"] is None
    assert record["expected_profit_open"] is None
    assert record["profit_open"] == 2000 * (60 - 51)
    assert record["is_final"] is False


@pytest.mark.offline
def test_refresh_rules() -> None:
    today = date(2024, 3, 1)
    fresh = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    base = {"schema_version": 1, "listing_date": "2024-01-08", "has_listing_data": True, "detail_fetched": True}
    horizons = {f"return_{name}_pct": 1.0 for name in ("d1", "w1", "m1")}

    assert ipo_record_needs_refresh({**base, "is_final": True}, today=today) is False
    assert ipo_record_needs_refresh({**base, "fetched_at": fresh}, today=today) is False
    # m1 has printed; m3 is not due until April.
    assert ipo_record_needs_refresh({**base, **horizons, "fetched_at": stale}, today=today) is False
    assert ipo_record_needs_refresh({**base, "return_d1_pct": 1.0, "fetched_at": stale}, today=today) is True
    assert ipo_record_needs_refresh({**base, **horizons, "detail_fetched": False, "fetched_at": stale}, today=today) is True
    assert ipo_record_needs_refresh({**base, "schema_version": 0, "is_final": True}, today=today) is True


@pytest.mark.offline
def test_backtest_reuses_final_records_without_network() -> None:
    client = FakeClient(fail_history=True, details={"BETA": SME_DETAIL})
    api = NSEIpo(client=client)
    existing = [{"key": "ALPHA:2024-01-08", "schema_version": 1, "symbol": "ALPHA", "is_final": True,
                 "listing_date": "2024-01-08", "has_listing_data": True}]

    records = api.backtest(existing=existing, max_workers=1, today=date(2024, 3, 1))

    assert [record["symbol"] for record in records] == ["BETA", "ALPHA"]
    assert records[1] is not existing[0] and records[1]["is_final"] is True
    assert not any(params.get("symbol") == "ALPHA" for _, params in client.calls)
    beta = records[0]
    assert beta["has_listing_data"] is False
    assert beta["errors"] and beta["errors"][0].startswith("history:")


@pytest.mark.offline
def test_backtest_cools_down_and_retries_network_failures() -> None:
    listing = date(2024, 1, 8)
    first = _bar("2024-01-08", 150, 180, 140, 170, previous=100, vwap=160)
    beta_first = _bar("2024-02-09", 60, 63, 57, 62, series="ST", previous=51, vwap=61)
    client = FakeClient(
        history={
            "ALPHA": _daily_bars(listing, 30, first=first),
            "BETA": _daily_bars(date(2024, 2, 9), 30, first=beta_first, series="ST"),
        },
        details={"ALPHA": MAINBOARD_DETAIL, "BETA": SME_DETAIL},
        flaky=2,
    )
    sleeps = []

    resets = []
    client.reset_session = lambda: resets.append(True)

    records = NSEIpo(client=client).backtest(
        max_workers=1, failure_burst=2, cooldown_seconds=5, sleep=sleeps.append, today=date(2024, 3, 1)
    )

    assert sleeps == [5]
    # The cooldown swaps in a fresh transport before resuming.
    assert resets == [True]
    assert {record["symbol"]: record["has_listing_data"] for record in records} == {"ALPHA": True, "BETA": True}
    assert not any(record["transient_error"] for record in records)


@pytest.mark.offline
def test_backtest_stops_after_max_cooldowns_and_never_finalizes_network_failures() -> None:
    client = FakeClient(flaky=10_000)
    sleeps = []
    seen = []

    records = NSEIpo(client=client).backtest(
        max_workers=1,
        failure_burst=1,
        cooldown_seconds=1,
        max_cooldowns=1,
        sleep=sleeps.append,
        progress=lambda done, total, record: seen.append(record["symbol"]),
        today=date(2030, 1, 1),
    )

    assert sleeps == [1]
    assert len(seen) <= 2
    for record in records:
        assert record["transient_error"] is True
        assert record["is_final"] is False
        assert record["attempts"] == 0
        assert ipo_record_needs_refresh(record, today=date(2030, 1, 1)) is True


def _record(symbol, listing, board, subscription, open_, close, *, probability=None, qty=100, issue=100.0):
    return {
        "symbol": symbol,
        "board": board,
        "listing_date": listing,
        "listing_year": int(listing[:4]),
        "has_listing_data": True,
        "issue_price": issue,
        "subscription_total_x": subscription,
        "return_open_pct": open_,
        "return_close_pct": close,
        "return_high_pct": max(open_, close) + 5,
        "return_low_pct": min(open_, close) - 5,
        "return_vwap_pct": (open_ + close) / 2,
        "close_vs_open_pct": close - open_,
        "high_vs_open_pct": 5.0,
        "low_vs_open_pct": -5.0,
        "profit_open": qty * issue * open_ / 100,
        "expected_profit_open": qty * issue * open_ / 100 * probability if probability is not None else None,
        "allotment_probability": probability,
        "min_application_value": qty * issue,
    }


@pytest.mark.offline
def test_summary_groups_strategies_and_pnl() -> None:
    records = [
        _record("A", "2023-01-10", "mainboard", 0.5, -10.0, -12.0, probability=1.0),
        _record("B", "2023-06-10", "mainboard", 50.0, 40.0, 50.0, probability=0.1),
        _record("C", "2024-02-10", "sme", 150.0, 90.0, 94.5),
        {**_record("D", "2024-03-10", "mainboard", 5.0, 10.0, 8.0), "has_listing_data": False},
        _record("E", "2024-04-10", "invit", 2.0, 1.0, 1.0),
    ]

    summary = summarize_ipo_backtest(records, "open")

    assert summary["count"] == 3
    assert summary["headline"]["median_pct"] == 40.0
    assert summary["headline"]["win_rate_pct"] == pytest.approx(66.6667, abs=1e-4)
    assert summary["strategies"]["close"]["mean_pct"] == pytest.approx((-12 + 50 + 94.5) / 3)
    assert [group["group"] for group in summary["by_subscription"]] == ["<1x", "30-100x", "100x+"]
    assert [group["group"] for group in summary["by_year"]] == ["2023", "2024"]
    assert summary["intraday"]["close_above_open_pct"] == pytest.approx(66.6667, abs=1e-4)
    pnl = summary["pnl"]
    assert pnl["applications"] == 3
    assert pnl["total_profit_if_always_allotted"] == -1000 + 4000 + 9000
    assert pnl["expected_profit_applications"] == 2
    assert pnl["total_expected_profit"] == -1000 + 400
    assert [point["cumulative_profit"] for point in pnl["curve"]] == [-1000, 3000, 12000]
    assert summary["best"][0]["symbol"] == "C"
    assert summary["worst"][0]["symbol"] == "A"

    sme_only = summarize_ipo_backtest(records, "close", boards=["sme"])
    assert sme_only["count"] == 1
    oversubscribed = summarize_ipo_backtest(records, "open", min_subscription=10)
    assert {row["symbol"] for row in oversubscribed["best"]} == {"B", "C"}

    with pytest.raises(InputValidationError):
        summarize_ipo_backtest(records, "moon")


@pytest.mark.offline
def test_distribution_and_buckets() -> None:
    assert return_distribution([None]) == {"count": 0}
    stats = return_distribution([-10, 0, 10, 20])
    assert stats["median_pct"] == 5
    assert stats["win_rate_pct"] == 50
    assert stats["loss_rate_pct"] == 25
    assert subscription_bucket(0.2) == "<1x"
    assert subscription_bucket(3) == "3-10x"
    assert subscription_bucket(1000) == "100x+"
    assert subscription_bucket(None) is None


@pytest.mark.offline
def test_live_issues_merge_feeds_and_backfill_sme_bands() -> None:
    class LiveClient(FakeClient):
        def get_json(self, path, params=None):
            if path == "/api/ipo-current-issue":
                return [
                    {"symbol": "OPEN", "series": "SME", "status": "Active", "issuePrice": None, "noOfTime": "3.5",
                     "issueStartDate": "20-Sep-2026", "issueEndDate": "22-Sep-2026"},
                    {"symbol": "MAINX", "series": "EQ", "status": "Active", "issuePrice": "Rs.10 to Rs.12",
                     "noOfTime": "1.2", "issueStartDate": "21-Sep-2026", "issueEndDate": "23-Sep-2026"},
                ]
            if path == "/api/all-upcoming-issues":
                return [
                    {"symbol": "MAINX", "series": "EQ", "status": "Active", "issuePrice": "Rs.10 to Rs.12",
                     "issueStartDate": "21-Sep-2026", "issueEndDate": "23-Sep-2026", "issueSize": "1000"},
                    {"symbol": "LATER", "series": "EQ", "status": "Forthcoming", "issuePrice": "Rs.50 to Rs.55",
                     "issueStartDate": "28-Sep-2026", "issueEndDate": "30-Sep-2026"},
                ]
            return super().get_json(path, params)

    rows = NSEIpo(client=LiveClient()).live_issues()

    assert [row["symbol"] for row in rows] == ["OPEN", "MAINX", "LATER"]
    open_sme, mainx, later = rows
    assert open_sme["board"] == "sme"
    assert open_sme["subscription_total_x"] == 3.5
    # Band comes from the past-issues list ("Rs.10 to Rs.12" for OPEN).
    assert (open_sme["price_band_low"], open_sme["price_band_high"]) == (10.0, 12.0)
    assert mainx["subscription_total_x"] == 1.2 and mainx["shares_offered"] == 1000
    assert later["status"] == "Forthcoming"


@pytest.mark.offline
def test_band_price_is_the_last_resort_when_no_base_price() -> None:
    rows = [{"date": date(2024, 2, 9), "open": 60.0, "high": 63.0, "low": 57.0, "close": 62.0, "previous_close": None}]
    result = analyze_listing_performance(rows, "2024-02-09", None, fallback_price=54.0)
    assert result["issue_price_used"] == 54.0
    assert result["return_open_pct"] == pytest.approx((60 / 54 - 1) * 100, abs=1e-3)


def _issue(symbol, *, price, band, bid_end, listed, board="mainboard", source="issue_price"):
    return {
        "symbol": symbol, "company_name": symbol, "board": board, "security_type": "EQ",
        "issue_start_date": bid_end - timedelta(days=2), "issue_end_date": bid_end, "listing_date": listed,
        "issue_price": price, "issue_price_source": source, "price_band_low": band[0], "price_band_high": band[1],
    }


@pytest.mark.offline
def test_clerical_issue_price_is_replaced_and_returns_remeasured() -> None:
    listed = date(2024, 2, 23)
    first = _bar("2024-02-23", 47, 50, 45, 49, series="ST", previous=45, vwap=48)
    client = FakeClient(history={"KTL": _daily_bars(listed, 5, first=first, series="ST")})
    issue = _issue("KTL", price=10.0, band=(45.0, 45.0), bid_end=date(2024, 2, 20), listed=listed, board="sme")

    record = build_ipo_record(NSEIpo(client=client), issue, include_detail=False, today=date(2024, 3, 1))

    assert record["issue_price"] == 45
    assert record["issue_price_source"] == "listing_base_price"
    assert record["return_open_pct"] == pytest.approx((47 / 45 - 1) * 100, abs=1e-3)
    assert record["listing_kind"] == "ipo"


@pytest.mark.offline
def test_later_listings_and_contradictory_prices_are_tagged_and_filtered() -> None:
    listed = date(2026, 3, 12)
    first = _bar("2026-03-12", 316, 320, 300, 310, series="EQ", previous=315.85, vwap=312)
    client = FakeClient(history={"KOTYARK": _daily_bars(listed, 5, first=first), "ODD": _daily_bars(listed, 5, first=first)})
    api = NSEIpo(client=client)
    # SME IPO from 2021 whose 2026 mainboard migration NSE lists as an "issue".
    migration = build_ipo_record(
        api, _issue("KOTYARK", price=281.0, band=(51.0, 51.0), bid_end=date(2021, 10, 25), listed=listed, board="sme"),
        include_detail=False, today=date(2026, 4, 1),
    )
    odd = build_ipo_record(
        api, _issue("ODD", price=10.0, band=(95.0, 100.0), bid_end=date(2026, 3, 9), listed=listed),
        include_detail=False, today=date(2026, 4, 1),
    )

    assert migration["listing_kind"] == "later_listing"
    assert "migration" in migration["listing_kind_reason"]
    assert odd["listing_kind"] == "unverified"
    ipo = {**migration, "key": "REAL:2026-03-12", "symbol": "REAL", "listing_kind": "ipo", "days_to_listing": 3}
    kept = filter_ipo_records([migration, odd, ipo])
    assert [row["symbol"] for row in kept] == ["REAL"]
    assert len(filter_ipo_records([migration, odd, ipo], include_later_listings=True)) == 3
    assert summarize_ipo_backtest([migration, odd, ipo])["count"] == 1
