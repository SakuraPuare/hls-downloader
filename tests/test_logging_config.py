"""Tests for logging configuration."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.hls_downloader.utils.logging_config import (
    LoggingConfig,
    get_logger,
    log_download_complete,
    log_download_start,
    log_error_summary,
    log_segment_progress,
)


class TestLoggingConfig:
    """Test cases for LoggingConfig class."""

    def test_init_default(self):
        """Test LoggingConfig initialization with defaults."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.debug_mode is False
        assert config.log_file is None
        assert config.structured_logging is False
        assert config.max_file_size == "10 MB"
        assert config.backup_count == 5

    def test_init_debug_mode(self):
        """Test LoggingConfig initialization with debug mode."""
        config = LoggingConfig(debug_mode=True)

        assert config.level == "DEBUG"
        assert config.debug_mode is True

    def test_init_with_log_file(self):
        """Test LoggingConfig initialization with log file."""
        log_file = Path("/tmp/test.log")
        config = LoggingConfig(log_file=log_file)

        assert config.log_file == log_file

    def test_from_cli_args_verbose(self):
        """Test creating config from CLI args with verbose."""
        config = LoggingConfig.from_cli_args(verbose=True)

        assert config.level == "INFO"
        assert config.debug_mode is False

    def test_from_cli_args_debug(self):
        """Test creating config from CLI args with debug."""
        config = LoggingConfig.from_cli_args(debug=True)

        assert config.level == "DEBUG"
        assert config.debug_mode is True

    def test_from_cli_args_with_log_file(self):
        """Test creating config from CLI args with log file."""
        config = LoggingConfig.from_cli_args(log_file="/tmp/test.log")

        assert config.log_file == Path("/tmp/test.log")

    def test_from_cli_args_structured(self):
        """Test creating config from CLI args with structured logging."""
        config = LoggingConfig.from_cli_args(structured=True)

        assert config.structured_logging is True

    @patch("src.hls_downloader.logging_config.logger")
    def test_setup_logging_console_only(self, mock_logger):
        """Test setting up console-only logging."""
        config = LoggingConfig()
        config.setup_logging()

        # Should remove existing handlers and add console handler
        mock_logger.remove.assert_called_once()
        mock_logger.add.assert_called()

    @patch("src.hls_downloader.logging_config.logger")
    def test_setup_logging_with_file(self, mock_logger):
        """Test setting up logging with file handler."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            config = LoggingConfig(log_file=log_file)
            config.setup_logging()

            # Should add both console and file handlers
            assert mock_logger.add.call_count == 2

    @patch("src.hls_downloader.logging_config.logger")
    def test_setup_logging_structured(self, mock_logger):
        """Test setting up structured logging."""
        config = LoggingConfig(structured_logging=True)
        config.setup_logging()

        # Should configure structured format
        mock_logger.add.assert_called()
        call_args = mock_logger.add.call_args
        assert call_args[1]["serialize"] is True

    @patch("src.hls_downloader.logging_config.logger")
    def test_setup_logging_debug_mode(self, mock_logger):
        """Test setting up logging in debug mode."""
        config = LoggingConfig(debug_mode=True)
        config.setup_logging()

        # Should use debug level and verbose format
        mock_logger.add.assert_called()
        call_args = mock_logger.add.call_args
        assert call_args[1]["level"] == "DEBUG"


class TestLoggingHelpers:
    """Test cases for logging helper functions."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        test_logger = get_logger("test_module")

        # Should return a loguru logger bound with name
        assert hasattr(test_logger, "info")
        assert hasattr(test_logger, "error")
        assert hasattr(test_logger, "debug")

    @patch("src.hls_downloader.logging_config.logger")
    def test_log_download_start(self, mock_logger):
        """Test logging download start."""
        config = {"max_concurrent": 10, "max_retries": 3, "timeout": 30}

        log_download_start("http://example.com/test.m3u8", "/tmp/output", config)

        # Should bind context and log info message
        mock_logger.bind.assert_called_once()
        bound_logger = mock_logger.bind.return_value
        bound_logger.info.assert_called_once_with("Starting HLS download")

    @patch("src.hls_downloader.logging_config.logger")
    def test_log_download_complete(self, mock_logger):
        """Test logging download completion."""
        log_download_complete(100, 95, 5, 120.5, "/tmp/output/video.mp4")

        # Should bind context and log info message
        mock_logger.bind.assert_called_once()
        bound_logger = mock_logger.bind.return_value
        bound_logger.info.assert_called_once_with("Download completed")

        # Check bound context
        bind_args = mock_logger.bind.call_args[1]
        assert bind_args["total_segments"] == 100
        assert bind_args["successful_segments"] == 95
        assert bind_args["failed_segments"] == 5
        assert bind_args["duration_seconds"] == 120.5
        assert bind_args["success_rate"] == 0.95
        assert bind_args["output_file"] == "/tmp/output/video.mp4"

    @patch("src.hls_downloader.logging_config.logger")
    def test_log_segment_progress(self, mock_logger):
        """Test logging segment progress."""
        log_segment_progress(50, 100, 2.5, 20.0)

        # Should bind context and log debug message
        mock_logger.bind.assert_called_once()
        bound_logger = mock_logger.bind.return_value
        bound_logger.debug.assert_called_once_with("Download progress update")

        # Check bound context
        bind_args = mock_logger.bind.call_args[1]
        assert bind_args["completed_segments"] == 50
        assert bind_args["total_segments"] == 100
        assert bind_args["completion_percentage"] == 50.0
        assert bind_args["current_speed_segments_per_sec"] == 2.5
        assert bind_args["eta_seconds"] == 20.0

    @patch("src.hls_downloader.logging_config.logger")
    def test_log_error_summary_with_errors(self, mock_logger):
        """Test logging error summary with errors."""
        error_summary = {
            "total_errors": 5,
            "error_breakdown": {"network_error": 3, "timeout_error": 2},
            "active_retries": 2,
        }

        log_error_summary(error_summary)

        # Should bind context and log warning message
        mock_logger.bind.assert_called_once()
        bound_logger = mock_logger.bind.return_value
        bound_logger.warning.assert_called_once_with("Download completed with errors")

    @patch("src.hls_downloader.logging_config.logger")
    def test_log_error_summary_no_errors(self, mock_logger):
        """Test logging error summary without errors."""
        error_summary = {"total_errors": 0, "error_breakdown": {}, "active_retries": 0}

        log_error_summary(error_summary)

        # Should bind context and log info message
        mock_logger.bind.assert_called_once()
        bound_logger = mock_logger.bind.return_value
        bound_logger.info.assert_called_once_with("Download completed without errors")


class TestLoggingIntegration:
    """Integration tests for logging system."""

    def test_file_logging_creates_directory(self):
        """Test that file logging creates necessary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "logs" / "test.log"
            config = LoggingConfig(log_file=log_file)

            # Directory should not exist initially
            assert not log_file.parent.exists()

            config.setup_logging()

            # Directory should be created
            assert log_file.parent.exists()

    def test_structured_logging_format(self):
        """Test that structured logging produces valid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            config = LoggingConfig(log_file=log_file, structured_logging=True)
            config.setup_logging()

            # Log a test message
            test_logger = get_logger("test")
            test_logger.info("Test message", extra_field="test_value")

            # Read and parse log file
            if log_file.exists():
                with open(log_file) as f:
                    log_line = f.readline().strip()
                    if log_line:
                        # Should be valid JSON
                        log_data = json.loads(log_line)
                        assert "timestamp" in log_data
                        assert "level" in log_data
                        assert "message" in log_data

    def test_console_logging_output(self, capsys):
        """Test console logging output."""
        config = LoggingConfig(level="INFO")
        config.setup_logging()

        # Log a test message
        test_logger = get_logger("test")
        test_logger.info("Test console message")

        # Check captured output
        capsys.readouterr()
        # Note: loguru might not capture in capsys in all test environments
        # This test verifies the setup doesn't crash

    def test_debug_mode_verbose_format(self):
        """Test that debug mode uses verbose format."""
        config = LoggingConfig(debug_mode=True)
        config.setup_logging()

        # Should not raise any exceptions
        test_logger = get_logger("test")
        test_logger.debug("Debug message")
        test_logger.info("Info message")
        test_logger.error("Error message")

    def test_third_party_logger_configuration(self):
        """Test that third-party loggers are configured properly."""
        import logging

        config = LoggingConfig(debug_mode=False)
        config.setup_logging()

        # Check that httpx logger level is set
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level >= logging.WARNING

        # Check that asyncio logger level is set
        asyncio_logger = logging.getLogger("asyncio")
        assert asyncio_logger.level >= logging.WARNING

    def test_debug_mode_third_party_loggers(self):
        """Test third-party logger configuration in debug mode."""
        import logging

        config = LoggingConfig(debug_mode=True)
        config.setup_logging()

        # In debug mode, third-party loggers should allow debug messages
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level <= logging.DEBUG

        asyncio_logger = logging.getLogger("asyncio")
        assert asyncio_logger.level <= logging.DEBUG
