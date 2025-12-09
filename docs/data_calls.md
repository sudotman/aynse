# Data Calls Reference

Brief, canonical reference for all public data calls. Return types are noted succinctly.

## Archives (aynse.nse.archives)

- bhavcopy_raw(dt: date) -> str
  - Equity bhavcopy CSV text for the given date.
  - Format: CSV string (columns per NSE CM bhavcopy).

- bhavcopy_save(dt: date, dest: str, skip_if_present=True) -> str
  - Saves equity bhavcopy CSV to dest.
  - Returns file path.

- full_bhavcopy_raw(dt: date) -> str
  - Full bhavcopy CSV text (includes delivery info).
  - Format: CSV string.

- full_bhavcopy_save(dt: date, dest: str, skip_if_present=True) -> str
  - Saves full bhavcopy CSV to dest; returns file path.

- bhavcopy_fo_raw(dt: date) -> str
  - F&O bhavcopy CSV text for the given date.

- bhavcopy_fo_save(dt: date, dest: str, skip_if_present=True) -> str
  - Saves F&O bhavcopy CSV; returns file path.

- bhavcopy_index_raw(dt: date) -> str
  - Index bhavcopy CSV text for the date (Nifty Indices).

- bhavcopy_index_save(dt: date, dest: str, skip_if_present=True) -> str
  - Saves index bhavcopy CSV; returns file path.

- index_constituent_raw(index_type: str) -> str
  - CSV text of constituents for an index (e.g., "nifty50").

- index_constituent_save(index_type: str, dest: str, skip_if_present=True) -> str
  - Saves constituents CSV; returns file path.

- index_constituent_save_all(dest: str, skip_if_present=True) -> list[str]
  - Saves constituents for all known indices; returns file paths.

- bulk_deals_raw(from_date: date, to_date: date) -> dict
  - JSON for NSE bulk deals in date range.
  - Structure: {"data": [ ... records ... ], ...}

- bulk_deals_save(from_date: date, to_date: date, dest: str) -> str
  - Saves bulk deals JSON to file; returns file path.

- expiry_dates(dt: date, instrument_type: str = "", symbol: str = "", contracts: int = 0, months_ahead: int = 6) -> list[date]
  - Algorithmic calculation of expiry dates honoring NSE policy changes.

## History (aynse.nse.history)

- stock_raw(symbol: str, from_date: date, to_date: date, series: str = "EQ") -> list[dict]
  - JSON-like list of rows from NSE "historical cm equity" API.
  - Keys include: CH_TIMESTAMP, CH_SERIES, CH_OPENING_PRICE, CH_TRADE_HIGH_PRICE, CH_TRADE_LOW_PRICE, CH_PREVIOUS_CLS_PRICE, CH_LAST_TRADED_PRICE, CH_CLOSING_PRICE, VWAP, CH_52WEEK_HIGH_PRICE, CH_52WEEK_LOW_PRICE, CH_TOT_TRADED_QTY, CH_TOT_TRADED_VAL, CH_TOTAL_TRADES, CH_SYMBOL.

- stock_df(symbol: str, from_date: date, to_date: date, series: str = "EQ") -> pandas.DataFrame
  - Columns: DATE, SERIES, OPEN, HIGH, LOW, PREV. CLOSE, LTP, CLOSE, VWAP, 52W H, 52W L, VOLUME, VALUE, NO OF TRADES, SYMBOL.

- stock_csv(symbol: str, from_date: date, to_date: date, series: str = "EQ", output: str = "", show_progress: bool = True) -> str
  - Saves CSV with same columns as stock_df; returns file path.

- derivatives_raw(symbol: str, from_date: date, to_date: date, expiry_date: date, instrument_type: str, strike_price: float | None, option_type: str | None) -> list[dict]
  - JSON-like list from NSE "historical fo derivatives" API.
  - Keys include (subset): FH_TIMESTAMP, FH_EXPIRY_DT, FH_OPTION_TYPE (if options), FH_STRIKE_PRICE (if options), FH_OPENING_PRICE, FH_TRADE_HIGH_PRICE, FH_TRADE_LOW_PRICE, FH_CLOSING_PRICE, FH_LAST_TRADED_PRICE, FH_SETTLE_PRICE, FH_TOT_TRADED_QTY, FH_MARKET_LOT, FH_TOT_TRADED_VAL, FH_OPEN_INT, FH_CHANGE_IN_OI, FH_SYMBOL.

- derivatives_df(...) -> pandas.DataFrame
  - FUT fields: DATE, EXPIRY, OPEN, HIGH, LOW, CLOSE, LTP, SETTLE PRICE, TOTAL TRADED QUANTITY, MARKET LOT, PREMIUM VALUE, OPEN INTEREST, CHANGE IN OI, SYMBOL.
  - OPT fields: DATE, EXPIRY, OPTION TYPE, STRIKE PRICE, OPEN, HIGH, LOW, CLOSE, LTP, SETTLE PRICE, TOTAL TRADED QUANTITY, MARKET LOT, PREMIUM VALUE, OPEN INTEREST, CHANGE IN OI, SYMBOL.

- derivatives_csv(...) -> str
  - Saves derivatives data to CSV; returns file path.

- index_raw(symbol: str, from_date: date, to_date: date) -> list[dict]
  - Nifty Indices historical data via POST JSON; list of dict rows.
  - Typical keys: INDEX_NAME, HistoricalDate, OPEN, HIGH, LOW, CLOSE.

- index_pe_raw(symbol: str, from_date: date, to_date: date) -> list[dict]
  - Nifty Indices PE/PB/dividend data; keys include: pe, pb, divYield, DATE, Index Name.

- index_df(symbol: str, from_date: date, to_date: date) -> pandas.DataFrame
  - Typed dataframe from index_raw.

- index_pe_df(symbol: str, from_date: date, to_date: date) -> pandas.DataFrame
  - Typed dataframe from index_pe_raw.

## Live (aynse.nse.live.NSELive)

All return Python dicts parsed from NSE JSON unless noted.

- stock_quote(symbol: str) -> dict
- stock_quote_fno(symbol: str) -> dict
- trade_info(symbol: str) -> dict
- market_status() -> dict
- chart_data(symbol: str, indices: bool = False, flag: str = "1D") -> dict
- tick_data(symbol: str, indices: bool = False, flag: str = "1D") -> dict  (alias of chart_data)
- market_turnover() -> dict
- eq_derivative_turnover(type: str = "allcontracts") -> dict
- all_indices() -> dict
- live_index(symbol: str = "NIFTY 50") -> dict
- index_option_chain(symbol: str = "NIFTY") -> dict  (option-chain-v3, auto-selects first expiry)
- equities_option_chain(symbol: str) -> dict        (option-chain-v3, auto-selects first expiry)
- currency_option_chain(symbol: str = "USDINR") -> dict
- live_fno() -> dict  (alias: live_index("SECURITIES IN F&O"))
- pre_open_market(key: str = "NIFTY") -> dict
- holiday_list() -> dict
- corporate_announcements(segment: str = 'equities', from_date: date | None = None, to_date: date | None = None, symbol: str | None = None) -> dict

Notes:
- Live methods are lightly cached (time-based) to reduce load.
- HTTP client handles retries, priming, and pooling automatically.

## RBI (aynse.rbi.historical)

- policy_rate_archive(n: int = 10) -> list[dict]
  - Scraped policy rate entries as list of dicts.
  - Columns normalized to lowercase with underscores.

## Batching (aynse.nse.request_batcher)

- batch_stock_requests(symbols: list[str], from_date: str, to_date: str, series: str = "EQ", batcher: RequestBatcher | None = None) -> list[BatchResult]
- batch_index_requests(symbols: list[str], from_date: str, to_date: str, batcher: RequestBatcher | None = None) -> list[BatchResult]
- batch_derivatives_requests(requests_data: list[dict], batcher: RequestBatcher | None = None) -> list[BatchResult]
  - BatchResult: { success: bool, data: Any, error: str | None, duration: float, retries: int }

## Streaming (aynse.nse.streaming_processor)

- StreamingProcessor.process_csv_file(file_path: str, processor_func, skip_header=True) -> Any
- StreamingProcessor.process_json_file(file_path: str, processor_func) -> Any
- stream_filter_data, stream_transform_data, stream_aggregate_data, create_data_generator(...)
  - Generators and helpers for memory-efficient processing.


