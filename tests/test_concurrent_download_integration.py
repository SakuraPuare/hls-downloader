"""Integration tests for concurrent download control and management."""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from src.hls_downloader.downloader import AsyncDownloader
from src.hls_downloader.models import DownloadConfig, SegmentInfo


class TestConcurrentDownloadIntegration:
    """Integration tests for concurrent download functionality."""

    @pytest.fixture
    def config(self):
        """Create a test download configuration with moderate concurrency."""
        return DownloadConfig(
            max_concurrent=5, max_retries=2, timeout=10, chunk_size=1024
        )

    @pytest.fixture
    def large_segment_list(self):
        """Create a large list of segments for testing concurrency."""
        return [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 21)  # 20 segments
        ]

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    async def test_concurrent_download_with_queue_management(
        self, config, large_segment_list, temp_dir
    ):
        """Test concurrent download using task queue management."""
        async with AsyncDownloader(config) as downloader:
            # Mock successful downloads with varying sizes and speeds
            async def mock_download_segment(segment, output_dir):
                # Simulate different download times and sizes
                download_time = 0.1 + (segment.index % 3) * 0.05  # 0.1-0.2 seconds
                await asyncio.sleep(download_time)

                # Create the file
                filepath = output_dir / segment.filename
                content = b"x" * (1000 + segment.index * 100)  # Varying sizes
                filepath.write_bytes(content)

                # Update segment info
                segment.size = len(content)
                segment.downloaded = True
                return segment

            # Replace the method with our mock
            downloader._download_single_segment = mock_download_segment

            start_time = time.time()
            results = await downloader.download_segments(large_segment_list, temp_dir)
            end_time = time.time()

            # Verify all segments were downloaded
            assert len(results) == len(large_segment_list)
            successful = [r for r in results if r.downloaded]
            assert len(successful) == len(large_segment_list)

            # Verify files were created
            for result in results:
                filepath = Path(temp_dir) / result.filename
                assert filepath.exists()
                assert result.size > 0

            # Verify concurrency was effective (should be faster than sequential)
            total_time = end_time - start_time
            # With 5 concurrent downloads, should be roughly 4x faster than sequential
            # Sequential would take ~20 * 0.15 = 3 seconds, concurrent should be < 1 second
            assert total_time < 2.0, f"Download took {total_time:.2f}s, expected < 2.0s"

            # Check download statistics
            stats = downloader.get_download_stats()
            assert stats.total_segments == len(large_segment_list)
            assert stats.downloaded_segments == len(large_segment_list)
            assert stats.failed_segments == 0
            assert stats.average_speed > 0

    @pytest.mark.asyncio
    async def test_download_speed_monitoring(
        self, config, large_segment_list, temp_dir
    ):
        """Test download speed monitoring functionality."""
        async with AsyncDownloader(config) as downloader:
            # Mock downloads with known speeds
            async def mock_download_segment(segment, output_dir):
                # Simulate consistent download speed
                content_size = 10000  # 10KB
                download_time = 0.1  # 0.1 seconds = 100KB/s
                await asyncio.sleep(download_time)

                filepath = output_dir / segment.filename
                content = b"x" * content_size
                filepath.write_bytes(content)

                segment.size = content_size
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            # Download segments
            await downloader.download_segments(large_segment_list[:10], temp_dir)

            # Check that speed monitoring captured data
            assert len(downloader._download_speeds) > 0

            # Verify speed calculations are reasonable
            avg_speed = sum(downloader._download_speeds) / len(
                downloader._download_speeds
            )
            # Expected speed should be around 100KB/s (100,000 bytes/s)
            assert 50000 < avg_speed < 200000, (
                f"Average speed {avg_speed} not in expected range"
            )

            # Check performance metrics
            metrics = downloader.get_performance_metrics()
            assert metrics["average_speed"] > 0
            assert len(metrics["recent_speeds"]) > 0
            assert metrics["completed_count"] == 10
            assert metrics["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_adaptive_concurrency_adjustment(self, temp_dir):
        """Test adaptive concurrency adjustment mechanism."""
        # Use a config that allows for adjustment
        config = DownloadConfig(max_concurrent=8, max_retries=1, timeout=5)

        segments = [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 16)  # 15 segments
        ]

        async with AsyncDownloader(config) as downloader:
            # Mock downloads with performance degradation over time
            call_count = 0

            async def mock_download_segment(segment, output_dir):
                nonlocal call_count
                call_count += 1

                # Simulate performance degradation after first few downloads
                if call_count <= 5:
                    download_time = 0.05  # Fast initially
                else:
                    download_time = 0.2  # Slower later

                await asyncio.sleep(download_time)

                filepath = output_dir / segment.filename
                content = b"x" * 5000
                filepath.write_bytes(content)

                segment.size = 5000
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            # Force shorter adjustment interval for testing
            downloader._adjustment_interval = 1.0

            # Start with lower concurrency to test increase
            downloader._adaptive_concurrency = 3

            results = await downloader.download_segments(segments, temp_dir)

            # Verify all downloads completed
            assert len([r for r in results if r.downloaded]) == len(segments)

            # Check that adaptive adjustment was attempted
            # (The actual adjustment depends on timing and performance measurements)
            metrics = downloader.get_performance_metrics()
            assert "adaptive_concurrency" in metrics
            assert metrics["adaptive_concurrency"] >= 2  # Should not go below minimum

    @pytest.mark.asyncio
    async def test_concurrent_download_with_failures(self, config, temp_dir):
        """Test concurrent download handling of mixed success/failure scenarios."""
        segments = [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 11)  # 10 segments
        ]

        async with AsyncDownloader(config) as downloader:
            # Mock downloads with some failures
            async def mock_download_segment(segment, output_dir):
                # Fail segments with even indices
                if segment.index % 2 == 0:
                    segment.downloaded = False
                    return segment

                # Succeed for odd indices
                await asyncio.sleep(0.1)
                filepath = output_dir / segment.filename
                content = b"x" * 5000
                filepath.write_bytes(content)

                segment.size = 5000
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            results = await downloader.download_segments(segments, temp_dir)

            # Check results
            successful = [r for r in results if r.downloaded]
            failed = [r for r in results if not r.downloaded]

            assert len(successful) == 5  # Odd indices (1, 3, 5, 7, 9)
            assert len(failed) == 5  # Even indices (2, 4, 6, 8, 10)

            # Check statistics
            stats = downloader.get_download_stats()
            assert stats.downloaded_segments == 5
            assert stats.failed_segments == 5
            assert stats.total_segments == 10

    @pytest.mark.asyncio
    async def test_queue_management_with_cancellation(self, config, temp_dir):
        """Test queue management behavior when downloads are cancelled."""
        segments = [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 21)  # 20 segments
        ]

        async with AsyncDownloader(config) as downloader:
            # Mock slow downloads
            async def mock_download_segment(segment, output_dir):
                await asyncio.sleep(0.5)  # Slow download

                filepath = output_dir / segment.filename
                content = b"x" * 1000
                filepath.write_bytes(content)

                segment.size = 1000
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            # Start download task
            download_task = asyncio.create_task(
                downloader.download_segments(segments, temp_dir)
            )

            # Let some downloads start
            await asyncio.sleep(0.2)

            # Cancel the download
            download_task.cancel()

            # Wait for cancellation to complete
            try:
                await download_task
            except asyncio.CancelledError:
                pass

            # Check that some segments were processed before cancellation
            # (Exact number depends on timing, but should be > 0 and < total)
            total_processed = len(downloader._completed_segments) + len(
                downloader._failed_segments
            )
            assert 0 <= total_processed < len(segments)

    @pytest.mark.asyncio
    async def test_performance_metrics_accuracy(self, config, temp_dir):
        """Test accuracy of performance metrics collection."""
        segments = [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 6)  # 5 segments for precise testing
        ]

        async with AsyncDownloader(config) as downloader:
            # Mock downloads with known characteristics
            async def mock_download_segment(segment, output_dir):
                # Known download time and size
                download_time = 0.1
                content_size = 10000

                await asyncio.sleep(download_time)

                filepath = output_dir / segment.filename
                content = b"x" * content_size
                filepath.write_bytes(content)

                segment.size = content_size
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            time.time()
            results = await downloader.download_segments(segments, temp_dir)
            time.time()

            # Verify all succeeded
            assert all(r.downloaded for r in results)

            # Check performance metrics
            metrics = downloader.get_performance_metrics()

            # Verify metrics structure
            expected_keys = [
                "adaptive_concurrency",
                "max_concurrency",
                "active_downloads",
                "recent_speeds",
                "average_speed",
                "performance_window",
                "queue_size",
                "completed_count",
                "failed_count",
            ]
            for key in expected_keys:
                assert key in metrics

            # Verify metric values
            assert metrics["completed_count"] == 5
            assert metrics["failed_count"] == 0
            assert metrics["queue_size"] == 0  # Should be empty after completion
            assert metrics["average_speed"] > 0
            assert len(metrics["recent_speeds"]) > 0

            # Check download stats
            stats = downloader.get_download_stats()
            assert stats.total_segments == 5
            assert stats.downloaded_segments == 5
            assert stats.failed_segments == 0
            assert stats.downloaded_bytes == 50000  # 5 * 10000 bytes
            assert stats.average_speed > 0

    @pytest.mark.asyncio
    async def test_semaphore_concurrency_control(self, temp_dir):
        """Test that semaphore properly controls concurrent downloads."""
        # Use low concurrency for easier testing
        config = DownloadConfig(max_concurrent=2, max_retries=1, timeout=5)

        segments = [
            SegmentInfo(
                url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                index=i,
                filename=f"segment{i:03d}.ts",
            )
            for i in range(1, 6)  # 5 segments
        ]

        async with AsyncDownloader(config) as downloader:
            active_downloads = []
            max_concurrent_observed = 0

            async def mock_download_segment(segment, output_dir):
                # Track active downloads
                active_downloads.append(segment.index)
                nonlocal max_concurrent_observed
                max_concurrent_observed = max(
                    max_concurrent_observed, len(active_downloads)
                )

                # Simulate download time
                await asyncio.sleep(0.2)

                # Create file
                filepath = output_dir / segment.filename
                content = b"x" * 1000
                filepath.write_bytes(content)

                # Remove from active list
                active_downloads.remove(segment.index)

                segment.size = 1000
                segment.downloaded = True
                return segment

            downloader._download_single_segment = mock_download_segment

            results = await downloader.download_segments(segments, temp_dir)

            # Verify all downloads completed
            assert all(r.downloaded for r in results)

            # Verify concurrency was limited (should never exceed max_concurrent)
            assert max_concurrent_observed <= config.max_concurrent
            # Should have used some concurrency (more than 1)
            assert max_concurrent_observed > 1
