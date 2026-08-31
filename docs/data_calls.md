# Data Calls Reference

Canonical reference for the standardized `aynse` public API.

## Shared contract

- Date boundaries accept `date | datetime | "YYYY-MM-DD"`.
- Symbol-based APIs normalize symbols to uppercase.
- Time-series record APIs return rows in chronological ascending order.
- `*_raw(...)` returns canonical records.
- `*_df(...)` returns a dataframe with the same canonical columns.
- `*_save(...)` writes a file and returns the written path.

## Historical data

### Stocks

- `stock_raw(symbol, from_date, to_date, series="EQ") -> list[dict]`
  - Canonical fields:
  - `date`, `symbol`, `series`, `open`, `high`, `low`, `close`, `previous_close`, `last_traded_price`, `vwap`, `week_52_high`, `week_52_low`, `volume`, `turnover`, `trades`
  - Compatibility alias: `last_price` mirrors `last_traded_price`.
- `stock_df(...) -> pandas.DataFrame`
- `stock_csv(...) -> str`

### Indices

- `index_raw(symbol, from_date, to_date) -> list[dict]`
  - Canonical fields:
  - `date`, `symbol`, `open`, `high`, `low`, `close`
- `index_df(...) -> pandas.DataFrame`
- `index_csv(...) -> str`

### Index valuations

- `index_pe_raw(symbol, from_date, to_date) -> list[dict]`
  - Canonical fields:
  - `date`, `symbol`, `price_to_earnings`, `price_to_book`, `dividend_yield`
- `index_pe_df(...) -> pandas.DataFrame`

### Derivatives

- `derivatives_raw(symbol, from_date, to_date, expiry_date, instrument_type, strike_price=None, option_type=None) -> list[dict]`
  - Canonical fields:
  - `date`, `symbol`, `instrument_type`, `expiry_date`, `option_type`, `strike_price`, `open`, `high`, `low`, `close`, `last_traded_price`, `settlement_price`, `volume`, `lot_size`, `turnover`, `open_interest`, `change_in_open_interest`
  - Compatibility aliases: `expiry`, `last_price`, `settle_price`, and `market_lot` mirror their canonical counterparts.
- `derivatives_df(...) -> pandas.DataFrame`
- `derivatives_csv(...) -> str`

## Archive data

### Equity bhavcopy

- `bhavcopy_raw(dt) -> list[dict]`
- `bhavcopy_df(dt) -> pandas.DataFrame`
- `bhavcopy_save(dt, dest, skip_if_present=True) -> str`

### Full bhavcopy

- `full_bhavcopy_raw(dt) -> list[dict]`
- `full_bhavcopy_df(dt) -> pandas.DataFrame`
- `full_bhavcopy_save(dt, dest, skip_if_present=True) -> str`

### F&O bhavcopy

- `bhavcopy_fo_raw(dt) -> list[dict]`
- `bhavcopy_fo_df(dt) -> pandas.DataFrame`
- `bhavcopy_fo_save(dt, dest, skip_if_present=True) -> str`

### Index bhavcopy

- `bhavcopy_index_raw(dt) -> list[dict]`
- `bhavcopy_index_df(dt) -> pandas.DataFrame`
- `bhavcopy_index_save(dt, dest, skip_if_present=True) -> str`

### Bulk deals

- `bulk_deals_raw(from_date, to_date) -> list[dict]`
  - Canonical fields vary by row, but dates, quantities, rates, client names, and symbols are normalized when present.
- `bulk_deals_df(from_date, to_date) -> pandas.DataFrame`
- `bulk_deals_save(from_date, to_date, dest) -> str`

### Index constituents

- `index_constituent_raw(index_type) -> list[dict]`
- `index_constituent_df(index_type) -> pandas.DataFrame`
- `index_constituent_save(index_type, dest, skip_if_present=True) -> str`
- `index_constituent_save_all(dest, skip_if_present=True) -> list[str]`

### Expiry calculations

- `expiry_dates(dt, instrument_type="", symbol="", contracts=0, months_ahead=6) -> list[date]`
  - This is an offline calendar calculation. NIFTY index options include weekly expiries; futures and other current contracts use their monthly cycle.
  - The calculator applies historical weekday transitions per contract month and moves holiday expiries to the previous trading day.
  - For the contracts currently listed by NSE, prefer `NSELive.option_chain_contract_info(symbol)`.

## Live data

All live methods return library-defined top-level payloads.

### Quotes and market state

- `NSELive.stock_quote(symbol) -> dict`
  - Keys:
  - `quote_type`, `symbol`, `company_name`, `isin`, `industry`, `listing_date`, `is_fno`, `identifier`, `price`, `week_range`, `metadata`
- `NSELive.stock_quote_fno(symbol) -> dict`
  - Includes `derivative_details`
- `NSELive.option_chain_contract_info(symbol) -> dict`
  - Keys:
  - `symbol`, `expiry_dates`, `strike_prices`
- `NSELive.trade_info(symbol) -> dict`
  - Keys:
  - `symbol`, `bulk_block_deals`, `market_depth`, `security_wise_dp`, `metadata`
- `NSELive.market_status() -> dict`
  - Keys:
  - `markets`, `market_cap`, `gift_nifty`, `indicative_nifty_50`
- `NSELive.market_turnover() -> dict`
  - Keys:
  - `records`, `source`
- `NSELive.eq_derivative_turnover(type="allcontracts") -> dict`
  - Keys:
  - `category`, `value`, `volume`
- `NSELive.all_indices() -> dict`
  - Keys:
  - `advances`, `declines`, `unchanged`, `indices`, `timestamp`
- `NSELive.live_index(symbol="NIFTY 50") -> dict`
  - Keys:
  - `name`, `advance`, `decline`, `unchanged`, `data`
- `NSELive.pre_open_market(key="NIFTY") -> dict`
  - Keys:
  - `key`, `advances`, `declines`, `unchanged`, `data`

### Charting

- `NSELive.chart_data(symbol, indices=False, flag="1D") -> dict`
- `NSELive.tick_data(symbol, indices=False, flag="1D") -> dict`
  - Keys:
  - `symbol`, `is_index`, `range`, `points`, `timestamp`, `open`, `high`, `low`, `close`

### Option chains

- `NSELive.index_option_chain(symbol="NIFTY", expiry=None) -> dict`
- `NSELive.equities_option_chain(symbol, expiry=None) -> dict`
- `NSELive.currency_option_chain(symbol="USDINR") -> dict`
  - Keys:
  - `symbol`, `market_type`, `timestamp`, `underlying_value`, `expiry_dates`, `strike_prices`, `records`, `summary`
  - Index and equity chains also include the validated `selected_expiry`.
  - Each `records` row contains:
  - `strike_price`, `expiry_date`, `call`, `put`

### Corporate events

- `NSELive.corporate_announcements(segment="equities", from_date=None, to_date=None, symbol=None) -> list[dict]`
- `NSELive.corporate_actions(from_date=None, to_date=None, symbol=None, event_types=None) -> list[dict]`
- `NSELive.results_calendar(from_date=None, to_date=None, symbol=None) -> list[dict]`
  - Canonical event fields:
  - `symbol`, `company_name`, `isin`, `event_type`, `headline`, `summary`, `event_date`, `exchange_received_at`, `attachment_url`, `attachment_size`, `segment`, `has_xbrl`

### Miscellaneous

- `NSELive.holiday_list() -> dict`
  - Keys:
  - `markets`
- `NSELive.live_fno() -> dict`
- `NSELive.bulk_equities_option_chain(symbols, max_workers=3) -> dict`
- `NSELive.get_options_around_date(symbol, target_date, days_before=5, days_after=5) -> dict`
  - Both date-window boundaries are inclusive and must be non-negative integers.
- `NSELive.analyze_earnings_options(symbols_and_dates, max_workers=3) -> dict`
- `NSELive.metadata() -> dict`

## Holidays and RBI

- `holiday_records(year=None, month=None) -> list[dict]`
  - Canonical fields:
  - `date`, `weekday`, `description`, `source`
- `holidays(year=None, month=None) -> list[date]`
  - The bundled offline NSE Capital Market calendar is maintained through 2026. Use `NSELive.holiday_list()` for exchange updates newer than the installed release.
- `is_holiday(dt) -> bool`
- `is_trading_day(dt) -> bool`
- `get_trading_days(from_date, to_date) -> list[date]`
- `count_trading_days(from_date, to_date) -> int`
- `policy_rate_archive(n=10) -> list[dict]`
  - Canonical fields:
  - `snapshot_date`, `policy_repo_rate`, `standing_deposit_facility_rate`, `marginal_standing_facility_rate`, `bank_rate`, `fixed_reverse_repo_rate`, `cash_reserve_ratio`, `statutory_liquidity_ratio`, `source`

## Metadata and analytics

- `supported_indices() -> list[dict]`
- `supported_instruments() -> list[dict]`
- `supported_event_categories() -> list[str]`
- `dataset_capabilities() -> dict`
- `add_returns(records, price_field="close") -> list[dict]`
- `add_rolling_volatility(records, window=20, price_field="close", annualization_period=252) -> list[dict]`
- `add_moving_average(records, window=20, price_field="close", kind="simple", output_field=None) -> list[dict]`
- `add_rsi(records, window=14, price_field="close") -> list[dict]`
- `add_atr(records, window=14) -> list[dict]`
- `add_bollinger_bands(records, window=20, standard_deviations=2.0, price_field="close") -> list[dict]`
  - Indicator fields: `moving_average` (or `output_field`), `rsi`, `atr`, and `bollinger_middle` / `bollinger_upper` / `bollinger_lower`
- `add_drawdown(records, price_field="close") -> list[dict]`
- `add_gap_metrics(records) -> list[dict]`
- `add_volume_metrics(records, window=20) -> list[dict]`
- `summarize_option_chain(chain) -> dict`
  - Positioning fields include total call/put OI, change in OI, volume, PCR,
    ATM strike/IV, call/put walls, `max_pain`, and `max_pain_payout`.
- `analyze_event_window(price_records, events, window_before=5, window_after=5, alignment="next") -> list[dict]`
  - `alignment` may be `exact`, `next`, `previous`, or `nearest`; weekend and
    holiday events default to the next observable trading session.

## Batching and streaming

- `batch_stock_requests(symbols, from_date, to_date, series="EQ", batcher=None, output="csv") -> list[BatchResult]`
- `batch_index_requests(symbols, from_date, to_date, batcher=None, output="csv") -> list[BatchResult]`
- `batch_derivatives_requests(requests_data, batcher=None, output="csv") -> list[BatchResult]`
  - Use `output="records"` to return canonical in-memory rows without writing files.
- `StreamingProcessor.process_csv_file(...) -> Any`
- `StreamingProcessor.process_csv_string(...) -> Any`
- `StreamingProcessor.process_json_file(...) -> Any`
- `StreamingProcessor.process_zip_file(...) -> Any`
