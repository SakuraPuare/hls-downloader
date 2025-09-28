"""Error handling utilities for HLS downloader."""

import asyncio
import random
import time
from enum import Enum
from typing import Any, Optional

import httpx
from loguru import logger

from ..models.segment import SegmentInfo


class ErrorType(Enum):
    """Classification of different error types."""

    NETWORK_ERROR = "network_error"
    HTTP_ERROR = "http_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    TIMEOUT_ERROR = "timeout_error"
    INTEGRITY_ERROR = "integrity_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(Enum):
    """Different retry strategies."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class DownloadError(Exception):
    """Base exception for download-related errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.segment = segment
        self.original_error = original_error
        self.timestamp = time.time()


class NetworkError(DownloadError):
    """Network-related download error."""

    def __init__(
        self,
        message: str,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, ErrorType.NETWORK_ERROR, segment, original_error)


class HTTPError(DownloadError):
    """HTTP-related download error."""

    def __init__(
        self,
        message: str,
        status_code: int,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, ErrorType.HTTP_ERROR, segment, original_error)
        self.status_code = status_code


class FileSystemError(DownloadError):
    """File system-related download error."""

    def __init__(
        self,
        message: str,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, ErrorType.FILE_SYSTEM_ERROR, segment, original_error)


class TimeoutError(DownloadError):
    """Timeout-related download error."""

    def __init__(
        self,
        message: str,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, ErrorType.TIMEOUT_ERROR, segment, original_error)


class IntegrityError(DownloadError):
    """File integrity-related download error."""

    def __init__(
        self,
        message: str,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, ErrorType.INTEGRITY_ERROR, segment, original_error)


class ErrorHandler:
    """Unified error handler for download operations."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """Initialize error handler.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_counts: dict[ErrorType, int] = {}
        self.retry_counts: dict[str, int] = {}  # segment URL -> retry count

    def classify_error(
        self, error: Exception, segment: Optional[SegmentInfo] = None
    ) -> DownloadError:
        """Classify an exception into a specific download error type.

        Args:
            error: The original exception
            segment: The segment being processed when error occurred

        Returns:
            Classified DownloadError instance
        """
        if isinstance(error, httpx.TimeoutException):
            return TimeoutError(
                f"Request timeout: {str(error)}", segment=segment, original_error=error
            )

        elif isinstance(error, httpx.HTTPStatusError):
            return HTTPError(
                f"HTTP {error.response.status_code}: {error.response.reason_phrase}",
                status_code=error.response.status_code,
                segment=segment,
                original_error=error,
            )

        elif isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
            return NetworkError(
                f"Network error: {str(error)}", segment=segment, original_error=error
            )

        elif isinstance(error, (OSError, IOError, PermissionError)):
            return FileSystemError(
                f"File system error: {str(error)}",
                segment=segment,
                original_error=error,
            )

        elif isinstance(error, IntegrityError):
            # IntegrityError is already properly classified
            return error

        else:
            return DownloadError(
                f"Unknown error: {str(error)}",
                ErrorType.UNKNOWN_ERROR,
                segment=segment,
                original_error=error,
            )

    def should_retry(self, error: DownloadError, segment: SegmentInfo) -> bool:
        """Determine if an error should trigger a retry.

        Args:
            error: The download error
            segment: The segment that failed

        Returns:
            True if retry should be attempted, False otherwise
        """
        # Check if we've exceeded max retries for this segment
        retry_count = self.retry_counts.get(segment.url, 0)
        if retry_count >= self.max_retries:
            return False

        # Determine retry strategy based on error type
        if error.error_type == ErrorType.NETWORK_ERROR:
            return True
        elif error.error_type == ErrorType.TIMEOUT_ERROR:
            return True
        elif error.error_type == ErrorType.HTTP_ERROR:
            # Retry on server errors (5xx) and some client errors
            if isinstance(error, HTTPError):
                return error.status_code in [429, 500, 502, 503, 504]
            return False
        elif error.error_type == ErrorType.FILE_SYSTEM_ERROR:
            # Don't retry permission errors, but retry disk space issues
            if "Permission denied" in str(error):
                return False
            return True
        elif error.error_type == ErrorType.INTEGRITY_ERROR:
            return True  # Retry integrity failures
        else:
            return False  # Don't retry unknown errors

    def get_retry_delay(
        self, attempt: int, strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    ) -> float:
        """Calculate delay before next retry attempt.

        Args:
            attempt: Current attempt number (0-based)
            strategy: Retry strategy to use

        Returns:
            Delay in seconds before next retry
        """
        if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            # Exponential backoff with jitter
            delay = self.base_delay * (2**attempt)
            jitter = random.uniform(0.1, 0.3) * delay
            return delay + jitter

        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            # Linear increase with jitter
            delay = self.base_delay * (attempt + 1)
            jitter = random.uniform(0.1, 0.3) * delay
            return delay + jitter

        elif strategy == RetryStrategy.FIXED_DELAY:
            # Fixed delay with small jitter
            jitter = random.uniform(0.1, 0.3) * self.base_delay
            return self.base_delay + jitter

        else:  # NO_RETRY
            return 0.0

    def log_error(
        self, error: DownloadError, context: Optional[dict[str, Any]] = None
    ) -> None:
        """Log detailed error information.

        Args:
            error: The download error to log
            context: Additional context information
        """
        # Update error counts
        self.error_counts[error.error_type] = (
            self.error_counts.get(error.error_type, 0) + 1
        )

        # Prepare log context
        log_context = {
            "error_type": error.error_type.value,
            "error_timestamp": error.timestamp,
            "error_message": str(error),
        }

        if error.segment:
            log_context.update(
                {
                    "segment_url": error.segment.url,
                    "segment_index": error.segment.index,
                    "segment_filename": error.segment.filename,
                }
            )

        if isinstance(error, HTTPError):
            log_context["status_code"] = error.status_code

        if context:
            log_context.update(context)

        # Create bound logger with context
        bound_logger = logger.bind(**log_context)

        # Log with appropriate level based on error type
        if error.error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR]:
            bound_logger.warning(f"Recoverable error: {error}")
        elif error.error_type == ErrorType.HTTP_ERROR:
            if isinstance(error, HTTPError) and error.status_code >= 500:
                bound_logger.warning(f"Server error: {error}")
            else:
                bound_logger.error(f"Client error: {error}")
        else:
            bound_logger.error(f"Download error: {error}")

    def log_retry_attempt(
        self, segment: SegmentInfo, attempt: int, delay: float, error: DownloadError
    ) -> None:
        """Log retry attempt information.

        Args:
            segment: The segment being retried
            attempt: Current attempt number (1-based)
            delay: Delay before this retry
            error: The error that triggered the retry
        """
        logger.bind(
            segment_url=segment.url,
            segment_index=segment.index,
            attempt=attempt,
            max_retries=self.max_retries,
            delay=delay,
            error_type=error.error_type.value,
        ).info(
            f"Retrying segment {segment.index} (attempt {attempt}/{self.max_retries}) "
            f"after {delay:.2f}s delay due to {error.error_type.value}: {error}"
        )

    def increment_retry_count(self, segment: SegmentInfo) -> int:
        """Increment and return retry count for a segment.

        Args:
            segment: The segment being retried

        Returns:
            New retry count for the segment
        """
        current_count = self.retry_counts.get(segment.url, 0)
        new_count = current_count + 1
        self.retry_counts[segment.url] = new_count
        return new_count

    def reset_retry_count(self, segment: SegmentInfo) -> None:
        """Reset retry count for a segment (called on success).

        Args:
            segment: The segment that succeeded
        """
        if segment.url in self.retry_counts:
            del self.retry_counts[segment.url]

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of all errors encountered.

        Returns:
            Dictionary with error statistics
        """
        total_errors = sum(self.error_counts.values())
        active_retries = len(self.retry_counts)

        return {
            "total_errors": total_errors,
            "error_breakdown": dict(self.error_counts),
            "active_retries": active_retries,
            "segments_with_retries": list(self.retry_counts.keys()),
        }

    async def handle_with_retry(
        self, operation, segment: SegmentInfo, *args, **kwargs
    ) -> Any:
        """Execute an operation with automatic retry handling.

        Args:
            operation: Async function to execute
            segment: Segment being processed
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation

        Returns:
            Result of successful operation

        Raises:
            DownloadError: If all retry attempts fail
        """
        last_error = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                result = await operation(*args, **kwargs)

                # Success - reset retry count and return result
                if attempt > 0:  # Only log if this was a retry
                    logger.bind(
                        segment_url=segment.url,
                        segment_index=segment.index,
                        attempts=attempt + 1,
                    ).info(f"Segment {segment.index} succeeded after {attempt} retries")
                    self.reset_retry_count(segment)

                return result

            except Exception as e:
                # Classify the error
                download_error = self.classify_error(e, segment)
                last_error = download_error

                # Log the error
                self.log_error(download_error, {"attempt": attempt + 1})

                # Check if we should retry
                if attempt < self.max_retries and self.should_retry(
                    download_error, segment
                ):
                    # Increment retry count
                    retry_count = self.increment_retry_count(segment)

                    # Calculate delay
                    delay = self.get_retry_delay(attempt)

                    # Log retry attempt
                    self.log_retry_attempt(segment, retry_count, delay, download_error)

                    # Wait before retry
                    await asyncio.sleep(delay)

                else:
                    # No more retries or error is not retryable
                    logger.bind(
                        segment_url=segment.url,
                        segment_index=segment.index,
                        total_attempts=attempt + 1,
                        final_error=str(download_error),
                    ).error(
                        f"Segment {segment.index} failed permanently after {attempt + 1} attempts"
                    )
                    break

        # All retries exhausted
        raise last_error or DownloadError(
            "Unknown error during retry handling", ErrorType.UNKNOWN_ERROR, segment
        )
