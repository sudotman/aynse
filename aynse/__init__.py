"""
aynse - A lean, modern Python library for fetching data from NSE (National Stock Exchange of India).

This package provides:
- Historical data: stocks, indices, derivatives
- Bhavcopy: equity, F&O, index downloads
- Live market data: real-time quotes
- CLI: simple commands for quick downloads
- Resilient networking: HTTP/2, pooling, retries, rate limit, circuit breaker
- Batching & streaming: adaptive concurrency and low-memory processing
"""

from __future__ import annotations

# Version is read from pyproject.toml - single source of truth
# This avoids needing to update version in multiple places
try:
    from importlib.metadata import version as _get_version
    __version__ = _get_version("aynse")
except Exception:
    # Fallback for editable installs or when package metadata isn't available
    __version__ = "0.0.0.dev"

__author__ = "satyam-kashyap"
__email__ = "satyamsudo@gmail.com"

from .nse import (
    # History functions
    stock_raw,
    stock_df,
    stock_csv,
    derivatives_raw,
    derivatives_df,
    derivatives_csv,
    index_raw,
    index_df,
    index_pe_raw,
    index_pe_df,
    index_csv,
    set_stock_history_backend,
    get_stock_history_backend,
    register_stock_history_provider,
    # Archives functions
    bhavcopy_raw,
    bhavcopy_df,
    bhavcopy_save,
    full_bhavcopy_raw,
    full_bhavcopy_df,
    full_bhavcopy_save,
    bhavcopy_fo_raw,
    bhavcopy_fo_df,
    bhavcopy_fo_save,
    bhavcopy_index_raw,
    bhavcopy_index_df,
    bhavcopy_index_save,
    bulk_deals_raw,
    bulk_deals_df,
    bulk_deals_save,
    expiry_dates,
    index_constituent_raw,
    index_constituent_df,
    index_constituent_save,
    index_constituent_save_all,
    # Live data
    NSELive,
    # Classes
    NSEHistory,
    NSEIndexHistory,
    NSEArchives,
    NSEIndices,
    NSEIndexConstituents,
    # Connection management
    NSEConnectionPool,
    # Batching
    RequestBatcher,
    BatchStrategy,
    batch_stock_requests,
    batch_index_requests,
    batch_derivatives_requests,
    # Streaming
    StreamingProcessor,
    StreamConfig,
    stream_process_stock_data,
    stream_process_index_data,
    stream_filter_data,
    stream_transform_data,
    stream_aggregate_data,
    create_data_generator,
)

from .holidays import holidays, holiday_records
from .rbi import RBI, policy_rate_archive
from .catalog import dataset_capabilities, supported_event_categories, supported_indices, supported_instruments
from .analytics import (
    add_atr,
    add_bollinger_bands,
    add_drawdown,
    add_gap_metrics,
    add_moving_average,
    add_returns,
    add_rolling_volatility,
    add_rsi,
    add_volume_metrics,
    analyze_event_window,
    summarize_option_chain,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    # History
    "stock_raw",
    "stock_df", 
    "stock_csv",
    "derivatives_raw",
    "derivatives_df",
    "derivatives_csv",
    "index_raw",
    "index_df",
    "index_pe_raw",
    "index_pe_df",
    "index_csv",
    "set_stock_history_backend",
    "get_stock_history_backend",
    "register_stock_history_provider",
    # Archives
    "bhavcopy_raw",
    "bhavcopy_df",
    "bhavcopy_save",
    "full_bhavcopy_raw",
    "full_bhavcopy_df",
    "full_bhavcopy_save",
    "bhavcopy_fo_raw",
    "bhavcopy_fo_df",
    "bhavcopy_fo_save",
    "bhavcopy_index_raw",
    "bhavcopy_index_df",
    "bhavcopy_index_save",
    "bulk_deals_raw",
    "bulk_deals_df",
    "bulk_deals_save",
    "expiry_dates",
    "index_constituent_raw",
    "index_constituent_df",
    "index_constituent_save",
    "index_constituent_save_all",
    # Live
    "NSELive",
    # Classes
    "NSEHistory",
    "NSEIndexHistory",
    "NSEArchives",
    "NSEIndices",
    "NSEIndexConstituents",
    # Connection
    "NSEConnectionPool",
    # Batching
    "RequestBatcher",
    "BatchStrategy",
    "batch_stock_requests",
    "batch_index_requests",
    "batch_derivatives_requests",
    # Streaming
    "StreamingProcessor",
    "StreamConfig",
    "stream_process_stock_data",
    "stream_process_index_data",
    "stream_filter_data",
    "stream_transform_data",
    "stream_aggregate_data",
    "create_data_generator",
    # Holidays
    "holidays",
    "holiday_records",
    # RBI
    "RBI",
    "policy_rate_archive",
    # Metadata
    "supported_indices",
    "supported_instruments",
    "supported_event_categories",
    "dataset_capabilities",
    # Analytics
    "add_returns",
    "add_rolling_volatility",
    "add_moving_average",
    "add_rsi",
    "add_atr",
    "add_bollinger_bands",
    "add_drawdown",
    "add_gap_metrics",
    "add_volume_metrics",
    "summarize_option_chain",
    "analyze_event_window",
]
