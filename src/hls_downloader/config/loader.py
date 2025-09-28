"""Configuration loader with multiple sources support."""

import os
from pathlib import Path
from typing import Optional

from ..models.config import DownloadConfig
from .settings import get_default_config, load_config_from_file


class ConfigLoader:
    """Loads configuration from multiple sources with priority order."""
    
    CONFIG_FILENAME = "hls_downloader.json"
    
    def __init__(self):
        """Initialize the configuration loader."""
        self._config_search_paths = [
            Path.cwd() / self.CONFIG_FILENAME,  # Current directory
            Path.home() / ".config" / "hls_downloader" / self.CONFIG_FILENAME,  # User config
            Path("/etc/hls_downloader") / self.CONFIG_FILENAME,  # System config
        ]
    
    def load(self, config_path: Optional[str | Path] = None) -> DownloadConfig:
        """Load configuration with priority order.
        
        Priority order:
        1. Explicitly provided config_path
        2. Current directory config file
        3. User config directory
        4. System config directory
        5. Default configuration
        
        Args:
            config_path: Explicit path to config file (highest priority)
            
        Returns:
            Loaded configuration
        """
        # Try explicit path first
        if config_path:
            config = load_config_from_file(config_path)
            if config:
                return config
        
        # Try standard search paths
        for path in self._config_search_paths:
            config = load_config_from_file(path)
            if config:
                return config
        
        # Fall back to default
        return get_default_config()
    
    def save(self, config: DownloadConfig, config_path: Optional[str | Path] = None) -> bool:
        """Save configuration to file.
        
        Args:
            config: Configuration to save
            config_path: Path to save to (defaults to user config directory)
            
        Returns:
            True if saved successfully
        """
        if config_path:
            save_path = Path(config_path)
        else:
            # Default to user config directory
            save_path = Path.home() / ".config" / "hls_downloader" / self.CONFIG_FILENAME
        
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert config to dict and save as JSON
            import json
            from dataclasses import asdict
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, indent=2, ensure_ascii=False)
            
            return True
        except (OSError, json.JSONEncodeError):
            return False
