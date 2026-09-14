# Mutual funds

`aynse` reads mutual-fund scheme and end-of-day NAV data from the official AMFI
reports. It supports current-scheme discovery, historical NAVs, comparisons,
and a compact set of NAV-based risk and return metrics.

## Search schemes

Scheme codes—not display names—are the stable input for history calls. Search
by name, code, ISIN, fund house, plan, option, or category:

```python
from aynse import mutual_fund_search

matches = mutual_fund_search("flexi cap direct growth", limit=10)
for fund in matches:
    print(fund["scheme_code"], fund["scheme_name"], fund["latest_nav"])
```

Each result keeps `plan` and `option` explicit because Direct/Regular and
Growth/IDCW schemes are distinct investments even when their base names match.

## History and analysis

```python
from aynse import mutual_fund_history_df, mutual_fund_summary

frame = mutual_fund_history_df("122639", "2025-09-01", "2026-09-01")
summary = mutual_fund_summary("122639", "2025-09-01", "2026-09-01")

print(summary["as_of_date"])
print(summary["metrics"]["absolute_return_percent"])
print(summary["metrics"]["max_drawdown_percent"])
```

History is chronological. The client scopes reports to the scheme's AMC,
streams the response, retries transient failures, and automatically splits
longer ranges into AMFI's maximum 90-day report windows. If a newly launched
fund house appears in the complete NAV feed before AMFI publishes its download
identifier, the client falls back to AMFI's larger all-fund history report.

`cagr_percent` is `None` for periods shorter than 365 days. Volatility uses
daily NAV changes and 252-period annualization. All calculations are **NAV
returns**, not investor total returns: IDCW cash distributions, loads, taxes,
and investor purchases/redemptions are excluded.

## Compare schemes

```python
from aynse import compare_mutual_funds

comparison = compare_mutual_funds(
    ["122639", "120503"],
    "2025-09-01",
    "2026-09-01",
)

for fund in comparison["funds"]:
    print(fund["scheme"]["scheme_name"], fund["metrics"])
```

The comparison response reports both the requested range and the effective
`from_date` / `to_date`. Every path retains only NAV observation dates present
for all selected schemes, and every metric is recalculated from those exact
shared observations. This prevents a newer or partially reported fund from
being measured over a different window while appearing beside an older fund.

## Data-source constraints

- AMFI NAV reports are end-of-day publications, not live prices.
- A scheme must be present in AMFI's current complete NAV report so `aynse` can
  resolve its fund house efficiently. Dormant or discontinued schemes may not
  be available through this API.
- AMFI controls report availability and can change, delay, or temporarily
  withhold upstream data. Header validation prevents HTML/error pages from
  being returned as NAV records.
