"""Tests for various error scenarios and edge cases."""

import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.hls_downloader.utils.error_handler import (
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
from src.hls_downloader.models.segment import SegmentInfo


class TestErrorScenarios:
    """Test various error scenarios that can occur during downloads."""

    @pytest.fixture
    def error_handler(self):
        """Create a test error handler."""
        return ErrorHandler(max_retries=3, base_delay=0.01)  # Fast retries for testing

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://example.com/segment1.ts", index=1, filename="segment1.ts"
        )

    def test_network_connection_refused(self, error_handler, sample_segment):
        """Test handling of connection refused errors."""
        original_error = httpx.ConnectError("Connection refused")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, NetworkError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_dns_resolution_failure(self, error_handler, sample_segment):
        """Test handling of DNS resolution failures."""
        original_error = httpx.ConnectError("Name resolution failed")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, NetworkError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_ssl_certificate_error(self, error_handler, sample_segment):
        """Test handling of SSL certificate errors."""
        original_error = httpx.ConnectError("SSL certificate verification failed")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, NetworkError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_read_timeout(self, error_handler, sample_segment):
        """Test handling of read timeout errors."""
        original_error = httpx.ReadTimeout("Read timeout")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, TimeoutError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_write_timeout(self, error_handler, sample_segment):
        """Test handling of write timeout errors."""
        original_error = httpx.WriteTimeout("Write timeout")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, TimeoutError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_pool_timeout(self, error_handler, sample_segment):
        """Test handling of connection pool timeout errors."""
        original_error = httpx.PoolTimeout("Pool timeout")
        classified = error_handler.classify_error(original_error, sample_segment)

        assert isinstance(classified, TimeoutError)
        assert error_handler.should_retry(classified, sample_segment)

    def test_http_status_errors(self, error_handler, sample_segment):
        """Test handling of various HTTP status errors."""
        status_codes = [400, 401, 403, 404, 429, 500, 502, 503, 504]

        for status_code in status_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.reason_phrase = f"HTTP {status_code}"

            original_error = httpx.HTTPStatusError(
                f"{status_code} Error", request=Mock(), response=mock_response
            )

            classified = error_handler.classify_error(original_error, sample_segment)

            assert isinstance(classified, HTTPError)
            assert classified.status_code == status_code

            # Check retry logic
            should_retry = error_handler.should_retry(classified, sample_segment)
            if status_code in [429, 500, 502, 503, 504]:
                assert should_retry, f"Should retry {status_code}"
            else:
                assert not should_retry, f"Should not retry {status_code}"

    def test_file_permission_errors(self, error_handler, sample_segment):
        """Test handling of file permission errors."""
        permission_errors = [
            PermissionError("Permission denied"),
            OSError("Operation not permitted"),
            FileNotFoundError("No such file or directory"),
        ]

        for original_error in permission_errors:
            classified = error_handler.classify_error(original_error, sample_segment)

            assert isinstance(classified, FileSystemError)

            # Permission errors should not be retried
            if "Permission denied" in str(original_error):
                assert not error_handler.should_retry(classified, sample_segment)
            else:
                # Other file system errors might be retryable
                pass

    def test_disk_space_errors(self, error_handler, sample_segment):
        """Test handling of disk space errors."""
        disk_errors = [
            OSError("No space left on device"),
            OSError("Disk quota exceeded"),
        ]

        for original_error in disk_errors:
            classified = error_handler.classify_error(original_error, sample_segment)

            assert isinstance(classified, FileSystemError)
            # Disk space errors should be retryable (user might free space)
            assert error_handler.should_retry(classified, sample_segment)

    def test_integrity_check_failure(self, error_handler, sample_segment):
        """Test handling of file integrity check failures."""
        original_error = IntegrityError("File size mismatch", segment=sample_segment)

        assert error_handler.should_retry(original_error, sample_segment)

    def test_unknown_exception_handling(self, error_handler, sample_segment):
        """Test handling of unknown exceptions."""
        unknown_errors = [
            ValueError("Invalid value"),
            RuntimeError("Runtime error"),
            KeyError("Missing key"),
            AttributeError("Missing attribute"),
        ]

        for original_error in unknown_errors:
            classified = error_handler.classify_error(original_error, sample_segment)

            assert isinstance(classified, DownloadError)
            assert classified.error_type == ErrorType.UNKNOWN_ERROR
            assert not error_handler.should_retry(classified, sample_segment)

    @pytest.mark.asyncio
    async def test_cascading_failures(self, error_handler, sample_segment):
        """Test handling of cascading failures (different errors on retries)."""
        mock_operation = AsyncMock()

        # Simulate different errors on each attempt
        mock_operation.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.ConnectError("Connection failed"),
            httpx.HTTPStatusError(
                "500 Server Error",
                request=Mock(),
                response=Mock(status_code=500, reason_phrase="Server Error"),
            ),
            "success",
        ]

        result = await error_handler.handle_with_retry(mock_operation, sample_segment)

        assert result == "success"
        assert mock_operation.call_count == 4

    @pytest.mark.asyncio
    async def test_max_retries_with_different_errors(
        self, error_handler, sample_segment
    ):
        """Test that max retries is respected even with different error types."""
        mock_operation = AsyncMock()

        # All retryable errors, but exceed max retries
        mock_operation.side_effect = [
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"),
            httpx.TimeoutException("Timeout 3"),
            httpx.TimeoutException("Timeout 4"),  # This should not be reached
        ]

        with pytest.raises(TimeoutError):
            await error_handler.handle_with_retry(mock_operation, sample_segment)

        # Should try initial + max_retries times
        assert mock_operation.call_count == error_handler.max_retries + 1

    @pytest.mark.asyncio
    async def test_non_retryable_error_stops_immediately(
        self, error_handler, sample_segment
    ):
        """Test that non-retryable errors stop retry attempts immediately."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"

        mock_operation = AsyncMock()
        mock_operation.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )

        with pytest.raises(HTTPError):
            await error_handler.handle_with_retry(mock_operation, sample_segment)

        # Should only try once for non-retryable errors
        assert mock_operation.call_count == 1

    def test_error_count_tracking(self, error_handler, sample_segment):
        """Test that error counts are tracked correctly."""
        # Generate various errors
        errors = [
            NetworkError("Network error 1", segment=sample_segment),
            NetworkError("Network error 2", segment=sample_segment),
            TimeoutError("Timeout error", segment=sample_segment),
            HTTPError("HTTP error", status_code=500, segment=sample_segment),
        ]

        for error in errors:
            error_handler.log_error(error)

        summary = error_handler.get_error_summary()

        assert summary["total_errors"] == 4
        assert summary["error_breakdown"][ErrorType.NETWORK_ERROR] == 2
        assert summary["error_breakdown"][ErrorType.TIMEOUT_ERROR] == 1
        assert summary["error_breakdown"][ErrorType.HTTP_ERROR] == 1

    def test_retry_count_tracking(self, error_handler, sample_segment):
        """Test that retry counts are tracked per segment."""
        # Increment retry count multiple times
        count1 = error_handler.increment_retry_count(sample_segment)
        count2 = error_handler.increment_retry_count(sample_segment)
        count3 = error_handler.increment_retry_count(sample_segment)

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

        summary = error_handler.get_error_summary()
        assert summary["active_retries"] == 1
        assert sample_segment.url in summary["segments_with_retries"]

    def test_retry_delay_calculation_edge_cases(self, error_handler):
        """Test retry delay calculation for edge cases."""
        # Test very high attempt numbers
        delay_high = error_handler.get_retry_delay(
            10, RetryStrategy.EXPONENTIAL_BACKOFF
        )
        assert delay_high > 0

        # Test zero attempt
        delay_zero = error_handler.get_retry_delay(0, RetryStrategy.EXPONENTIAL_BACKOFF)
        assert delay_zero >= error_handler.base_delay

        # Test negative attempt (should handle gracefully)
        delay_negative = error_handler.get_retry_delay(
            -1, RetryStrategy.EXPONENTIAL_BACKOFF
        )
        assert delay_negative >= 0

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, error_handler):
        """Test error handling with concurrent operations."""
        segments = [
            SegmentInfo(
                url=f"https://example.com/segment{i}.ts",
                index=i,
                filename=f"segment{i}.ts",
            )
            for i in range(5)
        ]

        async def failing_operation():
            raise httpx.TimeoutException("Concurrent timeout")

        # Run multiple operations concurrently
        tasks = [
            error_handler.handle_with_retry(failing_operation, segment)
            for segment in segments
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail with TimeoutError
        for result in results:
            assert isinstance(result, TimeoutError)

        # Check that error counts are tracked correctly
        summary = error_handler.get_error_summary()
        assert summary["total_errors"] >= len(
            segments
        )  # At least one error per segment

    def test_error_context_preservation(self, error_handler, sample_segment):
        """Test that error context is preserved through classification."""
        original_error = httpx.ConnectError("Connection failed")
        original_error.custom_attribute = "test_value"

        classified = error_handler.classify_error(original_error, sample_segment)

        assert classified.original_error == original_error
        assert classified.segment == sample_segment
        assert hasattr(classified.original_error, "custom_attribute")
        assert classified.original_error.custom_attribute == "test_value"

    def test_error_timestamp_tracking(self, error_handler, sample_segment):
        """Test that error timestamps are tracked."""
        import time

        start_time = time.time()
        error = NetworkError("Network error", segment=sample_segment)
        end_time = time.time()

        assert start_time <= error.timestamp <= end_time

    @pytest.mark.asyncio
    async def test_operation_success_after_errors(self, error_handler, sample_segment):
        """Test that successful operations reset retry counts."""
        mock_operation = AsyncMock()

        # Fail once, then succeed
        mock_operation.side_effect = [httpx.TimeoutException("Timeout"), "success"]

        # Pre-populate retry count
        error_handler.increment_retry_count(sample_segment)

        result = await error_handler.handle_with_retry(mock_operation, sample_segment)

        assert result == "success"
        # Retry count should be reset after success
        assert sample_segment.url not in error_handler.retry_counts

    def test_error_logging_with_context(self, error_handler, sample_segment):
        """Test error logging with additional context."""
        error = NetworkError("Network error", segment=sample_segment)
        context = {"attempt": 2, "total_attempts": 3, "custom_field": "test_value"}

        # Should not raise any exceptions
        error_handler.log_error(error, context)

        # Verify error was counted
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def error_handler(self):
        """Create a test error handler."""
        return ErrorHandler(
            max_retries=0, base_delay=0.01
        )  # No retries for edge case testing

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing."""
        return SegmentInfo(
            url="https://example.com/segment1.ts", index=1, filename="segment1.ts"
        )

    def test_zero_max_retries(self, error_handler, sample_segment):
        """Test behavior with zero max retries."""
        error = NetworkError("Network error", segment=sample_segment)

        # Should not retry even for retryable errors
        assert not error_handler.should_retry(error, sample_segment)

    def test_empty_error_message(self, error_handler, sample_segment):
        """Test handling of errors with empty messages."""
        error = NetworkError("", segment=sample_segment)

        # Should handle gracefully
        error_handler.log_error(error)
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1

    def test_none_segment(self, error_handler):
        """Test error handling with None segment."""
        original_error = httpx.TimeoutException("Timeout")
        classified = error_handler.classify_error(original_error, None)

        assert isinstance(classified, TimeoutError)
        assert classified.segment is None

    def test_error_summary_empty_state(self, error_handler):
        """Test error summary in empty state."""
        summary = error_handler.get_error_summary()

        assert summary["total_errors"] == 0
        assert summary["error_breakdown"] == {}
        assert summary["active_retries"] == 0
        assert summary["segments_with_retries"] == []

    def test_reset_nonexistent_retry_count(self, error_handler, sample_segment):
        """Test resetting retry count for segment that hasn't been retried."""
        # Should not raise any exceptions
        error_handler.reset_retry_count(sample_segment)

        # Should still be empty
        assert sample_segment.url not in error_handler.retry_counts

    def test_very_long_error_message(self, error_handler, sample_segment):
        """Test handling of very long error messages."""
        long_message = "A" * 10000  # Very long error message
        error = NetworkError(long_message, segment=sample_segment)

        # Should handle gracefully
        error_handler.log_error(error)
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1

    def test_unicode_error_message(self, error_handler, sample_segment):
        """Test handling of unicode error messages."""
        unicode_message = "网络错误: 连接失败 🌐❌"
        error = NetworkError(unicode_message, segment=sample_segment)

        # Should handle gracefully
        error_handler.log_error(error)
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1

    @pytest.mark.asyncio
    async def test_operation_returning_none(self, error_handler, sample_segment):
        """Test operation that returns None."""
        mock_operation = AsyncMock(return_value=None)

        result = await error_handler.handle_with_retry(mock_operation, sample_segment)

        assert result is None

    @pytest.mark.asyncio
    async def test_operation_with_complex_return_value(
        self, error_handler, sample_segment
    ):
        """Test operation that returns complex data structures."""
        complex_result = {
            "data": [1, 2, 3],
            "metadata": {"size": 1024, "type": "video"},
            "nested": {"deep": {"value": "test"}},
        }

        mock_operation = AsyncMock(return_value=complex_result)

        result = await error_handler.handle_with_retry(mock_operation, sample_segment)

        assert result == complex_result
