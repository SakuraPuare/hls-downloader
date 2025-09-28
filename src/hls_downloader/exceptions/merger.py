"""Video merger exceptions."""

from .base import HLSDownloaderError


class VideoMergerError(HLSDownloaderError):
    """Base exception for video merger errors."""
    pass


class FFmpegNotFoundError(VideoMergerError):
    """Raised when ffmpeg is not available."""
    pass


class MergeError(VideoMergerError):
    """Raised when video merge operation fails."""
    pass
