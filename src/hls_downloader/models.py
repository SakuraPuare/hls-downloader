"""Data models for HLS downloader."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DownloadConfig:
    """Configuration for HLS download process."""

    max_concurrent: int = 10  # 最大并发数
    max_retries: int = 3  # 最大重试次数
    timeout: int = 30  # 请求超时时间
    chunk_size: int = 8192  # 下载块大小
    auto_merge: bool = True  # 自动合并
    cleanup_segments: bool = False  # 清理切片文件
    output_format: str = "mp4"  # 输出格式

    def __post_init__(self):
        """Validate configuration values after initialization."""
        if self.max_concurrent <= 0:
            raise ValueError("max_concurrent must be greater than 0")
        if self.max_concurrent > 100:
            raise ValueError("max_concurrent must not exceed 100")

        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.max_retries > 10:
            raise ValueError("max_retries must not exceed 10")

        if self.timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        if self.timeout > 300:
            raise ValueError("timeout must not exceed 300 seconds")

        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_size > 1024 * 1024:  # 1MB max
            raise ValueError("chunk_size must not exceed 1MB")

        valid_formats = {"mp4", "mkv", "avi", "mov", "ts"}
        if self.output_format not in valid_formats:
            raise ValueError(f"output_format must be one of {valid_formats}")

    def validate(self) -> bool:
        """Validate the configuration and return True if valid."""
        try:
            self.__post_init__()
            return True
        except ValueError:
            return False


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


@dataclass
class DownloadStats:
    """Statistics for download process."""

    total_segments: int  # 总切片数
    downloaded_segments: int = 0  # 已下载数
    failed_segments: int = 0  # 失败数
    total_bytes: int = 0  # 总字节数
    downloaded_bytes: int = 0  # 已下载字节数
    start_time: float = field(default_factory=lambda: 0.0)  # 开始时间
    average_speed: float = 0.0  # 平均速度

    def __post_init__(self):
        """Validate download statistics after initialization."""
        if self.total_segments < 0:
            raise ValueError("total_segments must be non-negative")

        if self.downloaded_segments < 0:
            raise ValueError("downloaded_segments must be non-negative")
        if self.downloaded_segments > self.total_segments:
            raise ValueError("downloaded_segments cannot exceed total_segments")

        if self.failed_segments < 0:
            raise ValueError("failed_segments must be non-negative")
        if self.failed_segments > self.total_segments:
            raise ValueError("failed_segments cannot exceed total_segments")

        if self.total_bytes < 0:
            raise ValueError("total_bytes must be non-negative")

        if self.downloaded_bytes < 0:
            raise ValueError("downloaded_bytes must be non-negative")
        if self.downloaded_bytes > self.total_bytes:
            raise ValueError("downloaded_bytes cannot exceed total_bytes")

        if self.start_time < 0:
            raise ValueError("start_time must be non-negative")

        if self.average_speed < 0:
            raise ValueError("average_speed must be non-negative")

    @property
    def progress_percentage(self) -> float:
        """Calculate download progress as percentage."""
        if self.total_segments == 0:
            return 0.0
        return (self.downloaded_segments / self.total_segments) * 100

    @property
    def remaining_segments(self) -> int:
        """Calculate remaining segments to download."""
        return self.total_segments - self.downloaded_segments - self.failed_segments

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        completed = self.downloaded_segments + self.failed_segments
        if completed == 0:
            return 0.0
        return (self.downloaded_segments / completed) * 100

    def update_speed(self, elapsed_time: float) -> None:
        """Update average download speed based on elapsed time."""
        if elapsed_time > 0:
            self.average_speed = self.downloaded_bytes / elapsed_time
