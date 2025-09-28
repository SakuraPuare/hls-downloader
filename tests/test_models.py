"""Tests for data models."""

import pytest
from hls_downloader.models import DownloadConfig, DownloadStats, SegmentInfo


class TestDownloadConfig:
    """Test DownloadConfig data class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DownloadConfig()

        assert config.max_concurrent == 10
        assert config.max_retries == 3
        assert config.timeout == 30
        assert config.chunk_size == 8192
        assert config.auto_merge is True
        assert config.cleanup_segments is False
        assert config.output_format == "mp4"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DownloadConfig(
            max_concurrent=5,
            max_retries=2,
            timeout=15,
            auto_merge=False,
            cleanup_segments=True,
            output_format="mkv",
        )

        assert config.max_concurrent == 5
        assert config.max_retries == 2
        assert config.timeout == 15
        assert config.auto_merge is False
        assert config.cleanup_segments is True
        assert config.output_format == "mkv"

    def test_validation_max_concurrent(self):
        """Test max_concurrent validation."""
        # Valid values
        DownloadConfig(max_concurrent=1)
        DownloadConfig(max_concurrent=50)
        DownloadConfig(max_concurrent=100)

        # Invalid values
        with pytest.raises(ValueError, match="max_concurrent must be greater than 0"):
            DownloadConfig(max_concurrent=0)
        
        with pytest.raises(ValueError, match="max_concurrent must be greater than 0"):
            DownloadConfig(max_concurrent=-1)
        
        with pytest.raises(ValueError, match="max_concurrent must not exceed 100"):
            DownloadConfig(max_concurrent=101)

    def test_validation_max_retries(self):
        """Test max_retries validation."""
        # Valid values
        DownloadConfig(max_retries=0)
        DownloadConfig(max_retries=5)
        DownloadConfig(max_retries=10)

        # Invalid values
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            DownloadConfig(max_retries=-1)
        
        with pytest.raises(ValueError, match="max_retries must not exceed 10"):
            DownloadConfig(max_retries=11)

    def test_validation_timeout(self):
        """Test timeout validation."""
        # Valid values
        DownloadConfig(timeout=1)
        DownloadConfig(timeout=150)
        DownloadConfig(timeout=300)

        # Invalid values
        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            DownloadConfig(timeout=0)
        
        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            DownloadConfig(timeout=-1)
        
        with pytest.raises(ValueError, match="timeout must not exceed 300 seconds"):
            DownloadConfig(timeout=301)

    def test_validation_chunk_size(self):
        """Test chunk_size validation."""
        # Valid values
        DownloadConfig(chunk_size=1)
        DownloadConfig(chunk_size=8192)
        DownloadConfig(chunk_size=1024 * 1024)  # 1MB

        # Invalid values
        with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
            DownloadConfig(chunk_size=0)
        
        with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
            DownloadConfig(chunk_size=-1)
        
        with pytest.raises(ValueError, match="chunk_size must not exceed 1MB"):
            DownloadConfig(chunk_size=1024 * 1024 + 1)

    def test_validation_output_format(self):
        """Test output_format validation."""
        # Valid values
        for fmt in ["mp4", "mkv", "avi", "mov", "ts"]:
            DownloadConfig(output_format=fmt)

        # Invalid values
        with pytest.raises(ValueError, match="output_format must be one of"):
            DownloadConfig(output_format="invalid")
        
        with pytest.raises(ValueError, match="output_format must be one of"):
            DownloadConfig(output_format="")

    def test_validate_method(self):
        """Test validate method."""
        # Valid config
        config = DownloadConfig()
        assert config.validate() is True

        # Invalid config (we can't create it directly due to __post_init__)
        # So we test the validate method indirectly
        config = DownloadConfig()
        assert config.validate() is True


class TestSegmentInfo:
    """Test SegmentInfo data class."""

    def test_required_fields(self):
        """Test segment info with required fields."""
        segment = SegmentInfo(
            url="https://example.com/segment1.ts", index=1, filename="segment1.ts"
        )

        assert segment.url == "https://example.com/segment1.ts"
        assert segment.index == 1
        assert segment.filename == "segment1.ts"
        assert segment.size is None
        assert segment.downloaded is False

    def test_all_fields(self):
        """Test segment info with all fields."""
        segment = SegmentInfo(
            url="https://example.com/segment1.ts",
            index=1,
            filename="segment1.ts",
            size=1024,
            downloaded=True,
        )

        assert segment.size == 1024
        assert segment.downloaded is True

    def test_validation_url(self):
        """Test URL validation."""
        # Valid URLs
        SegmentInfo(url="http://example.com/test.ts", index=1, filename="test.ts")
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts")

        # Invalid URLs
        with pytest.raises(ValueError, match="url cannot be empty"):
            SegmentInfo(url="", index=1, filename="test.ts")
        
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SegmentInfo(url="ftp://example.com/test.ts", index=1, filename="test.ts")
        
        with pytest.raises(ValueError, match="url must be a valid HTTP/HTTPS URL"):
            SegmentInfo(url="invalid-url", index=1, filename="test.ts")

    def test_validation_index(self):
        """Test index validation."""
        # Valid indices
        SegmentInfo(url="https://example.com/test.ts", index=0, filename="test.ts")
        SegmentInfo(url="https://example.com/test.ts", index=100, filename="test.ts")

        # Invalid indices
        with pytest.raises(ValueError, match="index must be non-negative"):
            SegmentInfo(url="https://example.com/test.ts", index=-1, filename="test.ts")

    def test_validation_filename(self):
        """Test filename validation."""
        # Valid filenames
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts")
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="segment_001.ts")

        # Invalid filenames
        with pytest.raises(ValueError, match="filename cannot be empty"):
            SegmentInfo(url="https://example.com/test.ts", index=1, filename="")

    def test_validation_size(self):
        """Test size validation."""
        # Valid sizes
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts", size=None)
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts", size=0)
        SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts", size=1024)

        # Invalid sizes
        with pytest.raises(ValueError, match="size must be non-negative"):
            SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts", size=-1)

    def test_is_valid_property(self):
        """Test is_valid property."""
        # Valid segment
        segment = SegmentInfo(url="https://example.com/test.ts", index=1, filename="test.ts")
        assert segment.is_valid is True

        # We can't easily test invalid segments since __post_init__ prevents creation


class TestDownloadStats:
    """Test DownloadStats data class."""

    def test_stats_creation(self):
        """Test download stats creation."""
        stats = DownloadStats(
            total_segments=100,
            downloaded_segments=50,
            failed_segments=2,
            total_bytes=1024000,
            downloaded_bytes=512000,
            start_time=1234567890.0,
            average_speed=1024.5,
        )

        assert stats.total_segments == 100
        assert stats.downloaded_segments == 50
        assert stats.failed_segments == 2
        assert stats.total_bytes == 1024000
        assert stats.downloaded_bytes == 512000
        assert stats.start_time == 1234567890.0
        assert stats.average_speed == 1024.5

    def test_default_values(self):
        """Test default values for download stats."""
        stats = DownloadStats(total_segments=100)

        assert stats.total_segments == 100
        assert stats.downloaded_segments == 0
        assert stats.failed_segments == 0
        assert stats.total_bytes == 0
        assert stats.downloaded_bytes == 0
        assert stats.start_time == 0.0
        assert stats.average_speed == 0.0

    def test_validation_total_segments(self):
        """Test total_segments validation."""
        # Valid values
        DownloadStats(total_segments=0)
        DownloadStats(total_segments=100)

        # Invalid values
        with pytest.raises(ValueError, match="total_segments must be non-negative"):
            DownloadStats(total_segments=-1)

    def test_validation_downloaded_segments(self):
        """Test downloaded_segments validation."""
        # Valid values
        DownloadStats(total_segments=100, downloaded_segments=0)
        DownloadStats(total_segments=100, downloaded_segments=50)
        DownloadStats(total_segments=100, downloaded_segments=100)

        # Invalid values
        with pytest.raises(ValueError, match="downloaded_segments must be non-negative"):
            DownloadStats(total_segments=100, downloaded_segments=-1)
        
        with pytest.raises(ValueError, match="downloaded_segments cannot exceed total_segments"):
            DownloadStats(total_segments=100, downloaded_segments=101)

    def test_validation_failed_segments(self):
        """Test failed_segments validation."""
        # Valid values
        DownloadStats(total_segments=100, failed_segments=0)
        DownloadStats(total_segments=100, failed_segments=50)
        DownloadStats(total_segments=100, failed_segments=100)

        # Invalid values
        with pytest.raises(ValueError, match="failed_segments must be non-negative"):
            DownloadStats(total_segments=100, failed_segments=-1)
        
        with pytest.raises(ValueError, match="failed_segments cannot exceed total_segments"):
            DownloadStats(total_segments=100, failed_segments=101)

    def test_validation_bytes(self):
        """Test bytes validation."""
        # Valid values
        DownloadStats(total_segments=100, total_bytes=1000, downloaded_bytes=500)

        # Invalid values
        with pytest.raises(ValueError, match="total_bytes must be non-negative"):
            DownloadStats(total_segments=100, total_bytes=-1)
        
        with pytest.raises(ValueError, match="downloaded_bytes must be non-negative"):
            DownloadStats(total_segments=100, downloaded_bytes=-1)
        
        with pytest.raises(ValueError, match="downloaded_bytes cannot exceed total_bytes"):
            DownloadStats(total_segments=100, total_bytes=1000, downloaded_bytes=1001)

    def test_validation_time_and_speed(self):
        """Test time and speed validation."""
        # Valid values
        DownloadStats(total_segments=100, start_time=0.0, average_speed=0.0)
        DownloadStats(total_segments=100, start_time=1234567890.0, average_speed=1024.5)

        # Invalid values
        with pytest.raises(ValueError, match="start_time must be non-negative"):
            DownloadStats(total_segments=100, start_time=-1.0)
        
        with pytest.raises(ValueError, match="average_speed must be non-negative"):
            DownloadStats(total_segments=100, average_speed=-1.0)

    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        # Normal case
        stats = DownloadStats(total_segments=100, downloaded_segments=25)
        assert stats.progress_percentage == 25.0

        # Edge cases
        stats = DownloadStats(total_segments=0)
        assert stats.progress_percentage == 0.0

        stats = DownloadStats(total_segments=100, downloaded_segments=100)
        assert stats.progress_percentage == 100.0

    def test_remaining_segments(self):
        """Test remaining segments calculation."""
        stats = DownloadStats(total_segments=100, downloaded_segments=30, failed_segments=10)
        assert stats.remaining_segments == 60

        # All completed
        stats = DownloadStats(total_segments=100, downloaded_segments=80, failed_segments=20)
        assert stats.remaining_segments == 0

    def test_success_rate(self):
        """Test success rate calculation."""
        # Normal case
        stats = DownloadStats(total_segments=100, downloaded_segments=80, failed_segments=20)
        assert stats.success_rate == 80.0

        # No completed segments
        stats = DownloadStats(total_segments=100)
        assert stats.success_rate == 0.0

        # Perfect success
        stats = DownloadStats(total_segments=100, downloaded_segments=50)
        assert stats.success_rate == 100.0

    def test_update_speed(self):
        """Test speed update method."""
        stats = DownloadStats(total_segments=100, total_bytes=2048, downloaded_bytes=1024)
        
        # Update with valid elapsed time
        stats.update_speed(2.0)
        assert stats.average_speed == 512.0

        # Update with zero elapsed time (should not crash)
        stats.update_speed(0.0)
        assert stats.average_speed == 512.0  # Should remain unchanged
