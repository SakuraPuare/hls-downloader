"""Utility functions for HLS downloader."""

# from .error_handler import ErrorHandler  # 延迟导入，避免httpx依赖
from .file_utils import ensure_directory, get_file_size, is_file_complete
from .logging_config import configure_logging
from .network_utils import is_url_accessible, parse_url_pattern
# from .resume_validator import ResumeValidator  # 延迟导入，避免httpx依赖
# from .user_messages import UserMessageDisplay  # 延迟导入，避免其他依赖
from .validation import validate_config, validate_segment_info, validate_url

__all__ = [
    # "ErrorHandler",  # 需要时单独导入
    "ensure_directory",
    "get_file_size", 
    "is_file_complete",
    "configure_logging",
    "is_url_accessible",
    "parse_url_pattern",
    # "ResumeValidator",  # 需要时单独导入
    # "UserMessageDisplay",  # 需要时单独导入
    "validate_config",
    "validate_segment_info",
    "validate_url",
]
