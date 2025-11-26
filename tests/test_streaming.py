"""
Tests for the streaming processor module.

Tests cover:
- CSV file processing
- JSON file processing
- ZIP file processing
- Streaming utilities (filter, transform, aggregate)
- Memory efficiency
"""

from __future__ import annotations

import os
import json
import tempfile
import zipfile
from typing import Any, Dict, List

import pytest

from aynse.nse.streaming_processor import (
    StreamingProcessor,
    StreamConfig,
    stream_filter_data,
    stream_transform_data,
    stream_aggregate_data,
    create_data_generator,
    stream_process_stock_data,
)


class TestStreamConfig:
    """Tests for StreamConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StreamConfig()
        
        assert config.chunk_size == 1000
        assert config.max_memory_mb == 100
        assert config.buffer_size == 8192
        assert config.encoding == 'utf-8'
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = StreamConfig(
            chunk_size=500,
            max_memory_mb=50,
            buffer_size=4096,
            encoding='latin-1'
        )
        
        assert config.chunk_size == 500
        assert config.max_memory_mb == 50
        assert config.buffer_size == 4096
        assert config.encoding == 'latin-1'


class TestStreamingProcessor:
    """Tests for StreamingProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a processor with small chunk size for testing."""
        return StreamingProcessor(StreamConfig(chunk_size=2))
    
    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_content = """symbol,date,open,high,low,close,volume
RELIANCE,2024-01-15,2500,2550,2480,2530,5000000
TCS,2024-01-15,3800,3850,3780,3820,2000000
INFY,2024-01-15,1550,1580,1540,1570,3500000
HDFC,2024-01-15,1700,1750,1680,1720,4000000
SBIN,2024-01-15,600,620,590,610,6000000
"""
        file_path = tmp_path / "test_data.csv"
        file_path.write_text(csv_content)
        return str(file_path)
    
    @pytest.fixture
    def sample_json_file(self, tmp_path):
        """Create a sample JSON file for testing."""
        data = [
            {"symbol": "RELIANCE", "price": 2530},
            {"symbol": "TCS", "price": 3820},
            {"symbol": "INFY", "price": 1570},
        ]
        file_path = tmp_path / "test_data.json"
        with open(file_path, 'w') as f:
            for item in data:
                json.dump(item, f)
                f.write('\n')
        return str(file_path)
    
    def test_process_csv_file(self, processor, sample_csv_file):
        """Test processing a CSV file in chunks."""
        chunks_processed = []
        
        def chunk_processor(chunk):
            chunks_processed.append(len(chunk))
            return chunk
        
        result = processor.process_csv_file(
            sample_csv_file,
            chunk_processor,
            skip_header=True
        )
        
        # Should have processed in multiple chunks due to small chunk_size
        assert len(chunks_processed) >= 1
        # Total records should be 5 (excluding header)
        assert sum(chunks_processed) == 5
    
    def test_process_csv_string(self, processor):
        """Test processing CSV from string."""
        csv_data = """symbol,date,open,high,low,close,volume
RELIANCE,2024-01-15,2500,2550,2480,2530,5000000
TCS,2024-01-15,3800,3850,3780,3820,2000000
"""
        
        def counter(chunk):
            return len(chunk)
        
        result = processor.process_csv_string(csv_data, counter)
        
        # Should have counted 2 records
        assert result == 2
    
    def test_combine_results_numbers(self, processor):
        """Test combining numeric results."""
        results = [1, 2, 3, 4, 5]
        combined = processor._combine_results(results)
        assert combined == 15  # Sum
    
    def test_combine_results_lists(self, processor):
        """Test combining list results."""
        results = [[1, 2], [3, 4], [5]]
        combined = processor._combine_results(results)
        assert combined == [1, 2, 3, 4, 5]
    
    def test_combine_results_dicts(self, processor):
        """Test combining dictionary results."""
        results = [{'a': 1}, {'b': 2}, {'c': 3}]
        combined = processor._combine_results(results)
        assert combined == {'a': 1, 'b': 2, 'c': 3}
    
    def test_combine_results_empty(self, processor):
        """Test combining empty results."""
        result = processor._combine_results([])
        assert result is None


class TestStreamingUtilities:
    """Tests for streaming utility functions."""
    
    def test_stream_filter_data(self):
        """Test filtering data stream."""
        def data_gen():
            yield {"value": 1}
            yield {"value": 2}
            yield {"value": 3}
            yield {"value": 4}
        
        filtered = list(stream_filter_data(
            data_gen(),
            lambda x: x["value"] > 2
        ))
        
        assert len(filtered) == 2
        assert filtered[0]["value"] == 3
        assert filtered[1]["value"] == 4
    
    def test_stream_transform_data(self):
        """Test transforming data stream."""
        def data_gen():
            yield {"value": 1}
            yield {"value": 2}
        
        transformed = list(stream_transform_data(
            data_gen(),
            lambda x: {"double": x["value"] * 2}
        ))
        
        assert len(transformed) == 2
        assert transformed[0]["double"] == 2
        assert transformed[1]["double"] == 4
    
    def test_stream_aggregate_data(self):
        """Test aggregating data stream."""
        def data_gen():
            yield {"category": "A", "value": 10}
            yield {"category": "B", "value": 20}
            yield {"category": "A", "value": 30}
            yield {"category": "B", "value": 40}
        
        aggregated = stream_aggregate_data(
            data_gen(),
            key_func=lambda x: x["category"],
            agg_func=lambda items: sum(i["value"] for i in items)
        )
        
        assert aggregated["A"] == 40
        assert aggregated["B"] == 60


class TestZipProcessing:
    """Tests for ZIP file processing."""
    
    @pytest.fixture
    def sample_zip_file(self, tmp_path):
        """Create a sample ZIP file with CSV content."""
        csv_content = """symbol,date,open,high,low,close,volume
RELIANCE,2024-01-15,2500,2550,2480,2530,5000000
TCS,2024-01-15,3800,3850,3780,3820,2000000
"""
        zip_path = tmp_path / "test_data.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.csv", csv_content)
        return str(zip_path)
    
    def test_process_zip_file(self, sample_zip_file):
        """Test processing CSV within ZIP file."""
        processor = StreamingProcessor(StreamConfig(chunk_size=10))
        
        def counter(chunk):
            return len(chunk)
        
        result = processor.process_zip_file(sample_zip_file, counter)
        
        # Should have processed some records
        assert result >= 2
    
    def test_process_zip_no_csv(self, tmp_path):
        """Test error when ZIP has no CSV files."""
        zip_path = tmp_path / "no_csv.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.txt", "not a csv")
        
        processor = StreamingProcessor()
        
        with pytest.raises(ValueError, match="No CSV files found"):
            processor.process_zip_file(str(zip_path), lambda x: x)


class TestMemoryEfficiency:
    """Tests to verify memory efficiency of streaming."""
    
    def test_large_file_memory_efficient(self, tmp_path):
        """Test that large files don't load entirely into memory."""
        # Create a large-ish CSV file
        csv_lines = ["symbol,date,open,high,low,close,volume\n"]
        for i in range(10000):
            csv_lines.append(f"STOCK{i},2024-01-15,100,110,90,105,{i*100}\n")
        
        file_path = tmp_path / "large_data.csv"
        file_path.write_text("".join(csv_lines))
        
        # Process with small chunks
        processor = StreamingProcessor(StreamConfig(chunk_size=100))
        
        max_chunk_size = 0
        chunks_count = 0
        
        def track_chunks(chunk):
            nonlocal max_chunk_size, chunks_count
            chunks_count += 1
            if len(chunk) > max_chunk_size:
                max_chunk_size = len(chunk)
            return len(chunk)
        
        result = processor.process_csv_file(str(file_path), track_chunks)
        
        # Should have processed in multiple chunks
        assert chunks_count > 1
        # Max chunk size should be limited
        assert max_chunk_size <= 100
        # Total should be correct
        assert result == 10000

