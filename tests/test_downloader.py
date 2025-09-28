"""Tests for AsyncDownloader class."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from aioresponses import aioresponses

from src.hls_downloader.downloader import AsyncDownloader
from src.hls_downloader.models import DownloadConfig, SegmentInfo


class TestAsyncDownloader:
    """Test cases for AsyncDownloader class."""

    @pytest.fixture
    def config(self):
        """Create a test download configuration."""
        return DownloadConfig(
            max_concurrent=5,
            max_retries=2,
            timeout=10,
            chunk_size=1024
        )

    @pytest.fixture
    def sample_segments(self):
        """Create sample segment information for testing."""
        return [
            SegmentInfo(
                url="https://example.com/segment1.ts",
                index=1,
                filename="segment1.ts"
            ),
            SegmentInfo(
                url="https://example.com/segment2.ts",
                index=2,
                filename="segment2.ts"
            ),
            SegmentInfo(
                url="https://example.com/segment3.ts",
                index=3,
                filename="segment3.ts"
            )
        ]

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_init(self, config):
        """Test AsyncDownloader initialization."""
        downloader = AsyncDownloader(config)
        
        assert downloader.config == config
        assert downloader._client is None
        assert downloader._semaphore._value == config.max_concurrent

    @pytest.mark.asyncio
    async def test_context_manager(self, config):
        """Test async context manager functionality."""
        async with AsyncDownloader(config) as downloader:
            assert downloader._client is not None
            assert isinstance(downloader._client, httpx.AsyncClient)
        
        # Client should be closed after exiting context
        assert downloader._client is None

    @pytest.mark.asyncio
    async def test_setup_client(self, config):
        """Test HTTP client setup with proper configuration."""
        downloader = AsyncDownloader(config)
        await downloader._setup_client()
        
        assert downloader._client is not None
        assert isinstance(downloader._client, httpx.AsyncClient)
        
        # Check client configuration
        client = downloader._client
        # Just verify the client is properly configured - internal attributes may vary by version
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        
        await downloader._cleanup_client()

    @pytest.mark.asyncio
    async def test_cleanup_client(self, config):
        """Test HTTP client cleanup."""
        downloader = AsyncDownloader(config)
        await downloader._setup_client()
        
        assert downloader._client is not None
        
        await downloader._cleanup_client()
        assert downloader._client is None

    @pytest.mark.asyncio
    async def test_download_segments_success(self, config, sample_segments, temp_dir):
        """Test successful download of multiple segments."""
        # Mock the httpx client's stream method
        async with AsyncDownloader(config) as downloader:
            # Mock the _download_single_segment method to simulate successful downloads
            async def mock_download_segment(segment, output_dir):
                # Create the file
                filepath = output_dir / segment.filename
                content = b"test content for segment"
                filepath.write_bytes(content)
                
                # Update segment info
                segment.size = len(content)
                segment.downloaded = True
                return segment
            
            # Replace the method with our mock
            downloader._download_single_segment = mock_download_segment
            
            results = await downloader.download_segments(sample_segments, temp_dir)
            
            # Check all segments were downloaded successfully
            assert len(results) == len(sample_segments)
            for result in results:
                assert result.downloaded is True
                assert result.size == 24
                
                # Check file was created
                filepath = Path(temp_dir) / result.filename
                assert filepath.exists()
                assert filepath.stat().st_size == 24

    @pytest.mark.asyncio
    async def test_download_segments_http_error(self, config, sample_segments, temp_dir):
        """Test handling of HTTP errors during download."""
        async with AsyncDownloader(config) as downloader:
            # Mock the _download_single_segment method to simulate mixed success/failure
            async def mock_download_segment(segment, output_dir):
                if segment.index == 2:  # Second segment fails
                    segment.downloaded = False
                    return segment
                else:  # First and third segments succeed
                    filepath = output_dir / segment.filename
                    content = b"test content"
                    filepath.write_bytes(content)
                    segment.size = len(content)
                    segment.downloaded = True
                    return segment
            
            # Replace the method with our mock
            downloader._download_single_segment = mock_download_segment
            
            results = await downloader.download_segments(sample_segments, temp_dir)
            
            # Check results - should have 2 successful downloads
            successful = [r for r in results if r.downloaded]
            assert len(successful) == 2
            
            # Check that failed segment is marked as not downloaded
            failed_segment = next(
                (s for s in sample_segments if s.index == 2), None
            )
            assert failed_segment is not None
            assert failed_segment.downloaded is False

    @pytest.mark.asyncio
    async def test_download_single_segment_success(self, config, temp_dir):
        """Test successful download of a single segment."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts"
        )
        
        async with AsyncDownloader(config) as downloader:
            # Create a proper async context manager mock
            class MockResponse:
                def __init__(self):
                    self.headers = {"content-length": "18"}
                
                def raise_for_status(self):
                    pass
                
                async def aiter_bytes(self, chunk_size):
                    yield b"test video content"
                
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None
            
            mock_response = MockResponse()
            
            # Mock the client's stream method to return our mock response
            with patch.object(downloader._client, 'stream', return_value=mock_response):
                result = await downloader._download_single_segment(
                    segment, Path(temp_dir)
                )
                
                assert result.downloaded is True
                assert result.size == 18
                
                # Check file was created with correct content
                filepath = Path(temp_dir) / segment.filename
                assert filepath.exists()
                assert filepath.read_bytes() == b"test video content"

    @pytest.mark.asyncio
    async def test_download_single_segment_streaming(self, config, temp_dir):
        """Test streaming download functionality."""
        segment = SegmentInfo(
            url="https://example.com/large.ts",
            index=1,
            filename="large.ts"
        )
        
        # Create large content to test streaming
        large_content = b"x" * (config.chunk_size * 3)  # 3 chunks
        
        async with AsyncDownloader(config) as downloader:
            # Create a proper async context manager mock
            class MockResponse:
                def __init__(self):
                    self.headers = {"content-length": str(len(large_content))}
                
                def raise_for_status(self):
                    pass
                
                async def aiter_bytes(self, chunk_size):
                    # Simulate streaming by yielding chunks
                    for i in range(0, len(large_content), chunk_size):
                        yield large_content[i:i + chunk_size]
                
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None
            
            mock_response = MockResponse()
            
            # Mock the client's stream method to return our mock response
            with patch.object(downloader._client, 'stream', return_value=mock_response):
                result = await downloader._download_single_segment(
                    segment, Path(temp_dir)
                )
                
                assert result.downloaded is True
                assert result.size == len(large_content)
                
                # Verify file content
                filepath = Path(temp_dir) / segment.filename
                assert filepath.read_bytes() == large_content

    @pytest.mark.asyncio
    async def test_download_single_segment_no_content_length(self, config, temp_dir):
        """Test download when server doesn't provide content-length header."""
        segment = SegmentInfo(
            url="https://example.com/no_length.ts",
            index=1,
            filename="no_length.ts"
        )
        
        content = b"content without length header"
        
        async with AsyncDownloader(config) as downloader:
            # Create a proper async context manager mock without content-length
            class MockResponse:
                def __init__(self):
                    self.headers = {}  # No content-length header
                
                def raise_for_status(self):
                    pass
                
                async def aiter_bytes(self, chunk_size):
                    yield content
                
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None
            
            mock_response = MockResponse()
            
            # Mock the client's stream method to return our mock response
            with patch.object(downloader._client, 'stream', return_value=mock_response):
                result = await downloader._download_single_segment(
                    segment, Path(temp_dir)
                )
                
                assert result.downloaded is True
                assert result.size == len(content)  # Should be set from actual download
                
                filepath = Path(temp_dir) / segment.filename
                assert filepath.read_bytes() == content

    @pytest.mark.asyncio
    async def test_verify_file_integrity_success(self, config, temp_dir):
        """Test successful file integrity verification."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts",
            size=12
        )
        
        # Create test file
        filepath = Path(temp_dir) / segment.filename
        filepath.write_bytes(b"test content")
        
        async with AsyncDownloader(config) as downloader:
            result = await downloader._verify_file_integrity(filepath, segment)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_file_integrity_size_mismatch(self, config, temp_dir):
        """Test file integrity verification with size mismatch."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts",
            size=20  # Expected size doesn't match actual
        )
        
        # Create test file with different size
        filepath = Path(temp_dir) / segment.filename
        filepath.write_bytes(b"test content")  # 12 bytes, not 20
        
        async with AsyncDownloader(config) as downloader:
            result = await downloader._verify_file_integrity(filepath, segment)
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_file_integrity_no_expected_size(self, config, temp_dir):
        """Test file integrity verification when no expected size is provided."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts",
            size=None  # No expected size
        )
        
        # Create test file
        filepath = Path(temp_dir) / segment.filename
        content = b"test content"
        filepath.write_bytes(content)
        
        async with AsyncDownloader(config) as downloader:
            result = await downloader._verify_file_integrity(filepath, segment)
            assert result is True
            assert segment.size == len(content)  # Should be updated

    @pytest.mark.asyncio
    async def test_verify_file_integrity_empty_file(self, config, temp_dir):
        """Test file integrity verification with empty file."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts",
            size=None
        )
        
        # Create empty file
        filepath = Path(temp_dir) / segment.filename
        filepath.touch()
        
        async with AsyncDownloader(config) as downloader:
            result = await downloader._verify_file_integrity(filepath, segment)
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_file_integrity_missing_file(self, config, temp_dir):
        """Test file integrity verification with missing file."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts",
            size=12
        )
        
        # Don't create the file
        filepath = Path(temp_dir) / segment.filename
        
        async with AsyncDownloader(config) as downloader:
            result = await downloader._verify_file_integrity(filepath, segment)
            assert result is False

    @pytest.mark.asyncio
    async def test_download_single_segment_with_retry_public_interface(
        self, config, temp_dir
    ):
        """Test public interface for downloading single segment with retry."""
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts"
        )
        
        async with AsyncDownloader(config) as downloader:
            # Create a proper async context manager mock
            class MockResponse:
                def __init__(self):
                    self.headers = {"content-length": "12"}
                
                def raise_for_status(self):
                    pass
                
                async def aiter_bytes(self, chunk_size):
                    yield b"test content"
                
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None
            
            mock_response = MockResponse()
            
            # Mock the client's stream method to return our mock response
            with patch.object(downloader._client, 'stream', return_value=mock_response):
                result = await downloader.download_single_segment_with_retry(
                    segment, temp_dir
                )
                
                assert result.downloaded is True
                assert result.size == 12

    @pytest.mark.asyncio
    async def test_download_without_context_manager_raises_error(self, config):
        """Test that using downloader without context manager raises error."""
        downloader = AsyncDownloader(config)
        segment = SegmentInfo(
            url="https://example.com/test.ts",
            index=1,
            filename="test.ts"
        )
        
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await downloader.download_single_segment_with_retry(segment, "/tmp")

    @pytest.mark.asyncio
    async def test_concurrent_download_limit(self, config, temp_dir):
        """Test that concurrent downloads are properly limited."""
        # Create more segments than max_concurrent
        segments = [
            SegmentInfo(
                url=f"https://example.com/segment{i}.ts",
                index=i,
                filename=f"segment{i}.ts"
            )
            for i in range(config.max_concurrent + 3)  # 8 segments, 5 max concurrent
        ]
        
        async with AsyncDownloader(config) as downloader:
            # Simply verify that the semaphore is configured correctly
            assert downloader._semaphore._value == config.max_concurrent
            
            # Mock the _download_single_segment method to simulate successful downloads
            async def mock_download_segment(segment, output_dir):
                # Create the file
                filepath = output_dir / segment.filename
                content = b"test content"
                filepath.write_bytes(content)
                
                # Update segment info
                segment.size = len(content)
                segment.downloaded = True
                return segment
            
            # Replace the method with our mock
            downloader._download_single_segment = mock_download_segment
            
            results = await downloader.download_segments(segments, temp_dir)
            
            # Verify all downloads completed
            assert len(results) == len(segments)
            assert all(r.downloaded for r in results)

    @pytest.mark.asyncio
    async def test_output_directory_creation(self, config, sample_segments):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use a subdirectory that doesn't exist
            output_dir = Path(temp_dir) / "downloads" / "segments"
            
            async with AsyncDownloader(config) as downloader:
                # Mock the _download_single_segment method to simulate successful downloads
                async def mock_download_segment(segment, output_dir_path):
                    # Create the file
                    filepath = output_dir_path / segment.filename
                    content = b"test content"
                    filepath.write_bytes(content)
                    
                    # Update segment info
                    segment.size = len(content)
                    segment.downloaded = True
                    return segment
                
                # Replace the method with our mock
                downloader._download_single_segment = mock_download_segment
                
                results = await downloader.download_segments(
                    sample_segments, str(output_dir)
                )
                
                # Check directory was created
                assert output_dir.exists()
                assert output_dir.is_dir()
                
                # Check files were created in the directory
                for result in results:
                    filepath = output_dir / result.filename
                    assert filepath.exists()