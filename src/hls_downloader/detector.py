"""HLS segment detector for discovering available segments."""

import asyncio
import re
from typing import List, Tuple, Optional, Dict, Set
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from time import time

import httpx

from .models import SegmentInfo


@dataclass
class CacheEntry:
    """Cache entry for segment existence checks."""
    exists: bool
    timestamp: float
    
    def is_expired(self, ttl: int = 300) -> bool:
        """Check if cache entry is expired (default 5 minutes TTL)."""
        return time() - self.timestamp > ttl


class HLSDetector:
    """Detector for HLS segments using binary search optimization."""

    def __init__(self, timeout: int = 30, max_concurrent_checks: int = 20, cache_ttl: int = 300):
        """Initialize the HLS detector.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent_checks: Maximum concurrent segment existence checks
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.timeout = timeout
        self.max_concurrent_checks = max_concurrent_checks
        self.cache_ttl = cache_ttl
        self._session: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, CacheEntry] = {}
        self._missing_ranges: Dict[str, Set[Tuple[int, int]]] = {}  # Track known missing ranges

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_connections=self.max_concurrent_checks)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.aclose()
            self._session = None

    def _extract_url_pattern(self, url: str) -> Tuple[str, str, str]:
        """Extract URL pattern components from a template URL.
        
        Args:
            url: Template URL with segment number (e.g., "http://example.com/segment1.ts")
            
        Returns:
            Tuple of (base_url, number_pattern, extension)
            
        Raises:
            ValueError: If URL pattern cannot be parsed
        """
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError("Invalid URL format")

        # Parse URL components
        parsed = urlparse(url)
        path = parsed.path
        
        # Extract filename from path
        filename = path.split('/')[-1]
        base_path = '/'.join(path.split('/')[:-1])
        
        # Find number patterns in filename
        # Support various formats: 1.ts, 001.ts, segment1.ts, seg_001.ts, etc.
        number_patterns = [
            r'^([a-zA-Z_-]+)(\d+)([a-zA-Z_-]+)\.(\w+)$',  # Complex: seg_001_hd.ts
            r'^([a-zA-Z_-]+)(\d+)\.(\w+)$',  # With prefix: segment1.ts, seg_001.ts
            r'^(\d+)\.(\w+)$',  # Simple: 1.ts, 001.ts
        ]
        
        for pattern in number_patterns:
            match = re.match(pattern, filename)
            if match:
                groups = match.groups()
                if len(groups) == 2:  # Simple pattern: number.ext
                    number_str, extension = groups
                    prefix = ""
                    suffix = ""
                elif len(groups) == 3:  # With prefix: prefix+number.ext
                    prefix, number_str, extension = groups
                    suffix = ""
                else:  # Complex pattern: prefix+number+suffix.ext
                    prefix, number_str, suffix, extension = groups
                
                # Determine number format (zero-padded or not)
                number_width = len(number_str) if number_str.startswith('0') and len(number_str) > 1 else 0
                
                # Construct base URL
                base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}/"
                
                # Create pattern template
                if number_width > 0:
                    number_template = f"{{:0{number_width}d}}"
                else:
                    number_template = "{}"
                
                pattern_template = f"{prefix}{number_template}{suffix}.{extension}"
                
                return base_url, pattern_template, extension
        
        raise ValueError(f"Could not extract number pattern from URL: {url}")

    def _generate_segment_url(self, base_url: str, pattern: str, index: int) -> str:
        """Generate segment URL for given index.
        
        Args:
            base_url: Base URL without filename
            pattern: Pattern template with {} placeholder for number
            index: Segment index
            
        Returns:
            Complete segment URL
        """
        filename = pattern.format(index)
        return urljoin(base_url, filename)

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return url
    
    def _is_in_missing_range(self, base_url: str, pattern: str, index: int) -> bool:
        """Check if segment index is in a known missing range."""
        cache_key = f"{base_url}:{pattern}"
        if cache_key not in self._missing_ranges:
            return False
        
        for start, end in self._missing_ranges[cache_key]:
            if start <= index <= end:
                return True
        return False
    
    def _add_missing_range(self, base_url: str, pattern: str, start: int, end: int):
        """Add a range of missing segments to cache."""
        cache_key = f"{base_url}:{pattern}"
        if cache_key not in self._missing_ranges:
            self._missing_ranges[cache_key] = set()
        self._missing_ranges[cache_key].add((start, end))
    
    async def _check_segment_exists(self, url: str, use_cache: bool = True) -> bool:
        """Check if a single segment exists.
        
        Args:
            url: Segment URL to check
            use_cache: Whether to use cached results
            
        Returns:
            True if segment exists, False otherwise
        """
        if not self._session:
            raise RuntimeError("Detector must be used as async context manager")
        
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(url)
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if not entry.is_expired(self.cache_ttl):
                    return entry.exists
                else:
                    # Remove expired entry
                    del self._cache[cache_key]
        
        exists = False
        try:
            # Use HEAD request for efficiency
            response = await self._session.head(url)
            exists = response.status_code == 200
        except httpx.HTTPStatusError:
            exists = False
        except httpx.RequestError:
            # If HEAD fails, try GET with range request
            try:
                response = await self._session.get(url, headers={"Range": "bytes=0-0"})
                exists = response.status_code in (200, 206)
            except (httpx.RequestError, httpx.HTTPStatusError):
                exists = False
        
        # Cache the result
        if use_cache:
            cache_key = self._get_cache_key(url)
            self._cache[cache_key] = CacheEntry(exists=exists, timestamp=time())
        
        return exists

    async def _batch_check_segments(self, urls: List[str]) -> List[bool]:
        """Check multiple segments concurrently.
        
        Args:
            urls: List of segment URLs to check
            
        Returns:
            List of boolean values indicating existence
        """
        semaphore = asyncio.Semaphore(self.max_concurrent_checks)
        
        async def check_with_semaphore(url: str) -> bool:
            async with semaphore:
                return await self._check_segment_exists(url)
        
        tasks = [check_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _find_upper_bound(self, base_url: str, pattern: str) -> int:
        """Find upper bound for binary search using exponential search.
        
        Args:
            base_url: Base URL without filename
            pattern: Pattern template
            
        Returns:
            Upper bound for segment range
        """
        # Start with small values and exponentially increase
        test_values = [1, 10, 100, 1000, 10000, 100000]
        
        for i, value in enumerate(test_values):
            # Skip if we know this range is missing
            if self._is_in_missing_range(base_url, pattern, value):
                continue
                
            url = self._generate_segment_url(base_url, pattern, value)
            exists = await self._check_segment_exists(url)
            
            if not exists:
                # Found upper bound, return previous value or do binary search in range
                if i == 0:
                    return 1  # Even segment 1 doesn't exist
                
                # Binary search between previous and current value
                lower = test_values[i - 1]
                upper = value
                
                while lower < upper:
                    mid = (lower + upper + 1) // 2
                    
                    # Skip if in known missing range
                    if self._is_in_missing_range(base_url, pattern, mid):
                        upper = mid - 1
                        continue
                    
                    url = self._generate_segment_url(base_url, pattern, mid)
                    exists = await self._check_segment_exists(url)
                    
                    if exists:
                        lower = mid
                    else:
                        upper = mid - 1
                
                return lower
        
        # If all test values exist, do a more thorough search
        return test_values[-1]

    async def _detect_missing_ranges(self, base_url: str, pattern: str, start: int, end: int, max_gap: int = 10) -> List[Tuple[int, int]]:
        """Detect ranges of consecutive missing segments.
        
        Args:
            base_url: Base URL without filename
            pattern: Pattern template
            start: Start index to check
            end: End index to check
            max_gap: Maximum gap size to consider as consecutive missing
            
        Returns:
            List of (start, end) tuples representing missing ranges
        """
        if end - start + 1 <= max_gap:
            # For small ranges, check all segments
            urls = [self._generate_segment_url(base_url, pattern, i) for i in range(start, end + 1)]
            exists_list = await self._batch_check_segments(urls)
            
            missing_ranges = []
            range_start = None
            
            for i, exists in enumerate(exists_list):
                index = start + i
                if not exists:
                    if range_start is None:
                        range_start = index
                else:
                    if range_start is not None:
                        missing_ranges.append((range_start, index - 1))
                        range_start = None
            
            # Handle case where missing range extends to the end
            if range_start is not None:
                missing_ranges.append((range_start, end))
            
            return missing_ranges
        
        # For larger ranges, use sampling approach
        sample_size = min(max_gap, (end - start + 1) // 10)
        sample_indices = []
        
        # Sample evenly across the range
        for i in range(sample_size):
            index = start + (i * (end - start)) // (sample_size - 1) if sample_size > 1 else start
            sample_indices.append(index)
        
        sample_urls = [self._generate_segment_url(base_url, pattern, i) for i in sample_indices]
        exists_list = await self._batch_check_segments(sample_urls)
        
        missing_ranges = []
        for i, exists in enumerate(exists_list):
            if not exists:
                # Found a missing segment, explore around it
                index = sample_indices[i]
                range_start = index
                range_end = index
                
                # Expand backwards
                while range_start > start:
                    url = self._generate_segment_url(base_url, pattern, range_start - 1)
                    if await self._check_segment_exists(url):
                        break
                    range_start -= 1
                
                # Expand forwards
                while range_end < end:
                    url = self._generate_segment_url(base_url, pattern, range_end + 1)
                    if await self._check_segment_exists(url):
                        break
                    range_end += 1
                
                missing_ranges.append((range_start, range_end))
        
        return missing_ranges

    async def _binary_search_max_segment(self, base_url: str, pattern: str) -> int:
        """Find the maximum valid segment index using binary search with intelligent boundary handling.
        
        Args:
            base_url: Base URL without filename
            pattern: Pattern template
            
        Returns:
            Maximum valid segment index
        """
        # First, find upper bound
        upper_bound = await self._find_upper_bound(base_url, pattern)
        
        if upper_bound <= 1:
            # Check if segment 1 exists
            url = self._generate_segment_url(base_url, pattern, 1)
            exists = await self._check_segment_exists(url)
            return 1 if exists else 0
        
        # Binary search for exact maximum with intelligent boundary handling
        left, right = 1, upper_bound
        max_valid = 0
        consecutive_missing = 0
        max_consecutive_missing = 5  # Stop if we find this many consecutive missing segments
        
        while left <= right:
            mid = (left + right) // 2
            
            # Skip if we know this is in a missing range
            if self._is_in_missing_range(base_url, pattern, mid):
                right = mid - 1
                continue
            
            # Check a small batch around mid for better accuracy and gap detection
            batch_start = max(1, mid - 2)
            batch_end = min(upper_bound, mid + 2)
            batch_indices = list(range(batch_start, batch_end + 1))
            batch_urls = [
                self._generate_segment_url(base_url, pattern, i)
                for i in batch_indices
            ]
            
            exists_list = await self._batch_check_segments(batch_urls)
            mid_index = mid - batch_start
            
            if mid_index < len(exists_list) and exists_list[mid_index]:
                max_valid = mid
                left = mid + 1
                consecutive_missing = 0
                
                # Check for gaps in the batch and cache missing ranges
                missing_start = None
                for i, exists in enumerate(exists_list):
                    index = batch_indices[i]
                    if not exists:
                        if missing_start is None:
                            missing_start = index
                    else:
                        if missing_start is not None:
                            self._add_missing_range(base_url, pattern, missing_start, index - 1)
                            missing_start = None
                
                # Handle missing range at the end of batch
                if missing_start is not None:
                    self._add_missing_range(base_url, pattern, missing_start, batch_indices[-1])
                    
            else:
                right = mid - 1
                consecutive_missing += 1
                
                # If we've found many consecutive missing segments, we might be past the end
                if consecutive_missing >= max_consecutive_missing:
                    # Do a more thorough check to find the actual end
                    missing_ranges = await self._detect_missing_ranges(base_url, pattern, max(1, mid - 10), mid + 10)
                    for start, end in missing_ranges:
                        self._add_missing_range(base_url, pattern, start, end)
                    break
        
        return max_valid

    async def detect_segments(self, url_template: str) -> List[SegmentInfo]:
        """Detect all available HLS segments from a template URL.
        
        Args:
            url_template: Template URL with segment number
            
        Returns:
            List of SegmentInfo objects for available segments
            
        Raises:
            ValueError: If URL template is invalid
            RuntimeError: If detector is not properly initialized
        """
        if not self._session:
            raise RuntimeError("Detector must be used as async context manager")
        
        # Extract URL pattern
        base_url, pattern, extension = self._extract_url_pattern(url_template)
        
        # Find maximum segment index
        max_index = await self._binary_search_max_segment(base_url, pattern)
        
        if max_index == 0:
            return []
        
        # Generate segment info for all valid segments
        segments = []
        for i in range(1, max_index + 1):
            url = self._generate_segment_url(base_url, pattern, i)
            filename = f"segment_{i:06d}.{extension}"
            segment = SegmentInfo(
                url=url,
                index=i,
                filename=filename
            )
            segments.append(segment)
        
        return segments

    def clear_cache(self):
        """Clear the detection cache."""
        self._cache.clear()
        self._missing_ranges.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired(self.cache_ttl))
        missing_ranges_count = sum(len(ranges) for ranges in self._missing_ranges.values())
        
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "missing_ranges": missing_ranges_count
        }

    async def detect_segment_range(self, url_template: str) -> Tuple[int, int]:
        """Detect the range of available segments.
        
        Args:
            url_template: Template URL with segment number
            
        Returns:
            Tuple of (start_index, end_index) for available segments
        """
        segments = await self.detect_segments(url_template)
        if not segments:
            return 0, 0
        
        return segments[0].index, segments[-1].index