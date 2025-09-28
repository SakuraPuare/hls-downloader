"""Network utility functions."""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


def is_url_accessible(url: str) -> bool:
    """Check if a URL is accessible (basic validation).
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be valid
    """
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ('http', 'https') and parsed.netloc)
    except Exception:
        return False


def parse_url_pattern(url_template: str) -> Optional[Tuple[str, str, str]]:
    """Parse URL template to extract base, number pattern, and extension.
    
    Args:
        url_template: URL template with number placeholder
        
    Returns:
        Tuple of (base_url, number_pattern, extension) or None if parsing fails
        
    Examples:
        "https://example.com/video{}.ts" -> ("https://example.com/video", "{}", ".ts")
        "https://example.com/seg001.m4s" -> ("https://example.com/seg", "001", ".m4s")
    """
    # Pattern for URLs with {} placeholder
    placeholder_pattern = r'^(.*?)(\{\d*\})(.*?)$'
    match = re.match(placeholder_pattern, url_template)
    if match:
        return match.group(1), match.group(2), match.group(3)
    
    # Pattern for URLs with numeric sequence
    numeric_pattern = r'^(.*?)(\d+)(\.[\w]+)$'
    match = re.match(numeric_pattern, url_template)
    if match:
        base_url = match.group(1)
        number_part = match.group(2)
        extension = match.group(3)
        return base_url, number_part, extension
    
    return None
