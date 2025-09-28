"""Tests for resume validator functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.hls_downloader.resume_validator import ResumeValidator
from src.hls_downloader.models import SegmentInfo


class TestResumeValidator:
    """Test cases for ResumeValidator class."""
    
    def test_init(self):
        """Test ResumeValidator initialization."""
        validator = ResumeValidator(timeout=60)
        assert validator.timeout == 60
        assert validator._client is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        validator = ResumeValidator()
        
        async with validator:
            assert validator._client is not None
            assert isinstance(validator._client, httpx.AsyncClient)
        
        # Client should be cleaned up after exit
        assert validator._client is None
    
    def test_scan_existing_files(self):
        """Test scanning directory for existing segment files."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test files
            (segments_dir / "segment_000001.ts").write_bytes(b"test data 1")
            (segments_dir / "segment_000002.ts").write_bytes(b"test data 2")
            (segments_dir / "segment_000003.ts").write_bytes(b"")  # Empty file
            (segments_dir / "other_file.txt").write_text("not a segment")
            
            # Scan files
            existing_files = validator.scan_existing_files(segments_dir)
            
            assert len(existing_files) == 3  # Only .ts files
            assert "segment_000001.ts" in existing_files
            assert "segment_000002.ts" in existing_files
            assert "segment_000003.ts" in existing_files
            assert "other_file.txt" not in existing_files
            
            # Check file info
            file1_info = existing_files["segment_000001.ts"]
            assert file1_info["size"] == 11
            assert not file1_info["is_empty"]
            
            file3_info = existing_files["segment_000003.ts"]
            assert file3_info["size"] == 0
            assert file3_info["is_empty"]
    
    def test_scan_nonexistent_directory(self):
        """Test scanning non-existent directory."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_dir = Path(temp_dir) / "nonexistent"
            
            existing_files = validator.scan_existing_files(nonexistent_dir)
            assert existing_files == {}
    
    @pytest.mark.asyncio
    async def test_validate_segments_basic(self):
        """Test basic segment validation."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segments
            segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="segment_000001.ts",
                    size=1024
                ),
                SegmentInfo(
                    url="http://example.com/segment2.ts",
                    index=2,
                    filename="segment_000002.ts",
                    size=2048
                ),
                SegmentInfo(
                    url="http://example.com/segment3.ts",
                    index=3,
                    filename="segment_000003.ts",
                    size=512
                )
            ]
            
            # Create files with correct sizes
            (segments_dir / "segment_000001.ts").write_bytes(b"x" * 1024)
            (segments_dir / "segment_000002.ts").write_bytes(b"x" * 1000)  # Wrong size
            # segment_000003.ts missing
            
            async with validator:
                valid, invalid, missing = await validator.validate_segments(segments, segments_dir)
            
            assert len(valid) == 1
            assert len(invalid) == 1
            assert len(missing) == 1
            
            assert valid[0].index == 1
            assert invalid[0].index == 2
            assert missing[0].index == 3
    
    @pytest.mark.asyncio
    async def test_validate_segments_empty_files(self):
        """Test validation of empty segment files."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=1024
            )
            
            # Create empty file
            (segments_dir / "segment_000001.ts").write_bytes(b"")
            
            async with validator:
                valid, invalid, missing = await validator.validate_segments([segment], segments_dir)
            
            assert len(valid) == 0
            assert len(invalid) == 1
            assert len(missing) == 0
            assert invalid[0].index == 1
    
    @pytest.mark.asyncio
    async def test_validate_segments_no_expected_size(self):
        """Test validation when segment has no expected size."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment without expected size
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None  # No expected size
            )
            
            # Create file
            (segments_dir / "segment_000001.ts").write_bytes(b"test data")
            
            async with validator:
                valid, invalid, missing = await validator.validate_segments([segment], segments_dir)
            
            assert len(valid) == 1
            assert len(invalid) == 0
            assert len(missing) == 0
            assert valid[0].size == 9  # Updated with actual size
    
    @pytest.mark.asyncio
    async def test_deep_validate_segments_success(self):
        """Test deep validation with successful server responses."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None
            )
            
            # Create file
            file_content = b"test data"
            (segments_dir / "segment_000001.ts").write_bytes(file_content)
            
            # Mock HTTP client
            mock_response = MagicMock()
            mock_response.headers = {"content-length": str(len(file_content))}
            mock_response.raise_for_status = MagicMock()
            
            with patch.object(validator, '_client') as mock_client:
                mock_client.head = AsyncMock(return_value=mock_response)
                
                valid, invalid = await validator.deep_validate_segments([segment], segments_dir)
            
            assert len(valid) == 1
            assert len(invalid) == 0
            assert valid[0].size == len(file_content)
    
    @pytest.mark.asyncio
    async def test_deep_validate_segments_size_mismatch(self):
        """Test deep validation with size mismatch."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None
            )
            
            # Create file
            (segments_dir / "segment_000001.ts").write_bytes(b"test data")
            
            # Mock HTTP client with different content length
            mock_response = MagicMock()
            mock_response.headers = {"content-length": "1000"}  # Different from actual size
            mock_response.raise_for_status = MagicMock()
            
            with patch.object(validator, '_client') as mock_client:
                mock_client.head = AsyncMock(return_value=mock_response)
                
                valid, invalid = await validator.deep_validate_segments([segment], segments_dir)
            
            assert len(valid) == 0
            assert len(invalid) == 1
    
    @pytest.mark.asyncio
    async def test_deep_validate_segments_404_error(self):
        """Test deep validation with 404 error."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None
            )
            
            # Create file
            (segments_dir / "segment_000001.ts").write_bytes(b"test data")
            
            # Mock HTTP client with 404 error
            mock_response = MagicMock()
            mock_response.status_code = 404
            http_error = httpx.HTTPStatusError("Not found", request=None, response=mock_response)
            
            with patch.object(validator, '_client') as mock_client:
                mock_client.head = AsyncMock(side_effect=http_error)
                
                valid, invalid = await validator.deep_validate_segments([segment], segments_dir)
            
            assert len(valid) == 0
            assert len(invalid) == 1
    
    @pytest.mark.asyncio
    async def test_deep_validate_segments_network_error(self):
        """Test deep validation with network error (should assume valid)."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None
            )
            
            # Create file
            (segments_dir / "segment_000001.ts").write_bytes(b"test data")
            
            # Mock HTTP client with network error
            with patch.object(validator, '_client') as mock_client:
                mock_client.head = AsyncMock(side_effect=httpx.RequestError("Network error"))
                
                valid, invalid = await validator.deep_validate_segments([segment], segments_dir)
            
            # Network errors should assume file is valid
            assert len(valid) == 1
            assert len(invalid) == 0
    
    @pytest.mark.asyncio
    async def test_deep_validate_segments_no_content_length(self):
        """Test deep validation when server doesn't provide content-length."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test segment
            segment = SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=None
            )
            
            # Create file
            (segments_dir / "segment_000001.ts").write_bytes(b"test data")
            
            # Mock HTTP client without content-length header
            mock_response = MagicMock()
            mock_response.headers = {}  # No content-length
            mock_response.raise_for_status = MagicMock()
            
            with patch.object(validator, '_client') as mock_client:
                mock_client.head = AsyncMock(return_value=mock_response)
                
                valid, invalid = await validator.deep_validate_segments([segment], segments_dir)
            
            # Should be valid if no content-length to compare
            assert len(valid) == 1
            assert len(invalid) == 0
    
    def test_cleanup_invalid_files(self):
        """Test cleanup of invalid segment files."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create test files
            file1 = segments_dir / "segment_000001.ts"
            file2 = segments_dir / "segment_000002.ts"
            file3 = segments_dir / "segment_000003.ts"
            
            file1.write_bytes(b"data1")
            file2.write_bytes(b"data2")
            file3.write_bytes(b"data3")
            
            # Create invalid segments list
            invalid_segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="segment_000001.ts"
                ),
                SegmentInfo(
                    url="http://example.com/segment3.ts",
                    index=3,
                    filename="segment_000003.ts"
                )
            ]
            
            # Cleanup invalid files
            removed_count = validator.cleanup_invalid_files(invalid_segments, segments_dir)
            
            assert removed_count == 2
            assert not file1.exists()
            assert file2.exists()  # Should not be removed
            assert not file3.exists()
    
    def test_cleanup_invalid_files_nonexistent(self):
        """Test cleanup when some files don't exist."""
        validator = ResumeValidator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()
            
            # Create invalid segments list with non-existent files
            invalid_segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="nonexistent.ts"
                )
            ]
            
            # Cleanup should not fail
            removed_count = validator.cleanup_invalid_files(invalid_segments, segments_dir)
            assert removed_count == 0
    
    def test_get_resume_summary(self):
        """Test generating resume summary."""
        validator = ResumeValidator()
        
        # Create test segments
        valid_segments = [
            SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=1024
            ),
            SegmentInfo(
                url="http://example.com/segment2.ts",
                index=2,
                filename="segment_000002.ts",
                size=2048
            )
        ]
        
        invalid_segments = [
            SegmentInfo(
                url="http://example.com/segment3.ts",
                index=3,
                filename="segment_000003.ts",
                size=512
            )
        ]
        
        missing_segments = [
            SegmentInfo(
                url="http://example.com/segment4.ts",
                index=4,
                filename="segment_000004.ts",
                size=256
            )
        ]
        
        # Get summary
        summary = validator.get_resume_summary(valid_segments, invalid_segments, missing_segments)
        
        assert summary["total_segments"] == 4
        assert summary["valid_segments"] == 2
        assert summary["invalid_segments"] == 1
        assert summary["missing_segments"] == 1
        assert summary["segments_to_download"] == 2
        assert summary["completion_percentage"] == 50.0
        assert summary["valid_bytes"] == 3072
        assert summary["can_resume"] == True
        assert summary["resume_benefit"] == 50.0
    
    def test_get_resume_summary_no_segments(self):
        """Test resume summary with no segments."""
        validator = ResumeValidator()
        
        summary = validator.get_resume_summary([], [], [])
        
        assert summary["total_segments"] == 0
        assert summary["completion_percentage"] == 0
        assert summary["can_resume"] == False
        assert summary["resume_benefit"] == 0
    
    def test_get_resume_summary_all_valid(self):
        """Test resume summary when all segments are valid."""
        validator = ResumeValidator()
        
        valid_segments = [
            SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=1024
            )
        ]
        
        summary = validator.get_resume_summary(valid_segments, [], [])
        
        assert summary["total_segments"] == 1
        assert summary["completion_percentage"] == 100.0
        assert summary["segments_to_download"] == 0
        assert summary["can_resume"] == False  # Nothing to download
        assert summary["resume_benefit"] == 100.0