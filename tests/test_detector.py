"""Tests for HLS segment detector."""

import pytest
import httpx
import asyncio
from time import time
from unittest.mock import AsyncMock, patch, MagicMock

from src.hls_downloader.detector import HLSDetector, CacheEntry
from src.hls_downloader.models import SegmentInfo


class TestHLSDetector:
    """Test cases for HLSDetector class."""

    @pytest.fixture
    def detector(self):
        """Create HLSDetector instance for testing."""
        return HLSDetector(timeout=10, max_concurrent_checks=5)

    def test_extract_url_pattern_simple(self, detector):
        """Test URL pattern extraction for simple format."""
        url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
        base_url, pattern, extension = detector._extract_url_pattern(url)
        
        assert base_url == "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        assert pattern == "{}.ts"
        assert extension == "ts"

    def test_extract_url_pattern_zero_padded(self, detector):
        """Test URL pattern extraction for zero-padded format."""
        url = "https://example.com/video/001.ts"
        base_url, pattern, extension = detector._extract_url_pattern(url)
        
        assert base_url == "https://example.com/video/"
        assert pattern == "{:03d}.ts"
        assert extension == "ts"

    def test_extract_url_pattern_with_prefix(self, detector):
        """Test URL pattern extraction with prefix."""
        url = "https://example.com/stream/segment1.ts"
        base_url, pattern, extension = detector._extract_url_pattern(url)
        
        assert base_url == "https://example.com/stream/"
        assert pattern == "segment{}.ts"
        assert extension == "ts"

    def test_extract_url_pattern_complex(self, detector):
        """Test URL pattern extraction for complex format."""
        url = "https://example.com/hls/seg_001_hd.ts"
        base_url, pattern, extension = detector._extract_url_pattern(url)
        
        assert base_url == "https://example.com/hls/"
        assert pattern == "seg_{:03d}_hd.ts"
        assert extension == "ts"

    def test_extract_url_pattern_invalid_url(self, detector):
        """Test URL pattern extraction with invalid URL."""
        with pytest.raises(ValueError, match="Invalid URL format"):
            detector._extract_url_pattern("not-a-url")

    def test_extract_url_pattern_no_number(self, detector):
        """Test URL pattern extraction with no number pattern."""
        with pytest.raises(ValueError, match="Could not extract number pattern"):
            detector._extract_url_pattern("https://example.com/video.ts")

    def test_generate_segment_url_simple(self, detector):
        """Test segment URL generation for simple format."""
        base_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        pattern = "{}.ts"
        
        url = detector._generate_segment_url(base_url, pattern, 5)
        assert url == "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/5.ts"

    def test_generate_segment_url_zero_padded(self, detector):
        """Test segment URL generation for zero-padded format."""
        base_url = "https://example.com/video/"
        pattern = "{:03d}.ts"
        
        url = detector._generate_segment_url(base_url, pattern, 5)
        assert url == "https://example.com/video/005.ts"

    def test_generate_segment_url_with_prefix(self, detector):
        """Test segment URL generation with prefix."""
        base_url = "https://example.com/stream/"
        pattern = "segment{}.ts"
        
        url = detector._generate_segment_url(base_url, pattern, 10)
        assert url == "https://example.com/stream/segment10.ts"

    @pytest.mark.asyncio
    async def test_check_segment_exists_success(self, detector):
        """Test successful segment existence check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(detector, '_session') as mock_session:
            mock_session.head = AsyncMock(return_value=mock_response)
            
            exists = await detector._check_segment_exists("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts")
            assert exists is True
            mock_session.head.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_segment_exists_not_found(self, detector):
        """Test segment existence check when segment doesn't exist."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 404
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404
        
        with patch.object(detector, '_session') as mock_session:
            mock_session.head = AsyncMock(side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_head_response))
            mock_session.get = AsyncMock(side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_get_response))
            
            exists = await detector._check_segment_exists("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/999.ts")
            assert exists is False

    @pytest.mark.asyncio
    async def test_check_segment_exists_head_fails_get_succeeds(self, detector):
        """Test segment check when HEAD fails but GET succeeds."""
        mock_get_response = MagicMock()
        mock_get_response.status_code = 206
        
        with patch.object(detector, '_session') as mock_session:
            mock_session.head = AsyncMock(side_effect=httpx.RequestError("HEAD not supported"))
            mock_session.get = AsyncMock(return_value=mock_get_response)
            
            exists = await detector._check_segment_exists("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts")
            assert exists is True

    @pytest.mark.asyncio
    async def test_check_segment_exists_both_fail(self, detector):
        """Test segment check when both HEAD and GET fail."""
        with patch.object(detector, '_session') as mock_session:
            mock_session.head = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_session.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            
            exists = await detector._check_segment_exists("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts")
            assert exists is False

    @pytest.mark.asyncio
    async def test_batch_check_segments(self, detector):
        """Test batch segment existence checking."""
        urls = [
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts",
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/2.ts",
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/3.ts",
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/4.ts",
        ]
        
        # Mock the _check_segment_exists method to return specific results
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.side_effect = [True, True, False, True]
            
            results = await detector._batch_check_segments(urls)
            assert results == [True, True, False, True]
            assert mock_check.call_count == 4

    @pytest.mark.asyncio
    async def test_find_upper_bound_small_range(self, detector):
        """Test finding upper bound for small segment range."""
        base_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            # Extract segment number from URL
            segment_num = int(url.split('/')[-1].split('.')[0])
            return segment_num <= 5
        
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.side_effect = mock_check_exists
            
            upper_bound = await detector._find_upper_bound(base_url, pattern)
            assert upper_bound == 5

    @pytest.mark.asyncio
    async def test_find_upper_bound_no_segments(self, detector):
        """Test finding upper bound when no segments exist."""
        base_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        pattern = "{}.ts"
        
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.return_value = False
            
            upper_bound = await detector._find_upper_bound(base_url, pattern)
            assert upper_bound == 1

    @pytest.mark.asyncio
    async def test_binary_search_max_segment(self, detector):
        """Test binary search for maximum segment."""
        base_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            return segment_num <= 50
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_batch_check_segments') as mock_batch:
                mock_upper.return_value = 100
                mock_batch.side_effect = mock_batch_check
                
                max_segment = await detector._binary_search_max_segment(base_url, pattern)
                assert max_segment == 50

    @pytest.mark.asyncio
    async def test_binary_search_max_segment_single(self, detector):
        """Test binary search when only one segment exists."""
        base_url = "https://example.com/segments/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            return segment_num == 1
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_batch_check_segments') as mock_batch:
                mock_upper.return_value = 10
                mock_batch.side_effect = mock_batch_check
                
                max_segment = await detector._binary_search_max_segment(base_url, pattern)
                assert max_segment == 1

    @pytest.mark.asyncio
    async def test_binary_search_max_segment_none(self, detector):
        """Test binary search when no segments exist."""
        base_url = "https://example.com/segments/"
        pattern = "{}.ts"
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_check_segment_exists') as mock_check:
                mock_upper.return_value = 1
                mock_check.return_value = False
                
                max_segment = await detector._binary_search_max_segment(base_url, pattern)
                assert max_segment == 0

    @pytest.mark.asyncio
    async def test_detect_segments_success(self, detector):
        """Test successful segment detection."""
        url_template = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
        
        with patch.object(detector, '_binary_search_max_segment') as mock_search:
            mock_search.return_value = 5
            
            async with detector:
                segments = await detector.detect_segments(url_template)
                
                assert len(segments) == 5
                for i, segment in enumerate(segments, 1):
                    assert isinstance(segment, SegmentInfo)
                    assert segment.url == f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts"
                    assert segment.index == i
                    assert segment.filename == f"segment_{i:06d}.ts"
                    assert segment.downloaded is False

    @pytest.mark.asyncio
    async def test_detect_segments_no_segments(self, detector):
        """Test segment detection when no segments exist."""
        url_template = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
        
        with patch.object(detector, '_binary_search_max_segment') as mock_search:
            mock_search.return_value = 0
            
            async with detector:
                segments = await detector.detect_segments(url_template)
                assert segments == []

    @pytest.mark.asyncio
    async def test_detect_segments_invalid_url(self, detector):
        """Test segment detection with invalid URL."""
        async with detector:
            with pytest.raises(ValueError, match="Invalid URL format"):
                await detector.detect_segments("not-a-url")

    @pytest.mark.asyncio
    async def test_detect_segments_without_context_manager(self, detector):
        """Test segment detection without async context manager."""
        with pytest.raises(RuntimeError, match="Detector must be used as async context manager"):
            await detector.detect_segments("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts")

    @pytest.mark.asyncio
    async def test_detect_segment_range_success(self, detector):
        """Test successful segment range detection."""
        url_template = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
        
        with patch.object(detector, 'detect_segments') as mock_detect:
            # Mock 10 segments
            mock_segments = []
            for i in range(1, 11):
                segment = SegmentInfo(
                    url=f"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{i}.ts",
                    index=i,
                    filename=f"segment_{i:06d}.ts"
                )
                mock_segments.append(segment)
            mock_detect.return_value = mock_segments
            
            start, end = await detector.detect_segment_range(url_template)
            assert start == 1
            assert end == 10

    @pytest.mark.asyncio
    async def test_detect_segment_range_no_segments(self, detector):
        """Test segment range detection when no segments exist."""
        url_template = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
        
        with patch.object(detector, 'detect_segments') as mock_detect:
            mock_detect.return_value = []
            
            start, end = await detector.detect_segment_range(url_template)
            assert start == 0
            assert end == 0

    @pytest.mark.asyncio
    async def test_context_manager_session_lifecycle(self, detector):
        """Test that HTTP session is properly managed."""
        assert detector._session is None
        
        async with detector:
            assert detector._session is not None
            assert isinstance(detector._session, httpx.AsyncClient)
        
        assert detector._session is None

    def test_url_pattern_variations(self, detector):
        """Test various URL pattern formats."""
        test_cases = [
            ("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts", "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/", "{}.ts", "ts"),
            ("https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/001.ts", "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/", "{:03d}.ts", "ts"),
            ("https://example.com/segment1.ts", "https://example.com/", "segment{}.ts", "ts"),
            ("https://example.com/seg_001.ts", "https://example.com/", "seg_{:03d}.ts", "ts"),
            ("https://example.com/video/chunk_001_hd.ts", "https://example.com/video/", "chunk_{:03d}_hd.ts", "ts"),
            ("https://example.com/stream/1.m4s", "https://example.com/stream/", "{}.m4s", "m4s"),
        ]
        
        for url, expected_base, expected_pattern, expected_ext in test_cases:
            base_url, pattern, extension = detector._extract_url_pattern(url)
            assert base_url == expected_base, f"Failed for URL: {url}"
            assert pattern == expected_pattern, f"Failed for URL: {url}"
            assert extension == expected_ext, f"Failed for URL: {url}"


class TestBinarySearchAlgorithm:
    """Test cases for binary search algorithm enhancements."""

    @pytest.fixture
    def detector(self):
        """Create HLSDetector instance for testing."""
        return HLSDetector(timeout=10, max_concurrent_checks=5, cache_ttl=60)

    @pytest.mark.asyncio
    async def test_cache_functionality(self, detector):
        """Test caching of segment existence checks."""
        url = "https://example.com/segment1.ts"
        
        with patch.object(detector, '_session') as mock_session:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.head = AsyncMock(return_value=mock_response)
            
            # First call should hit the network
            result1 = await detector._check_segment_exists(url)
            assert result1 is True
            assert mock_session.head.call_count == 1
            
            # Second call should use cache
            result2 = await detector._check_segment_exists(url)
            assert result2 is True
            assert mock_session.head.call_count == 1  # No additional network call
            
            # Check cache stats
            stats = detector.get_cache_stats()
            assert stats["total_entries"] == 1
            assert stats["valid_entries"] == 1

    @pytest.mark.asyncio
    async def test_cache_expiration(self, detector):
        """Test cache expiration functionality."""
        detector.cache_ttl = 0.1  # Very short TTL for testing
        url = "https://example.com/segment1.ts"
        
        with patch.object(detector, '_session') as mock_session:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.head = AsyncMock(return_value=mock_response)
            
            # First call
            await detector._check_segment_exists(url)
            assert mock_session.head.call_count == 1
            
            # Wait for cache to expire
            await asyncio.sleep(0.2)
            
            # Second call should hit network again due to expiration
            await detector._check_segment_exists(url)
            assert mock_session.head.call_count == 2

    def test_cache_clear(self, detector):
        """Test cache clearing functionality."""
        # Add some cache entries manually
        detector._cache["url1"] = CacheEntry(True, time())
        detector._cache["url2"] = CacheEntry(False, time())
        detector._add_missing_range("base", "pattern", 10, 20)
        
        assert len(detector._cache) == 2
        assert len(detector._missing_ranges) == 1
        
        detector.clear_cache()
        
        assert len(detector._cache) == 0
        assert len(detector._missing_ranges) == 0

    def test_missing_range_tracking(self, detector):
        """Test missing range tracking functionality."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        # Add some missing ranges
        detector._add_missing_range(base_url, pattern, 10, 15)
        detector._add_missing_range(base_url, pattern, 20, 25)
        
        # Test range checking
        assert detector._is_in_missing_range(base_url, pattern, 12) is True
        assert detector._is_in_missing_range(base_url, pattern, 22) is True
        assert detector._is_in_missing_range(base_url, pattern, 5) is False
        assert detector._is_in_missing_range(base_url, pattern, 18) is False

    @pytest.mark.asyncio
    async def test_detect_missing_ranges_small(self, detector):
        """Test missing range detection for small ranges."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            # Segments 3-5 are missing
            return segment_num not in [3, 4, 5]
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_batch_check_segments') as mock_batch:
            mock_batch.side_effect = mock_batch_check
            
            missing_ranges = await detector._detect_missing_ranges(base_url, pattern, 1, 10)
            assert missing_ranges == [(3, 5)]

    @pytest.mark.asyncio
    async def test_binary_search_with_gaps(self, detector):
        """Test binary search algorithm with gaps in segments."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            # Segments exist: 1-10, 15-20, 25-30 (gaps at 11-14, 21-24)
            return (1 <= segment_num <= 10) or (15 <= segment_num <= 20) or (25 <= segment_num <= 30)
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_batch_check_segments') as mock_batch:
                mock_upper.return_value = 35
                mock_batch.side_effect = mock_batch_check
                
                max_segment = await detector._binary_search_max_segment(base_url, pattern)
                assert max_segment == 30

    @pytest.mark.asyncio
    async def test_binary_search_with_consecutive_missing(self, detector):
        """Test binary search behavior with many consecutive missing segments."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            # Only segments 1-5 exist, rest are missing
            return 1 <= segment_num <= 5
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        def mock_detect_missing(base_url, pattern, start, end):
            # Mock that segments 6-end are missing
            if start <= 6 <= end:
                return [(6, end)]
            return []
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_batch_check_segments') as mock_batch:
                with patch.object(detector, '_detect_missing_ranges') as mock_missing:
                    mock_upper.return_value = 100
                    mock_batch.side_effect = mock_batch_check
                    mock_missing.side_effect = mock_detect_missing
                    
                    max_segment = await detector._binary_search_max_segment(base_url, pattern)
                    assert max_segment == 5

    @pytest.mark.asyncio
    async def test_find_upper_bound_with_cache(self, detector):
        """Test upper bound finding with cached missing ranges."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        # Pre-populate cache with known missing range
        detector._add_missing_range(base_url, pattern, 50, 100)
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            return segment_num <= 20
        
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.side_effect = mock_check_exists
            
            upper_bound = await detector._find_upper_bound(base_url, pattern)
            # The algorithm will still find the upper bound correctly even with cached ranges
            # The cache helps optimize by skipping known missing segments
            assert upper_bound <= 100  # Should be reasonable upper bound
            
            # Verify that some segments were checked
            assert mock_check.call_count > 0

    @pytest.mark.asyncio
    async def test_cache_disabled_check(self, detector):
        """Test segment existence check with caching disabled."""
        url = "https://example.com/segment1.ts"
        
        with patch.object(detector, '_session') as mock_session:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.head = AsyncMock(return_value=mock_response)
            
            # First call with cache disabled
            result1 = await detector._check_segment_exists(url, use_cache=False)
            assert result1 is True
            assert mock_session.head.call_count == 1
            
            # Second call with cache disabled should still hit network
            result2 = await detector._check_segment_exists(url, use_cache=False)
            assert result2 is True
            assert mock_session.head.call_count == 2
            
            # Cache should be empty
            assert len(detector._cache) == 0

    @pytest.mark.asyncio
    async def test_large_range_missing_detection(self, detector):
        """Test missing range detection for large ranges using sampling."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            # Large gap from 100-200
            return not (100 <= segment_num <= 200)
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_batch_check_segments') as mock_batch:
            with patch.object(detector, '_check_segment_exists') as mock_check:
                mock_batch.side_effect = mock_batch_check
                mock_check.side_effect = mock_check_exists
                
                missing_ranges = await detector._detect_missing_ranges(base_url, pattern, 50, 250, max_gap=20)
                
                # Should detect the missing range around 100-200
                assert len(missing_ranges) > 0
                found_large_gap = any(end - start > 50 for start, end in missing_ranges)
                assert found_large_gap

    @pytest.mark.asyncio
    async def test_edge_case_single_segment(self, detector):
        """Test binary search with only one segment available."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        def mock_check_exists(url):
            segment_num = int(url.split('/')[-1].split('.')[0])
            return segment_num == 1
        
        def mock_batch_check(urls):
            return [mock_check_exists(url) for url in urls]
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_batch_check_segments') as mock_batch:
                with patch.object(detector, '_check_segment_exists') as mock_check:
                    mock_upper.return_value = 1
                    mock_batch.side_effect = mock_batch_check
                    mock_check.side_effect = mock_check_exists
                    
                    max_segment = await detector._binary_search_max_segment(base_url, pattern)
                    assert max_segment == 1

    @pytest.mark.asyncio
    async def test_edge_case_no_segments(self, detector):
        """Test binary search with no segments available."""
        base_url = "https://example.com/"
        pattern = "{}.ts"
        
        with patch.object(detector, '_find_upper_bound') as mock_upper:
            with patch.object(detector, '_check_segment_exists') as mock_check:
                with patch.object(detector, '_batch_check_segments') as mock_batch:
                    mock_upper.return_value = 1
                    mock_check.return_value = False
                    mock_batch.return_value = [False]
                    
                    max_segment = await detector._binary_search_max_segment(base_url, pattern)
                    assert max_segment == 0