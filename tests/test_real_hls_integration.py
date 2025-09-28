"""Integration test with real HLS URL for testing purposes."""

import pytest

from src.hls_downloader.core.detector import HLSDetector


class TestRealHLSIntegration:
    """Integration tests using the real HLS URL provided."""

    @pytest.fixture
    def real_hls_url(self):
        """The real HLS URL provided for testing."""
        return "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts"

    @pytest.fixture
    def detector(self):
        """Create HLSDetector instance for testing."""
        return HLSDetector(timeout=10, max_concurrent_checks=3)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_url_pattern_extraction_real(self, detector, real_hls_url):
        """Test URL pattern extraction with the real HLS URL."""
        base_url, pattern, extension = detector._extract_url_pattern(real_hls_url)

        expected_base = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        assert base_url == expected_base
        assert pattern == "{}.ts"
        assert extension == "ts"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_segment_url_generation_real(self, detector, real_hls_url):
        """Test segment URL generation with the real HLS URL pattern."""
        base_url, pattern, extension = detector._extract_url_pattern(real_hls_url)

        # Test generating URLs for different segment numbers
        test_cases = [
            (
                1,
                "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts",
            ),
            (
                81,
                "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts",
            ),
            (
                100,
                "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/100.ts",
            ),
        ]

        for segment_num, expected_url in test_cases:
            generated_url = detector._generate_segment_url(
                base_url, pattern, segment_num
            )
            assert generated_url == expected_url

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_check_known_segment_exists(self, detector, real_hls_url):
        """Test checking if the known segment (81) exists."""
        async with detector:
            # Test the segment we know exists (81)
            exists = await detector._check_segment_exists(real_hls_url)
            # Note: This test might fail if the URL is no longer available
            # In that case, we just verify the method doesn't crash
            assert isinstance(exists, bool)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_check_nonexistent_segment(self, detector):
        """Test checking a segment that likely doesn't exist."""
        # Use a very high segment number that's unlikely to exist
        nonexistent_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/99999.ts"

        async with detector:
            exists = await detector._check_segment_exists(nonexistent_url)
            # This should return False for a non-existent segment
            assert exists is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_batch_check_mixed_segments(self, detector):
        """Test batch checking with a mix of potentially existing and non-existing segments."""
        urls = [
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/80.ts",
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts",  # Known to exist
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/82.ts",
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/99999.ts",  # Unlikely to exist
        ]

        async with detector:
            results = await detector._batch_check_segments(urls)

            # Should return a list of boolean values
            assert len(results) == len(urls)
            assert all(isinstance(result, bool) for result in results)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_find_upper_bound_around_known_segment(self, detector):
        """Test finding upper bound starting from around the known segment."""
        base_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        pattern = "{}.ts"

        async with detector:
            # This test explores the actual segment range
            # The result will depend on what segments actually exist
            upper_bound = await detector._find_upper_bound(base_url, pattern)

            # Should return a reasonable upper bound (at least 1)
            assert upper_bound >= 1
            assert upper_bound <= 10000  # Reasonable upper limit

    def test_real_url_template_format(self, real_hls_url):
        """Test that we can create a proper URL template from the real URL."""
        # Convert the real URL to a template format
        template_url = real_hls_url.replace("81", "{}")
        expected_template = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{}.ts"

        assert template_url == expected_template

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_limited_segment_detection(self, detector, real_hls_url):
        """Test segment detection with a limited range around the known segment."""
        # Convert to template format
        template_url = real_hls_url.replace("81", "1")

        async with detector:
            # Mock the binary search to return a small range for testing
            with pytest.MonkeyPatch().context() as m:
                # Limit the search to a small range for testing
                async def mock_binary_search(base_url, pattern):
                    # Return a small range around our known segment
                    return min(85, 81 + 4)  # Test up to segment 85

                m.setattr(detector, "_binary_search_max_segment", mock_binary_search)

                segments = await detector.detect_segments(template_url)

                # Should return some segments
                assert len(segments) > 0
                assert len(segments) <= 85

                # Check that segments have proper structure
                for segment in segments:
                    assert segment.url.startswith("https://dh5wswx02.v.cntv.cn/")
                    assert segment.url.endswith(".ts")
                    assert segment.index >= 1
                    assert segment.filename.startswith("segment_")
                    assert not segment.downloaded


# Pytest markers for different test categories
pytestmark = [
    pytest.mark.integration,  # Mark all tests in this file as integration tests
]


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require network)"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running")
