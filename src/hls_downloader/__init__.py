"""HLS Downloader - A modern HLS stream segment downloader."""

__version__ = "0.1.0"
__author__ = "HLS Downloader Team"
__email__ = "team@hlsdownloader.dev"

from .download_manager import DownloadManager
from .detector import HLSDetector
from .models import DownloadConfig, DownloadStats, SegmentInfo
from .progress_display import ProgressDisplay, MultiThreadProgressWrapper

__all__ = [
    "DownloadManager",
    "HLSDetector",
    "DownloadConfig",
    "SegmentInfo",
    "DownloadStats",
    "ProgressDisplay",
    "MultiThreadProgressWrapper",
]
