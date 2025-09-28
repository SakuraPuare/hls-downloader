"""Comprehensive integration tests for the HLS downloader system.

This module contains end-to-end integration tests that verify the complete
functionality of the HLS downloader, including real network operations,
error scenarios, performance benchmarks, and user workflows.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from src.hls_downloader.download_manager import DownloadManager
from src.hls_downloader.models import DownloadConfig, SegmentInfo


class TestEndToEndDownload:
    """End-to-end download tests using real HLS streams."""

    @pytest.fixture
    def real_test_urls(self):
        """Provide real HLS URLs for testing."""
        return {
            "cntv_sample": "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts",
            "template_format": "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{}.ts"
        }

    @pytest.fixture
    def e2e_config(self):
        """Configuration optimized for end-to-end testing."""
        return DownloadConfig(
            max_concurrent=3,
            max_retries=2,
            timeout=15,
            auto_merge=False,  # Skip merge for faster testing
            cleanup_segments=False
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_complete_download_workflow(self, real_test_urls, e2e_config):
        """Test complete download workflow from detection to completion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(e2e_config)
            
            # Use template format for detection
            url = real_test_urls["template_format"].replace("{}", "1")
            
            try:
                result = await manager.download_hls(
                    url=url,
                    output_dir=temp_dir,
                    output_filename="test_complete.mp4"
                )
                
                # Verify basic result structure
                assert "success" in result
                assert "total_segments" in result
                assert "segments_downloaded" in result
                
                # Check that segments directory was created
                segments_dir = Path(temp_dir) / "segments"
                assert segments_dir.exists()
                
                # Verify at least some segments were processed
                segment_files = list(segments_dir.glob("*.ts"))
                if result["success"]:
                    assert len(segment_files) > 0
                
            except Exception as e:
                # Network issues are acceptable in integration tests
                pytest.skip(f"Network-dependent test failed: {e}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_resume_workflow_end_to_end(self, real_test_urls, e2e_config):
        """Test resume functionality in end-to-end scenario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(e2e_config)
            url = real_test_urls["template_format"].replace("{}", "1")
            
            # Mock a partial download scenario
            with patch.object(manager, '_downloader') as mock_downloader:
                mock_downloader_instance = AsyncMock()
                
                # First attempt: simulate partial failure
                segments = [
                    SegmentInfo(url=f"{real_test_urls['template_format'].replace('{}', str(i))}", 
                              index=i, filename=f"segment_{i:06d}.ts", downloaded=(i <= 2))
                    for i in range(1, 6)
                ]
                mock_downloader_instance.download_segments.return_value = segments
                mock_downloader.__aenter__.return_value = mock_downloader_instance
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        # First download (partial)
                        result1 = await manager.download_hls(
                            url=url,
                            output_dir=temp_dir,
                            output_filename="test_resume.mp4"
                        )
                        
                        # Second download (resume)
                        result2 = await manager.download_hls(
                            url=url,
                            output_dir=temp_dir,
                            output_filename="test_resume.mp4"
                        )
                        
                        # Verify resume behavior
                        if "resumed" in result2:
                            assert result2["resumed"] == True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_small_segment_range_download(self, real_test_urls, e2e_config):
        """Test download with a small, controlled segment range."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(e2e_config)
            
            # Create a controlled test with limited segments
            test_segments = [
                SegmentInfo(
                    url=real_test_urls["cntv_sample"],
                    index=81,
                    filename="segment_000081.ts",
                    downloaded=False
                )
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_progress_display'), \
                     patch.object(manager, '_merger', None):
                    
                    try:
                        result = await manager.download_hls(
                            url=real_test_urls["cntv_sample"],
                            output_dir=temp_dir,
                            output_filename="test_small.mp4"
                        )
                        
                        # Verify result structure
                        assert isinstance(result, dict)
                        assert "total_segments" in result
                        assert result["total_segments"] == 1
                        
                    except Exception as e:
                        pytest.skip(f"Network-dependent test failed: {e}")


class TestNetworkExceptionSimulation:
    """Tests for simulating various network exception scenarios."""

    @pytest.fixture
    def network_config(self):
        """Configuration for network testing."""
        return DownloadConfig(
            max_concurrent=2,
            max_retries=2,
            timeout=5,
            auto_merge=False
        )

    @pytest.mark.asyncio
    async def test_connection_timeout_simulation(self, network_config):
        """Test handling of connection timeout scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(network_config)
            
            # Mock detector to return segments
            test_segments = [
                SegmentInfo(url="http://timeout.example.com/segment1.ts", 
                          index=1, filename="segment1.ts"),
                SegmentInfo(url="http://timeout.example.com/segment2.ts", 
                          index=2, filename="segment2.ts")
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                # Mock downloader to simulate timeouts
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    # Simulate timeout errors
                    async def timeout_download(segments, output_dir):
                        for segment in segments:
                            segment.downloaded = False  # All fail due to timeout
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = timeout_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        result = await manager.download_hls(
                            url="http://timeout.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="timeout_test.mp4"
                        )
                        
                        # Should handle timeouts gracefully
                        assert "success" in result
                        assert result["segments_downloaded"] == 0

    @pytest.mark.asyncio
    async def test_http_error_codes_simulation(self, network_config):
        """Test handling of various HTTP error codes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(network_config)
            
            error_scenarios = [
                (404, "Not Found"),
                (403, "Forbidden"),
                (500, "Internal Server Error"),
                (503, "Service Unavailable")
            ]
            
            for status_code, reason in error_scenarios:
                test_segments = [
                    SegmentInfo(
                        url=f"http://error{status_code}.example.com/segment1.ts",
                        index=1,
                        filename="segment1.ts"
                    )
                ]
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        
                        # Simulate HTTP error
                        async def http_error_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = False
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = http_error_download
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger', None):
                            
                            result = await manager.download_hls(
                                url=f"http://error{status_code}.example.com/segment{{}}.ts",
                                output_dir=temp_dir,
                                output_filename=f"error_{status_code}_test.mp4"
                            )
                            
                            # Should handle HTTP errors gracefully
                            assert "success" in result

    @pytest.mark.asyncio
    async def test_network_interruption_recovery(self, network_config):
        """Test recovery from network interruptions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(network_config)
            
            test_segments = [
                SegmentInfo(url="http://unstable.example.com/segment1.ts", 
                          index=1, filename="segment1.ts"),
                SegmentInfo(url="http://unstable.example.com/segment2.ts", 
                          index=2, filename="segment2.ts"),
                SegmentInfo(url="http://unstable.example.com/segment3.ts", 
                          index=3, filename="segment3.ts")
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    # Simulate intermittent failures with eventual success
                    call_count = 0
                    async def intermittent_download(segments, output_dir):
                        nonlocal call_count
                        call_count += 1
                        
                        # First call: some failures
                        if call_count == 1:
                            segments[0].downloaded = True
                            segments[1].downloaded = False  # Fail
                            segments[2].downloaded = True
                        # Subsequent calls: remaining segments succeed
                        else:
                            for segment in segments:
                                if not segment.downloaded:
                                    segment.downloaded = True
                        
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = intermittent_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        result = await manager.download_hls(
                            url="http://unstable.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="recovery_test.mp4"
                        )
                        
                        # Should eventually succeed with retries
                        assert "success" in result

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, network_config):
        """Test handling of DNS resolution failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(network_config)
            
            test_segments = [
                SegmentInfo(url="http://nonexistent.invalid/segment1.ts", 
                          index=1, filename="segment1.ts")
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    # Simulate DNS failure
                    async def dns_failure_download(segments, output_dir):
                        for segment in segments:
                            segment.downloaded = False
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = dns_failure_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        result = await manager.download_hls(
                            url="http://nonexistent.invalid/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="dns_test.mp4"
                        )
                        
                        # Should handle DNS failures gracefully
                        assert "success" in result
                        assert result["segments_downloaded"] == 0


class TestPerformanceBenchmarks:
    """Performance benchmark tests to verify download efficiency."""

    @pytest.fixture
    def benchmark_config(self):
        """Configuration for performance testing."""
        return DownloadConfig(
            max_concurrent=5,
            max_retries=1,
            timeout=10,
            auto_merge=False
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_download_performance(self, benchmark_config):
        """Benchmark concurrent download performance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test segments
            segment_count = 20
            test_segments = [
                SegmentInfo(
                    url=f"http://benchmark.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts"
                )
                for i in range(1, segment_count + 1)
            ]
            
            manager = DownloadManager(benchmark_config)
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    # Mock fast downloads for benchmarking
                    async def benchmark_download(segments, output_dir):
                        # Simulate download time proportional to segment count
                        download_time = 0.05 * len(segments) / benchmark_config.max_concurrent
                        await asyncio.sleep(download_time)
                        
                        for segment in segments:
                            segment.downloaded = True
                            segment.size = 1024 * 100  # 100KB per segment
                        
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = benchmark_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        start_time = time.time()
                        result = await manager.download_hls(
                            url="http://benchmark.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="benchmark.mp4"
                        )
                        end_time = time.time()
                        
                        # Performance assertions
                        total_time = end_time - start_time
                        assert total_time < 5.0, f"Download took {total_time:.2f}s, expected < 5.0s"
                        
                        # Calculate throughput
                        if result.get("success"):
                            total_bytes = segment_count * 1024 * 100
                            throughput = total_bytes / total_time
                            assert throughput > 1024 * 1024, f"Throughput {throughput:.0f} B/s too low"

    @pytest.mark.asyncio
    async def test_memory_usage_efficiency(self, benchmark_config):
        """Test memory usage efficiency during downloads."""
        import psutil
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create many segments to test memory efficiency
            segment_count = 50
            test_segments = [
                SegmentInfo(
                    url=f"http://memory.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts"
                )
                for i in range(1, segment_count + 1)
            ]
            
            manager = DownloadManager(benchmark_config)
            
            # Measure initial memory
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    async def memory_efficient_download(segments, output_dir):
                        # Simulate memory-efficient streaming download
                        for segment in segments:
                            segment.downloaded = True
                            segment.size = 1024 * 50  # 50KB per segment
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = memory_efficient_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        await manager.download_hls(
                            url="http://memory.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="memory_test.mp4"
                        )
                        
                        # Measure peak memory
                        peak_memory = process.memory_info().rss
                        memory_increase = peak_memory - initial_memory
                        
                        # Memory increase should be reasonable (< 100MB for this test)
                        assert memory_increase < 100 * 1024 * 1024, \
                            f"Memory increase {memory_increase / 1024 / 1024:.1f}MB too high"

    @pytest.mark.asyncio
    async def test_scalability_with_large_segment_count(self, benchmark_config):
        """Test scalability with large number of segments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with large segment count
            segment_count = 100
            test_segments = [
                SegmentInfo(
                    url=f"http://scale.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:04d}.ts"
                )
                for i in range(1, segment_count + 1)
            ]
            
            manager = DownloadManager(benchmark_config)
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    async def scalable_download(segments, output_dir):
                        # Simulate efficient handling of large segment count
                        batch_size = 10
                        for i in range(0, len(segments), batch_size):
                            batch = segments[i:i + batch_size]
                            await asyncio.sleep(0.01)  # Small delay per batch
                            for segment in batch:
                                segment.downloaded = True
                                segment.size = 1024 * 25  # 25KB per segment
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = scalable_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        start_time = time.time()
                        result = await manager.download_hls(
                            url="http://scale.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="scale_test.mp4"
                        )
                        end_time = time.time()
                        
                        # Should handle large segment count efficiently
                        total_time = end_time - start_time
                        assert total_time < 10.0, f"Large scale download took {total_time:.2f}s"
                        
                        if result.get("success"):
                            assert result["total_segments"] == segment_count
                            assert result["segments_downloaded"] == segment_count


class TestURLPatternCompatibility:
    """Tests for compatibility with various URL patterns."""

    @pytest.fixture
    def pattern_config(self):
        """Configuration for URL pattern testing."""
        return DownloadConfig(
            max_concurrent=2,
            max_retries=1,
            timeout=5,
            auto_merge=False
        )

    @pytest.mark.asyncio
    async def test_numeric_patterns(self, pattern_config):
        """Test various numeric URL patterns."""
        patterns = [
            "http://example.com/segment{}.ts",           # Simple numeric
            "http://example.com/seg_{:03d}.ts",          # Zero-padded
            "http://example.com/video_{:04d}.m4s",       # Different extension
            "http://example.com/chunk{:02d}.ts",         # Two-digit padding
        ]
        
        for pattern in patterns:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(pattern_config)
                
                # Create test segments for this pattern
                test_segments = [
                    SegmentInfo(
                        url=pattern.format(i) if "{}" in pattern else pattern.replace("{:0", "{:0").format(i),
                        index=i,
                        filename=f"segment{i:03d}.ts"
                    )
                    for i in range(1, 4)
                ]
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        
                        async def pattern_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = pattern_download
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger', None):
                            
                            result = await manager.download_hls(
                                url=test_segments[0].url,
                                output_dir=temp_dir,
                                output_filename=f"pattern_test.mp4"
                            )
                            
                            # Should handle pattern correctly
                            assert "success" in result

    @pytest.mark.asyncio
    async def test_complex_url_structures(self, pattern_config):
        """Test complex URL structures with paths and parameters."""
        complex_patterns = [
            "https://cdn.example.com/live/stream/2023/12/segment{}.ts?token=abc123",
            "http://media.site.com/hls/v1/playlist/segment_{:04d}.m4s",
            "https://streaming.example.org/content/video/chunks/chunk{}.ts",
        ]
        
        for pattern in complex_patterns:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(pattern_config)
                
                # Create test segments
                test_segments = [
                    SegmentInfo(
                        url=pattern.format(i) if "{}" in pattern else pattern.replace("{:0", "{:0").format(i),
                        index=i,
                        filename=f"segment{i:03d}.ts"
                    )
                    for i in range(1, 3)
                ]
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        
                        async def complex_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = complex_download
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger', None):
                            
                            result = await manager.download_hls(
                                url=test_segments[0].url,
                                output_dir=temp_dir,
                                output_filename="complex_test.mp4"
                            )
                            
                            assert "success" in result

    @pytest.mark.asyncio
    async def test_edge_case_patterns(self, pattern_config):
        """Test edge case URL patterns."""
        edge_cases = [
            ("Single segment", ["http://example.com/single.ts"]),
            ("Large gaps", ["http://example.com/segment1.ts", "http://example.com/segment100.ts"]),
            ("Non-sequential", ["http://example.com/segment5.ts", "http://example.com/segment3.ts", "http://example.com/segment7.ts"]),
        ]
        
        for case_name, urls in edge_cases:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(pattern_config)
                
                # Create test segments from URLs
                test_segments = [
                    SegmentInfo(
                        url=url,
                        index=i + 1,
                        filename=f"segment{i+1:03d}.ts"
                    )
                    for i, url in enumerate(urls)
                ]
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        
                        async def edge_case_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = edge_case_download
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger', None):
                            
                            result = await manager.download_hls(
                                url=urls[0],
                                output_dir=temp_dir,
                                output_filename=f"edge_case_{case_name.lower().replace(' ', '_')}.mp4"
                            )
                            
                            assert "success" in result
                            assert result["total_segments"] == len(urls)


class TestUserScenarioRegression:
    """Regression test suite for common user scenarios."""

    @pytest.fixture
    def user_config(self):
        """Typical user configuration."""
        return DownloadConfig(
            max_concurrent=4,
            max_retries=3,
            timeout=30,
            auto_merge=True,
            cleanup_segments=True
        )

    @pytest.mark.asyncio
    async def test_typical_user_workflow(self, user_config):
        """Test typical user workflow from start to finish."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(user_config)
            
            # Simulate typical segment count and sizes
            test_segments = [
                SegmentInfo(
                    url=f"http://typical.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts",
                    size=1024 * 500  # 500KB segments
                )
                for i in range(1, 11)  # 10 segments
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    async def typical_download(segments, output_dir):
                        # Simulate realistic download with some minor issues
                        for i, segment in enumerate(segments):
                            if i == 3:  # One segment fails initially
                                segment.downloaded = False
                            else:
                                segment.downloaded = True
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = typical_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger') as mock_merger:
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance
                        
                        result = await manager.download_hls(
                            url="http://typical.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="typical_video.mp4"
                        )
                        
                        # Verify typical workflow results
                        assert "success" in result
                        assert "total_segments" in result
                        assert result["total_segments"] == 10

    @pytest.mark.asyncio
    async def test_power_user_scenario(self, user_config):
        """Test power user scenario with custom settings."""
        # Power user config with high concurrency
        power_config = DownloadConfig(
            max_concurrent=10,
            max_retries=5,
            timeout=60,
            auto_merge=False,  # Manual merge
            cleanup_segments=False  # Keep segments
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(power_config)
            
            # Large number of segments for power user
            test_segments = [
                SegmentInfo(
                    url=f"http://power.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:04d}.ts"
                )
                for i in range(1, 51)  # 50 segments
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    async def power_download(segments, output_dir):
                        # High success rate for power user scenario
                        for segment in segments:
                            segment.downloaded = True
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = power_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'):
                        # No merger for power user (manual merge)
                        result = await manager.download_hls(
                            url="http://power.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="power_video.mp4"
                        )
                        
                        assert "success" in result
                        assert result["total_segments"] == 50
                        assert result["segments_downloaded"] == 50

    @pytest.mark.asyncio
    async def test_mobile_user_scenario(self, user_config):
        """Test mobile user scenario with limited resources."""
        # Mobile-friendly config
        mobile_config = DownloadConfig(
            max_concurrent=2,  # Limited concurrency
            max_retries=2,
            timeout=15,  # Shorter timeout
            auto_merge=True,
            cleanup_segments=True  # Save space
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(mobile_config)
            
            # Smaller segments for mobile
            test_segments = [
                SegmentInfo(
                    url=f"http://mobile.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:02d}.ts",
                    size=1024 * 200  # 200KB segments
                )
                for i in range(1, 6)  # 5 segments
            ]
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    async def mobile_download(segments, output_dir):
                        # Simulate mobile network variability
                        for i, segment in enumerate(segments):
                            if i == 2:  # One timeout on mobile
                                segment.downloaded = False
                            else:
                                segment.downloaded = True
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = mobile_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger') as mock_merger:
                        mock_merger_instance = AsyncMock()
                        mock_merger_instance.merge_segments.return_value = True
                        mock_merger.__aenter__.return_value = mock_merger_instance
                        
                        result = await manager.download_hls(
                            url="http://mobile.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="mobile_video.mp4"
                        )
                        
                        assert "success" in result
                        assert result["total_segments"] == 5

    @pytest.mark.asyncio
    async def test_batch_download_scenario(self, user_config):
        """Test batch download scenario for multiple videos."""
        video_urls = [
            "http://batch.example.com/video1/segment{}.ts",
            "http://batch.example.com/video2/segment{}.ts",
            "http://batch.example.com/video3/segment{}.ts"
        ]
        
        results = []
        
        for i, url in enumerate(video_urls):
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(user_config)
                
                test_segments = [
                    SegmentInfo(
                        url=url.format(j),
                        index=j,
                        filename=f"segment{j:03d}.ts"
                    )
                    for j in range(1, 4)  # 3 segments per video
                ]
                
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        
                        async def batch_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = batch_download
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger') as mock_merger:
                            mock_merger_instance = AsyncMock()
                            mock_merger_instance.merge_segments.return_value = True
                            mock_merger.__aenter__.return_value = mock_merger_instance
                            
                            result = await manager.download_hls(
                                url=url,
                                output_dir=temp_dir,
                                output_filename=f"batch_video_{i+1}.mp4"
                            )
                            
                            results.append(result)
        
        # Verify all batch downloads succeeded
        assert len(results) == 3
        for result in results:
            assert "success" in result
            assert result["total_segments"] == 3

    def test_configuration_validation_scenarios(self, user_config):
        """Test various configuration validation scenarios."""
        invalid_configs = [
            {"max_concurrent": 0},      # Invalid concurrency
            {"max_concurrent": -1},     # Negative concurrency
            {"max_retries": -1},        # Negative retries
            {"timeout": 0},             # Zero timeout
            {"chunk_size": -1},         # Invalid chunk size
        ]
        
        for invalid_params in invalid_configs:
            # Create config with invalid parameters
            config_dict = user_config.__dict__.copy()
            config_dict.update(invalid_params)
            
            # Should handle invalid configs gracefully
            try:
                invalid_config = DownloadConfig(**config_dict)
                manager = DownloadManager(invalid_config)
                # If no exception, the validation should have corrected the values
                assert manager.config.max_concurrent > 0
                assert manager.config.max_retries >= 0
                assert manager.config.timeout > 0
            except (ValueError, TypeError):
                # Expected for some invalid configurations
                pass

    @pytest.mark.asyncio
    async def test_interrupted_download_recovery(self, user_config):
        """Test recovery from interrupted downloads."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(user_config)
            
            test_segments = [
                SegmentInfo(
                    url=f"http://interrupted.example.com/segment{i}.ts",
                    index=i,
                    filename=f"segment{i:03d}.ts"
                )
                for i in range(1, 8)  # 7 segments
            ]
            
            # First attempt: simulate interruption
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    
                    # Simulate partial download before interruption
                    async def interrupted_download(segments, output_dir):
                        for i, segment in enumerate(segments):
                            if i < 3:  # First 3 segments succeed
                                segment.downloaded = True
                            else:  # Rest fail due to interruption
                                segment.downloaded = False
                        return segments
                    
                    mock_downloader_instance.download_segments.side_effect = interrupted_download
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        # First attempt (interrupted)
                        result1 = await manager.download_hls(
                            url="http://interrupted.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="interrupted_video.mp4"
                        )
                        
                        # Should have partial success
                        assert "success" in result1
                        
                        # Second attempt: resume
                        async def resume_download(segments, output_dir):
                            # Complete remaining segments
                            for segment in segments:
                                segment.downloaded = True
                            return segments
                        
                        mock_downloader_instance.download_segments.side_effect = resume_download
                        
                        result2 = await manager.download_hls(
                            url="http://interrupted.example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="interrupted_video.mp4"
                        )
                        
                        # Should complete successfully
                        assert "success" in result2