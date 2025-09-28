"""Segment information data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SegmentInfo:
    """Information about a single HLS segment."""

    url: str  # 切片URL
    index: int  # 切片索引
    filename: str  # 本地文件名
    size: Optional[int] = None  # 文件大小
    downloaded: bool = False  # 下载状态

    def __post_init__(self):
        """Validate segment information after initialization."""
        if not self.url:
            raise ValueError("url cannot be empty")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("url must be a valid HTTP/HTTPS URL")

        if self.index < 0:
            raise ValueError("index must be non-negative")

        if not self.filename:
            raise ValueError("filename cannot be empty")

        if self.size is not None and self.size < 0:
            raise ValueError("size must be non-negative")

    @property
    def is_valid(self) -> bool:
        """Check if the segment info is valid."""
        try:
            self.__post_init__()
            return True
        except ValueError:
            return False
