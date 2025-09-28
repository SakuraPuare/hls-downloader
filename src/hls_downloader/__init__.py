"""HLS Downloader - A modern HLS stream segment downloader."""

__version__ = "0.1.0"
__author__ = "HLS Downloader Team"
__email__ = "team@hlsdownloader.dev"

# 延迟导入，避免在包级别导入时触发外部依赖
def __getattr__(name):
    """延迟导入模块属性。"""
    if name == "DownloadManager":
        from .core.manager import DownloadManager
        return DownloadManager
    elif name == "HLSDetector":
        from .core.detector import HLSDetector
        return HLSDetector
    elif name == "AsyncDownloader":
        from .core.downloader import AsyncDownloader
        return AsyncDownloader
    elif name == "VideoMerger":
        from .core.merger import VideoMerger
        return VideoMerger
    elif name == "ProgressDisplay":
        from .core.progress import ProgressDisplay
        return ProgressDisplay
    elif name == "StateManager":
        from .core.state_manager import StateManager
        return StateManager
    elif name == "DownloadConfig":
        from .models.config import DownloadConfig
        return DownloadConfig
    elif name == "SegmentInfo":
        from .models.segment import SegmentInfo
        return SegmentInfo
    elif name == "DownloadStats":
        from .models.stats import DownloadStats
        return DownloadStats
    elif name == "DownloadState":
        from .models.state import DownloadState
        return DownloadState
    elif name in ("FFmpegNotFoundError", "MergeError", "VideoMergerError"):
        from .exceptions.merger import FFmpegNotFoundError, MergeError, VideoMergerError
        return locals()[name]
    elif name in ("DownloadError", "ConfigurationError"):
        if name == "DownloadError":
            from .exceptions.download import DownloadError
            return DownloadError
        else:
            from .exceptions.manager import ConfigurationError
            return ConfigurationError
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# 导入基础模型，这些不依赖外部库
from .models import DownloadConfig, DownloadStats, SegmentInfo, DownloadState

__all__ = [
    "DownloadManager",
    "HLSDetector",
    "AsyncDownloader",
    "VideoMerger",
    "ProgressDisplay",
    "StateManager",
    "VideoMergerError",
    "FFmpegNotFoundError",
    "MergeError",
    "DownloadError",
    "ConfigurationError",
    "DownloadConfig",
    "SegmentInfo",
    "DownloadStats",
    "DownloadState",
]
