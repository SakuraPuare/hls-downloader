"""Tests for state manager functionality."""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.hls_downloader.models.config import DownloadConfig
from src.hls_downloader.models.stats import DownloadStats
from src.hls_downloader.models.segment import SegmentInfo
from src.hls_downloader.models.state import DownloadState
from src.hls_downloader.core.state_manager import StateManager


class TestStateManager:
    """Test cases for StateManager class."""

    def test_init(self):
        """Test StateManager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)

            assert manager.output_dir == Path(temp_dir)
            assert manager.state_file == Path(temp_dir) / ".hls_download_state.json"
            assert (
                manager.backup_file
                == Path(temp_dir) / ".hls_download_state.backup.json"
            )

    def test_create_initial_state(self):
        """Test creating initial download state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            assert state.url == "http://example.com/segment1.ts"
            assert state.output_dir == temp_dir
            assert state.output_filename == "test.mp4"
            assert state.config == config
            assert state.segments == []
            assert state.stats.total_segments == 0
            assert state.status == "detecting"
            assert state.resume_count == 0
            assert state.last_resume_at is None
            assert state.created_at > 0
            assert state.updated_at > 0

    def test_save_and_load_state(self):
        """Test saving and loading download state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig(max_concurrent=5)

            # Create test segments
            segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="segment_000001.ts",
                    size=1024,
                    downloaded=True,
                ),
                SegmentInfo(
                    url="http://example.com/segment2.ts",
                    index=2,
                    filename="segment_000002.ts",
                    size=2048,
                    downloaded=False,
                ),
            ]

            # Create test stats
            stats = DownloadStats(
                total_segments=2,
                downloaded_segments=1,
                failed_segments=0,
                total_bytes=3072,
                downloaded_bytes=1024,
                start_time=time.time(),
                average_speed=1000.0,
            )

            # Create state
            original_state = DownloadState(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
                segments=segments,
                stats=stats,
                created_at=time.time(),
                updated_at=time.time(),
                status="downloading",
                resume_count=1,
                last_resume_at=time.time(),
            )

            # Save state
            manager.save_state(original_state)

            # Verify file exists
            assert manager.state_file.exists()

            # Load state
            loaded_state = manager.load_state()

            assert loaded_state is not None
            assert loaded_state.url == original_state.url
            assert loaded_state.output_dir == original_state.output_dir
            assert loaded_state.output_filename == original_state.output_filename
            assert (
                loaded_state.config.max_concurrent
                == original_state.config.max_concurrent
            )
            assert len(loaded_state.segments) == len(original_state.segments)
            assert loaded_state.segments[0].url == original_state.segments[0].url
            assert (
                loaded_state.segments[0].downloaded
                == original_state.segments[0].downloaded
            )
            assert (
                loaded_state.stats.total_segments == original_state.stats.total_segments
            )
            assert loaded_state.status == original_state.status
            assert loaded_state.resume_count == original_state.resume_count

    def test_load_nonexistent_state(self):
        """Test loading state when no state file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)

            state = manager.load_state()
            assert state is None

    def test_load_corrupted_state_with_backup(self):
        """Test loading state when main file is corrupted but backup exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create valid state
            original_state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            # Save state first time (no backup created yet)
            manager.save_state(original_state)

            # Save state second time (this creates backup from first save)
            original_state.status = "downloading"
            manager.save_state(original_state)

            # Corrupt main file
            with open(manager.state_file, "w") as f:
                f.write("invalid json")

            # Load should use backup
            loaded_state = manager.load_state()

            assert loaded_state is not None
            assert loaded_state.url == original_state.url

    def test_delete_state(self):
        """Test deleting state files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create and save state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )
            manager.save_state(state)

            # Verify files exist
            assert manager.state_file.exists()

            # Delete state
            manager.delete_state()

            # Verify files are deleted
            assert not manager.state_file.exists()
            assert not manager.backup_file.exists()

    def test_has_saved_state(self):
        """Test checking for saved state existence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)

            # Initially no state
            assert not manager.has_saved_state()

            # Create state file
            manager.state_file.touch()
            assert manager.has_saved_state()

            # Remove main file, create backup
            manager.state_file.unlink()
            manager.backup_file.touch()
            assert manager.has_saved_state()

    def test_get_state_info(self):
        """Test getting basic state information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # No state initially
            info = manager.get_state_info()
            assert info is None

            # Create and save state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )
            state.stats.total_segments = 10
            state.stats.downloaded_segments = 5
            state.status = "downloading"
            manager.save_state(state)

            # Get state info
            info = manager.get_state_info()

            assert info is not None
            assert info["url"] == "http://example.com/segment1.ts"
            assert info["status"] == "downloading"
            assert info["total_segments"] == 10
            assert info["downloaded_segments"] == 5
            assert info["resume_count"] == 0

    def test_update_state_status(self):
        """Test updating state status."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            # Update status
            manager.update_state_status(state, "downloading")

            assert state.status == "downloading"
            assert manager.state_file.exists()

            # Verify saved state has updated status
            loaded_state = manager.load_state()
            assert loaded_state.status == "downloading"

    def test_update_state_segments(self):
        """Test updating state with segments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            # Create segments
            segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="segment_000001.ts",
                ),
                SegmentInfo(
                    url="http://example.com/segment2.ts",
                    index=2,
                    filename="segment_000002.ts",
                ),
            ]

            # Update segments
            manager.update_state_segments(state, segments)

            assert len(state.segments) == 2
            assert state.stats.total_segments == 2

            # Verify saved state has updated segments
            loaded_state = manager.load_state()
            assert len(loaded_state.segments) == 2
            assert loaded_state.stats.total_segments == 2

    def test_update_state_progress(self):
        """Test updating state with download progress."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state with segments
            segments = [
                SegmentInfo(
                    url="http://example.com/segment1.ts",
                    index=1,
                    filename="segment_000001.ts",
                    size=1024,
                ),
                SegmentInfo(
                    url="http://example.com/segment2.ts",
                    index=2,
                    filename="segment_000002.ts",
                    size=2048,
                ),
            ]

            state = DownloadState(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
                segments=segments,
                stats=DownloadStats(total_segments=2),
                created_at=time.time(),
                updated_at=time.time(),
                status="downloading",
            )

            # Update progress
            downloaded_segments = [segments[0]]  # First segment downloaded
            downloaded_segments[0].downloaded = True
            failed_segments = []

            manager.update_state_progress(state, downloaded_segments, failed_segments)

            assert state.stats.downloaded_segments == 1
            assert state.stats.failed_segments == 0
            assert state.stats.downloaded_bytes == 1024
            assert state.segments[0].downloaded
            assert not state.segments[1].downloaded

    def test_mark_resume(self):
        """Test marking state as resumed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            # Mark as resumed
            manager.mark_resume(state)

            assert state.resume_count == 1
            assert state.last_resume_at is not None

            # Mark as resumed again
            manager.mark_resume(state)

            assert state.resume_count == 2

    def test_state_serialization_with_special_characters(self):
        """Test state serialization with special characters in URLs and filenames."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state with special characters
            state = manager.create_initial_state(
                url="http://example.com/测试/segment1.ts?param=value&other=测试",
                output_dir=temp_dir,
                output_filename="测试视频.mp4",
                config=config,
            )

            # Save and load
            manager.save_state(state)
            loaded_state = manager.load_state()

            assert loaded_state is not None
            assert loaded_state.url == state.url
            assert loaded_state.output_filename == state.output_filename

    @patch("src.hls_downloader.state_manager.logger")
    def test_save_state_error_handling(self, mock_logger):
        """Test error handling during state save."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)
            config = DownloadConfig()

            # Create state
            state = manager.create_initial_state(
                url="http://example.com/segment1.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=config,
            )

            # Make directory read-only to cause save error
            Path(temp_dir).chmod(0o444)

            try:
                with pytest.raises(OSError):
                    manager.save_state(state)

                # Verify error was logged
                mock_logger.error.assert_called()
            finally:
                # Restore permissions for cleanup
                Path(temp_dir).chmod(0o755)

    def test_invalid_state_dict_conversion(self):
        """Test handling of invalid state dictionary during conversion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StateManager(temp_dir)

            # Test missing required field
            invalid_dict = {
                "url": "http://example.com/segment1.ts",
                # Missing other required fields
            }

            with pytest.raises(ValueError, match="Missing required field"):
                manager._dict_to_state(invalid_dict)

            # Test invalid config
            invalid_dict = {
                "url": "http://example.com/segment1.ts",
                "output_dir": temp_dir,
                "config": {"max_concurrent": -1},  # Invalid value
                "segments": [],
                "stats": {"total_segments": 0},
                "status": "detecting",
            }

            with pytest.raises(ValueError, match="Invalid state dictionary"):
                manager._dict_to_state(invalid_dict)
