"""HLS Downloader - A modern HLS stream segment downloader."""

__version__ = "0.1.0"
__author__ = "HLS Downloader Team"
__email__ = "team@hlsdownloader.dev"

from .detector import HLSDetector
from .download_manager import DownloadManager
from .merger import FFmpegNotFoundError, MergeError, VideoMerger, VideoMergerError
from .models import DownloadConfig, DownloadStats, SegmentInfo
from .progress_display import MultiThreadProgressWrapper, ProgressDisplay

__all__ = [
    "DownloadManager",
    "HLSDetector",
    "VideoMerger",
    "VideoMergerError",
    "FFmpegNotFoundError",
    "MergeError",
    "DownloadConfig",
    "SegmentInfo",
    "DownloadStats",
    "ProgressDisplay",
    "MultiThreadProgressWrapper",
]
