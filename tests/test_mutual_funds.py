from datetime import date

import pytest

from aynse import (
    AMFIMutualFunds,
    analyze_mutual_fund,
    compare_mutual_funds,
    mutual_fund_history_raw,
    mutual_fund_search,
)
from aynse.mutual_funds import (
    AMFI_NAV_DOWNLOAD_PAGE_URL,
    AMFI_MAX_HISTORY_WINDOW_DAYS,
    _history_windows,
    _normalized_lookup,
    _parse_amfi_records,
)
from aynse.standard import InputValidationError
from aynse.standard import UpstreamResponseError


@pytest.mark.offline
def test_current_latest_nav_layout_is_parsed_by_header_name() -> None:
    payload = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Flexi Cap Fund)

PPFAS Mutual Fund

122639;INF879O01027;-;Parag Parikh Flexi Cap Fund;Direct Plan;Growth;89.5712;11-Sep-2026
"""
    records, saw_header = _parse_amfi_records(payload.splitlines())

    assert saw_header is True
    assert records == [
        {
            "scheme_code": "122639",
            "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
            "scheme_base_name": "Parag Parikh Flexi Cap Fund",
            "fund_house": "PPFAS Mutual Fund",
            "scheme_type": "Open Ended",
            "scheme_category": "Equity Scheme - Flexi Cap Fund",
            "plan": "Direct Plan",
            "option": "Growth",
            "isin_growth": "INF879O01027",
            "isin_div_reinvestment": None,
            "nav": 89.5712,
            "date": date(2026, 9, 11),
            "source": "AMFI",
        }
    ]


@pytest.mark.offline
def test_current_history_layout_is_parsed_and_filtered() -> None:
    payload = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Flexi Cap Fund )
PPFAS Mutual Fund
122638;Parag Parikh Flexi Cap Fund - Regular Plan - Growth;Regular Plan;Growth;INF879O01019;;82.1;10-Sep-2026
122639;Parag Parikh Flexi Cap Fund - Direct Plan - Growth;Direct Plan;Growth;INF879O01027;;89.4;10-Sep-2026
122639;Parag Parikh Flexi Cap Fund - Direct Plan - Growth;Direct Plan;Growth;INF879O01027;;89.5712;11-Sep-2026
"""
    records, saw_header = _parse_amfi_records(payload.splitlines(), scheme_code="122639")

    assert saw_header is True
    assert [record["date"] for record in records] == [date(2026, 9, 10), date(2026, 9, 11)]
    assert records[0]["scheme_name"] == "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"
    assert records[0]["plan"] == "Direct Plan"


@pytest.mark.offline
def test_fund_house_persists_across_sections_in_latest_report() -> None:
    payload = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
PPFAS Mutual Fund
Open Ended Schemes(Equity Scheme - Flexi Cap Fund)
122639;INF879O01027;-;Parag Parikh Flexi Cap Fund;Direct Plan;Growth;89.5712;11-Sep-2026
Open Ended Schemes(Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage)
148978;INF879O01142;-;Parag Parikh Dynamic Asset Allocation Fund;Direct Plan;Growth;16.25;11-Sep-2026
"""

    records, saw_header = _parse_amfi_records(payload.splitlines())

    assert saw_header is True
    assert [record["fund_house"] for record in records] == ["PPFAS Mutual Fund", "PPFAS Mutual Fund"]


@pytest.mark.offline
def test_legacy_latest_and_history_layouts_remain_compatible() -> None:
    old_latest = """Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
Open Ended Schemes(Debt Scheme - Liquid Fund)
Axis Mutual Fund
112210;INF846K01412;-;Axis Liquid Fund - Regular Plan - Growth Option;2500.5;10-Sep-2026
"""
    latest, latest_header = _parse_amfi_records(old_latest.splitlines())
    assert latest_header is True
    assert latest[0]["scheme_name"] == "Axis Liquid Fund - Regular Plan - Growth Option"
    assert latest[0]["nav"] == 2500.5

    old_history = """Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date
Open Ended Schemes ( Debt Scheme - Liquid Fund )
Axis Mutual Fund
112210;Axis Liquid Fund - Regular Plan - Growth Option;INF846K01412;;2499.1;;;09-Sep-2026
"""
    history, history_header = _parse_amfi_records(old_history.splitlines())
    assert history_header is True
    assert history[0]["date"] == date(2026, 9, 9)
    assert history[0]["isin_growth"] == "INF846K01412"


@pytest.mark.offline
def test_history_ranges_are_inclusive_and_never_exceed_amfi_limit() -> None:
    windows = _history_windows(date(2026, 1, 1), date(2026, 7, 15))

    assert windows[0] == (date(2026, 1, 1), date(2026, 3, 31))
    assert windows[-1][1] == date(2026, 7, 15)
    assert all((end - start).days + 1 <= AMFI_MAX_HISTORY_WINDOW_DAYS for start, end in windows)


@pytest.mark.offline
def test_nav_analytics_are_explicitly_short_period_safe() -> None:
    records = [
        {"date": "2026-01-01", "nav": 100.0},
        {"date": "2026-01-02", "nav": 90.0},
        {"date": "2026-06-01", "nav": 110.0},
    ]

    metrics = analyze_mutual_fund(records)

    assert metrics["absolute_return_percent"] == 10.0
    assert metrics["cagr_percent"] is None
    assert metrics["max_drawdown_percent"] == -10.0
    assert metrics["observations"] == 3


@pytest.mark.offline
def test_nav_analytics_compute_cagr_for_a_full_year() -> None:
    metrics = analyze_mutual_fund(
        [
            {"date": "2025-01-01", "nav": 100.0},
            {"date": "2026-01-01", "nav": 121.0},
        ]
    )

    assert metrics["cagr_percent"] == pytest.approx(21.0, abs=0.03)
    assert metrics["annualized_volatility_percent"] is None


@pytest.mark.offline
def test_search_ranks_exact_scheme_code_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AMFIMutualFunds(latest_cache_seconds=0)
    monkeypatch.setattr(
        client,
        "latest",
        lambda: [
            {
                "scheme_code": "100001",
                "scheme_name": "Example Fund - Direct Plan - Growth",
                "scheme_base_name": "Example Fund",
                "fund_house": "Example Mutual Fund",
                "scheme_type": "Open Ended",
                "scheme_category": "Equity Scheme - Flexi Cap Fund",
                "plan": "Direct Plan",
                "option": "Growth",
                "isin_growth": "INF000000001",
                "isin_div_reinvestment": None,
                "nav": 12.5,
                "date": date(2026, 9, 11),
            }
        ],
    )

    result = client.search("100001")

    assert result[0]["scheme_code"] == "100001"
    assert result[0]["latest_nav_date"] == "2026-09-11"


@pytest.mark.offline
def test_latest_cache_is_isolated_per_client(monkeypatch: pytest.MonkeyPatch) -> None:
    first = AMFIMutualFunds(latest_cache_seconds=3600)
    second = AMFIMutualFunds(latest_cache_seconds=3600)
    monkeypatch.setattr(first, "_fetch_latest", lambda: [{"scheme_code": "1"}])
    monkeypatch.setattr(second, "_fetch_latest", lambda: [{"scheme_code": "2"}])

    assert first.latest() == [{"scheme_code": "1"}]
    assert second.latest() == [{"scheme_code": "2"}]


@pytest.mark.offline
def test_empty_latest_report_is_an_upstream_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AMFIMutualFunds()
    monkeypatch.setattr(
        client,
        "_response_lines",
        lambda _url: iter(
            [
                "Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;"
                "Scheme Name;Net Asset Value;Date"
            ]
        ),
    )

    with pytest.raises(UpstreamResponseError, match="no usable scheme records"):
        client.latest()


@pytest.mark.offline
def test_amc_ids_parse_escaped_download_page_data(monkeypatch: pytest.MonkeyPatch) -> None:
    page = (
        r'{\"mfId\":\"39\",\"mfName\":\"ABN AMRO Mutual Fund\"},'
        r'{\"mfId\":\"29\",\"mfName\":\"Zurich India Mutual Fund\"}'
    )

    class Response:
        text = page

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(url, **_kwargs):
            assert url == AMFI_NAV_DOWNLOAD_PAGE_URL
            return Response()

    client = AMFIMutualFunds(session=Session(), amc_cache_seconds=0)
    mappings = client._amc_ids()

    assert mappings[_normalized_lookup("ABN AMRO Mutual Fund")] == "39"
    assert mappings[_normalized_lookup("Zurich India Mutual Fund")] == "29"


@pytest.mark.offline
def test_history_falls_back_to_all_amcs_when_download_id_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AMFIMutualFunds()
    monkeypatch.setattr(
        client,
        "_latest_scheme",
        lambda _code: {
            "scheme_code": "999999",
            "scheme_name": "New Fund - Direct Plan - Growth",
            "fund_house": "New Mutual Fund",
        },
    )
    monkeypatch.setattr(client, "_amc_ids", lambda: {})
    seen_params = []

    def response_lines(_url, *, params=None):
        seen_params.append(params)
        return iter(
            """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date
New Mutual Fund
999999;New Fund - Direct Plan - Growth;Direct Plan;Growth;INF000000001;;10.5;11-Sep-2026
""".splitlines()
        )

    monkeypatch.setattr(client, "_response_lines", response_lines)
    records = client.history("999999", "2026-09-01", "2026-09-14")

    assert "mf" not in seen_params[0]
    assert records[0]["nav"] == 10.5


@pytest.mark.offline
def test_comparison_recalculates_metrics_on_common_nav_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = {
        "1": {
            "scheme": {"scheme_code": "1", "scheme_name": "Older Fund"},
            "nav_points": [
                {"date": "2025-01-01", "nav": 50.0},
                {"date": "2025-01-02", "nav": 100.0},
                {"date": "2025-01-03", "nav": 105.0},
                {"date": "2025-01-04", "nav": 110.0},
            ],
            "metrics": {},
            "source": "AMFI",
        },
        "2": {
            "scheme": {"scheme_code": "2", "scheme_name": "Newer Fund"},
            "nav_points": [
                {"date": "2025-01-02", "nav": 200.0},
                {"date": "2025-01-04", "nav": 220.0},
            ],
            "metrics": {},
            "source": "AMFI",
        },
    }

    class FakeClient:
        def summary(self, code, _start, _end):
            return summaries[str(code)]

    monkeypatch.setattr("aynse.mutual_funds._default_client", lambda: FakeClient())
    result = compare_mutual_funds(["1", "2"], "2025-01-01", "2025-01-04")

    assert result["from_date"] == "2025-01-02"
    assert result["to_date"] == "2025-01-04"
    assert result["requested_from_date"] == "2025-01-01"
    assert [fund["metrics"]["absolute_return_percent"] for fund in result["funds"]] == [10.0, 10.0]
    assert [fund["nav_points"][0]["date"] for fund in result["funds"]] == ["2025-01-02", "2025-01-02"]
    assert [len(fund["nav_points"]) for fund in result["funds"]] == [2, 2]


@pytest.mark.offline
def test_invalid_scheme_code_and_date_order_are_rejected() -> None:
    with pytest.raises(InputValidationError, match="positive AMFI numeric"):
        mutual_fund_history_raw("not-a-code", "2026-01-01", "2026-01-31")
    with pytest.raises(InputValidationError, match="on or before"):
        _history_windows(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(InputValidationError, match="at least two"):
        compare_mutual_funds(["122639"], "2026-01-01", "2026-01-31")
    with pytest.raises(InputValidationError, match="sequence"):
        compare_mutual_funds("122639", "2026-01-01", "2026-01-31")


@pytest.mark.offline
def test_mutual_fund_functions_are_public_exports() -> None:
    assert callable(mutual_fund_search)
    assert callable(mutual_fund_history_raw)
    assert callable(compare_mutual_funds)
