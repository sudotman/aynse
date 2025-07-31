from datetime import date
from aynse.nse import bhavcopy_raw, full_bhavcopy_raw, bhavcopy_fo_raw, bhavcopy_index_raw, expiry_dates, bulk_deals_raw
import pytest
import requests

def test_bhavcopy():
    r = bhavcopy_raw(date(2020,1,1))
    header = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN"
    assert "RELIANCE" in r
    assert header in r

def test_full_bhavcopy():
    """Test full bhavcopy download with new API"""
    # Using a fixed date known to have data to make the test reliable.
    test_date = date(2024, 7, 24) # A Wednesday
    
    try:
        # Fetch the full bhavcopy data
        csv_data = full_bhavcopy_raw(test_date)

        # 1. Check if the data is a non-empty string
        assert isinstance(csv_data, str)
        assert len(csv_data) > 0

        # 2. Check for CSV-like structure by validating the headers
        first_line = csv_data.strip().split('\n')[0]
        headers = [h.strip() for h in first_line.split(',')]
        
        expected_headers = ["SYMBOL", "SERIES", "DATE1"]
        assert headers[:3] == expected_headers, f"Expected headers {expected_headers}, but got {headers[:3]}"

    except FileNotFoundError:
        pytest.fail(f"Test failed: Full Bhavcopy data not found for {test_date}. The endpoint might be down or the date is a holiday.")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred during full_bhavcopy_raw test: {e}")

def test_bulk_deals():
    """Test bulk deals download with new API"""
    from_date = date(2025, 7, 22)
    to_date = date(2025, 7, 29)
    
    try:
        data = bulk_deals_raw(from_date, to_date)
        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)
        if len(data["data"]) > 0:
            assert "BD_SYMBOL" in data["data"][0]
            assert "BD_CLIENT_NAME" in data["data"][0]

    except Exception as e:
        pytest.fail(f"An unexpected error occurred during bulk_deals_raw test: {e}")

def test_bhavcopy_fo():
    r = bhavcopy_fo_raw(date(2020,1,1))
    header = "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_O"
    assert "SBIN" in r
    assert header in r

# def test_bhavcopy_index():
#     r = bhavcopy_index_raw(date(2020,1,1))
#     header = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,Change(%)"
#     assert "NIFTY" in r
#     assert header in r

def test_expiry_dates():
    dt = date(2020, 9, 28)
    
    # Test NIFTY weekly expiries (should include weekly dates)
    dts = expiry_dates(dt, "OPTIDX", "NIFTY")
    assert date(2020, 10, 1) in dts
    assert date(2020, 10, 8) in dts
    
    # Test with specific parameters
    dts = expiry_dates(dt, "OPTIDX", "NIFTY", 10000)
    assert date(2020, 10, 1) in dts
    assert date(2020, 10, 8) in dts
    
    # Test NIFTY futures (weekly expiries, should have 3+ expiries in near term)
    dts = expiry_dates(dt, "FUTIDX", "NIFTY")
    assert len(dts) >= 3
    assert date(2020, 10, 1) in dts
    assert date(2020, 10, 8) in dts
    
    # Test RELIANCE futures (monthly expiries, should have 3+ monthly expiries)
    dts = expiry_dates(dt, "FUTSTK", "RELIANCE")
    assert len(dts) >= 3
    # Monthly expiries for RELIANCE should include end-of-month dates
    assert date(2020, 10, 29) in dts
    assert date(2020, 11, 26) in dts
    
    # Test RELIANCE options (monthly expiries)
    dts = expiry_dates(dt, "OPTSTK", "RELIANCE")
    assert date(2020, 10, 29) in dts
    assert date(2020, 11, 26) in dts

"""
def test_bhavcopy_on_holiday():
    r = bhavcopy_raw(date(2020,1,5))
    header = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN"
    assert "RELIANCE" in r
    assert header in r

"""
