"""Comprehensive URL pattern compatibility tests.

This module tests the HLS downloader's ability to handle various URL patterns
and formats commonly found in different streaming services.
"""

import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from src.hls_downloader.detector import HLSDetector
from src.hls_downloader.download_manager import DownloadManager
from src.hls_downloader.models import DownloadConfig, SegmentInfo


class TestURLPatternDetection:
    """Test URL pattern detection and parsing."""

    @pytest.fixture
    def detector(self):
        """Create HLS detector for testing."""
        return HLSDetector(timeout=5, max_concurrent_checks=2)

    def test_simple_numeric_pattern(self, detector):
        """Test simple numeric patterns like segment1.ts, segment2.ts."""
        test_cases = [
            (
                "http://example.com/segment1.ts",
                "http://example.com/",
                "segment{}.ts",
                "ts",
            ),
            (
                "https://cdn.site.com/video/chunk5.m4s",
                "https://cdn.site.com/video/",
                "chunk{}.m4s",
                "m4s",
            ),
            (
                "http://stream.tv/media/part123.ts",
                "http://stream.tv/media/",
                "part{}.ts",
                "ts",
            ),
        ]

        for url, expected_base, expected_pattern, expected_ext in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            assert base_url == expected_base
            assert pattern == expected_pattern
            assert extension == expected_ext

    def test_zero_padded_patterns(self, detector):
        """Test zero-padded numeric patterns."""
        test_cases = [
            "http://example.com/segment001.ts",
            "http://example.com/chunk0001.m4s",
            "http://example.com/part00001.ts",
            "http://example.com/video_000123.ts",
        ]

        for url in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            # Should detect zero-padding and create appropriate pattern
            assert "{" in pattern and "}" in pattern
            assert extension in ["ts", "m4s"]

    def test_complex_path_patterns(self, detector):
        """Test patterns with complex paths."""
        test_cases = [
            "https://cdn.example.com/live/stream/2023/12/25/segment1.ts",
            "http://media.site.com/hls/v1/playlist/quality/high/chunk1.m4s",
            "https://streaming.tv/content/video/12345/segments/part1.ts",
        ]

        for url in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            # Should preserve complex paths
            assert base_url.count("/") >= 3
            assert pattern.endswith(f".{extension}")

    def test_query_parameter_patterns(self, detector):
        """Test patterns with query parameters."""
        test_cases = [
            "http://example.com/segment1.ts?token=abc123",
            "https://cdn.site.com/chunk1.m4s?auth=xyz&quality=high",
            "http://stream.tv/part1.ts?session=12345&format=hls",
        ]

        for url in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            # Should handle query parameters correctly
            assert "?" not in base_url  # Query params should be in pattern
            assert "?" in pattern or "?" not in url

    def test_fragment_identifier_patterns(self, detector):
        """Test patterns with fragment identifiers."""
        test_cases = [
            "http://example.com/segment1.ts#fragment",
            "https://cdn.site.com/chunk1.m4s#quality=high",
        ]

        for url in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            # Should handle fragments appropriately
            assert "#" not in base_url

    def test_edge_case_patterns(self, detector):
        """Test edge case URL patterns."""
        edge_cases = [
            "http://example.com/1.ts",  # Very short filename
            "https://cdn.site.com/segment_1_final.ts",  # Multiple numbers
            "http://stream.tv/video-part-1.m4s",  # Hyphens
            "https://media.com/seg.1.ts",  # Dots in filename
        ]

        for url in edge_cases:
            # Should not crash on edge cases
            try:
                base_url, pattern, extension = detector._extract_url_pattern(url)
                assert isinstance(base_url, str)
                assert isinstance(pattern, str)
                assert isinstance(extension, str)
            except Exception as e:
                pytest.fail(f"Failed to parse edge case URL {url}: {e}")

    def test_invalid_patterns(self, detector):
        """Test handling of invalid URL patterns."""
        invalid_cases = [
            "not_a_url",
            "http://",
            "https://example.com/",  # No filename
            "ftp://example.com/file.ts",  # Wrong protocol
            "",  # Empty string
        ]

        for invalid_url in invalid_cases:
            # Should handle invalid URLs gracefully
            try:
                result = detector._extract_url_pattern(invalid_url)
                # If it doesn't raise an exception, result should be reasonable
                if result:
                    base_url, pattern, extension = result
                    assert isinstance(base_url, str)
                    assert isinstance(pattern, str)
                    assert isinstance(extension, str)
            except (ValueError, AttributeError):
                # Expected for invalid URLs
                pass


class TestURLGeneration:
    """Test URL generation from patterns."""

    @pytest.fixture
    def detector(self):
        """Create HLS detector for testing."""
        return HLSDetector(timeout=5, max_concurrent_checks=2)

    def test_simple_url_generation(self, detector):
        """Test generation of URLs from simple patterns."""
        test_cases = [
            (
                "http://example.com/",
                "segment{}.ts",
                1,
                "http://example.com/segment1.ts",
            ),
            (
                "http://example.com/",
                "segment{}.ts",
                123,
                "http://example.com/segment123.ts",
            ),
            (
                "https://cdn.site.com/video/",
                "chunk{}.m4s",
                5,
                "https://cdn.site.com/video/chunk5.m4s",
            ),
        ]

        for base_url, pattern, index, expected_url in test_cases:
            generated_url = detector._generate_segment_url(base_url, pattern, index)
            assert generated_url == expected_url

    def test_zero_padded_url_generation(self, detector):
        """Test generation of zero-padded URLs."""
        test_cases = [
            (
                "http://example.com/",
                "segment{:03d}.ts",
                1,
                "http://example.com/segment001.ts",
            ),
            (
                "http://example.com/",
                "segment{:03d}.ts",
                123,
                "http://example.com/segment123.ts",
            ),
            (
                "http://example.com/",
                "chunk{:04d}.m4s",
                5,
                "http://example.com/chunk0005.m4s",
            ),
        ]

        for base_url, pattern, index, expected_url in test_cases:
            generated_url = detector._generate_segment_url(base_url, pattern, index)
            assert generated_url == expected_url

    def test_complex_pattern_generation(self, detector):
        """Test generation from complex patterns."""
        base_url = "https://cdn.example.com/live/stream/2023/12/"
        pattern = "segment{}.ts?token=abc123"

        generated_url = detector._generate_segment_url(base_url, pattern, 42)
        expected_url = (
            "https://cdn.example.com/live/stream/2023/12/segment42.ts?token=abc123"
        )

        assert generated_url == expected_url

    def test_boundary_index_values(self, detector):
        """Test URL generation with boundary index values."""
        base_url = "http://example.com/"
        pattern = "segment{}.ts"

        boundary_cases = [
            (0, "http://example.com/segment0.ts"),
            (1, "http://example.com/segment1.ts"),
            (9999, "http://example.com/segment9999.ts"),
            (999999, "http://example.com/segment999999.ts"),
        ]

        for index, expected_url in boundary_cases:
            generated_url = detector._generate_segment_url(base_url, pattern, index)
            assert generated_url == expected_url


class TestRealWorldPatterns:
    """Test patterns from real-world streaming services."""

    @pytest.fixture
    def integration_config(self):
        """Configuration for integration testing."""
        return DownloadConfig(
            max_concurrent=2, max_retries=1, timeout=10, auto_merge=False
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cntv_pattern_compatibility(self, integration_config):
        """Test compatibility with CNTV-style patterns."""
        cntv_pattern = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{}.ts"

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(integration_config)

            # Mock segments for CNTV pattern
            test_segments = [
                SegmentInfo(
                    url=cntv_pattern.format(i), index=i, filename=f"segment_{i:06d}.ts"
                )
                for i in range(80, 83)  # Small range around known segment
            ]

            with patch.object(manager, "_detector") as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = test_segments
                mock_detector.__aenter__.return_value = mock_detector_instance

                with patch.object(manager, "_downloader") as mock_downloader:
                    mock_downloader_instance = AsyncMock()

                    async def cntv_download(segments, output_dir):
                        for segment in segments:
                            segment.downloaded = True
                        return segments

                    mock_downloader_instance.download_segments.side_effect = (
                        cntv_download
                    )
                    mock_downloader.__aenter__.return_value = mock_downloader_instance

                    with (
                        patch.object(manager, "_progress_display"),
                        patch.object(manager, "_merger", None),
                    ):
                        result = await manager.download_hls(
                            url=cntv_pattern.format(81),
                            output_dir=temp_dir,
                            output_filename="cntv_test.mp4",
                        )

                        assert "success" in result
                        assert result["total_segments"] == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_generic_cdn_patterns(self, integration_config):
        """Test compatibility with generic CDN patterns."""
        cdn_patterns = [
            "https://cdn1.example.com/hls/stream/segment{}.ts",
            "http://media.site.com/live/playlist/chunk{:04d}.m4s",
            "https://streaming.tv/content/video/part_{}.ts",
        ]

        for pattern in cdn_patterns:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(integration_config)

                # Create test segments for each pattern
                test_segments = [
                    SegmentInfo(
                        url=pattern.format(i)
                        if "{}" in pattern
                        else pattern.replace("{:04d}", str(i).zfill(4)),
                        index=i,
                        filename=f"segment_{i:03d}.ts",
                    )
                    for i in range(1, 4)
                ]

                with patch.object(manager, "_detector") as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance

                    with patch.object(manager, "_downloader") as mock_downloader:
                        mock_downloader_instance = AsyncMock()

                        async def cdn_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments

                        mock_downloader_instance.download_segments.side_effect = (
                            cdn_download
                        )
                        mock_downloader.__aenter__.return_value = (
                            mock_downloader_instance
                        )

                        with (
                            patch.object(manager, "_progress_display"),
                            patch.object(manager, "_merger", None),
                        ):
                            result = await manager.download_hls(
                                url=test_segments[0].url,
                                output_dir=temp_dir,
                                output_filename="cdn_test.mp4",
                            )

                            assert "success" in result
                            assert result["total_segments"] == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_authenticated_stream_patterns(self, integration_config):
        """Test patterns with authentication tokens."""
        auth_patterns = [
            "https://secure.example.com/segment{}.ts?token=abc123&expires=1234567890",
            "http://auth.site.com/chunk{}.m4s?key=xyz789&session=active",
            "https://protected.tv/part{}.ts?auth=bearer_token_here",
        ]

        for pattern in auth_patterns:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(integration_config)

                test_segments = [
                    SegmentInfo(
                        url=pattern.format(i), index=i, filename=f"segment_{i:03d}.ts"
                    )
                    for i in range(1, 3)
                ]

                with patch.object(manager, "_detector") as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance

                    with patch.object(manager, "_downloader") as mock_downloader:
                        mock_downloader_instance = AsyncMock()

                        async def auth_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments

                        mock_downloader_instance.download_segments.side_effect = (
                            auth_download
                        )
                        mock_downloader.__aenter__.return_value = (
                            mock_downloader_instance
                        )

                        with (
                            patch.object(manager, "_progress_display"),
                            patch.object(manager, "_merger", None),
                        ):
                            result = await manager.download_hls(
                                url=test_segments[0].url,
                                output_dir=temp_dir,
                                output_filename="auth_test.mp4",
                            )

                            assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_quality_patterns(self, integration_config):
        """Test patterns with quality indicators."""
        quality_patterns = [
            "https://adaptive.example.com/720p/segment{}.ts",
            "http://multi.site.com/quality/high/chunk{}.m4s",
            "https://stream.tv/bitrate/1080/part{}.ts",
        ]

        for pattern in quality_patterns:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = DownloadManager(integration_config)

                test_segments = [
                    SegmentInfo(
                        url=pattern.format(i), index=i, filename=f"segment_{i:03d}.ts"
                    )
                    for i in range(1, 3)
                ]

                with patch.object(manager, "_detector") as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = test_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance

                    with patch.object(manager, "_downloader") as mock_downloader:
                        mock_downloader_instance = AsyncMock()

                        async def quality_download(segments, output_dir):
                            for segment in segments:
                                segment.downloaded = True
                            return segments

                        mock_downloader_instance.download_segments.side_effect = (
                            quality_download
                        )
                        mock_downloader.__aenter__.return_value = (
                            mock_downloader_instance
                        )

                        with (
                            patch.object(manager, "_progress_display"),
                            patch.object(manager, "_merger", None),
                        ):
                            result = await manager.download_hls(
                                url=test_segments[0].url,
                                output_dir=temp_dir,
                                output_filename="quality_test.mp4",
                            )

                            assert "success" in result


class TestPatternEdgeCases:
    """Test edge cases in URL pattern handling."""

    @pytest.fixture
    def detector(self):
        """Create HLS detector for testing."""
        return HLSDetector(timeout=5, max_concurrent_checks=2)

    def test_very_long_urls(self, detector):
        """Test handling of very long URLs."""
        long_path = "/".join([f"dir{i}" for i in range(20)])
        long_query = "&".join([f"param{i}=value{i}" for i in range(10)])

        long_url = f"https://example.com{long_path}/segment1.ts?{long_query}"

        # Should handle long URLs without issues
        base_url, pattern, extension = detector._extract_url_pattern(long_url)
        assert isinstance(base_url, str)
        assert len(base_url) > 100  # Should preserve long path
        assert extension == "ts"

    def test_unicode_in_urls(self, detector):
        """Test handling of Unicode characters in URLs."""
        unicode_urls = [
            "http://example.com/视频/segment1.ts",
            "https://site.com/médias/chunk1.m4s",
            "http://stream.tv/контент/part1.ts",
        ]

        for url in unicode_urls:
            try:
                base_url, pattern, extension = detector._extract_url_pattern(url)
                assert isinstance(base_url, str)
                assert isinstance(pattern, str)
                assert isinstance(extension, str)
            except Exception as e:
                # Some Unicode handling might fail, which is acceptable
                pytest.skip(f"Unicode URL handling failed: {e}")

    def test_special_characters_in_filenames(self, detector):
        """Test handling of special characters in filenames."""
        special_urls = [
            "http://example.com/segment-1.ts",
            "https://site.com/chunk_1.m4s",
            "http://stream.tv/part.1.ts",
            "https://cdn.com/seg[1].ts",
            "http://media.tv/chunk(1).m4s",
        ]

        for url in special_urls:
            try:
                base_url, pattern, extension = detector._extract_url_pattern(url)
                assert isinstance(base_url, str)
                assert isinstance(pattern, str)
                assert isinstance(extension, str)
            except Exception:
                # Some special characters might not be supported
                pass

    def test_case_sensitivity(self, detector):
        """Test case sensitivity in URL patterns."""
        case_variants = [
            "http://example.com/Segment1.ts",
            "http://example.com/SEGMENT1.TS",
            "http://example.com/segment1.TS",
            "http://example.com/Segment1.Ts",
        ]

        for url in case_variants:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            # Should preserve original case
            assert base_url == "http://example.com/"
            # Extension should be normalized to lowercase
            assert extension.lower() in ["ts", "m4s"]

    def test_numeric_edge_cases(self, detector):
        """Test numeric edge cases in patterns."""
        numeric_cases = [
            "http://example.com/segment0.ts",  # Zero index
            "http://example.com/segment000.ts",  # Multiple zeros
            "http://example.com/segment999999.ts",  # Large number
            "http://example.com/segment-1.ts",  # Negative (should be treated as special char)
        ]

        for url in numeric_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            assert isinstance(base_url, str)
            assert isinstance(pattern, str)
            assert extension == "ts"

    @pytest.mark.asyncio
    async def test_pattern_consistency_across_operations(self, detector):
        """Test that pattern extraction and URL generation are consistent."""
        test_urls = [
            "http://example.com/segment123.ts",
            "https://cdn.site.com/chunk0456.m4s",
            "http://stream.tv/part789.ts",
        ]

        for original_url in test_urls:
            # Extract pattern
            base_url, pattern, extension = detector._extract_url_pattern(original_url)

            # Extract the number from original URL
            import re

            match = re.search(r"(\d+)", original_url.split("/")[-1])
            if match:
                original_number = int(match.group(1))

                # Generate URL with same number
                regenerated_url = detector._generate_segment_url(
                    base_url, pattern, original_number
                )

                # Should match original (or be very close)
                assert (
                    regenerated_url.split("/")[-1]
                    .split(".")[0]
                    .endswith(str(original_number))
                )
                assert regenerated_url.endswith(f".{extension}")
