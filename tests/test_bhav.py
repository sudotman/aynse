from datetime import date

import pytest

from aynse.nse import (
    bhavcopy_fo_raw,
    bhavcopy_index_raw,
    bhavcopy_raw,
    bulk_deals_raw,
    expiry_dates,
    full_bhavcopy_raw,
)


def test_bhavcopy():
    rows = bhavcopy_raw(date(2020, 1, 1))
    assert isinstance(rows, list)
    assert len(rows) > 0
    assert "symbol" in rows[0]
    assert "series" in rows[0]


def test_full_bhavcopy():
    test_date = date(2024, 7, 24)
    rows = full_bhavcopy_raw(test_date)
    assert isinstance(rows, list)
    assert len(rows) > 0
    assert "symbol" in rows[0]
    assert "date1" in rows[0]


def test_bulk_deals():
    from_date = date(2025, 7, 22)
    to_date = date(2025, 7, 29)
    rows = bulk_deals_raw(from_date, to_date)
    assert isinstance(rows, list)
    if rows:
        assert "bd_symbol" in rows[0]


def test_bhavcopy_fo():
    rows = bhavcopy_fo_raw(date(2020, 1, 1))
    assert isinstance(rows, list)
    assert len(rows) > 0
    assert "symbol" in rows[0]
    assert "expiry_dt" in rows[0]


def test_bhavcopy_index():
    rows = bhavcopy_index_raw(date(2020, 1, 1))
    assert isinstance(rows, list)
    assert len(rows) > 0
    assert "index_name" in rows[0] or "index_date" in rows[0]


def test_expiry_dates():
    dt = date(2020, 9, 28)

    dts = expiry_dates(dt, "OPTIDX", "NIFTY")
    assert date(2020, 10, 1) in dts
    assert date(2020, 10, 8) in dts

    dts = expiry_dates(dt, "OPTIDX", "NIFTY", 10000)
    assert date(2020, 10, 1) in dts
    assert date(2020, 10, 8) in dts

    dts = expiry_dates(dt, "FUTIDX", "NIFTY")
    assert len(dts) >= 3
    assert date(2020, 10, 29) in dts
    assert date(2020, 11, 26) in dts

    dts = expiry_dates(dt, "FUTSTK", "RELIANCE")
    assert len(dts) >= 3
    assert date(2020, 10, 29) in dts
    assert date(2020, 11, 26) in dts

    dts = expiry_dates(dt, "OPTSTK", "RELIANCE")
    assert date(2020, 10, 29) in dts
    assert date(2020, 11, 26) in dts
