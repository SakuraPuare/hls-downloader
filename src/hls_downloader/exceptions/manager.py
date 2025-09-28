"""Download manager exceptions."""

from .base import HLSDownloaderError


class DownloadManagerError(HLSDownloaderError):
    """Base exception for download manager errors."""
    pass


class ConfigurationError(DownloadManagerError):
    """Raised when configuration is invalid."""
    pass
