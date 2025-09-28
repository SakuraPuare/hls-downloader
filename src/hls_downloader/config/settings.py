"""Default configuration settings."""

import json
from pathlib import Path
from typing import Optional

from ..models.config import DownloadConfig


DEFAULT_CONFIG = DownloadConfig(
    max_concurrent=10,
    max_retries=3,
    timeout=30,
    chunk_size=8192,
    auto_merge=True,
    cleanup_segments=False,
    output_format="mp4"
)


def get_default_config() -> DownloadConfig:
    """Get a copy of the default configuration.
    
    Returns:
        Default download configuration
    """
    return DownloadConfig(
        max_concurrent=DEFAULT_CONFIG.max_concurrent,
        max_retries=DEFAULT_CONFIG.max_retries,
        timeout=DEFAULT_CONFIG.timeout,
        chunk_size=DEFAULT_CONFIG.chunk_size,
        auto_merge=DEFAULT_CONFIG.auto_merge,
        cleanup_segments=DEFAULT_CONFIG.cleanup_segments,
        output_format=DEFAULT_CONFIG.output_format
    )


def load_config_from_file(config_path: str | Path) -> Optional[DownloadConfig]:
    """Load configuration from a JSON file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Loaded configuration or None if file doesn't exist
    """
    path = Path(config_path)
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create config with defaults, then update with loaded values
        config = get_default_config()
        
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    except (json.JSONDecodeError, OSError):
        return None
