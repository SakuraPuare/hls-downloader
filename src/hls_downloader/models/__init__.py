"""Data models for HLS downloader."""

from .config import DownloadConfig
from .segment import SegmentInfo
from .stats import DownloadStats
from .state import DownloadState

__all__ = [
    "DownloadConfig",
    "SegmentInfo", 
    "DownloadStats",
    "DownloadState",
]
