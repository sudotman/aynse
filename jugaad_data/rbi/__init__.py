from requests import Session
from bs4 import BeautifulSoup

from jugaad_data.rbi.historical import policy_rate_archive


def tr_to_json(wrapper):
    trs = wrapper.find_all("tr")
    op = {}
    for tr in trs:
        tds = tr.find_all('td')
        if len(tds) >= 2:
            key = tds[0].text.strip()
            val = tds[1].text.replace(':', '').replace('*','').replace('#', '').strip()
            
            op[key] = val
    return op



class RBI:
    base_url = "https://www.rbi.org.in/"

    def __init__(self):
        self.s = Session()
    
    def current_rates(self):
        """DEPRECATED: This function is broken because of website changes."""
        raise DeprecationWarning("This function is broken and will be removed in a future version. Please use policy_rate_archive() instead.")

    def policy_rate_archive(self, n=10):
        return policy_rate_archive(n)


