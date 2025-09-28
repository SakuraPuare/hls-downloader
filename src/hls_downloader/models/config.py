"""Configuration data model."""

from dataclasses import dataclass


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
