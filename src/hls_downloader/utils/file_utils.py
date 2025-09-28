"""File system utility functions."""

import os
from pathlib import Path
from typing import Optional


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, create if it doesn't.
    
    Args:
        path: Directory path to ensure
        
    Returns:
        Path object of the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_size(file_path: str | Path) -> Optional[int]:
    """Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes, or None if file doesn't exist
    """
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError):
        return None


def is_file_complete(file_path: str | Path, expected_size: Optional[int] = None) -> bool:
    """Check if a file exists and is complete.
    
    Args:
        file_path: Path to the file
        expected_size: Expected file size in bytes (optional)
        
    Returns:
        True if file exists and is complete
    """
    path = Path(file_path)
    if not path.exists():
        return False
    
    if expected_size is not None:
        actual_size = get_file_size(path)
        return actual_size == expected_size
    
    return True
