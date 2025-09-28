"""Tests for download manager."""

import pytest

from hls_downloader.download_manager import DownloadManager
from hls_downloader.models import DownloadConfig


class TestDownloadManager:
    """Test DownloadManager class."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        manager = DownloadManager()

        assert manager.config is not None
        assert isinstance(manager.config, DownloadConfig)
        assert manager.config.max_concurrent == 10

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = DownloadConfig(max_concurrent=5, max_retries=2)
        manager = DownloadManager(config)

        assert manager.config == config
        assert manager.config.max_concurrent == 5
        assert manager.config.max_retries == 2

    @pytest.mark.asyncio
    async def test_download_hls_placeholder(self):
        """Test download_hls method placeholder."""
        manager = DownloadManager()

        # This should not raise an exception (placeholder implementation)
        await manager.download_hls("https://example.com/segment{}.ts", "./test_output")

    @pytest.mark.asyncio
    async def test_setup_output_directory_placeholder(self):
        """Test _setup_output_directory method placeholder."""
        manager = DownloadManager()

        # This should not raise an exception (placeholder implementation)
        await manager._setup_output_directory("./test_output")

    def test_validate_config_placeholder(self):
        """Test _validate_config method placeholder."""
        manager = DownloadManager()
        config = DownloadConfig()

        # This should not raise an exception (placeholder implementation)
        manager._validate_config(config)
