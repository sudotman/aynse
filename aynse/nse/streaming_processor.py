"""
Streaming data processor for efficient handling of large datasets.

This module provides tools for processing NSE data in chunks to minimize
memory usage and improve performance with large datasets.
"""

import csv
import io
import json
from typing import Dict, List, Any, Generator, Callable, Iterable, Iterator, Optional
from dataclasses import dataclass
import zipfile

_MISSING = object()


@dataclass
class StreamConfig:
    """Configuration for streaming data processing"""
    chunk_size: int = 1000  # Number of records per chunk
    max_memory_mb: int = 100  # Maximum memory usage in MB
    buffer_size: int = 8192  # Buffer size for file operations
    encoding: str = 'utf-8'

    def __post_init__(self) -> None:
        if (
            isinstance(self.chunk_size, bool)
            or not isinstance(self.chunk_size, int)
            or self.chunk_size <= 0
        ):
            raise ValueError("chunk_size must be a positive integer")
        if (
            isinstance(self.max_memory_mb, bool)
            or not isinstance(self.max_memory_mb, int)
            or self.max_memory_mb <= 0
        ):
            raise ValueError("max_memory_mb must be a positive integer")
        if (
            isinstance(self.buffer_size, bool)
            or not isinstance(self.buffer_size, int)
            or self.buffer_size <= 0
        ):
            raise ValueError("buffer_size must be a positive integer")
        if not str(self.encoding).strip():
            raise ValueError("encoding cannot be empty")

class StreamingProcessor:
    """
    Efficient streaming processor for large NSE datasets.

    Processes data in chunks to minimize memory usage and handle
    large files that wouldn't fit in memory.
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        """Initialize streaming processor with configuration"""
        self.config = config or StreamConfig()

    def iter_csv_file(
        self,
        file_path: str,
        skip_header: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """Yield CSV rows without materializing the complete file."""
        with open(
            file_path,
            "r",
            encoding=self.config.encoding,
            buffering=self.config.buffer_size,
            newline="",
        ) as file:
            yield from self._iter_csv_text(file, skip_header=skip_header)

    def iter_csv_string(
        self,
        csv_data: str,
        skip_header: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """Yield rows from an in-memory CSV string."""
        with io.StringIO(csv_data) as buffer:
            yield from self._iter_csv_text(buffer, skip_header=skip_header)

    def _iter_csv_text(
        self,
        text_stream: Iterable[str],
        *,
        skip_header: bool,
    ) -> Iterator[Dict[str, Any]]:
        if skip_header:
            for row in csv.DictReader(text_stream):
                yield dict(row)
            return

        for values in csv.reader(text_stream):
            yield {f"column_{index}": value for index, value in enumerate(values)}

    def iter_json_file(self, file_path: str) -> Iterator[Any]:
        """
        Yield JSON objects from either NDJSON or a top-level JSON array.

        NDJSON is processed line by line. Standard-library JSON array parsing
        necessarily loads the array before yielding; use NDJSON for very large
        streams.
        """
        with open(file_path, "r", encoding=self.config.encoding) as file:
            first_non_empty = ""
            while not first_non_empty:
                line = file.readline()
                if not line:
                    return
                first_non_empty = line.strip()
            file.seek(0)

            if first_non_empty.startswith("["):
                data = json.load(file)
                if not isinstance(data, list):
                    raise ValueError("Top-level JSON payload must be an array")
                yield from data
                return

            for line in file:
                text = line.strip()
                if text:
                    yield json.loads(text)

    def iter_zip_file(
        self,
        zip_path: str,
        csv_filename: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield rows from a selected CSV member inside a ZIP archive."""
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            csv_files = [name for name in zip_file.namelist() if name.lower().endswith(".csv")]
            if not csv_files:
                raise ValueError("No CSV files found in ZIP archive")
            target_file = csv_filename or csv_files[0]
            if target_file not in csv_files:
                raise ValueError(f"CSV file not found in ZIP archive: {target_file}")
            with zip_file.open(target_file) as csv_file:
                wrapper = io.TextIOWrapper(csv_file, encoding=self.config.encoding, newline="")
                yield from (dict(row) for row in csv.DictReader(wrapper))

    def _chunks(self, records: Iterable[Any]) -> Iterator[List[Any]]:
        chunk: List[Any] = []
        for record in records:
            chunk.append(record)
            if len(chunk) >= self.config.chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def _process_chunks(
        self,
        chunks: Iterable[List[Any]],
        processor_func: Callable[[List[Any]], Any],
        *,
        reducer: Optional[Callable[[Any, Any], Any]] = None,
        initial: Any = _MISSING,
        stop_when: Optional[Callable[[Any], bool]] = None,
    ) -> Any:
        results: List[Any] = []
        aggregate = initial
        has_aggregate = initial is not _MISSING

        for chunk in chunks:
            result = processor_func(chunk)
            if reducer is None:
                results.append(result)
                # Combining all prior chunks on every iteration makes the
                # ordinary path quadratic. Only materialize an intermediate
                # aggregate when early-stop logic actually needs one.
                current = (
                    self._combine_results(results)
                    if stop_when is not None
                    else None
                )
            else:
                if has_aggregate:
                    aggregate = reducer(aggregate, result)
                else:
                    aggregate = result
                    has_aggregate = True
                current = aggregate
            if stop_when is not None and stop_when(current):
                break

        if reducer is not None:
            return aggregate if has_aggregate else None
        return self._combine_results(results)

    def process_csv_file(self,
                        file_path: str,
                        processor_func: Callable[[List[Dict[str, Any]]], Any],
                        skip_header: bool = True,
                        *,
                        reducer: Optional[Callable[[Any, Any], Any]] = None,
                        initial: Any = _MISSING,
                        stop_when: Optional[Callable[[Any], bool]] = None) -> Any:
        """
        Process a CSV file in streaming chunks.

        Args:
            file_path: Path to CSV file
            processor_func: Function to process each chunk of data
            skip_header: Whether to skip the first row (header)

        Returns:
            Result of processing all chunks
        """
        return self._process_chunks(
            self._chunks(self.iter_csv_file(file_path, skip_header=skip_header)),
            processor_func,
            reducer=reducer,
            initial=initial,
            stop_when=stop_when,
        )

    def process_csv_string(self,
                          csv_data: str,
                          processor_func: Callable[[List[Dict[str, Any]]], Any],
                          skip_header: bool = True,
                          *,
                          reducer: Optional[Callable[[Any, Any], Any]] = None,
                          initial: Any = _MISSING,
                          stop_when: Optional[Callable[[Any], bool]] = None) -> Any:
        """
        Process CSV data from string in streaming chunks.

        Args:
            csv_data: CSV data as string
            processor_func: Function to process each chunk
            skip_header: Whether to skip the first row

        Returns:
            Result of processing all chunks
        """
        return self._process_chunks(
            self._chunks(self.iter_csv_string(csv_data, skip_header=skip_header)),
            processor_func,
            reducer=reducer,
            initial=initial,
            stop_when=stop_when,
        )

    def process_json_file(self,
                         file_path: str,
                         processor_func: Callable[[List[Dict[str, Any]]], Any],
                         *,
                         reducer: Optional[Callable[[Any, Any], Any]] = None,
                         initial: Any = _MISSING,
                         stop_when: Optional[Callable[[Any], bool]] = None) -> Any:
        """
        Process a JSON file in streaming chunks.

        Args:
            file_path: Path to JSON file (assumed to be array of objects)
            processor_func: Function to process each chunk

        Returns:
            Result of processing all chunks
        """
        return self._process_chunks(
            self._chunks(self.iter_json_file(file_path)),
            processor_func,
            reducer=reducer,
            initial=initial,
            stop_when=stop_when,
        )

    def process_zip_file(self,
                        zip_path: str,
                        processor_func: Callable[[List[Dict[str, Any]]], Any],
                        csv_filename: Optional[str] = None,
                        *,
                        reducer: Optional[Callable[[Any, Any], Any]] = None,
                        initial: Any = _MISSING,
                        stop_when: Optional[Callable[[Any], bool]] = None) -> Any:
        """
        Process CSV data from within a ZIP file in streaming chunks.

        Args:
            zip_path: Path to ZIP file
            processor_func: Function to process each chunk
            csv_filename: Specific CSV file within ZIP (if None, uses first CSV found)

        Returns:
            Result of processing all chunks
        """
        return self._process_chunks(
            self._chunks(self.iter_zip_file(zip_path, csv_filename=csv_filename)),
            processor_func,
            reducer=reducer,
            initial=initial,
            stop_when=stop_when,
        )

    def _combine_results(self, results: List[Any]) -> Any:
        """Combine results from multiple chunks"""
        if not results:
            return None

        # If results are numbers, sum them
        if all(isinstance(r, (int, float)) for r in results):
            return sum(results)

        # If results are lists, concatenate them
        if all(isinstance(r, list) for r in results):
            combined = []
            for result in results:
                combined.extend(result)
            return combined

        # If results are dictionaries, merge them
        if all(isinstance(r, dict) for r in results):
            combined = {}
            for result in results:
                combined.update(result)
            return combined

        # Return list of results for complex cases
        return results

# Utility functions for common streaming operations

def stream_filter_data(data_stream: Generator[Dict[str, Any], None, None],
                      filter_func: Callable[[Dict[str, Any]], bool]) -> Generator[Dict[str, Any], None, None]:
    """Filter data from a streaming source"""
    for record in data_stream:
        if filter_func(record):
            yield record

def stream_transform_data(data_stream: Generator[Dict[str, Any], None, None],
                         transform_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
    """Transform data from a streaming source"""
    for record in data_stream:
        yield transform_func(record)

def stream_aggregate_data(data_stream: Generator[Dict[str, Any], None, None],
                         key_func: Callable[[Dict[str, Any]], str],
                         agg_func: Callable[[List[Dict[str, Any]]], Any]) -> Dict[str, Any]:
    """Aggregate data by key from a streaming source"""
    groups = {}

    for record in data_stream:
        key = key_func(record)
        if key not in groups:
            groups[key] = []
        groups[key].append(record)

    # Apply aggregation function to each group
    return {key: agg_func(group) for key, group in groups.items()}

def create_data_generator(file_path: str,
                         data_format: str = 'csv',
                         chunk_size: int = 1000) -> Generator[Dict[str, Any], None, None]:
    """
    Create a generator that yields data records from a file.

    Args:
        file_path: Path to data file
        data_format: Format of data ('csv', 'json')
        chunk_size: Number of records to read at once

    Yields:
        Individual data records
    """
    processor = StreamingProcessor(StreamConfig(chunk_size=chunk_size))

    if data_format.lower() == 'csv':
        yield from processor.iter_csv_file(file_path)

    elif data_format.lower() == 'json':
        yield from processor.iter_json_file(file_path)

    else:
        raise ValueError(f"Unsupported data format: {data_format}")

# Example usage functions for NSE data

def stream_process_stock_data(file_path: str,
                             chunk_processor: Callable[[List[Dict[str, Any]]], Any]) -> Any:
    """Process stock data file in streaming chunks"""
    processor = StreamingProcessor()
    return processor.process_csv_file(file_path, chunk_processor)

def stream_process_index_data(file_path: str,
                             chunk_processor: Callable[[List[Dict[str, Any]]], Any]) -> Any:
    """Process index data file in streaming chunks"""
    processor = StreamingProcessor()
    return processor.process_csv_file(file_path, chunk_processor)

def stream_validate_data_integrity(data_generator: Generator[Dict[str, Any], None, None],
                                  validator_func: Callable[[Dict[str, Any]], bool]) -> Dict[str, int]:
    """Validate data integrity in streaming fashion"""
    valid_count = 0
    invalid_count = 0

    for record in data_generator:
        if validator_func(record):
            valid_count += 1
        else:
            invalid_count += 1

    return {
        'valid_records': valid_count,
        'invalid_records': invalid_count,
        'total_processed': valid_count + invalid_count
    }
