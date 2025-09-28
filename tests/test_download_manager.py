"""Tests for download manager integration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hls_downloader.download_manager import (
    ConfigurationError,
    DownloadManager,
    DownloadManagerError,
)
from src.hls_downloader.merger import FFmpegNotFoundError
from src.hls_downloader.models import DownloadConfig, DownloadStats, SegmentInfo


class TestDownloadManager:
    """Test cases for DownloadManager class."""

    def test_init_default_config(self):
        """Test initialization with default configuration."""
        manager = DownloadManager()

        assert manager.config is not None
        assert isinstance(manager.config, DownloadConfig)
        assert manager.config.max_concurrent == 10
        assert manager.config.max_retries == 3
        assert manager.config.auto_merge is True

    def test_init_custom_config(self):
        """Test initialization with custom configuration."""
        config = DownloadConfig(max_concurrent=5, max_retries=2, auto_merge=False)
        manager = DownloadManager(config)

        assert manager.config == config
        assert manager.config.max_concurrent == 5
        assert manager.config.max_retries == 2
        assert manager.config.auto_merge is False

    def test_init_invalid_config(self):
        """Test initialization with invalid configuration."""
        with pytest.raises(ConfigurationError):
            # Create invalid config that will fail validation
            try:
                invalid_config = DownloadConfig(max_concurrent=-1)
            except ValueError:
                # If DownloadConfig itself raises ValueError, create a valid config
                # and test the manager's validation
                invalid_config = DownloadConfig()
                invalid_config.max_concurrent = -1  # Set invalid value after creation
            DownloadManager(invalid_config)

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        manager = DownloadManager()
        config = DownloadConfig(max_concurrent=10, max_retries=3, timeout=30)

        # Should not raise any exception
        manager._validate_config(config)

    def test_validate_config_invalid_concurrent(self):
        """Test configuration validation with invalid concurrent setting."""
        manager = DownloadManager()

        with pytest.raises(
            ConfigurationError, match="max_concurrent must be greater than 0"
        ):
            # Create a valid config first, then modify it to be invalid
            config = DownloadConfig()
            config.max_concurrent = 0  # Set invalid value
            manager._validate_config(config)

    def test_validate_config_invalid_timeout(self):
        """Test configuration validation with invalid timeout."""
        manager = DownloadManager()

        with pytest.raises(ConfigurationError, match="timeout must be greater than 0"):
            # Create a valid config first, then modify it to be invalid
            config = DownloadConfig()
            config.timeout = 0  # Set invalid value
            manager._validate_config(config)

    @pytest.mark.asyncio
    async def test_setup_output_directory(self):
        """Test output directory setup."""
        manager = DownloadManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "test_output")

            await manager._setup_output_directory(output_dir)

            assert manager._output_directory is not None
            assert manager._output_directory.exists()
            assert manager._segments_directory is not None
            assert manager._segments_directory.exists()
            assert manager._segments_directory.parent == manager._output_directory

    @pytest.mark.asyncio
    async def test_setup_output_directory_existing(self):
        """Test output directory setup with existing directory."""
        manager = DownloadManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory first
            output_dir = Path(temp_dir) / "existing_output"
            output_dir.mkdir()

            await manager._setup_output_directory(str(output_dir))

            assert manager._output_directory == output_dir.resolve()
            assert manager._segments_directory.exists()

    @pytest.mark.asyncio
    async def test_setup_output_directory_permission_error(self):
        """Test output directory setup with permission error."""
        manager = DownloadManager()

        # Try to create directory in root (should fail on most systems)
        with pytest.raises(
            DownloadManagerError, match="Failed to setup output directory"
        ):
            await manager._setup_output_directory("/root/test_output")

    @pytest.mark.asyncio
    async def test_initialize_components(self):
        """Test component initialization."""
        manager = DownloadManager()

        with patch("src.hls_downloader.download_manager.VideoMerger") as mock_merger:
            mock_merger.return_value = MagicMock()

            await manager._initialize_components()

            assert manager._detector is not None
            assert manager._downloader is not None
            assert manager._merger is not None
            assert manager._progress_display is not None

    @pytest.mark.asyncio
    async def test_initialize_components_ffmpeg_not_found_auto_merge_enabled(self):
        """Test component initialization when ffmpeg not found but auto-merge enabled."""
        config = DownloadConfig(auto_merge=True)
        manager = DownloadManager(config)

        with patch("src.hls_downloader.download_manager.VideoMerger") as mock_merger:
            mock_merger.side_effect = FFmpegNotFoundError("ffmpeg not found")

            with pytest.raises(
                DownloadManagerError, match="ffmpeg required for auto-merge"
            ):
                await manager._initialize_components()

    @pytest.mark.asyncio
    async def test_initialize_components_ffmpeg_not_found_auto_merge_disabled(self):
        """Test component initialization when ffmpeg not found but auto-merge disabled."""
        config = DownloadConfig(auto_merge=False)
        manager = DownloadManager(config)

        with patch("src.hls_downloader.download_manager.VideoMerger") as mock_merger:
            mock_merger.side_effect = FFmpegNotFoundError("ffmpeg not found")

            await manager._initialize_components()

            assert manager._merger is None
            assert manager._detector is not None
            assert manager._downloader is not None

    @pytest.mark.asyncio
    async def test_cleanup_components(self):
        """Test component cleanup."""
        manager = DownloadManager()

        # Initialize components first
        with patch("src.hls_downloader.download_manager.VideoMerger"):
            await manager._initialize_components()

        # Mock progress display close method
        manager._progress_display.close_all_progress = MagicMock()

        await manager._cleanup_components()

        assert manager._detector is None
        assert manager._downloader is None
        assert manager._merger is None
        assert manager._progress_display is None

    @pytest.mark.asyncio
    async def test_detect_segments(self):
        """Test segment detection."""
        manager = DownloadManager()

        # Mock detector
        mock_detector = AsyncMock()
        mock_segments = [
            SegmentInfo(url="http://example.com/1.ts", index=1, filename="1.ts"),
            SegmentInfo(url="http://example.com/2.ts", index=2, filename="2.ts"),
        ]
        mock_detector.detect_segments.return_value = mock_segments
        manager._detector = mock_detector

        # Mock async context manager
        mock_detector.__aenter__ = AsyncMock(return_value=mock_detector)
        mock_detector.__aexit__ = AsyncMock(return_value=None)

        result = await manager._detect_segments("http://example.com/1.ts")

        assert len(result) == 2
        assert result[0].filename == "segment_000001.ts"
        assert result[1].filename == "segment_000002.ts"
        mock_detector.detect_segments.assert_called_once_with("http://example.com/1.ts")

    @pytest.mark.asyncio
    async def test_detect_segments_no_detector(self):
        """Test segment detection without initialized detector."""
        manager = DownloadManager()

        with pytest.raises(DownloadManagerError, match="Detector not initialized"):
            await manager._detect_segments("http://example.com/1.ts")

    @pytest.mark.asyncio
    async def test_download_segments(self):
        """Test segment downloading."""
        manager = DownloadManager()

        # Setup mock components
        mock_downloader = AsyncMock()
        mock_progress = MagicMock()

        # Mock successful download results
        segments = [
            SegmentInfo(
                url="http://example.com/1.ts", index=1, filename="segment_000001.ts"
            ),
            SegmentInfo(
                url="http://example.com/2.ts", index=2, filename="segment_000002.ts"
            ),
        ]

        download_results = [
            SegmentInfo(
                url="http://example.com/1.ts",
                index=1,
                filename="segment_000001.ts",
                downloaded=True,
                size=1000,
            ),
            SegmentInfo(
                url="http://example.com/2.ts",
                index=2,
                filename="segment_000002.ts",
                downloaded=True,
                size=1500,
            ),
        ]

        mock_downloader.download_segments.return_value = download_results
        mock_downloader.__aenter__ = AsyncMock(return_value=mock_downloader)
        mock_downloader.__aexit__ = AsyncMock(return_value=None)

        mock_progress.create_main_progress.return_value = MagicMock()
        mock_progress.update_stats = MagicMock()

        manager._downloader = mock_downloader
        manager._progress_display = mock_progress
        manager._segments_directory = Path("/tmp/segments")

        result = await manager._download_segments(segments)

        assert len(result) == 2
        assert all(s.downloaded for s in result)
        assert manager._download_stats is not None
        assert manager._download_stats.downloaded_segments == 2
        assert manager._download_stats.failed_segments == 0

    @pytest.mark.asyncio
    async def test_download_segments_with_failures(self):
        """Test segment downloading with some failures."""
        manager = DownloadManager()

        # Setup mock components
        mock_downloader = AsyncMock()
        mock_progress = MagicMock()

        segments = [
            SegmentInfo(
                url="http://example.com/1.ts", index=1, filename="segment_000001.ts"
            ),
            SegmentInfo(
                url="http://example.com/2.ts", index=2, filename="segment_000002.ts"
            ),
        ]

        # One successful, one failed
        download_results = [
            SegmentInfo(
                url="http://example.com/1.ts",
                index=1,
                filename="segment_000001.ts",
                downloaded=True,
                size=1000,
            ),
            SegmentInfo(
                url="http://example.com/2.ts",
                index=2,
                filename="segment_000002.ts",
                downloaded=False,
            ),
        ]

        mock_downloader.download_segments.return_value = download_results
        mock_downloader.__aenter__ = AsyncMock(return_value=mock_downloader)
        mock_downloader.__aexit__ = AsyncMock(return_value=None)

        mock_progress.create_main_progress.return_value = MagicMock()
        mock_progress.update_stats = MagicMock()

        manager._downloader = mock_downloader
        manager._progress_display = mock_progress
        manager._segments_directory = Path("/tmp/segments")

        result = await manager._download_segments(segments)

        assert len(result) == 2
        assert manager._download_stats.downloaded_segments == 1
        assert manager._download_stats.failed_segments == 1

    @pytest.mark.asyncio
    async def test_merge_segments_auto_merge_disabled(self):
        """Test segment merging when auto-merge is disabled."""
        config = DownloadConfig(auto_merge=False)
        manager = DownloadManager(config)

        result = await manager._merge_segments()

        assert result is None

    @pytest.mark.asyncio
    async def test_merge_segments_no_merger(self):
        """Test segment merging when merger is not available."""
        config = DownloadConfig(auto_merge=True)
        manager = DownloadManager(config)
        manager._merger = None

        result = await manager._merge_segments()

        assert result is None

    @pytest.mark.asyncio
    async def test_merge_segments_success(self):
        """Test successful segment merging."""
        config = DownloadConfig(auto_merge=True)
        manager = DownloadManager(config)

        # Setup mock merger and directories
        mock_merger = AsyncMock()
        mock_merger.merge_segments = AsyncMock()

        manager._merger = mock_merger
        manager._segments_directory = Path("/tmp/segments")
        manager._output_directory = Path("/tmp/output")

        result = await manager._merge_segments("test_video")

        assert result is not None
        assert result.endswith("test_video.mp4")
        mock_merger.merge_segments.assert_called_once()

    def test_generate_results_success(self):
        """Test results generation for successful download."""
        manager = DownloadManager()
        manager._output_directory = Path("/tmp/output")
        manager._segments_directory = Path("/tmp/segments")
        manager._download_stats = DownloadStats(total_segments=2, start_time=1000.0)

        download_results = [
            SegmentInfo(
                url="http://example.com/1.ts",
                index=1,
                filename="1.ts",
                downloaded=True,
                size=1000,
            ),
            SegmentInfo(
                url="http://example.com/2.ts",
                index=2,
                filename="2.ts",
                downloaded=True,
                size=1500,
            ),
        ]

        with patch("time.time", return_value=1010.0):  # 10 seconds elapsed
            results = manager._generate_results(
                download_results, "/tmp/output/video.mp4"
            )

        assert results["success"] is True
        assert results["total_segments"] == 2
        assert results["successful_segments"] == 2
        assert results["failed_segments"] == 0
        assert results["merged_video_path"] == "/tmp/output/video.mp4"
        assert results["download_stats"]["total_bytes"] == 2500
        assert results["download_stats"]["total_time"] == 10.0

    def test_generate_results_with_failures(self):
        """Test results generation with some failures."""
        manager = DownloadManager()
        manager._output_directory = Path("/tmp/output")
        manager._segments_directory = Path("/tmp/segments")
        manager._download_stats = DownloadStats(total_segments=2, start_time=1000.0)

        download_results = [
            SegmentInfo(
                url="http://example.com/1.ts",
                index=1,
                filename="1.ts",
                downloaded=True,
                size=1000,
            ),
            SegmentInfo(
                url="http://example.com/2.ts",
                index=2,
                filename="2.ts",
                downloaded=False,
            ),
        ]

        with patch("time.time", return_value=1010.0):
            results = manager._generate_results(download_results, None)

        assert results["success"] is False
        assert results["total_segments"] == 2
        assert results["successful_segments"] == 1
        assert results["failed_segments"] == 1
        assert "failed_segment_details" in results
        assert len(results["failed_segment_details"]) == 1

    def test_update_config(self):
        """Test configuration update."""
        manager = DownloadManager()

        manager.update_config(max_concurrent=20, max_retries=5)

        assert manager.config.max_concurrent == 20
        assert manager.config.max_retries == 5
        # Other values should remain unchanged
        assert manager.config.timeout == 30  # default value

    def test_update_config_invalid(self):
        """Test configuration update with invalid values."""
        manager = DownloadManager()

        # This should raise ConfigurationError because the validation in update_config
        # will catch the ValueError from DownloadConfig and re-raise as ConfigurationError
        with pytest.raises((ConfigurationError, ValueError)):
            manager.update_config(max_concurrent=-1)

    def test_get_download_stats_none(self):
        """Test getting download stats when none available."""
        manager = DownloadManager()

        stats = manager.get_download_stats()

        assert stats is None

    def test_get_download_stats_available(self):
        """Test getting download stats when available."""
        manager = DownloadManager()
        test_stats = DownloadStats(total_segments=10)
        manager._download_stats = test_stats

        stats = manager.get_download_stats()

        assert stats == test_stats

    def test_get_segments_info_empty(self):
        """Test getting segments info when empty."""
        manager = DownloadManager()

        segments = manager.get_segments_info()

        assert segments == []

    def test_get_segments_info_available(self):
        """Test getting segments info when available."""
        manager = DownloadManager()
        test_segments = [
            SegmentInfo(url="http://example.com/1.ts", index=1, filename="1.ts"),
            SegmentInfo(url="http://example.com/2.ts", index=2, filename="2.ts"),
        ]
        manager._segments = test_segments

        segments = manager.get_segments_info()

        assert len(segments) == 2
        assert segments == test_segments
        # Should return a copy, not the original list
        assert segments is not manager._segments

    @pytest.mark.asyncio
    async def test_download_hls_invalid_url(self):
        """Test download with invalid URL."""
        manager = DownloadManager()

        with pytest.raises(DownloadManagerError, match="Invalid URL provided"):
            await manager.download_hls("", "/tmp/output")

        with pytest.raises(DownloadManagerError, match="Invalid URL provided"):
            await manager.download_hls("ftp://example.com/video.ts", "/tmp/output")

    @pytest.mark.asyncio
    async def test_download_hls_empty_output_dir(self):
        """Test download with empty output directory."""
        manager = DownloadManager()

        with pytest.raises(
            DownloadManagerError, match="Output directory cannot be empty"
        ):
            await manager.download_hls("http://example.com/1.ts", "")

    @pytest.mark.asyncio
    async def test_download_hls_no_segments_found(self):
        """Test download when no segments are found."""
        manager = DownloadManager()

        with (
            patch.object(manager, "_setup_output_directory") as mock_setup,
            patch.object(manager, "_initialize_components") as mock_init,
            patch.object(manager, "_detect_segments") as mock_detect,
            patch.object(manager, "_cleanup_components") as mock_cleanup,
        ):
            mock_setup.return_value = None
            mock_init.return_value = None
            mock_detect.return_value = []  # No segments found
            mock_cleanup.return_value = None

            with pytest.raises(DownloadManagerError, match="No segments found"):
                await manager.download_hls("http://example.com/1.ts", "/tmp/output")

    @pytest.mark.asyncio
    async def test_download_hls_full_success(self):
        """Test complete successful download flow."""
        manager = DownloadManager()

        # Mock all the methods
        with (
            patch.object(manager, "_setup_output_directory") as mock_setup,
            patch.object(manager, "_initialize_components") as mock_init,
            patch.object(manager, "_detect_segments") as mock_detect,
            patch.object(manager, "_download_segments_with_resume") as mock_download,
            patch.object(manager, "_merge_segments") as mock_merge,
            patch.object(manager, "_cleanup_components") as mock_cleanup,
            patch.object(manager, "_check_and_handle_resume") as mock_resume,
        ):
            # Setup return values
            mock_setup.return_value = None
            mock_init.return_value = None

            test_segments = [
                SegmentInfo(url="http://example.com/1.ts", index=1, filename="1.ts"),
                SegmentInfo(url="http://example.com/2.ts", index=2, filename="2.ts"),
            ]
            mock_detect.return_value = test_segments

            download_results = [
                SegmentInfo(
                    url="http://example.com/1.ts",
                    index=1,
                    filename="1.ts",
                    downloaded=True,
                    size=1000,
                ),
                SegmentInfo(
                    url="http://example.com/2.ts",
                    index=2,
                    filename="2.ts",
                    downloaded=True,
                    size=1500,
                ),
            ]
            mock_download.return_value = download_results

            mock_merge.return_value = "/tmp/output/video.mp4"
            mock_cleanup.return_value = None

            # Setup required attributes for _generate_results
            manager._output_directory = Path("/tmp/output")
            manager._segments_directory = Path("/tmp/segments")
            manager._download_stats = DownloadStats(total_segments=2, start_time=1000.0)

            # Mock resume check
            mock_resume.return_value = {"resumed": False, "message": "Starting fresh"}

            with patch("time.time", return_value=1010.0):
                result = await manager.download_hls(
                    "http://example.com/1.ts", "/tmp/output"
                )

            # Verify all methods were called
            mock_setup.assert_called_once_with("/tmp/output")
            mock_init.assert_called_once()
            mock_detect.assert_called_once_with("http://example.com/1.ts")
            mock_download.assert_called_once_with(test_segments)
            mock_merge.assert_called_once_with(None)
            mock_cleanup.assert_called_once()

            # Verify result structure
            assert result["success"] is True
            assert result["total_segments"] == 2
            assert result["merged_video_path"] == "/tmp/output/video.mp4"

    @pytest.mark.asyncio
    async def test_resume_download_no_existing_directory(self):
        """Test resume download when output directory doesn't exist."""
        manager = DownloadManager()

        with patch.object(manager, "download_hls") as mock_download:
            mock_download.return_value = {"success": True}

            await manager.resume_download(
                "http://example.com/1.ts", "/nonexistent/path", "video.mp4"
            )

            # Should fall back to regular download
            mock_download.assert_called_once_with(
                "http://example.com/1.ts",
                "/nonexistent/path",
                "video.mp4",
                force_restart=False,
            )

    @pytest.mark.asyncio
    async def test_resume_download_no_segments_directory(self):
        """Test resume download when segments directory doesn't exist."""
        manager = DownloadManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create output directory but not segments subdirectory
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            with patch.object(manager, "download_hls") as mock_download:
                mock_download.return_value = {"success": True}

                await manager.resume_download(
                    "http://example.com/1.ts", str(output_dir), "video.mp4"
                )

                # Should fall back to regular download
                mock_download.assert_called_once_with(
                    "http://example.com/1.ts",
                    str(output_dir),
                    "video.mp4",
                    force_restart=False,
                )

    @pytest.mark.asyncio
    async def test_resume_download_with_existing_segments(self):
        """Test resume download with existing segment files."""
        manager = DownloadManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create output and segments directories
            output_dir = Path(temp_dir) / "output"
            segments_dir = output_dir / "segments"
            segments_dir.mkdir(parents=True)

            # Create some existing segment files
            (segments_dir / "segment_000001.ts").write_text("segment1")
            (segments_dir / "segment_000002.ts").write_text("segment2")

            with patch.object(manager, "download_hls") as mock_download:
                mock_download.return_value = {"success": True}

                await manager.resume_download(
                    "http://example.com/1.ts", str(output_dir), "video.mp4"
                )

                # Should proceed with regular download (downloader handles resume logic)
                mock_download.assert_called_once_with(
                    "http://example.com/1.ts",
                    str(output_dir),
                    "video.mp4",
                    force_restart=False,
                )


@pytest.mark.asyncio
async def test_download_manager_integration():
    """Integration test for download manager with mocked components."""
    config = DownloadConfig(
        max_concurrent=2,
        max_retries=1,
        auto_merge=False,  # Disable merge to avoid ffmpeg dependency
        cleanup_segments=False,
    )

    manager = DownloadManager(config)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock all external dependencies
        with (
            patch(
                "src.hls_downloader.download_manager.HLSDetector"
            ) as mock_detector_class,
            patch(
                "src.hls_downloader.download_manager.AsyncDownloader"
            ) as mock_downloader_class,
            patch(
                "src.hls_downloader.download_manager.ProgressDisplay"
            ) as mock_progress_class,
            patch(
                "src.hls_downloader.download_manager.StateManager"
            ) as mock_state_manager_class,
            patch(
                "src.hls_downloader.download_manager.ResumeValidator"
            ) as mock_resume_validator_class,
        ):
            # Setup mock detector
            mock_detector = AsyncMock()
            mock_detector_class.return_value = mock_detector
            mock_detector.__aenter__ = AsyncMock(return_value=mock_detector)
            mock_detector.__aexit__ = AsyncMock(return_value=None)

            test_segments = [
                SegmentInfo(url="http://example.com/1.ts", index=1, filename="1.ts"),
                SegmentInfo(url="http://example.com/2.ts", index=2, filename="2.ts"),
            ]
            mock_detector.detect_segments.return_value = test_segments

            # Setup mock downloader
            mock_downloader = AsyncMock()
            mock_downloader_class.return_value = mock_downloader
            mock_downloader.__aenter__ = AsyncMock(return_value=mock_downloader)
            mock_downloader.__aexit__ = AsyncMock(return_value=None)

            download_results = [
                SegmentInfo(
                    url="http://example.com/1.ts",
                    index=1,
                    filename="segment_000001.ts",
                    downloaded=True,
                    size=1000,
                ),
                SegmentInfo(
                    url="http://example.com/2.ts",
                    index=2,
                    filename="segment_000002.ts",
                    downloaded=True,
                    size=1500,
                ),
            ]
            mock_downloader.download_segments = AsyncMock(return_value=download_results)
            mock_downloader.get_error_summary = MagicMock(
                return_value={"total_errors": 0}
            )

            # Setup mock progress display
            mock_progress = MagicMock()
            mock_progress_class.return_value = mock_progress
            mock_progress.create_main_progress.return_value = MagicMock()

            # Setup mock state manager
            mock_state_manager = MagicMock()
            mock_state_manager_class.return_value = mock_state_manager
            mock_state_manager.has_saved_state.return_value = False
            mock_state_manager.create_initial_state.return_value = MagicMock()

            # Setup mock resume validator
            mock_resume_validator = MagicMock()
            mock_resume_validator_class.return_value = mock_resume_validator
            mock_resume_validator.__aenter__ = AsyncMock(
                return_value=mock_resume_validator
            )
            mock_resume_validator.__aexit__ = AsyncMock(return_value=None)

            # Manually set the manager's internal components to avoid initialization issues
            manager._downloader = mock_downloader
            manager._progress_display = mock_progress
            manager._state_manager = mock_state_manager
            manager._resume_validator = mock_resume_validator

            # Mock the resume method to return no resume
            with patch.object(manager, "_check_and_handle_resume") as mock_resume_check:
                mock_resume_check.return_value = {
                    "resumed": False,
                    "message": "Starting fresh",
                }

                # Mock the download segments with resume method
                with patch.object(
                    manager, "_download_segments_with_resume"
                ) as mock_download_resume:
                    mock_download_resume.return_value = download_results

                    # Run the download
                    result = await manager.download_hls(
                        "http://example.com/1.ts", temp_dir
                    )

            # Verify results
            assert result["success"] is True
            assert result["total_segments"] == 2
            assert result["successful_segments"] == 2
            assert result["failed_segments"] == 0
            assert result["merged_video_path"] is None  # Auto-merge disabled

            # Verify components were called correctly
            mock_detector.detect_segments.assert_called_once_with(
                "http://example.com/1.ts"
            )
            mock_download_resume.assert_called_once()

            # Verify output directory structure was created
            output_path = Path(temp_dir)
            segments_path = output_path / "segments"
            assert output_path.exists()
            assert segments_path.exists()
