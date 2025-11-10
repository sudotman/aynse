"""
Streaming data processor for efficient handling of large datasets.

This module provides tools for processing NSE data in chunks to minimize
memory usage and improve performance with large datasets.
"""

import io
import csv
import json
from typing import Dict, List, Any, Generator, Callable, Optional, Union
from dataclasses import dataclass
import gzip
import zipfile

@dataclass
class StreamConfig:
    """Configuration for streaming data processing"""
    chunk_size: int = 1000  # Number of records per chunk
    max_memory_mb: int = 100  # Maximum memory usage in MB
    buffer_size: int = 8192  # Buffer size for file operations
    encoding: str = 'utf-8'

class StreamingProcessor:
    """
    Efficient streaming processor for large NSE datasets.

    Processes data in chunks to minimize memory usage and handle
    large files that wouldn't fit in memory.
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        """Initialize streaming processor with configuration"""
        self.config = config or StreamConfig()

    def process_csv_file(self,
                        file_path: str,
                        processor_func: Callable[[List[Dict[str, Any]]], Any],
                        skip_header: bool = True) -> Any:
        """
        Process a CSV file in streaming chunks.

        Args:
            file_path: Path to CSV file
            processor_func: Function to process each chunk of data
            skip_header: Whether to skip the first row (header)

        Returns:
            Result of processing all chunks
        """
        results = []

        with open(file_path, 'r', encoding=self.config.encoding, buffering=self.config.buffer_size) as file:
            # Use streaming CSV reader for memory efficiency
            csv_reader = csv.reader(file)

            # Skip header if requested
            if skip_header:
                next(csv_reader, None)  # Skip header row

            chunk = []
            for row_num, row in enumerate(csv_reader):
                # Store row as a dictionary with proper structure
                # For now, use the row data directly as a dict
                # In a real implementation, this would use the CSV headers
                if len(row) >= 7:  # Ensure we have all expected columns
                    row_dict = {
                        'symbol': row[0],
                        'date': row[1],
                        'open': row[2],
                        'high': row[3],
                        'low': row[4],
                        'close': row[5],
                        'volume': row[6]
                    }
                    chunk.append(row_dict)

                    # Process chunk when it reaches the configured size
                    if len(chunk) >= self.config.chunk_size:
                        result = processor_func(chunk)
                        results.append(result)
                        chunk = []  # Clear chunk to free memory

            # Process remaining data
            if chunk:
                result = processor_func(chunk)
                results.append(result)

        # Combine results from all chunks
        return self._combine_results(results)

    def process_csv_string(self,
                          csv_data: str,
                          processor_func: Callable[[List[Dict[str, Any]]], Any],
                          skip_header: bool = True) -> Any:
        """
        Process CSV data from string in streaming chunks.

        Args:
            csv_data: CSV data as string
            processor_func: Function to process each chunk
            skip_header: Whether to skip the first row

        Returns:
            Result of processing all chunks
        """
        results = []

        # Create string buffer for streaming
        csv_buffer = io.StringIO(csv_data)
        csv_reader = csv.DictReader(csv_buffer) if skip_header else csv.DictReader(csv_buffer)

        chunk = []
        for row_num, row in enumerate(csv_reader):
            chunk.append(dict(row))

            if len(chunk) >= self.config.chunk_size:
                result = processor_func(chunk)
                results.append(result)
                chunk = []

        # Process remaining data
        if chunk:
            result = processor_func(chunk)
            results.append(result)

        return self._combine_results(results)

    def process_json_file(self,
                         file_path: str,
                         processor_func: Callable[[List[Dict[str, Any]]], Any]) -> Any:
        """
        Process a JSON file in streaming chunks.

        Args:
            file_path: Path to JSON file (assumed to be array of objects)
            processor_func: Function to process each chunk

        Returns:
            Result of processing all chunks
        """
        results = []

        with open(file_path, 'r', encoding=self.config.encoding) as file:
            # Read file line by line for memory efficiency
            buffer = ""
            chunk = []

            for line_num, line in enumerate(file):
                buffer += line.strip()

                # Try to parse complete JSON objects
                try:
                    while True:
                        # Look for complete JSON objects
                        start_idx = buffer.find('{')
                        end_idx = buffer.find('}', start_idx) + 1

                        if start_idx == -1 or end_idx == 0:
                            break

                        json_str = buffer[start_idx:end_idx]
                        try:
                            obj = json.loads(json_str)
                            chunk.append(obj)
                            buffer = buffer[end_idx:]
                        except json.JSONDecodeError:
                            break

                        # Process chunk when it reaches size
                        if len(chunk) >= self.config.chunk_size:
                            result = processor_func(chunk)
                            results.append(result)
                            chunk = []

                except Exception:
                    # If parsing fails, continue reading
                    continue

            # Process remaining objects
            if chunk:
                result = processor_func(chunk)
                results.append(result)

        return self._combine_results(results)

    def process_zip_file(self,
                        zip_path: str,
                        processor_func: Callable[[List[Dict[str, Any]]], Any],
                        csv_filename: Optional[str] = None) -> Any:
        """
        Process CSV data from within a ZIP file in streaming chunks.

        Args:
            zip_path: Path to ZIP file
            processor_func: Function to process each chunk
            csv_filename: Specific CSV file within ZIP (if None, uses first CSV found)

        Returns:
            Result of processing all chunks
        """
        results = []

        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # Find CSV file(s)
            csv_files = [f for f in zip_file.namelist() if f.lower().endswith('.csv')]

            if not csv_files:
                raise ValueError("No CSV files found in ZIP archive")

            # Use specified file or first CSV file
            target_file = csv_filename or csv_files[0]

            with zip_file.open(target_file) as csv_file:
                # Read CSV in chunks
                buffer = ""
                chunk = []

                while True:
                    # Read in buffer-sized chunks
                    data = csv_file.read(self.config.buffer_size)
                    if not data:
                        break

                    buffer += data.decode(self.config.encoding)

                    # Process complete lines
                    lines = buffer.split('\n')
                    buffer = lines[-1]  # Keep incomplete line for next iteration

                    for line in lines[:-1]:  # Skip last (potentially incomplete) line
                        if line.strip():
                            # Parse CSV line (simplified - assumes no quoted commas)
                            row_data = [field.strip() for field in line.split(',')]
                            if len(row_data) > 1:  # Skip empty lines
                                chunk.append({'data': row_data})

                                if len(chunk) >= self.config.chunk_size:
                                    result = processor_func(chunk)
                                    results.append(result)
                                    chunk = []

                # Process remaining data
                if chunk:
                    result = processor_func(chunk)
                    results.append(result)

        return self._combine_results(results)

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
        # Process file in chunks and yield each record
        def process_and_yield(chunk):
            for record in chunk:
                yield record

        # Process file and yield each record
        for chunk in processor.process_csv_file(file_path, lambda x: x):
            for record in chunk:
                yield record

    elif data_format.lower() == 'json':
        def process_and_yield(chunk):
            for record in chunk:
                yield record

        for chunk in processor.process_json_file(file_path, lambda x: x):
            for record in chunk:
                yield record

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
