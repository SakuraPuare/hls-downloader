"""Tests for ErrorHandler class."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.hls_downloader.error_handler import (
    DownloadError,
    ErrorHandler,
    ErrorType,
    FileSystemError,
    HTTPError,
    IntegrityError,
    NetworkError,
    RetryStrategy,
    TimeoutError,
)
from src.hls_downloader.models import SegmentInfo


class TestErrorHandler:
    """Test cases for ErrorHandler class."""

    @pytest.fixture
    def error_handler(self):
        """Create a test error handler."""
        return ErrorHandler(max_retries=3, base_delay=0.1)

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/segment1.ts",
            index=1,
            filename="segment1.ts"
        )

    def test_init(self):
        """Test ErrorHandler initialization."""
        handler = ErrorHandler(max_retries=5, base_delay=2.0)
        
        assert handler.max_retries == 5
        assert handler.base_delay == 2.0
        assert handler.error_counts == {}
        assert handler.retry_counts == {}

    def test_classify_timeout_error(self, error_handler, sample_segment):
        """Test classification of timeout errors."""
        original_error = httpx.TimeoutException("Request timeout")
        
        classified = error_handler.classify_error(original_error, sample_segment)
        
        assert isinstance(classified, TimeoutError)
        assert classified.error_type == ErrorType.TIMEOUT_ERROR
        assert classified.segment == sample_segment
        assert classified.original_error == original_error

    def test_classify_http_status_error(self, error_handler, sample_segment):
        """Test classification of HTTP status errors."""
        # Create a mock response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        
        original_error = httpx.HTTPStatusError(
            "404 Not Found", 
            request=Mock(), 
            response=mock_response
        )
        
        classified = error_handler.classify_error(original_error, sample_segment)
        
        assert isinstance(classified, HTTPError)
        assert classified.error_type == ErrorType.HTTP_ERROR
        assert classified.status_code == 404
        assert classified.segment == sample_segment
        assert classified.original_error == original_error

    def test_classify_network_error(self, error_handler, sample_segment):
        """Test classification of network errors."""
        original_error = httpx.ConnectError("Connection failed")
        
        classified = error_handler.classify_error(original_error, sample_segment)
        
        assert isinstance(classified, NetworkError)
        assert classified.error_type == ErrorType.NETWORK_ERROR
        assert classified.segment == sample_segment
        assert classified.original_error == original_error

    def test_classify_file_system_error(self, error_handler, sample_segment):
        """Test classification of file system errors."""
        original_error = PermissionError("Permission denied")
        
        classified = error_handler.classify_error(original_error, sample_segment)
        
        assert isinstance(classified, FileSystemError)
        assert classified.error_type == ErrorType.FILE_SYSTEM_ERROR
        assert classified.segment == sample_segment
        assert classified.original_error == original_error

    def test_classify_unknown_error(self, error_handler, sample_segment):
        """Test classification of unknown errors."""
        original_error = ValueError("Some unknown error")
        
        classified = error_handler.classify_error(original_error, sample_segment)
        
        assert isinstance(classified, DownloadError)
        assert classified.error_type == ErrorType.UNKNOWN_ERROR
        assert classified.segment == sample_segment
        assert classified.original_error == original_error

    def test_should_retry_network_error(self, error_handler, sample_segment):
        """Test retry decision for network errors."""
        error = NetworkError("Connection failed", segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_timeout_error(self, error_handler, sample_segment):
        """Test retry decision for timeout errors."""
        error = TimeoutError("Request timeout", segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_http_server_error(self, error_handler, sample_segment):
        """Test retry decision for HTTP server errors."""
        error = HTTPError("Server error", status_code=500, segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_http_client_error(self, error_handler, sample_segment):
        """Test retry decision for HTTP client errors."""
        error = HTTPError("Not found", status_code=404, segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is False

    def test_should_retry_http_rate_limit(self, error_handler, sample_segment):
        """Test retry decision for HTTP rate limit errors."""
        error = HTTPError("Rate limited", status_code=429, segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_permission_error(self, error_handler, sample_segment):
        """Test retry decision for permission errors."""
        error = FileSystemError("Permission denied", segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is False

    def test_should_retry_disk_space_error(self, error_handler, sample_segment):
        """Test retry decision for disk space errors."""
        error = FileSystemError("No space left on device", segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_integrity_error(self, error_handler, sample_segment):
        """Test retry decision for integrity errors."""
        error = IntegrityError("File corrupted", segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is True

    def test_should_retry_unknown_error(self, error_handler, sample_segment):
        """Test retry decision for unknown errors."""
        error = DownloadError("Unknown error", ErrorType.UNKNOWN_ERROR, segment=sample_segment)
        
        assert error_handler.should_retry(error, sample_segment) is False

    def test_should_retry_max_retries_exceeded(self, error_handler, sample_segment):
        """Test retry decision when max retries exceeded."""
        error = NetworkError("Connection failed", segment=sample_segment)
        
        # Simulate max retries reached
        error_handler.retry_counts[sample_segment.url] = error_handler.max_retries
        
        assert error_handler.should_retry(error, sample_segment) is False

    def test_get_retry_delay_exponential_backoff(self, error_handler):
        """Test exponential backoff retry delay calculation."""
        delay0 = error_handler.get_retry_delay(0, RetryStrategy.EXPONENTIAL_BACKOFF)
        delay1 = error_handler.get_retry_delay(1, RetryStrategy.EXPONENTIAL_BACKOFF)
        delay2 = error_handler.get_retry_delay(2, RetryStrategy.EXPONENTIAL_BACKOFF)
        
        # Should increase exponentially (with jitter)
        assert 0.1 <= delay0 <= 0.2  # base_delay * 1 + jitter
        assert 0.2 <= delay1 <= 0.4  # base_delay * 2 + jitter
        assert 0.4 <= delay2 <= 0.8  # base_delay * 4 + jitter

    def test_get_retry_delay_linear_backoff(self, error_handler):
        """Test linear backoff retry delay calculation."""
        delay0 = error_handler.get_retry_delay(0, RetryStrategy.LINEAR_BACKOFF)
        delay1 = error_handler.get_retry_delay(1, RetryStrategy.LINEAR_BACKOFF)
        delay2 = error_handler.get_retry_delay(2, RetryStrategy.LINEAR_BACKOFF)
        
        # Should increase linearly (with jitter)
        assert 0.1 <= delay0 <= 0.2  # base_delay * 1 + jitter
        assert 0.2 <= delay1 <= 0.3  # base_delay * 2 + jitter
        assert 0.3 <= delay2 <= 0.4  # base_delay * 3 + jitter

    def test_get_retry_delay_fixed_delay(self, error_handler):
        """Test fixed delay retry calculation."""
        delay0 = error_handler.get_retry_delay(0, RetryStrategy.FIXED_DELAY)
        delay1 = error_handler.get_retry_delay(1, RetryStrategy.FIXED_DELAY)
        delay2 = error_handler.get_retry_delay(2, RetryStrategy.FIXED_DELAY)
        
        # Should be roughly the same (with small jitter)
        assert 0.1 <= delay0 <= 0.15
        assert 0.1 <= delay1 <= 0.15
        assert 0.1 <= delay2 <= 0.15

    def test_get_retry_delay_no_retry(self, error_handler):
        """Test no retry delay calculation."""
        delay = error_handler.get_retry_delay(0, RetryStrategy.NO_RETRY)
        
        assert delay == 0.0

    def test_log_error_updates_counts(self, error_handler, sample_segment):
        """Test that logging errors updates error counts."""
        error = NetworkError("Connection failed", segment=sample_segment)
        
        error_handler.log_error(error)
        
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1

    def test_log_error_multiple_same_type(self, error_handler, sample_segment):
        """Test logging multiple errors of the same type."""
        error1 = NetworkError("Connection failed", segment=sample_segment)
        error2 = NetworkError("DNS resolution failed", segment=sample_segment)
        
        error_handler.log_error(error1)
        error_handler.log_error(error2)
        
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 2

    def test_increment_retry_count(self, error_handler, sample_segment):
        """Test incrementing retry count for a segment."""
        count1 = error_handler.increment_retry_count(sample_segment)
        count2 = error_handler.increment_retry_count(sample_segment)
        
        assert count1 == 1
        assert count2 == 2
        assert error_handler.retry_counts[sample_segment.url] == 2

    def test_reset_retry_count(self, error_handler, sample_segment):
        """Test resetting retry count for a segment."""
        error_handler.increment_retry_count(sample_segment)
        error_handler.increment_retry_count(sample_segment)
        
        assert error_handler.retry_counts[sample_segment.url] == 2
        
        error_handler.reset_retry_count(sample_segment)
        
        assert sample_segment.url not in error_handler.retry_counts

    def test_get_error_summary_empty(self, error_handler):
        """Test error summary when no errors occurred."""
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 0
        assert summary["error_breakdown"] == {}
        assert summary["active_retries"] == 0
        assert summary["segments_with_retries"] == []

    def test_get_error_summary_with_errors(self, error_handler, sample_segment):
        """Test error summary with errors and retries."""
        error1 = NetworkError("Connection failed", segment=sample_segment)
        error2 = HTTPError("Server error", status_code=500, segment=sample_segment)
        
        error_handler.log_error(error1)
        error_handler.log_error(error2)
        error_handler.increment_retry_count(sample_segment)
        
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 2
        assert summary["error_breakdown"][ErrorType.NETWORK_ERROR] == 1
        assert summary["error_breakdown"][ErrorType.HTTP_ERROR] == 1
        assert summary["active_retries"] == 1
        assert sample_segment.url in summary["segments_with_retries"]

    @pytest.mark.asyncio
    async def test_handle_with_retry_success_first_attempt(self, error_handler, sample_segment):
        """Test successful operation on first attempt."""
        mock_operation = AsyncMock(return_value="success")
        
        result = await error_handler.handle_with_retry(
            mock_operation, sample_segment, "arg1", kwarg1="value1"
        )
        
        assert result == "success"
        assert mock_operation.call_count == 1
        mock_operation.assert_called_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_handle_with_retry_success_after_retries(self, error_handler, sample_segment):
        """Test successful operation after some retries."""
        mock_operation = AsyncMock()
        # Fail twice, then succeed
        mock_operation.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            "success"
        ]
        
        result = await error_handler.handle_with_retry(
            mock_operation, sample_segment
        )
        
        assert result == "success"
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_handle_with_retry_permanent_failure(self, error_handler, sample_segment):
        """Test permanent failure after all retries exhausted."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = httpx.TimeoutException("Persistent timeout")
        
        with pytest.raises(TimeoutError):
            await error_handler.handle_with_retry(
                mock_operation, sample_segment
            )
        
        # Should try initial + max_retries times
        assert mock_operation.call_count == error_handler.max_retries + 1

    @pytest.mark.asyncio
    async def test_handle_with_retry_non_retryable_error(self, error_handler, sample_segment):
        """Test non-retryable error fails immediately."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        
        mock_operation = AsyncMock()
        mock_operation.side_effect = httpx.HTTPStatusError(
            "404 Not Found", 
            request=Mock(), 
            response=mock_response
        )
        
        with pytest.raises(HTTPError):
            await error_handler.handle_with_retry(
                mock_operation, sample_segment
            )
        
        # Should only try once for non-retryable errors
        assert mock_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_with_retry_delay_between_attempts(self, error_handler, sample_segment):
        """Test that there's a delay between retry attempts."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            httpx.TimeoutException("Timeout"),
            "success"
        ]
        
        start_time = time.time()
        result = await error_handler.handle_with_retry(
            mock_operation, sample_segment
        )
        end_time = time.time()
        
        assert result == "success"
        assert mock_operation.call_count == 2
        # Should have some delay (at least base_delay)
        assert end_time - start_time >= error_handler.base_delay

    @pytest.mark.asyncio
    async def test_handle_with_retry_resets_count_on_success(self, error_handler, sample_segment):
        """Test that retry count is reset on successful retry."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            httpx.TimeoutException("Timeout"),
            "success"
        ]
        
        # Pre-populate retry count
        error_handler.retry_counts[sample_segment.url] = 1
        
        result = await error_handler.handle_with_retry(
            mock_operation, sample_segment
        )
        
        assert result == "success"
        # Retry count should be reset after success
        assert sample_segment.url not in error_handler.retry_counts


class TestDownloadErrorClasses:
    """Test cases for download error classes."""

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/segment1.ts",
            index=1,
            filename="segment1.ts"
        )

    def test_download_error_base_class(self, sample_segment):
        """Test base DownloadError class."""
        original_error = ValueError("Original error")
        error = DownloadError(
            "Test error", 
            ErrorType.UNKNOWN_ERROR, 
            segment=sample_segment,
            original_error=original_error
        )
        
        assert str(error) == "Test error"
        assert error.error_type == ErrorType.UNKNOWN_ERROR
        assert error.segment == sample_segment
        assert error.original_error == original_error
        assert error.timestamp > 0

    def test_network_error(self, sample_segment):
        """Test NetworkError class."""
        error = NetworkError("Connection failed", segment=sample_segment)
        
        assert error.error_type == ErrorType.NETWORK_ERROR
        assert str(error) == "Connection failed"

    def test_http_error(self, sample_segment):
        """Test HTTPError class."""
        error = HTTPError("Not found", status_code=404, segment=sample_segment)
        
        assert error.error_type == ErrorType.HTTP_ERROR
        assert error.status_code == 404
        assert str(error) == "Not found"

    def test_file_system_error(self, sample_segment):
        """Test FileSystemError class."""
        error = FileSystemError("Permission denied", segment=sample_segment)
        
        assert error.error_type == ErrorType.FILE_SYSTEM_ERROR
        assert str(error) == "Permission denied"

    def test_timeout_error(self, sample_segment):
        """Test TimeoutError class."""
        error = TimeoutError("Request timeout", segment=sample_segment)
        
        assert error.error_type == ErrorType.TIMEOUT_ERROR
        assert str(error) == "Request timeout"

    def test_integrity_error(self, sample_segment):
        """Test IntegrityError class."""
        error = IntegrityError("File corrupted", segment=sample_segment)
        
        assert error.error_type == ErrorType.INTEGRITY_ERROR
        assert str(error) == "File corrupted"