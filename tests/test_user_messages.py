"""Tests for user-friendly message display."""

from unittest.mock import patch

import pytest

from src.hls_downloader.error_handler import (
    DownloadError,
    ErrorType,
    FileSystemError,
    HTTPError,
    IntegrityError,
    NetworkError,
    TimeoutError,
)
from src.hls_downloader.models import SegmentInfo
from src.hls_downloader.user_messages import (
    UserMessageDisplay,
    display_completion_info,
    display_progress_info,
    display_startup_info,
    show_debug_info,
    show_info,
    show_success,
    show_user_error,
    show_warning,
)


class TestUserMessageDisplay:
    """Test cases for UserMessageDisplay class."""

    @pytest.fixture
    def message_display(self):
        """Create a test message display."""
        return UserMessageDisplay(verbose=False)

    @pytest.fixture
    def verbose_display(self):
        """Create a verbose message display."""
        return UserMessageDisplay(verbose=True)

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://example.com/segment1.ts", index=1, filename="segment1.ts"
        )

    def test_init(self):
        """Test UserMessageDisplay initialization."""
        display = UserMessageDisplay()
        assert display.verbose is False

        verbose_display = UserMessageDisplay(verbose=True)
        assert verbose_display.verbose is True

    def test_show_error_network_error(self, message_display, sample_segment, capsys):
        """Test showing network error."""
        error = NetworkError("Connection failed", segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Network connection failed" in captured.err
        assert "Segment: 1" in captured.err

    def test_show_error_timeout_error(self, message_display, sample_segment, capsys):
        """Test showing timeout error."""
        error = TimeoutError("Request timeout", segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Request timed out" in captured.err

    def test_show_error_http_404(self, message_display, sample_segment, capsys):
        """Test showing HTTP 404 error."""
        error = HTTPError("Not found", status_code=404, segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Segment not found" in captured.err

    def test_show_error_http_403(self, message_display, sample_segment, capsys):
        """Test showing HTTP 403 error."""
        error = HTTPError("Forbidden", status_code=403, segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Access denied" in captured.err

    def test_show_error_http_429(self, message_display, sample_segment, capsys):
        """Test showing HTTP 429 error."""
        error = HTTPError("Rate limited", status_code=429, segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Rate limited" in captured.err

    def test_show_error_http_500(self, message_display, sample_segment, capsys):
        """Test showing HTTP 500 error."""
        error = HTTPError("Server error", status_code=500, segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Server error" in captured.err

    def test_show_error_file_permission(self, message_display, sample_segment, capsys):
        """Test showing file permission error."""
        error = FileSystemError("Permission denied", segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Permission denied" in captured.err

    def test_show_error_disk_full(self, message_display, sample_segment, capsys):
        """Test showing disk full error."""
        error = FileSystemError("No space left on device", segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Disk full" in captured.err

    def test_show_error_integrity_error(self, message_display, sample_segment, capsys):
        """Test showing integrity error."""
        error = IntegrityError("File corrupted", segment=sample_segment)

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Downloaded file is corrupted" in captured.err

    def test_show_error_unknown_error(self, message_display, sample_segment, capsys):
        """Test showing unknown error."""
        error = DownloadError(
            "Unknown error", ErrorType.UNKNOWN_ERROR, segment=sample_segment
        )

        message_display.show_error(error)

        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Unexpected error occurred" in captured.err

    def test_show_error_with_technical_details(
        self, message_display, sample_segment, capsys
    ):
        """Test showing error with technical details."""
        error = NetworkError("Connection failed", segment=sample_segment)

        message_display.show_error(error, show_technical=True)

        captured = capsys.readouterr()
        assert "Technical:" in captured.err

    def test_show_error_verbose_mode(self, verbose_display, sample_segment, capsys):
        """Test showing error in verbose mode."""
        error = NetworkError("Connection failed", segment=sample_segment)

        verbose_display.show_error(error)

        captured = capsys.readouterr()
        assert "Technical:" in captured.err

    def test_show_error_summary_no_errors(self, message_display, capsys):
        """Test showing error summary with no errors."""
        error_summary = {"total_errors": 0, "error_breakdown": {}, "active_retries": 0}

        message_display.show_error_summary(error_summary)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "successfully with no errors" in captured.out

    def test_show_error_summary_with_errors(self, message_display, capsys):
        """Test showing error summary with errors."""
        error_summary = {
            "total_errors": 5,
            "error_breakdown": {"network_error": 3, "timeout_error": 2},
            "active_retries": 2,
        }

        message_display.show_error_summary(error_summary)

        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "5 error(s)" in captured.out
        assert "Network errors: 3" in captured.out
        assert "Timeout errors: 2" in captured.out
        assert "Segments with retries: 2" in captured.out

    def test_show_error_summary_with_recommendations(self, message_display, capsys):
        """Test showing error summary with recommendations."""
        error_summary = {
            "total_errors": 3,
            "error_breakdown": {"network_error": 2, "http_error": 1},
            "active_retries": 0,
        }

        message_display.show_error_summary(error_summary)

        captured = capsys.readouterr()
        assert "💡 Recommendations:" in captured.out
        assert "Check your internet connection" in captured.out
        assert "reducing --concurrent" in captured.out
        assert "Verify the URL is correct" in captured.out

    def test_show_download_tips(self, message_display, capsys):
        """Test showing download tips."""
        message_display.show_download_tips()

        captured = capsys.readouterr()
        assert "💡 Tips for better downloads:" in captured.out
        assert "--debug" in captured.out
        assert "--concurrent" in captured.out
        assert "--retries" in captured.out

    def test_show_ffmpeg_help(self, message_display, capsys):
        """Test showing ffmpeg help."""
        message_display.show_ffmpeg_help()

        captured = capsys.readouterr()
        assert "🎬 FFmpeg is required" in captured.out
        assert "brew install ffmpeg" in captured.out
        assert "apt install ffmpeg" in captured.out
        assert "--no-merge" in captured.out

    def test_show_resume_help(self, message_display, capsys):
        """Test showing resume help."""
        message_display.show_resume_help("/tmp/downloads")

        captured = capsys.readouterr()
        assert "🔄 To resume this download" in captured.out
        assert "--resume" in captured.out
        assert "/tmp/downloads" in captured.out

    def test_get_friendly_error_type(self, message_display):
        """Test getting friendly error type names."""
        assert (
            message_display._get_friendly_error_type("network_error")
            == "Network errors"
        )
        assert (
            message_display._get_friendly_error_type("timeout_error")
            == "Timeout errors"
        )
        assert message_display._get_friendly_error_type("http_error") == "HTTP errors"
        assert (
            message_display._get_friendly_error_type("file_system_error")
            == "File system errors"
        )
        assert (
            message_display._get_friendly_error_type("integrity_error")
            == "File corruption errors"
        )
        assert (
            message_display._get_friendly_error_type("unknown_error")
            == "Unknown errors"
        )
        assert (
            message_display._get_friendly_error_type("custom_error") == "Custom Error"
        )


class TestDisplayFunctions:
    """Test cases for display utility functions."""

    def test_display_startup_info(self, capsys):
        """Test displaying startup information."""
        config = {"max_concurrent": 10, "max_retries": 3}

        display_startup_info("http://example.com/test.m3u8", "/tmp/output", config)

        captured = capsys.readouterr()
        assert "🚀 Starting HLS download" in captured.out
        assert "http://example.com/test.m3u8" in captured.out
        assert "/tmp/output" in captured.out
        assert "Concurrent: 10" in captured.out
        assert "Max retries: 3" in captured.out

    def test_display_completion_info(self, capsys):
        """Test displaying completion information."""
        display_completion_info(100, 95, 5, 120.5, "/tmp/output/video.mp4")

        captured = capsys.readouterr()
        assert "📊 Download Statistics:" in captured.out
        assert "Total segments: 100" in captured.out
        assert "Successful: 95" in captured.out
        assert "Failed: 5" in captured.out
        assert "Success rate: 95.0%" in captured.out
        assert "Duration: 120.5 seconds" in captured.out
        assert "Merged video: /tmp/output/video.mp4" in captured.out

    def test_display_completion_info_no_output_file(self, capsys):
        """Test displaying completion information without output file."""
        display_completion_info(50, 50, 0, 60.0)

        captured = capsys.readouterr()
        assert "📊 Download Statistics:" in captured.out
        assert "Success rate: 100.0%" in captured.out
        assert "Merged video:" not in captured.out

    def test_display_progress_info(self, capsys):
        """Test displaying progress information."""
        display_progress_info(50, 100, 2.5)

        captured = capsys.readouterr()
        assert "📥 Progress: 50/100 (50.0%)" in captured.out
        assert "2.5 segments/sec" in captured.out

    @patch("src.hls_downloader.user_messages.logger")
    def test_show_debug_info(self, mock_logger):
        """Test showing debug information."""
        show_debug_info("Debug message", segment_id=1, status="downloading")

        # Should bind context and log debug message
        mock_logger.bind.assert_called_once_with(segment_id=1, status="downloading")
        bound_logger = mock_logger.bind.return_value
        bound_logger.debug.assert_called_once_with("Debug message")

    def test_show_user_error(self, capsys):
        """Test showing user error."""
        show_user_error("Something went wrong")

        captured = capsys.readouterr()
        assert "❌ Error: Something went wrong" in captured.err
        assert "Use --help for usage information" in captured.err

    def test_show_user_error_no_help(self, capsys):
        """Test showing user error without help."""
        show_user_error("Something went wrong", show_help=False)

        captured = capsys.readouterr()
        assert "❌ Error: Something went wrong" in captured.err
        assert "Use --help" not in captured.err

    def test_show_warning(self, capsys):
        """Test showing warning message."""
        show_warning("This is a warning")

        captured = capsys.readouterr()
        assert "⚠️  Warning: This is a warning" in captured.err

    def test_show_success(self, capsys):
        """Test showing success message."""
        show_success("Operation completed")

        captured = capsys.readouterr()
        assert "✅ Operation completed" in captured.out

    def test_show_info(self, capsys):
        """Test showing info message."""
        show_info("Information message")

        captured = capsys.readouterr()
        assert "ℹ️  Information message" in captured.out


class TestErrorMessageMapping:
    """Test cases for error message mapping logic."""

    @pytest.fixture
    def message_display(self):
        """Create a test message display."""
        return UserMessageDisplay()

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://example.com/segment1.ts", index=1, filename="segment1.ts"
        )

    def test_network_error_message(self, message_display, sample_segment):
        """Test network error message mapping."""
        error = NetworkError("Connection failed", segment=sample_segment)
        message = message_display._get_friendly_error_message(error)
        assert "Network connection failed" in message

    def test_timeout_error_message(self, message_display, sample_segment):
        """Test timeout error message mapping."""
        error = TimeoutError("Request timeout", segment=sample_segment)
        message = message_display._get_friendly_error_message(error)
        assert "Request timed out" in message

    def test_http_error_messages(self, message_display, sample_segment):
        """Test various HTTP error message mappings."""
        # Test 404
        error_404 = HTTPError("Not found", status_code=404, segment=sample_segment)
        message_404 = message_display._get_friendly_error_message(error_404)
        assert "Segment not found" in message_404

        # Test 403
        error_403 = HTTPError("Forbidden", status_code=403, segment=sample_segment)
        message_403 = message_display._get_friendly_error_message(error_403)
        assert "Access denied" in message_403

        # Test 429
        error_429 = HTTPError("Rate limited", status_code=429, segment=sample_segment)
        message_429 = message_display._get_friendly_error_message(error_429)
        assert "Rate limited" in message_429

        # Test 500
        error_500 = HTTPError("Server error", status_code=500, segment=sample_segment)
        message_500 = message_display._get_friendly_error_message(error_500)
        assert "Server error" in message_500

        # Test other client error
        error_400 = HTTPError("Bad request", status_code=400, segment=sample_segment)
        message_400 = message_display._get_friendly_error_message(error_400)
        assert "HTTP error 400" in message_400

    def test_file_system_error_messages(self, message_display, sample_segment):
        """Test file system error message mappings."""
        # Test permission denied
        error_perm = FileSystemError("Permission denied", segment=sample_segment)
        message_perm = message_display._get_friendly_error_message(error_perm)
        assert "Permission denied" in message_perm

        # Test disk full
        error_space = FileSystemError("No space left on device", segment=sample_segment)
        message_space = message_display._get_friendly_error_message(error_space)
        assert "Disk full" in message_space

        # Test file exists
        error_exists = FileSystemError("File exists", segment=sample_segment)
        message_exists = message_display._get_friendly_error_message(error_exists)
        assert "File already exists" in message_exists

        # Test generic file system error
        error_generic = FileSystemError("Generic error", segment=sample_segment)
        message_generic = message_display._get_friendly_error_message(error_generic)
        assert "File system error" in message_generic

    def test_integrity_error_message(self, message_display, sample_segment):
        """Test integrity error message mapping."""
        error = IntegrityError("File corrupted", segment=sample_segment)
        message = message_display._get_friendly_error_message(error)
        assert "Downloaded file is corrupted" in message

    def test_unknown_error_message(self, message_display, sample_segment):
        """Test unknown error message mapping."""
        error = DownloadError(
            "Unknown error", ErrorType.UNKNOWN_ERROR, segment=sample_segment
        )
        message = message_display._get_friendly_error_message(error)
        assert "Unexpected error occurred" in message
