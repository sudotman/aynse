import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO

def policy_rate_archive(n=10):
    """
    Fetches historical policy rates from RBI website.
    Args:
        n (int): Number of past rates to fetch.
    Returns:
        list: A list of dictionaries with policy rates data.
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
    
    s = requests.Session()
    r = s.get(base_url, params=params)
    r.raise_for_status()
    
    soup = BeautifulSoup(r.content, "html.parser")
    table_div = soup.find("div", class_="table-responsive")
    
    if not table_div:
        return []

    tables = table_div.find_all("table")
    if not tables:
        return []

    # Assuming the first table is what we need
    html_string = str(tables[0])
    
    # Use StringIO to treat the string as a file for pandas
    df = pd.read_html(StringIO(html_string))[0]

    # Drop rows with all NaN values which can sometimes be parsed from the table
    df = df.dropna(how='all')

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
    else:
        df.columns = [str(col).strip() for col in df.columns]

    df = df.rename(columns=lambda x: x.lower().replace(' ', '_').replace('unnamed:_0_level_0_', ''))
    
    return df.to_dict('records')

