"""Tests for CLI interface."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from argparse import Namespace

from src.hls_downloader.cli import (
    create_parser,
    load_config_file,
    save_config_file,
    get_default_config_path,
    merge_config,
    validate_arguments,
    show_config,
    main,
)
from src.hls_downloader.models import DownloadConfig


class TestConfigFileOperations:
    """Test configuration file operations."""

    def test_load_config_file_success(self):
        """Test successful config file loading."""
        config_data = {
            "max_concurrent": 20,
            "max_retries": 5,
            "timeout": 60,
            "auto_merge": False,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            result = load_config_file(config_path)
            assert result == config_data
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        config_path = Path("/non/existent/config.json")
        result = load_config_file(config_path)
        assert result == {}

    def test_load_config_file_invalid_json(self, capsys):
        """Test loading invalid JSON config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_path = Path(f.name)
        
        try:
            result = load_config_file(config_path)
            assert result == {}
            
            captured = capsys.readouterr()
            assert "Error parsing config file" in captured.err
        finally:
            config_path.unlink()

    def test_save_config_file_success(self):
        """Test successful config file saving."""
        config_data = {
            "max_concurrent": 15,
            "timeout": 45,
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            
            result = save_config_file(config_path, config_data)
            assert result is True
            assert config_path.exists()
            
            # Verify content
            with open(config_path, 'r') as f:
                saved_data = json.load(f)
            assert saved_data == config_data

    def test_save_config_file_create_directory(self):
        """Test config file saving with directory creation."""
        config_data = {"max_concurrent": 10}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "subdir" / "config.json"
            
            result = save_config_file(config_path, config_data)
            assert result is True
            assert config_path.exists()
            assert config_path.parent.exists()

    def test_get_default_config_path(self):
        """Test default config path generation."""
        path = get_default_config_path()
        assert path.name == "config.json"
        assert ".hls_downloader" in str(path)


class TestArgumentParser:
    """Test argument parser functionality."""

    def test_create_parser_basic(self):
        """Test basic parser creation."""
        parser = create_parser()
        assert parser.prog == "pytest"  # pytest sets this
        assert "HLS Downloader" in parser.description

    def test_parse_minimal_args(self):
        """Test parsing minimal required arguments."""
        parser = create_parser()
        args = parser.parse_args(["https://example.com/segment{}.ts"])
        
        assert args.url == "https://example.com/segment{}.ts"
        assert args.output == "./downloads"
        assert args.concurrent == 10
        assert args.retries == 3
        assert args.timeout == 30

    def test_parse_all_args(self):
        """Test parsing all available arguments."""
        parser = create_parser()
        args = parser.parse_args([
            "https://example.com/video_{}.ts",
            "-o", "/tmp/output",
            "-c", "20",
            "-r", "5",
            "--timeout", "60",
            "--chunk-size", "16384",
            "--format", "mkv",
            "--no-merge",
            "--cleanup",
            "--verbose",
        ])
        
        assert args.url == "https://example.com/video_{}.ts"
        assert args.output == "/tmp/output"
        assert args.concurrent == 20
        assert args.retries == 5
        assert args.timeout == 60
        assert args.chunk_size == 16384
        assert args.format == "mkv"
        assert args.no_merge is True
        assert args.cleanup is True
        assert args.verbose is True

    def test_parse_config_args(self):
        """Test parsing configuration-related arguments."""
        parser = create_parser()
        
        # Test --show-config
        args = parser.parse_args(["--show-config"])
        assert args.show_config is True
        
        # Test --save-config
        args = parser.parse_args(["--save-config"])
        assert args.save_config is True
        
        # Test --config
        args = parser.parse_args(["--config", "/path/to/config.json", "url"])
        assert str(args.config) == "/path/to/config.json"


class TestConfigMerging:
    """Test configuration merging functionality."""

    def test_merge_config_empty_base(self):
        """Test merging with empty base configuration."""
        base_config = {}
        args = Namespace(
            concurrent=15,
            retries=4,
            timeout=45,
            no_merge=True,
            cleanup=False,
        )
        
        result = merge_config(base_config, args)
        expected = {
            "max_concurrent": 15,
            "max_retries": 4,
            "timeout": 45,
            "auto_merge": False,  # Inverted from no_merge=True
            "cleanup_segments": False,
        }
        
        assert result == expected

    def test_merge_config_cli_overrides_file(self):
        """Test that CLI arguments override file configuration."""
        base_config = {
            "max_concurrent": 10,
            "max_retries": 3,
            "timeout": 30,
        }
        args = Namespace(
            concurrent=20,  # Should override
            retries=None,   # Should not override
            timeout=60,     # Should override
        )
        
        result = merge_config(base_config, args)
        expected = {
            "max_concurrent": 20,  # Overridden
            "max_retries": 3,      # From file
            "timeout": 60,         # Overridden
        }
        
        assert result == expected

    def test_merge_config_boolean_inversion(self):
        """Test boolean inversion for no_merge argument."""
        base_config = {"auto_merge": True}
        
        # Test no_merge=True should set auto_merge=False
        args = Namespace(no_merge=True)
        result = merge_config(base_config, args)
        assert result["auto_merge"] is False
        
        # Test no_merge=False should set auto_merge=True
        args = Namespace(no_merge=False)
        result = merge_config(base_config, args)
        assert result["auto_merge"] is True


class TestArgumentValidation:
    """Test argument validation functionality."""

    def test_validate_arguments_valid(self):
        """Test validation with valid arguments."""
        args = Namespace(
            concurrent=10,
            retries=3,
            timeout=30,
            chunk_size=8192,
            url="https://example.com/segment{}.ts",
        )
        
        assert validate_arguments(args) is True

    def test_validate_arguments_invalid_concurrent(self, capsys):
        """Test validation with invalid concurrent value."""
        args = Namespace(
            concurrent=0,  # Invalid
            retries=3,
            timeout=30,
            chunk_size=8192,
            url="https://example.com/segment{}.ts",
        )
        
        assert validate_arguments(args) is False
        captured = capsys.readouterr()
        assert "Concurrent downloads must be between 1 and 100" in captured.err

    def test_validate_arguments_invalid_retries(self, capsys):
        """Test validation with invalid retries value."""
        args = Namespace(
            concurrent=10,
            retries=-1,  # Invalid
            timeout=30,
            chunk_size=8192,
            url="https://example.com/segment{}.ts",
        )
        
        assert validate_arguments(args) is False
        captured = capsys.readouterr()
        assert "Retries must be between 0 and 10" in captured.err

    def test_validate_arguments_invalid_url(self, capsys):
        """Test validation with invalid URL format."""
        args = Namespace(
            concurrent=10,
            retries=3,
            timeout=30,
            chunk_size=8192,
            url="https://example.com/segment.ts",  # Missing {} placeholder
        )
        
        assert validate_arguments(args) is False
        captured = capsys.readouterr()
        assert "URL must contain '{}' placeholder" in captured.err

    def test_validate_arguments_multiple_errors(self, capsys):
        """Test validation with multiple errors."""
        args = Namespace(
            concurrent=101,  # Invalid
            retries=11,      # Invalid
            timeout=0,       # Invalid
            chunk_size=8192,
            url="invalid_url",  # Invalid
        )
        
        assert validate_arguments(args) is False
        captured = capsys.readouterr()
        assert "Concurrent downloads must be between 1 and 100" in captured.err
        assert "Retries must be between 0 and 10" in captured.err
        assert "Timeout must be between 1 and 300" in captured.err


class TestShowConfig:
    """Test configuration display functionality."""

    def test_show_config_basic(self, capsys):
        """Test basic configuration display."""
        config = DownloadConfig(
            max_concurrent=15,
            max_retries=5,
            timeout=60,
        )
        
        show_config(config)
        captured = capsys.readouterr()
        
        assert "Current Configuration:" in captured.out
        assert "Max Concurrent Downloads: 15" in captured.out
        assert "Max Retries: 5" in captured.out
        assert "Timeout: 60 seconds" in captured.out

    def test_show_config_with_path(self, capsys):
        """Test configuration display with config file path."""
        config = DownloadConfig()
        config_path = Path("/tmp/test_config.json")
        
        show_config(config, config_path)
        captured = capsys.readouterr()
        
        assert f"Config file: {config_path}" in captured.out
        assert "Status: Not found" in captured.out


class TestMainFunction:
    """Test main function functionality."""

    @pytest.mark.asyncio
    async def test_main_show_config(self, capsys):
        """Test main function with --show-config."""
        with patch('sys.argv', ['cli.py', '--show-config']):
            await main()
        
        captured = capsys.readouterr()
        assert "Current Configuration:" in captured.out

    @pytest.mark.asyncio
    async def test_main_save_config(self, capsys):
        """Test main function with --save-config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            with patch('sys.argv', ['cli.py', '--save-config', '--config', str(config_path)]):
                await main()
            
            captured = capsys.readouterr()
            assert f"Configuration saved to {config_path}" in captured.out
            assert config_path.exists()

    @pytest.mark.asyncio
    async def test_main_no_url_error(self, capsys):
        """Test main function without URL argument."""
        with patch('sys.argv', ['cli.py']):
            with pytest.raises(SystemExit) as exc_info:
                await main()
            
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Error: URL is required for download" in captured.err

    @pytest.mark.asyncio
    async def test_main_invalid_config_error(self, capsys):
        """Test main function with invalid configuration."""
        with patch('sys.argv', ['cli.py', 'url', '--concurrent', '0']):
            with pytest.raises(SystemExit) as exc_info:
                await main()
            
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    @patch('src.hls_downloader.cli.DownloadManager')
    async def test_main_successful_download(self, mock_manager_class, capsys):
        """Test main function with successful download."""
        # Mock the download manager
        mock_manager = Mock()
        mock_manager.download_hls = AsyncMock()
        mock_manager_class.return_value = mock_manager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', [
                'cli.py', 
                'https://example.com/segment{}.ts',
                '-o', temp_dir
            ]):
                await main()
        
        captured = capsys.readouterr()
        assert "Download completed successfully!" in captured.out
        mock_manager.download_hls.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.hls_downloader.cli.DownloadManager')
    async def test_main_download_failure(self, mock_manager_class, capsys):
        """Test main function with download failure."""
        # Mock the download manager to raise an exception
        mock_manager = Mock()
        mock_manager.download_hls = AsyncMock(side_effect=Exception("Download failed"))
        mock_manager_class.return_value = mock_manager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', [
                'cli.py', 
                'https://example.com/segment{}.ts',
                '-o', temp_dir
            ]):
                with pytest.raises(SystemExit) as exc_info:
                    await main()
                
                assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "Download failed: Download failed" in captured.err

    @pytest.mark.asyncio
    @patch('src.hls_downloader.cli.DownloadManager')
    async def test_main_keyboard_interrupt(self, mock_manager_class, capsys):
        """Test main function with keyboard interrupt."""
        # Mock the download manager to raise KeyboardInterrupt
        mock_manager = Mock()
        mock_manager.download_hls = AsyncMock(side_effect=KeyboardInterrupt())
        mock_manager_class.return_value = mock_manager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', [
                'cli.py', 
                'https://example.com/segment{}.ts',
                '-o', temp_dir
            ]):
                with pytest.raises(SystemExit) as exc_info:
                    await main()
                
                assert exc_info.value.code == 130  # SIGINT exit code
        
        captured = capsys.readouterr()
        assert "Download interrupted by user" in captured.err

    @pytest.mark.asyncio
    @patch('src.hls_downloader.cli.DownloadManager')
    async def test_main_verbose_output(self, mock_manager_class, capsys):
        """Test main function with verbose output."""
        # Mock the download manager
        mock_manager = Mock()
        mock_manager.download_hls = AsyncMock()
        mock_manager_class.return_value = mock_manager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', [
                'cli.py', 
                'https://example.com/segment{}.ts',
                '-o', temp_dir,
                '--verbose'
            ]):
                await main()
        
        captured = capsys.readouterr()
        assert "Starting download with configuration:" in captured.out
        assert "Downloading from: https://example.com/segment{}.ts" in captured.out


class TestIntegration:
    """Integration tests for CLI functionality."""

    @pytest.mark.asyncio
    async def test_config_file_integration(self):
        """Test complete config file integration."""
        config_data = {
            "max_concurrent": 25,
            "max_retries": 7,
            "timeout": 90,
            "auto_merge": False,
            "cleanup_segments": True,
            "output_format": "mkv",
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            
            # Save config
            assert save_config_file(config_path, config_data)
            
            # Load and verify
            loaded_config = load_config_file(config_path)
            assert loaded_config == config_data
            
            # Test CLI integration
            with patch('sys.argv', [
                'cli.py', 
                '--config', str(config_path),
                '--show-config'
            ]):
                await main()

    def test_argument_precedence(self):
        """Test that CLI arguments take precedence over config file."""
        base_config = {
            "max_concurrent": 10,
            "timeout": 30,
        }
        
        args = Namespace(
            concurrent=20,  # Should override
            retries=None,   # Should not affect
            timeout=None,   # Should not override
        )
        
        result = merge_config(base_config, args)
        
        # CLI arg should override
        assert result["max_concurrent"] == 20
        # File config should remain
        assert result["timeout"] == 30
        # New values should not appear if None
        assert "max_retries" not in result