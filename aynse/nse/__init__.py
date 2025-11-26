"""
NSE data fetching module.

This module provides access to:
- Historical stock, index, and derivatives data
- Bhavcopy archives (equity, F&O, index)
- Live market data and quotes
- Connection pooling and request batching
- Streaming data processing
"""

from .history import (
    # Functions
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
    # Classes
    NSEHistory,
    NSEIndexHistory,
    # Constants
    APP_NAME,
    stock_select_headers,
    stock_final_headers,
    futures_select_headers,
    futures_final_headers,
    options_select_headers,
    options_final_headers,
)

from .archives import (
    # Functions
    bhavcopy_raw,
    bhavcopy_save,
    full_bhavcopy_raw,
    full_bhavcopy_save,
    bhavcopy_fo_raw,
    bhavcopy_fo_save,
    bhavcopy_index_raw,
    bhavcopy_index_save,
    bulk_deals_raw,
    bulk_deals_save,
    expiry_dates,
    index_constituent_raw,
    index_constituent_save,
    index_constituent_save_all,
    # Classes
    NSEArchives,
    NSEIndicesArchives,
    NSEIndices,
    NSEIndexConstituents,
)

from .live import NSELive

from .connection_pool import (
    NSEConnectionPool,
    get_connection_pool,
    reset_connection_pool,
)

from .request_batcher import (
    RequestBatcher,
    BatchStrategy,
    BatchResult,
    BatchStats,
    batch_stock_requests,
    batch_index_requests,
    batch_derivatives_requests,
)

from .streaming_processor import (
    StreamingProcessor,
    StreamConfig,
    stream_process_stock_data,
    stream_process_index_data,
    stream_filter_data,
    stream_transform_data,
    stream_aggregate_data,
    create_data_generator,
)

__all__ = [
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
    "NSEHistory",
    "NSEIndexHistory",
    "APP_NAME",
    "stock_select_headers",
    "stock_final_headers",
    "futures_select_headers",
    "futures_final_headers",
    "options_select_headers",
    "options_final_headers",
    # Archives
    "bhavcopy_raw",
    "bhavcopy_save",
    "full_bhavcopy_raw",
    "full_bhavcopy_save",
    "bhavcopy_fo_raw",
    "bhavcopy_fo_save",
    "bhavcopy_index_raw",
    "bhavcopy_index_save",
    "bulk_deals_raw",
    "bulk_deals_save",
    "expiry_dates",
    "index_constituent_raw",
    "index_constituent_save",
    "index_constituent_save_all",
    "NSEArchives",
    "NSEIndicesArchives",
    "NSEIndices",
    "NSEIndexConstituents",
    # Live
    "NSELive",
    # Connection
    "NSEConnectionPool",
    "get_connection_pool",
    "reset_connection_pool",
    # Batching
    "RequestBatcher",
    "BatchStrategy",
    "BatchResult",
    "BatchStats",
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
]
