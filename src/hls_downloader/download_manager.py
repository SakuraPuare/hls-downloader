"""Download manager for coordinating HLS download process."""

from typing import Optional

from .models import DownloadConfig


class DownloadManager:
    """Coordinates the entire HLS download process."""

    def __init__(self, config: Optional[DownloadConfig] = None):
        """Initialize download manager with configuration."""
        self.config = config or DownloadConfig()

    async def download_hls(self, url: str, output_dir: str) -> None:
        """Download HLS stream to specified directory."""
        # Implementation will be added in later tasks
        pass

    async def _setup_output_directory(self, output_dir: str) -> None:
        """Setup output directory for downloads."""
        # Implementation will be added in later tasks
        pass

    def _validate_config(self, config: DownloadConfig) -> None:
        """Validate download configuration."""
        # Implementation will be added in later tasks
        pass
