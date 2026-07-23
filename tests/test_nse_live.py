from aynse.nse.live import NSELive
from datetime import date

n = NSELive()


def test_stock_quote():
    r = n.stock_quote("HDFCBANK")
    assert r["symbol"] == "HDFCBANK"
    assert "price" in r


def test_stock_quote_fno():
    r = n.stock_quote_fno("HDFCBANK")
    assert "derivative_details" in r
    assert "strike_prices" in r["derivative_details"]


def test_trade_info():
    r = n.trade_info("HDFC")
    assert "bulk_block_deals" in r
    assert "market_depth" in r


def test_market_status():
    r = n.market_status()
    assert "markets" in r


def test_tick_data():
    d = n.tick_data("SBIN")
    assert "points" in d
    d = n.tick_data("NIFTY 50", True)
    assert "points" in d


def test_eq_derivative_turnover():
    d = n.eq_derivative_turnover()
    assert "value" in d
    assert "volume" in d

    d = n.eq_derivative_turnover(type="fu_nifty50")
    assert "value" in d
    assert "volume" in d


def test_all_indices():
    d = n.all_indices()
    assert "advances" in d
    assert "declines" in d
    assert len(d["indices"]) > 1


def test_live_index():
    d = n.live_index("NIFTY 50")
    assert "advance" in d
    assert len(d["data"]) >= 1


def test_index_option_chain():
    d = n.index_option_chain("NIFTY")
    assert "records" in d
    assert "summary" in d


def test_equities_option_chain():
    d = n.equities_option_chain("RELIANCE")
    assert "records" in d
    assert "summary" in d


def test_currency_option_chain():
    d = n.currency_option_chain("USDINR")
    assert "records" in d
    assert "summary" in d


def test_live_fno():
    d = n.live_fno()
    assert "name" in d


def test_pre_open_market():
    d = n.pre_open_market("NIFTY")
    assert "declines" in d
    assert "advances" in d


def test_corporate_announcements():
    d = n.corporate_announcements()
    assert isinstance(d, list)
    if len(d) > 0:
        row = d[0]
        assert "symbol" in row
        assert "event_type" in row

    from_date = date(2024, 1, 1)
    to_date = date(2024, 1, 2)
    d = n.corporate_announcements(from_date=from_date, to_date=to_date)
    if len(d) > 0:
        assert "symbol" in d[0]
    d = n.corporate_announcements(from_date=from_date, to_date=to_date, symbol='NESCO')
    if d:
        assert d[0]['symbol'] == 'NESCO'


def test_event_helpers():
    from_date = date(2024, 1, 1)
    to_date = date(2024, 1, 31)
    actions = n.corporate_actions(from_date=from_date, to_date=to_date)
    results = n.results_calendar(from_date=from_date, to_date=to_date)
    assert isinstance(actions, list)
    assert isinstance(results, list)

