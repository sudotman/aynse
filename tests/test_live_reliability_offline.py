from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from aynse.nse import http_client
from aynse.nse.live import NSELive
from aynse.standard import InputValidationError


def _live_with_client(client: MagicMock) -> NSELive:
    live = object.__new__(NSELive)
    live.client = client
    live.time_out = 0
    return live


def _quote_payload() -> dict:
    return {
        "info": {
            "symbol": "RELIANCE",
            "companyName": "Reliance Industries Limited",
            "isin": "INE002A01018",
            "industry": "REFINERIES",
            "isFNOSec": True,
        },
        "priceInfo": {
            "lastPrice": 3_100.5,
            "change": 20.5,
            "pChange": 0.67,
            "previousClose": 3_080,
            "intraDayHighLow": {"min": 3_075, "max": 3_125},
            "weekHighLow": {"min": 2_220, "max": 3_217},
        },
    }


def _chain_payload(expiry: str) -> dict:
    return {
        "records": {
            "timestamp": "16-Jul-2026 15:30:00",
            "underlyingValue": 3_100.5,
            "expiryDates": [expiry],
            "strikePrices": [3_100],
            "data": [
                {
                    "expiryDate": expiry,
                    "strikePrice": 3_100,
                    "CE": {
                        "identifier": "RELIANCE",
                        "openInterest": 120,
                        "lastPrice": 55.5,
                    },
                    "PE": {
                        "identifier": "RELIANCE",
                        "openInterest": 80,
                        "lastPrice": 42.0,
                    },
                }
            ],
        }
    }


def test_sync_and_async_clients_do_not_advertise_brotli() -> None:
    for client_type, constructor_name in (
        (http_client.NSEHttpClient, "Client"),
        (http_client.NSEAsyncHttpClient, "AsyncClient"),
    ):
        instance = object.__new__(client_type)
        instance.base_url = "https://www.nseindia.com"
        instance.timeout = 5.0
        instance._limits = MagicMock()

        with patch.object(http_client.httpx, constructor_name) as constructor:
            instance._build_client()

        encoding = constructor.call_args.kwargs["headers"]["Accept-Encoding"]
        assert encoding == "gzip, deflate"
        assert "br" not in {item.strip() for item in encoding.split(",")}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "expiryDates": ["30-Jul-2026", "27-Aug-2026"],
            "strikePrice": ["3,000", 3_100, 3_100],
        },
        {
            "records": {
                "expiryDates": ["30-Jul-2026", "27-Aug-2026"],
                "strikePrices": [3_000, "3100"],
            }
        },
        {
            "data": {
                "expiryDate": ["30-Jul-2026", "27-Aug-2026"],
                "strike_prices": [3_000, 3_100],
            }
        },
    ],
)
def test_option_chain_contract_info_normalizes_response_variants(
    payload: dict,
) -> None:
    client = MagicMock()
    client.get_json.return_value = payload
    live = _live_with_client(client)

    result = live.option_chain_contract_info(" reliance ")

    assert result == {
        "symbol": "RELIANCE",
        "expiry_dates": [date(2026, 7, 30), date(2026, 8, 27)],
        "strike_prices": [3_000.0, 3_100.0],
    }
    client.get_json.assert_called_once_with(
        "/api/option-chain-contract-info",
        params={"symbol": "RELIANCE"},
    )


def test_stock_quote_fno_combines_equity_quote_and_contract_info() -> None:
    client = MagicMock()

    def get_json(path: str, params=None):
        if path == "/api/quote-equity":
            return _quote_payload()
        if path == "/api/option-chain-contract-info":
            return {
                "expiryDates": ["30-Jul-2026"],
                "strikePrice": [3_000, 3_100],
            }
        raise AssertionError(f"Unexpected endpoint: {path}")

    client.get_json.side_effect = get_json
    live = _live_with_client(client)

    result = live.stock_quote_fno(" reliance ")

    assert result["quote_type"] == "derivative"
    assert result["symbol"] == "RELIANCE"
    assert result["company_name"] == "Reliance Industries Limited"
    assert result["price"]["last"] == 3_100.5
    assert result["is_fno"] is True
    assert result["derivative_details"] == {
        "stocks": [],
        "strike_prices": [3_000.0, 3_100.0],
        "expiry_dates": [date(2026, 7, 30)],
    }
    paths = [call.args[0] for call in client.get_json.call_args_list]
    assert paths == [
        "/api/quote-equity",
        "/api/option-chain-contract-info",
    ]
    assert "/api/quote-derivative" not in paths


def test_index_option_chain_defaults_to_first_advertised_expiry() -> None:
    client = MagicMock()

    def get_json(path: str, params=None):
        if path == "/api/option-chain-contract-info":
            return {
                "expiryDates": ["30-Jul-2026", "27-Aug-2026"],
                "strikePrice": [24_500],
            }
        if path == "/api/option-chain-v3":
            assert params == {
                "type": "Indices",
                "symbol": "NIFTY",
                "expiry": "30-Jul-2026",
            }
            return _chain_payload("30-Jul-2026")
        raise AssertionError(f"Unexpected endpoint: {path}")

    client.get_json.side_effect = get_json
    live = _live_with_client(client)

    result = live.index_option_chain(" nifty ")

    client.get.assert_called_once_with("/option-chain")
    assert result["symbol"] == "NIFTY"
    assert result["market_type"] == "index"
    assert result["selected_expiry"] == date(2026, 7, 30)
    assert result["records"][0]["expiry_date"] == date(2026, 7, 30)


def test_equities_option_chain_accepts_an_available_expiry() -> None:
    client = MagicMock()

    def get_json(path: str, params=None):
        if path == "/api/option-chain-contract-info":
            return {
                "expiryDates": ["30-Jul-2026", "27-Aug-2026"],
                "strikePrice": [3_100],
            }
        if path == "/api/option-chain-v3":
            assert params == {
                "type": "Stocks",
                "symbol": "RELIANCE",
                "expiry": "27-Aug-2026",
            }
            return _chain_payload("27-Aug-2026")
        raise AssertionError(f"Unexpected endpoint: {path}")

    client.get_json.side_effect = get_json
    live = _live_with_client(client)

    result = live.equities_option_chain(
        " reliance ",
        expiry=date(2026, 8, 27),
    )

    client.get.assert_called_once_with("/option-chain-equities")
    assert result["market_type"] == "equity"
    assert result["selected_expiry"] == date(2026, 8, 27)
    assert result["records"][0]["expiry_date"] == date(2026, 8, 27)


def test_option_chain_rejects_an_unavailable_expiry_before_data_request() -> None:
    client = MagicMock()
    client.get_json.return_value = {
        "expiryDates": ["30-Jul-2026", "27-Aug-2026"],
        "strikePrice": [24_500],
    }
    live = _live_with_client(client)

    with pytest.raises(
        InputValidationError,
        match="Expiry 2026-09-24 is not available for NIFTY",
    ):
        live.index_option_chain("NIFTY", expiry="24-Sep-2026")

    paths = [call.args[0] for call in client.get_json.call_args_list]
    assert paths == ["/api/option-chain-contract-info"]
    assert "/api/option-chain-v3" not in paths


def test_option_chain_rejects_symbols_without_expiries() -> None:
    client = MagicMock()
    client.get_json.return_value = {"expiryDates": [], "strikePrice": []}
    live = _live_with_client(client)

    with pytest.raises(
        InputValidationError,
        match="No option-chain expiries are available for CONTINFO",
    ):
        live.equities_option_chain("continfo")

    paths = [call.args[0] for call in client.get_json.call_args_list]
    assert paths == ["/api/option-chain-contract-info"]
