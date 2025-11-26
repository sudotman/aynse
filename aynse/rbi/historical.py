"""
Historical policy rate data from RBI.

This module fetches policy rate archives from the RBI website
by scraping the policy rate archive page.
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import Any, Dict, List

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def policy_rate_archive(n: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch historical policy rates from RBI website.
    
    Scrapes the RBI policy rate archive page to extract historical
    policy rate data including repo rate, reverse repo rate, etc.
    
    Args:
        n: Number of past rate records to fetch (default: 10).
            Higher values will fetch more historical data.
           
    Returns:
        List of dictionaries containing policy rate data.
        Each dictionary represents one rate announcement.
        Column names are normalized to lowercase with underscores.
        
    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If no data table is found on the page
        
    Example:
        >>> rates = policy_rate_archive(n=5)
        >>> for rate in rates:
        ...     print(f"Date: {rate.get('date')}, Repo: {rate.get('repo_rate')}")
    """
    base_url = "https://website.rbi.org.in/web/rbi/policy-rate-archive"
    
    params = {
        "p_p_id": "com_rbi_policy_rate_archive_RBIPolicyRateArchivePortlet_INSTANCE_uwbl",
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
        "_com_rbi_policy_rate_archive_RBIPolicyRateArchivePortlet_INSTANCE_uwbl_cur": "1",
        "_com_rbi_policy_rate_archive_RBIPolicyRateArchivePortlet_INSTANCE_uwbl_resetCur": "false",
        "_com_rbi_policy_rate_archive_RBIPolicyRateArchivePortlet_INSTANCE_uwbl_delta": str(n),
    }
    
    session = requests.Session()
    
    try:
        response = session.get(base_url, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch policy rate archive: {e}")
        raise
    
    soup = BeautifulSoup(response.content, "html.parser")
    table_div = soup.find("div", class_="table-responsive")
    
    if not table_div:
        logger.warning("No table-responsive div found on page")
        return []

    tables = table_div.find_all("table")
    if not tables:
        logger.warning("No tables found in table-responsive div")
        return []

    # Parse the first table using pandas
    html_string = str(tables[0])
    
    try:
        df_list = pd.read_html(StringIO(html_string))
        if not df_list:
            return []
        df = df_list[0]
    except ValueError as e:
        logger.error(f"Failed to parse HTML table: {e}")
        return []

    # Drop rows with all NaN values
    df = df.dropna(how='all')

    # Handle multi-level column headers
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            '_'.join(str(c) for c in col).strip()
            for col in df.columns.values
        ]
    else:
        df.columns = [str(col).strip() for col in df.columns]

    # Normalize column names: lowercase, spaces to underscores, remove prefixes
    df.columns = [
        col.lower()
        .replace(' ', '_')
        .replace('unnamed:_0_level_0_', '')
        .replace('unnamed:_1_level_0_', '')
        for col in df.columns
    ]
    
    return df.to_dict('records')
