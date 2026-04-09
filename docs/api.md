# API Reference

This page lists the standardized public API for `aynse`.

## Historical data

::: aynse.nse.history.stock_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.stock_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.stock_csv
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.derivatives_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.derivatives_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.derivatives_csv
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_csv
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_pe_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.index_pe_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.set_stock_history_backend
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.get_stock_history_backend
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.history.register_stock_history_provider
    options:
      show_root_heading: true
      show_source: false

## Archive data

::: aynse.nse.archives.bhavcopy_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.full_bhavcopy_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.full_bhavcopy_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.full_bhavcopy_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_fo_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_fo_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_fo_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_index_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_index_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bhavcopy_index_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bulk_deals_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bulk_deals_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.bulk_deals_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.index_constituent_raw
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.index_constituent_df
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.index_constituent_save
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.index_constituent_save_all
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.archives.expiry_dates
    options:
      show_root_heading: true
      show_source: false

## Live data

::: aynse.nse.live.NSELive
    options:
      show_root_heading: true
      show_source: false
      members:
        - stock_quote
        - stock_quote_fno
        - trade_info
        - market_status
        - chart_data
        - tick_data
        - market_turnover
        - eq_derivative_turnover
        - all_indices
        - live_index
        - index_option_chain
        - equities_option_chain
        - currency_option_chain
        - live_fno
        - pre_open_market
        - holiday_list
        - corporate_announcements
        - corporate_actions
        - results_calendar
        - bulk_equities_option_chain
        - get_options_around_date
        - analyze_earnings_options
        - metadata

## Holidays and RBI

::: aynse.holidays.holiday_records
    options:
      show_root_heading: true
      show_source: false

::: aynse.holidays.holidays
    options:
      show_root_heading: true
      show_source: false

::: aynse.holidays.is_holiday
    options:
      show_root_heading: true
      show_source: false

::: aynse.holidays.is_trading_day
    options:
      show_root_heading: true
      show_source: false

::: aynse.holidays.get_trading_days
    options:
      show_root_heading: true
      show_source: false

::: aynse.holidays.count_trading_days
    options:
      show_root_heading: true
      show_source: false

::: aynse.rbi.policy_rate_archive
    options:
      show_root_heading: true
      show_source: false

## Metadata and analytics

::: aynse.catalog.supported_indices
    options:
      show_root_heading: true
      show_source: false

::: aynse.catalog.supported_instruments
    options:
      show_root_heading: true
      show_source: false

::: aynse.catalog.supported_event_categories
    options:
      show_root_heading: true
      show_source: false

::: aynse.catalog.dataset_capabilities
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.add_returns
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.add_rolling_volatility
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.add_drawdown
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.add_gap_metrics
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.add_volume_metrics
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.summarize_option_chain
    options:
      show_root_heading: true
      show_source: false

::: aynse.analytics.analyze_event_window
    options:
      show_root_heading: true
      show_source: false

## Batching and streaming

::: aynse.nse.request_batcher.RequestBatcher
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.request_batcher.BatchStrategy
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.streaming_processor.StreamingProcessor
    options:
      show_root_heading: true
      show_source: false

::: aynse.nse.streaming_processor.StreamConfig
    options:
      show_root_heading: true
      show_source: false
