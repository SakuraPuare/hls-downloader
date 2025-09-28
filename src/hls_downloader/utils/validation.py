"""Validation utility functions."""

from ..exceptions.validation import ValidationError
from ..models.config import DownloadConfig
from ..models.segment import SegmentInfo


def validate_url(url: str) -> bool:
    """Validate if URL is properly formatted.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")
    
    if not url.startswith(('http://', 'https://')):
        raise ValidationError("URL must start with http:// or https://")
    
    return True


def validate_config(config: DownloadConfig) -> bool:
    """Validate download configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    try:
        config.__post_init__()
        return True
    except ValueError as e:
        raise ValidationError(f"Invalid configuration: {e}")


def validate_segment_info(segment: SegmentInfo) -> bool:
    """Validate segment information.
    
    Args:
        segment: Segment info to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If segment info is invalid
    """
    try:
        segment.__post_init__()
        return True
    except ValueError as e:
        raise ValidationError(f"Invalid segment info: {e}")
