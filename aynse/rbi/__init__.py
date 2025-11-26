"""
RBI (Reserve Bank of India) data fetching module.

This module provides access to RBI policy rate data and other
monetary policy information.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

from requests import Session
from bs4 import BeautifulSoup

from .historical import policy_rate_archive


def tr_to_json(wrapper: Any) -> Dict[str, str]:
    """
    Convert HTML table rows to a JSON-like dictionary.
    
    Args:
        wrapper: BeautifulSoup element containing table rows
        
    Returns:
        Dictionary with key-value pairs extracted from table cells
    """
    trs = wrapper.find_all("tr")
    result: Dict[str, str] = {}
    
    for tr in trs:
        tds = tr.find_all('td')
        if len(tds) >= 2:
            key = tds[0].text.strip()
            val = (
                tds[1].text
                .replace(':', '')
                .replace('*', '')
                .replace('#', '')
                .strip()
            )
            result[key] = val
    
    return result


class RBI:
    """
    Client for fetching RBI (Reserve Bank of India) data.
    
    Provides access to policy rate archives and other monetary
    policy information from the RBI website.
    
    Example:
        >>> rbi = RBI()
        >>> rates = rbi.policy_rate_archive(n=10)
        >>> print(rates[0])
    """
    
    base_url: str = "https://www.rbi.org.in/"

    def __init__(self) -> None:
        """Initialize RBI client with a requests session."""
        self.session = Session()
    
    def current_rates(self) -> None:
        """
        Get current RBI policy rates.
        
        .. deprecated::
            This function is broken due to website changes.
            Use `policy_rate_archive()` instead.
            
        Raises:
            DeprecationWarning: Always raised as this method is deprecated
        """
        raise DeprecationWarning(
            "current_rates() is deprecated due to RBI website changes. "
            "Please use policy_rate_archive() instead."
        )

    def policy_rate_archive(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch historical policy rates from RBI website.
        
        Args:
            n: Number of past rate records to fetch (default: 10)
            
        Returns:
            List of dictionaries containing policy rate data.
            Keys are normalized to lowercase with underscores.
            
        Example:
            >>> rbi = RBI()
            >>> rates = rbi.policy_rate_archive(n=5)
            >>> for rate in rates:
            ...     print(rate.get('date'), rate.get('repo_rate'))
        """
        return policy_rate_archive(n)


__all__ = [
    'RBI',
    'policy_rate_archive',
    'tr_to_json',
]
