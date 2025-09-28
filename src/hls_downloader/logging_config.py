"""Structured logging configuration for HLS downloader using loguru."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger


class LoggingConfig:
    """Centralized logging configuration using loguru."""
    
    def __init__(
        self,
        level: str = "INFO",
        debug_mode: bool = False,
        log_file: Optional[Path] = None,
        structured_logging: bool = False,
        max_file_size: str = "10 MB",
        backup_count: int = 5
    ):
        """Initialize logging configuration.
        
        Args:
            level: Logging level (TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL)
            debug_mode: Enable debug mode with verbose output
            log_file: Path to log file (None for no file logging)
            structured_logging: Use structured JSON logging
            max_file_size: Maximum log file size before rotation (e.g., "10 MB")
            backup_count: Number of backup log files to keep
        """
        self.level = level
        self.debug_mode = debug_mode
        self.log_file = log_file
        self.structured_logging = structured_logging
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Adjust level for debug mode
        if debug_mode:
            self.level = "DEBUG"
    
    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        # Remove default handler
        logger.remove()
        
        # Setup console handler
        self._setup_console_handler()
        
        # Setup file handler if specified
        if self.log_file:
            self._setup_file_handler()
        
        # Configure third-party loggers
        self._configure_third_party_loggers()
    
    def _setup_console_handler(self) -> None:
        """Setup console logging handler."""
        if self.structured_logging:
            # Structured JSON format for console
            format_string = (
                "{"
                '"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
                '"level": "{level}", '
                '"logger": "{name}", '
                '"message": "{message}", '
                '"module": "{module}", '
                '"function": "{function}", '
                '"line": {line}'
                "{extra}"
                "}"
            )
        else:
            if self.debug_mode:
                # Verbose format with timestamp and level
                format_string = (
                    "<green>{time:HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                    "{extra}"
                )
            else:
                # Simple format for normal use
                format_string = "<level>{message}</level>{extra}"
        
        logger.add(
            sys.stdout,
            format=format_string,
            level=self.level,
            colorize=not self.structured_logging,
            serialize=self.structured_logging
        )
    
    def _setup_file_handler(self) -> None:
        """Setup file logging handler with rotation."""
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Always use structured JSON format for files
        format_string = (
            "{"
            '"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"logger": "{name}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"process": {process.id}, '
            '"thread": {thread.id}'
            "{extra}"
            "}"
        )
        
        logger.add(
            self.log_file,
            format=format_string,
            level="DEBUG",  # Log everything to file
            rotation=self.max_file_size,
            retention=self.backup_count,
            compression="gz",
            serialize=True,
            encoding="utf-8"
        )
    
    def _configure_third_party_loggers(self) -> None:
        """Configure third-party library loggers."""
        import logging
        
        # Reduce httpx logging noise unless in debug mode
        httpx_level = logging.DEBUG if self.debug_mode else logging.WARNING
        logging.getLogger("httpx").setLevel(httpx_level)
        
        # Reduce asyncio logging noise
        asyncio_level = logging.DEBUG if self.debug_mode else logging.WARNING
        logging.getLogger("asyncio").setLevel(asyncio_level)
        
        # Intercept standard logging and redirect to loguru
        class InterceptHandler(logging.Handler):
            def emit(self, record):
                # Get corresponding Loguru level if it exists
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                # Find caller from where originated the logged message
                frame, depth = logging.currentframe(), 2
                while frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

                logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
        
        # Replace standard logging with loguru
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    @classmethod
    def from_cli_args(
        cls,
        verbose: bool = False,
        debug: bool = False,
        log_file: Optional[str] = None,
        structured: bool = False
    ) -> 'LoggingConfig':
        """Create logging config from CLI arguments.
        
        Args:
            verbose: Enable verbose output
            debug: Enable debug mode
            log_file: Path to log file
            structured: Use structured logging
            
        Returns:
            Configured LoggingConfig instance
        """
        # Determine log level
        if debug:
            level = "DEBUG"
        elif verbose:
            level = "INFO"
        else:
            level = "WARNING"
        
        # Convert log file path
        log_path = Path(log_file) if log_file else None
        
        return cls(
            level=level,
            debug_mode=debug,
            log_file=log_path,
            structured_logging=structured
        )


def get_logger(name: str):
    """Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Loguru logger instance bound with name
    """
    return logger.bind(name=name)


def log_download_start(
    url: str,
    output_dir: str,
    config: Dict[str, Any]
) -> None:
    """Log download start with context.
    
    Args:
        url: Download URL
        output_dir: Output directory
        config: Download configuration
    """
    logger.bind(
        event="download_start",
        url=url,
        output_dir=output_dir,
        max_concurrent=config.get("max_concurrent"),
        max_retries=config.get("max_retries"),
        timeout=config.get("timeout"),
    ).info("Starting HLS download")


def log_download_complete(
    total_segments: int,
    successful_segments: int,
    failed_segments: int,
    duration: float,
    output_file: Optional[str] = None
) -> None:
    """Log download completion with statistics.
    
    Args:
        total_segments: Total number of segments
        successful_segments: Number of successful downloads
        failed_segments: Number of failed downloads
        duration: Total download duration in seconds
        output_file: Path to merged output file
    """
    success_rate = successful_segments / total_segments if total_segments > 0 else 0
    
    logger.bind(
        event="download_complete",
        total_segments=total_segments,
        successful_segments=successful_segments,
        failed_segments=failed_segments,
        duration_seconds=duration,
        success_rate=success_rate,
        output_file=output_file,
    ).info("Download completed")


def log_segment_progress(
    completed: int,
    total: int,
    current_speed: float,
    eta_seconds: Optional[float] = None
) -> None:
    """Log download progress.
    
    Args:
        completed: Number of completed segments
        total: Total number of segments
        current_speed: Current download speed (segments/second)
        eta_seconds: Estimated time to completion
    """
    completion_percentage = (completed / total * 100) if total > 0 else 0
    
    logger.bind(
        event="progress_update",
        completed_segments=completed,
        total_segments=total,
        completion_percentage=completion_percentage,
        current_speed_segments_per_sec=current_speed,
        eta_seconds=eta_seconds,
    ).debug("Download progress update")


def log_error_summary(
    error_summary: Dict[str, Any]
) -> None:
    """Log error summary at end of download.
    
    Args:
        error_summary: Error summary from ErrorHandler
    """
    if error_summary["total_errors"] > 0:
        logger.bind(
            event="error_summary",
            **error_summary
        ).warning("Download completed with errors")
    else:
        logger.bind(
            event="error_summary",
            **error_summary
        ).info("Download completed without errors")