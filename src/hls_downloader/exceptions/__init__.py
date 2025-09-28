"""Exception classes for HLS downloader."""

from .base import HLSDownloaderError
from .download import DownloadError, IntegrityError, NetworkError, TimeoutError
from .manager import ConfigurationError, DownloadManagerError
from .merger import FFmpegNotFoundError, MergeError, VideoMergerError
from .validation import ValidationError

__all__ = [
    "HLSDownloaderError",
    "DownloadError",
    "IntegrityError", 
    "NetworkError",
    "TimeoutError",
    "DownloadManagerError",
    "ConfigurationError",
    "VideoMergerError",
    "FFmpegNotFoundError",
    "MergeError",
    "ValidationError",
]
