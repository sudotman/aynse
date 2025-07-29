from aynse.rbi import RBI, policy_rate_archive
from unittest.mock import patch, Mock
import pandas as pd
import pytest

def test_policy_rate_archive():
    # Test the standalone function
    rates = policy_rate_archive(n=2)
    assert isinstance(rates, list)
    assert len(rates) == 2
    assert isinstance(rates[0], dict)
    assert 'policy_repo_rate' in rates[0]
    assert 'bank_rate' in rates[0]

def test_rbi_class_method():
    # Test the method within the RBI class
    r = RBI()
    rates = r.policy_rate_archive(n=5)
    assert isinstance(rates, list)
    assert len(rates) == 5
    assert 'effective_date' in rates[0]

def test_current_rates_deprecation():
    r = RBI()
    with pytest.raises(DeprecationWarning):
        r.current_rates()
