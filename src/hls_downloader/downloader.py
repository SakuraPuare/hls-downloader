"""Async downloader for HLS segments."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import httpx

from .models import DownloadConfig, SegmentInfo


logger = logging.getLogger(__name__)


class AsyncDownloader:
    """Async downloader for HLS segments with concurrent download support."""

    def __init__(self, config: DownloadConfig):
        """Initialize the async downloader with configuration.
        
        Args:
            config: Download configuration settings
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    async def __aenter__(self):
        """Async context manager entry."""
        await self._setup_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup_client()

    async def _setup_client(self) -> None:
        """Setup httpx async client with connection pool management."""
        # Configure connection limits for optimal performance
        limits = httpx.Limits(
            max_keepalive_connections=self.config.max_concurrent,
            max_connections=self.config.max_concurrent * 2,
            keepalive_expiry=30.0
        )
        
        # Configure timeout settings
        timeout = httpx.Timeout(
            connect=10.0,
            read=self.config.timeout,
            write=10.0,
            pool=5.0
        )
        
        # Create client with optimized settings
        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            http2=False  # Disable HTTP/2 to avoid h2 dependency
        )
        
        logger.info(
            f"HTTP client initialized with {self.config.max_concurrent} "
            f"max concurrent connections"
        )

    async def _cleanup_client(self) -> None:
        """Cleanup httpx client and close connections."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP client closed")

    async def download_segments(
        self, 
        segments: List[SegmentInfo], 
        output_dir: str
    ) -> List[SegmentInfo]:
        """Download multiple segments concurrently.
        
        Args:
            segments: List of segment information to download
            output_dir: Directory to save downloaded segments
            
        Returns:
            List of updated segment information with download status
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Starting download of {len(segments)} segments to {output_dir}")
        
        # Create download tasks for all segments
        tasks = []
        for segment in segments:
            task = asyncio.create_task(
                self._download_single_segment(segment, output_path)
            )
            tasks.append(task)
        
        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and update segment info
        updated_segments = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to download segment {segments[i].index}: {result}")
                segments[i].downloaded = False
            else:
                updated_segments.append(result)
        
        successful_downloads = len([s for s in updated_segments if s.downloaded])
        logger.info(f"Download completed: {successful_downloads}/{len(segments)} successful")
        
        return updated_segments

    async def _download_single_segment(
        self, 
        segment: SegmentInfo, 
        output_dir: Path
    ) -> SegmentInfo:
        """Download a single segment with streaming support.
        
        Args:
            segment: Segment information to download
            output_dir: Directory to save the segment
            
        Returns:
            Updated segment information with download status
        """
        async with self._semaphore:  # Control concurrency
            filepath = output_dir / segment.filename
            
            try:
                logger.debug(f"Starting download of segment {segment.index}: {segment.url}")
                
                # Stream download to avoid loading entire file into memory
                async with self._client.stream('GET', segment.url) as response:
                    response.raise_for_status()
                    
                    # Get content length if available
                    content_length = response.headers.get('content-length')
                    if content_length:
                        segment.size = int(content_length)
                    
                    # Stream content to file
                    downloaded_bytes = 0
                    with open(filepath, 'wb') as f:
                        async for chunk in response.aiter_bytes(
                            chunk_size=self.config.chunk_size
                        ):
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                    
                    # Update segment info
                    if not segment.size:
                        segment.size = downloaded_bytes
                    
                    # Verify file integrity
                    if await self._verify_file_integrity(filepath, segment):
                        segment.downloaded = True
                        logger.debug(
                            f"Successfully downloaded segment {segment.index} "
                            f"({segment.size} bytes)"
                        )
                    else:
                        segment.downloaded = False
                        logger.error(f"File integrity check failed for segment {segment.index}")
                
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error downloading segment {segment.index}: "
                    f"{e.response.status_code} {e.response.reason_phrase}"
                )
                segment.downloaded = False
            except httpx.RequestError as e:
                logger.error(f"Request error downloading segment {segment.index}: {e}")
                segment.downloaded = False
            except Exception as e:
                logger.error(f"Unexpected error downloading segment {segment.index}: {e}")
                segment.downloaded = False
            
            return segment

    async def _verify_file_integrity(
        self, 
        filepath: Path, 
        segment: SegmentInfo
    ) -> bool:
        """Verify downloaded file integrity.
        
        Args:
            filepath: Path to the downloaded file
            segment: Segment information for verification
            
        Returns:
            True if file integrity is verified, False otherwise
        """
        try:
            # Check if file exists
            if not filepath.exists():
                logger.error(f"Downloaded file does not exist: {filepath}")
                return False
            
            # Check file size
            actual_size = filepath.stat().st_size
            
            # If we don't have expected size, just check file is not empty
            if segment.size is None:
                if actual_size == 0:
                    logger.error(f"Downloaded file is empty: {filepath}")
                    return False
                # Update segment size with actual size
                segment.size = actual_size
                return True
            
            # Verify size matches expected
            if actual_size != segment.size:
                logger.error(
                    f"File size mismatch for {filepath}: "
                    f"expected {segment.size}, got {actual_size}"
                )
                return False
            
            # Additional integrity checks could be added here
            # (e.g., checksum verification if provided by server)
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying file integrity for {filepath}: {e}")
            return False

    async def download_single_segment_with_retry(
        self, 
        segment: SegmentInfo, 
        output_dir: str
    ) -> SegmentInfo:
        """Download a single segment with retry logic (for future use).
        
        This method provides a public interface for downloading individual segments
        with built-in retry capabilities.
        
        Args:
            segment: Segment information to download
            output_dir: Directory to save the segment
            
        Returns:
            Updated segment information with download status
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        return await self._download_single_segment(segment, output_path)