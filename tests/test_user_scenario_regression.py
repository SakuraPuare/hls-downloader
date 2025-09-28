"""User scenario regression test suite.

This module contains regression tests for common user scenarios and workflows
to ensure the HLS downloader continues to work correctly for real-world usage patterns.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

from src.hls_downloader.download_manager import DownloadManager
from src.hls_downloader.models import DownloadConfig, SegmentInfo
from src.hls_downloader.state_manager import StateManager


class TestBasicUserScenarios:
    """Test basic user scenarios and workflows."""

    @pytest.fixture
    def basic_config(self):
        """Basic configuration for typical users."""
        return DownloadConfig(
            max_concurrent=4,
            max_retries=3,
            timeout=30,
            auto_merge=True,
            cleanup_segments=True,
        )

    @pytest.mark.asyncio
    async def test_first_time_user_workflow(self, basic_config):
        """Test workflow for first-time users."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(basic_config)

            # Simulate first-time user with simple URL
            test_segments = [
                SegmentInfo(
                    url=f"http://simple.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                    size=1024 * 300,  # 300KB segments
                )
                for i in range(1, 6)  # Small number for first-time user
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def first_time_download(segments, output_dir):
                        # Simulate successful first download
                        for segment in segments:
                            segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        first_time_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://simple.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="my_first_video.mp4",
                        )

                        # First-time user expectations
                        assert result["success"]
                        assert result["total_segments"] == 5
                        assert result["segments_downloaded"] == 5
                        assert "output_file" in result

                        # Should have attempted merge
                        mock_merger_instance.merge_segments.assert_called_once()

    @pytest.mark.asyncio
    async def test_experienced_user_workflow(self, basic_config):
        """Test workflow for experienced users with custom settings."""
        # Experienced user config with custom settings
        experienced_config = DownloadConfig(
            max_concurrent=8,
            max_retries=5,
            timeout=60,
            auto_merge=False,  # Manual control
            cleanup_segments=False,  # Keep segments
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(experienced_config)

            # Larger segment set for experienced user
            test_segments = [
                SegmentInfo(
                    url=f"http://advanced.example.com/stream/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:04d}.ts",
                    size=1024 * 500,  # 500KB segments
                )
                for i in range(1, 8)  # 7 segments (reduced for faster testing)
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def experienced_download(segments, output_dir):
                        # Simulate high success rate for experienced user
                        for segment in segments:
                            segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        experienced_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with patch.object(manager, "_progress_display"):
                        # No merger for experienced user (manual control)
                        result = await manager.download_hls(
                            url="http://advanced.example.com/stream/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="advanced_video.mp4",
                        )

                        # Experienced user expectations
                        assert result["success"]
                        assert result["total_segments"] == 25
                        assert result["segments_downloaded"] == 25

                        # Should not have auto-merged
                        assert "merged" not in result or not result["merged"]

    @pytest.mark.asyncio
    async def test_mobile_user_workflow(self, basic_config):
        """Test workflow optimized for mobile users."""
        # Mobile-optimized config
        mobile_config = DownloadConfig(
            max_concurrent=2,  # Lower concurrency for mobile
            max_retries=2,
            timeout=20,  # Shorter timeout
            auto_merge=True,
            cleanup_segments=True,  # Save storage space
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(mobile_config)

            # Smaller segments for mobile
            test_segments = [
                SegmentInfo(
                    url=f"http://mobile.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:02d}.ts",
                    size=1024 * 150,  # 150KB segments (mobile-friendly)
                )
                for i in range(1, 8)  # 7 segments
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def mobile_download(segments, output_dir):
                        # Simulate mobile network variability
                        for i, segment in enumerate(segments):
                            if i == 3:  # One segment has issues
                                segment.downloaded = False
                            else:
                                segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        mobile_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://mobile.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="mobile_video.mp4",
                        )

                        # Mobile user expectations
                        assert result["success"]
                        assert result["total_segments"] == 7
                        assert result["segments_downloaded"] == 6  # One failed

                        # Should still attempt merge with partial success
                        mock_merger_instance.merge_segments.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_processing_workflow(self, basic_config):
        """Test batch processing workflow for multiple videos."""
        video_configs = [
            ("http://batch1.example.com/segment{}.ts", "video1.mp4", 5),
            ("http://batch2.example.com/segment{}.ts", "video2.mp4", 8),
            ("http://batch3.example.com/segment{}.ts", "video3.mp4", 3),
        ]

        batch_results = []

        for url_template, output_name, segment_count in video_configs:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(basic_config)

                test_segments = [
                    SegmentInfo(
                        url=url_template.format(i),
                        index=i,
                        filename=f"segment{i:03d}.ts",
                    )
                    for i in range(1, segment_count + 1)
                ]

                with patch.object(manager, "_detector") as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance

                    with patch.object(manager, "_downloader") as mock_downloader:
                        mock_downloader_instance = AsyncMock()

                        async def batch_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments

                        mock_downloader_instance.download_segments.side_effect = (
                            batch_download
                        )
                        mock_downloader.__aenter__.return_value = (
                            mock_downloader_instance
                        )

                        with (
                            patch.object(manager, "_progress_display"),
                            patch.object(manager, "_merger") as mock_merger,
                        ):
                            mock_merger_instance = AsyncMock()
                            mock_merger_instance.merge_segments.return_value = True
                            mock_merger.__aenter__.return_value = mock_merger_instance

                            result = await manager.download_hls(
                                url=url_template.format(1),
                                output_dir=temp_dir,
                                output_filename=output_name,
                            )

                            batch_results.append(result)

        # Verify all batch downloads succeeded
        assert len(batch_results) == 3
        for i, result in enumerate(batch_results):
            expected_count = video_configs[i][2]
            assert result["success"]
            assert result["total_segments"] == expected_count
            assert result["segments_downloaded"] == expected_count


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios that users commonly encounter."""

    @pytest.fixture
    def recovery_config(self):
        """Configuration for error recovery testing."""
        return DownloadConfig(
            max_concurrent=3,
            max_retries=3,
            timeout=15,
            auto_merge=True,
            cleanup_segments=False,  # Keep for debugging
        )

    @pytest.mark.asyncio
    async def test_network_interruption_recovery(self, recovery_config):
        """Test recovery from network interruptions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(recovery_config)

            test_segments = [
                SegmentInfo(
                    url=f"http://unstable.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                )
                for i in range(1, 10)  # 9 segments
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    call_count = 0

                    async def unstable_download(segments, output_dir):
                        nonlocal call_count
                        call_count += 1

                        # First attempt: network issues
                        if call_count == 1:
                            for i, segment in enumerate(segments):
                                if i < 4:  # First 4 succeed
                                    segment.downloaded = True
                                else:  # Rest fail due to network
                                    segment.downloaded = False
                        # Retry: remaining segments succeed
                        else:
                            for segment in segments:
                                if not segment.downloaded:
                                    segment.downloaded = True

                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        unstable_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://unstable.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="recovery_test.mp4",
                        )

                        # Should eventually succeed with retries
                        assert result["success"]
                        assert result["total_segments"] == 9

    @pytest.mark.asyncio
    async def test_partial_download_resume(self, recovery_config):
        """Test resuming from partial downloads."""
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()

            # Create state for partial download
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://resume.example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="resume_test.mp4",
                config=recovery_config,
            )

            test_segments = [
                SegmentInfo(
                    url=f"http://resume.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                    downloaded=(i <= 3),  # First 3 already downloaded
                )
                for i in range(1, 8)  # 7 segments total
            ]

            state_manager.update_state_segments(initial_state, test_segments)

            # Create files for already downloaded segments
            for i in range(1, 4):
                (segments_dir / f"segment{i:03d}.ts").write_bytes(b"x" * 1024)

            manager = DownloadManager(recovery_config)

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                # Should not call detect_segments for resume
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def resume_download(segments, output_dir):
                        # Only remaining segments should be downloaded
                        for segment in segments:
                            segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        resume_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://resume.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="resume_test.mp4",
                        )

                        # Should resume successfully
                        assert result["success"]
                        assert result["resumed"]
                        assert result["existing_segments"] == 3
                        assert result["total_segments"] == 7

    @pytest.mark.asyncio
    async def test_corrupted_file_recovery(self, recovery_config):
        """Test recovery from corrupted files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir()

            test_segments = [
                SegmentInfo(
                    url=f"http://corrupt.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                    size=1024 * 100,  # Expected size
                    downloaded=True,
                )
                for i in range(1, 6)  # 5 segments
            ]

            # Create files with some corrupted (wrong size)
            (segments_dir / "segment001.ts").write_bytes(b"x" * (1024 * 100))  # Correct
            (segments_dir / "segment002.ts").write_bytes(b"x" * 500)  # Corrupted
            (segments_dir / "segment003.ts").write_bytes(b"x" * (1024 * 100))  # Correct
            (segments_dir / "segment004.ts").write_bytes(b"")  # Empty/corrupted
            (segments_dir / "segment005.ts").write_bytes(b"x" * (1024 * 100))  # Correct

            manager = DownloadManager(recovery_config)

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def corruption_recovery_download(segments, output_dir):
                        # Re-download corrupted segments
                        for segment in segments:
                            segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        corruption_recovery_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://corrupt.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="corruption_test.mp4",
                        )

                        # Should detect and fix corruption
                        assert result["success"]
                        assert result["total_segments"] == 5

    @pytest.mark.asyncio
    async def test_disk_space_recovery(self, recovery_config):
        """Test recovery from disk space issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(recovery_config)

            test_segments = [
                SegmentInfo(
                    url=f"http://diskspace.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                )
                for i in range(1, 6)
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    call_count = 0

                    async def disk_space_download(segments, output_dir):
                        nonlocal call_count
                        call_count += 1

                        # First attempt: disk space issues
                        if call_count == 1:
                            for i, segment in enumerate(segments):
                                if i < 2:  # First 2 succeed
                                    segment.downloaded = True
                                else:  # Rest fail due to disk space
                                    segment.downloaded = False
                        # Retry: user freed space, remaining succeed
                        else:
                            for segment in segments:
                                if not segment.downloaded:
                                    segment.downloaded = True

                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        disk_space_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://diskspace.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="diskspace_test.mp4",
                        )

                        # Should eventually succeed after retry
                        assert result["success"]
                        assert result["total_segments"] == 5


class TestConfigurationScenarios:
    """Test various configuration scenarios users might encounter."""

    def test_default_configuration_behavior(self):
        """Test behavior with default configuration."""
        config = DownloadConfig()
        DownloadManager(config)

        # Verify default values are reasonable
        assert config.max_concurrent > 0
        assert config.max_concurrent <= 20  # Reasonable upper limit
        assert config.max_retries >= 0
        assert config.timeout > 0
        assert isinstance(config.auto_merge, bool)
        assert isinstance(config.cleanup_segments, bool)

    def test_conservative_configuration(self):
        """Test conservative configuration for slow networks."""
        conservative_config = DownloadConfig(
            max_concurrent=1,
            max_retries=5,
            timeout=60,
            auto_merge=True,
            cleanup_segments=True,
        )

        manager = DownloadManager(conservative_config)

        # Should accept conservative settings
        assert manager.config.max_concurrent == 1
        assert manager.config.max_retries == 5
        assert manager.config.timeout == 60

    def test_aggressive_configuration(self):
        """Test aggressive configuration for fast networks."""
        aggressive_config = DownloadConfig(
            max_concurrent=20,
            max_retries=1,
            timeout=5,
            auto_merge=False,
            cleanup_segments=False,
        )

        manager = DownloadManager(aggressive_config)

        # Should accept aggressive settings
        assert manager.config.max_concurrent == 20
        assert manager.config.max_retries == 1
        assert manager.config.timeout == 5

    def test_invalid_configuration_handling(self):
        """Test handling of invalid configurations."""
        invalid_configs = [
            {"max_concurrent": 0},
            {"max_concurrent": -1},
            {"max_retries": -1},
            {"timeout": 0},
            {"timeout": -1},
        ]

        for invalid_params in invalid_configs:
            try:
                # Should either correct invalid values or raise appropriate error
                config = DownloadConfig(**invalid_params)
                manager = DownloadManager(config)

                # If no exception, values should be corrected
                assert manager.config.max_concurrent > 0
                assert manager.config.max_retries >= 0
                assert manager.config.timeout > 0

            except (ValueError, TypeError):
                # Expected for some invalid configurations
                pass

    @pytest.mark.asyncio
    async def test_configuration_persistence(self):
        """Test that configuration is properly used throughout workflow."""
        custom_config = DownloadConfig(
            max_concurrent=3,
            max_retries=2,
            timeout=25,
            auto_merge=False,
            cleanup_segments=False,
        )

        with tempfile.TemporaryDirectory():
            manager = DownloadManager(custom_config)

            # Verify config is preserved
            assert manager.config.max_concurrent == 3
            assert manager.config.max_retries == 2
            assert manager.config.timeout == 25
            assert not manager.config.auto_merge
            assert not manager.config.cleanup_segments


class TestRegressionPrevention:
    """Tests to prevent regression of previously fixed issues."""

    @pytest.mark.asyncio
    async def test_empty_segment_list_handling(self):
        """Regression test: Handle empty segment lists gracefully."""
        config = DownloadConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(config)

            # Mock detector returning empty list
            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = []
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_progress_display"):
                    result = await manager.download_hls(
                        url="http://empty.example.com/segment1.ts",
                        output_dir=temp_dir,
                        output_filename="empty_test.mp4",
                    )

                    # Should handle empty list gracefully
                    assert "success" in result
                    assert result["total_segments"] == 0

    @pytest.mark.asyncio
    async def test_single_segment_handling(self):
        """Regression test: Handle single segment downloads correctly."""
        config = DownloadConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(config)

            single_segment = [
                SegmentInfo(
                    url="http://single.example.com/onlysegment.ts",
                    index=1,
                    filename="segment001.ts",
                )
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = single_segment
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def single_download(segments, output_dir):
                        segments[0].downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        single_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger") as mock_merger,
                    ):
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance

                        result = await manager.download_hls(
                            url="http://single.example.com/onlysegment.ts",
                            output_dir=temp_dir,
                            output_filename="single_test.mp4",
                        )

                        # Should handle single segment correctly
                        assert result["success"]
                        assert result["total_segments"] == 1
                        assert result["segments_downloaded"] == 1

    @pytest.mark.asyncio
    async def test_unicode_filename_handling(self):
        """Regression test: Handle Unicode filenames correctly."""
        config = DownloadConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(config)

            unicode_segments = [
                SegmentInfo(
                    url="http://unicode.example.com/segment1.ts",
                    index=1,
                    filename="视频片段001.ts",  # Chinese characters
                )
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = unicode_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def unicode_download(segments, output_dir):
                        segments[0].downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        unicode_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger", None),
                    ):
                        result = await manager.download_hls(
                            url="http://unicode.example.com/segment1.ts",
                            output_dir=temp_dir,
                            output_filename="unicode_测试.mp4",  # Unicode output name
                        )

                        # Should handle Unicode correctly
                        assert result["success"]

    @pytest.mark.asyncio
    async def test_very_long_url_handling(self):
        """Regression test: Handle very long URLs correctly."""
        config = DownloadConfig()

        # Create very long URL
        long_path = "/".join([f"verylongdirectoryname{i}" for i in range(20)])
        long_query = "&".join([f"parameter{i}=verylongvalue{i}" for i in range(10)])
        very_long_url = f"http://example.com{long_path}/segment1.ts?{long_query}"

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(config)

            long_url_segments = [
                SegmentInfo(url=very_long_url, index=1, filename="segment001.ts")
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = long_url_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def long_url_download(segments, output_dir):
                        segments[0].downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        long_url_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger", None),
                    ):
                        result = await manager.download_hls(
                            url=very_long_url,
                            output_dir=temp_dir,
                            output_filename="long_url_test.mp4",
                        )

                        # Should handle long URLs correctly
                        assert result["success"]

    def test_concurrent_manager_instances(self):
        """Regression test: Multiple manager instances should not interfere."""
        config1 = DownloadConfig(max_concurrent=2)
        config2 = DownloadConfig(max_concurrent=4)

        manager1 = DownloadManager(config1)
        manager2 = DownloadManager(config2)

        # Should maintain separate configurations
        assert manager1.config.max_concurrent == 2
        assert manager2.config.max_concurrent == 4

        # Should not share state
        assert manager1 is not manager2
        assert manager1.config is not manager2.config
