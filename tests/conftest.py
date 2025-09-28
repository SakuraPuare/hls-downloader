"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest

from hls_downloader.models import DownloadConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def default_config():
    """Provide default download configuration for tests."""
    return DownloadConfig()


@pytest.fixture
def test_config():
    """Provide test-specific download configuration."""
    return DownloadConfig(
        max_concurrent=2,
        max_retries=1,
        timeout=5,
        auto_merge=False,
        cleanup_segments=False,
    )
