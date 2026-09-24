# IPOs

`aynse.ipo` answers a practical question: *if you had applied to an IPO, been
allotted, and sold on listing day (or held a little longer), what would it have
returned?* It builds one record per NSE-listed IPO — mainboard and SME, since
2012 — from three NSE sources:

| Source | Used for |
|---|---|
| `/api/public-past-issues` | every listed public issue: issue price, price band, bidding window, listing date |
| `/api/ipo-detail` | category-wise subscription book (QIB / HNI / retail …), lot size, issue structure, retail discount |
| `/api/historicalOR/cm/equity` | daily OHLC and VWAP from the listing session onward |

The listing session's `previous_close` is NSE's IPO base price, which equals the
issue price. It fills in issue prices the issue list leaves blank and flags
mismatches.

## Browse issues

```python
from aynse import ipo_past_issues, ipo_live_issues, ipo_detail

mainboard_2025 = ipo_past_issues("2025-01-01", "2025-12-31", boards=["mainboard"])
open_now = ipo_live_issues()          # open + forthcoming, live subscription so far
book = ipo_detail("ZOMATO")           # subscription per category, lot size, structure
```

`board` is one of `mainboard`, `sme`, `reit`, `invit`, or `debt` (NCDs and
municipal bonds that NSE lists through the same feed).

## One IPO

```python
from aynse import ipo_report

record = ipo_report("LICI")
print(record["return_open_pct"], record["return_close_pct"], record["return_y1_pct"])
print(record["subscription_retail_x"], record["allotment_probability"])
print(len(record["path"]), "daily bars after listing")
```

## Backtest every IPO

```python
from aynse import ipo_backtest, summarize_ipo_backtest

records = ipo_backtest(boards=["mainboard", "sme"])   # thousands of requests the first time
summary = summarize_ipo_backtest(records, exit="open", boards=["mainboard"])

print(summary["headline"])            # median / mean / percentiles / win rate
print(summary["strategies"]["close"]) # every exit side by side
print(summary["by_subscription"])     # cohorts: year, board, subscription, issue size
print(summary["pnl"]["mean_expected_profit_per_application"])
```

A full build touches every issue since 2012. Records are JSON-ready, so keep
them and pass them back as `existing`: final records are reused untouched and
only new listings or still-maturing horizons are fetched again.

```python
import json

records = ipo_backtest(existing=json.load(open("ipos.json")))
json.dump(records, open("ipos.json", "w"))
```

`aynse ipo backtest --cache ipos.json` does the same from the command line.

NSE throttles sustained scraping. The builder therefore dispatches at most
`max_workers` records at a time. After a burst of network failures it drains,
cools down, rebuilds the HTTP session, and resumes. Records that failed on the
network are retried and never marked final, so the next run picks them up.

## What a record contains

| Field | Meaning |
|---|---|
| `return_{open,high,low,close,vwap}_pct` | listing-day exit versus issue price |
| `close_vs_open_pct`, `high_vs_open_pct`, `low_vs_open_pct` | what waiting after the opening auction added or cost |
| `return_{d1,w1,m1,m3,m6,y1}_pct` | holding exits (see below) |
| `return_max_m1_pct`, `return_min_m1_pct` | best high / worst low within the first month |
| `subscription_{total,qib,nii,nii_big,nii_small,retail,employee,…}_x` | times subscribed, consolidated NSE + BSE book |
| `allotment_probability` | mainboard retail odds, `min(1, 1 / retail subscription)` |
| `min_application_qty`, `min_application_value` | one minimum retail application |
| `profit_*`, `expected_profit_*` | rupee P&L of one minimum application, and after allotment odds |
| `issue_size_cr` | public book plus anchor portion (estimated where NSE's text omits it) |
| `is_final` | nothing more can be learned by re-fetching |

## Method and caveats

- **Exits.** The listing open is the price discovered in NSE's pre-open call
  auction. VWAP approximates "sold sometime during the day". The day's high and
  low are bounds: nobody reliably hits the exact high.
- **Holding horizons** exit at the close of the first session on or after
  listing + 7, 30, 91, 182, and 365 calendar days; `d1` is the next session.
  Calendar horizons keep exchange holidays from shifting a "one year" hold.
- **Allotment odds.** Mainboard retail allotment is a lottery of minimum lots
  when oversubscribed. `1 / retail subscription` assumes every applicant bid
  for one lot. Some bid for more, so the true odds are at least this high and
  the estimate is conservative. NSE does not publish SME category
  reservations, so SME odds are left unset rather than guessed. SME total
  subscription is estimated as NSE bids ÷ net shares offered (issue less
  market-maker and anchor portions), flagged as `nse_book_estimate`.
- **Minimum applications.** Mainboard: one lot. SME: two lots where NSE's book
  shows the "bidding for 2 lots" individual category (post-2025 rules),
  otherwise one lot.
- **Not modelled:** brokerage, taxes, the opportunity cost of blocked ASBA funds,
  retail/employee discounts (reported as `retail_discount`), and applications
  above the minimum lot. BSE-only listings are not in NSE's feed.
