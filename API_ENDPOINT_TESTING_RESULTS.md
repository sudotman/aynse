# nse api endpoint testing & remediation plan

**last updated:** july 29, 2025

---

## 1. summary of fixed endpoints

### a. equity bhavcopy (`bhavcopy_raw`) & f&o bhavcopy (`bhavcopy_fo_raw`)
- **status:** fixed
- **summary of fix:** repaired the equity and f&o bhavcopy downloads in `jugaad_data/nse/archives.py` to address nse's new api structure effective from **july 8, 2024**. the implementation now handles both the old (json link) and new (direct zip file) formats, including the nested zip archives returned by the new api. a unified response handler (`_handle_bhavcopy_response`) robustly processes the data.

### b. full bhavcopy (`full_bhavcopy_raw`)
- **status:** fixed
- **summary of fix:** updated to use the new `/api/reports` endpoint, which returns brotli-compressed csv data. the function now works for all dates.

### c. bulk deals (`bulk_deals_raw`)
- **status:** fixed
- **summary of fix:** updated to use the new `/api/historicalOR/bulk-block-short-deals` endpoint. the function now accepts a date range and parses the json response.

### d. RBI policy rate archive
- **status:** fixed
- **summary of fix:** the `policy_rate_archive` function in `jugaad_data/rbi/historical.py` was repaired. it now correctly scrapes the policy rates table from the RBI website's new layout. the fix involves finding the correct table within a `div` with class `table-responsive`, parsing it with `pandas`, and cleaning the resulting data to handle extraneous rows.
