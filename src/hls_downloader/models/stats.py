"""Download statistics data model."""

from dataclasses import dataclass, field


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
