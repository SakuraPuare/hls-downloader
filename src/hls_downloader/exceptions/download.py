"""Download-related exceptions."""

import time
from typing import Optional

from ..models.segment import SegmentInfo
from .base import HLSDownloaderError


class DownloadError(HLSDownloaderError):
    """Base exception for download-related errors."""

    def __init__(
        self,
        message: str,
        segment: Optional[SegmentInfo] = None,
        original_error: Optional[Exception] = None,
        error_code: str = None,
    ):
        super().__init__(message, error_code)
        self.segment = segment
        self.original_error = original_error
        self.timestamp = time.time()


class NetworkError(DownloadError):
    """Raised when network-related errors occur."""
    pass


class TimeoutError(DownloadError):
    """Raised when download timeout occurs."""
    pass


class IntegrityError(DownloadError):
    """Raised when file integrity check fails."""
    pass
