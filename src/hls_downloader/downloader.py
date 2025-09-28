"""Async downloader for HLS segments."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import httpx

from .error_handler import ErrorHandler, IntegrityError
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
        self._error_handler = ErrorHandler(
            max_retries=config.max_retries,
            base_delay=1.0
        )

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
                self._download_single_segment_with_retry(segment, output_path)
            )
            tasks.append(task)
        
        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and update segment info
        updated_segments = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Error was already logged by error handler
                segments[i].downloaded = False
                updated_segments.append(segments[i])
            else:
                updated_segments.append(result)
        
        successful_downloads = len([s for s in updated_segments if s.downloaded])
        logger.info(f"Download completed: {successful_downloads}/{len(segments)} successful")
        
        return updated_segments

    async def _download_single_segment_with_retry(
        self, 
        segment: SegmentInfo, 
        output_dir: Path
    ) -> SegmentInfo:
        """Download a single segment with retry and resume support.
        
        Args:
            segment: Segment information to download
            output_dir: Directory to save the segment
            
        Returns:
            Updated segment information with download status
        """
        async def download_operation():
            return await self._download_single_segment(segment, output_dir)
        
        return await self._error_handler.handle_with_retry(
            download_operation, segment
        )

    async def _download_single_segment(
        self, 
        segment: SegmentInfo, 
        output_dir: Path
    ) -> SegmentInfo:
        """Download a single segment with streaming and resume support.
        
        Args:
            segment: Segment information to download
            output_dir: Directory to save the segment
            
        Returns:
            Updated segment information with download status
            
        Raises:
            Various exceptions that will be handled by the error handler
        """
        async with self._semaphore:  # Control concurrency
            filepath = output_dir / segment.filename
            
            logger.debug(f"Starting download of segment {segment.index}: {segment.url}")
            
            # Check if file already exists (for resume support)
            resume_from = 0
            if filepath.exists():
                existing_size = filepath.stat().st_size
                if existing_size > 0:
                    logger.debug(f"Found partial file for segment {segment.index}, resuming from byte {existing_size}")
                    resume_from = existing_size
            
            # Prepare headers for resume support
            headers = {}
            if resume_from > 0:
                headers['Range'] = f'bytes={resume_from}-'
            
            # Stream download to avoid loading entire file into memory
            async with self._client.stream('GET', segment.url, headers=headers) as response:
                response.raise_for_status()
                
                # Handle partial content response
                if resume_from > 0 and response.status_code == 206:
                    logger.debug(f"Server supports resume for segment {segment.index}")
                    file_mode = 'ab'  # Append mode for resume
                elif resume_from > 0 and response.status_code == 200:
                    logger.debug(f"Server doesn't support resume for segment {segment.index}, restarting download")
                    file_mode = 'wb'  # Overwrite mode
                    resume_from = 0
                else:
                    file_mode = 'wb'  # Normal download
                
                # Get content length if available
                content_length = response.headers.get('content-length')
                if content_length:
                    total_size = int(content_length)
                    if resume_from > 0 and response.status_code == 206:
                        # For partial content, add the resume offset
                        segment.size = resume_from + total_size
                    else:
                        segment.size = total_size
                
                # Stream content to file
                downloaded_bytes = resume_from
                with open(filepath, file_mode) as f:
                    async for chunk in response.aiter_bytes(
                        chunk_size=self.config.chunk_size
                    ):
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                
                # Update segment info
                if not segment.size:
                    segment.size = downloaded_bytes
                
                # Verify file integrity
                await self._verify_file_integrity(filepath, segment)
                
                # If we get here, integrity check passed
                segment.downloaded = True
                logger.debug(
                    f"Successfully downloaded segment {segment.index} "
                    f"({segment.size} bytes)"
                )
            
            return segment

    async def _verify_file_integrity(
        self, 
        filepath: Path, 
        segment: SegmentInfo
    ) -> None:
        """Verify downloaded file integrity.
        
        Args:
            filepath: Path to the downloaded file
            segment: Segment information for verification
            
        Raises:
            IntegrityError: If file integrity check fails
        """
        try:
            # Check if file exists
            if not filepath.exists():
                raise IntegrityError(
                    f"Downloaded file does not exist: {filepath}",
                    segment=segment
                )
            
            # Check file size
            actual_size = filepath.stat().st_size
            
            # If we don't have expected size, just check file is not empty
            if segment.size is None:
                if actual_size == 0:
                    raise IntegrityError(
                        f"Downloaded file is empty: {filepath}",
                        segment=segment
                    )
                # Update segment size with actual size
                segment.size = actual_size
                return
            
            # Verify size matches expected (with small tolerance for resume downloads)
            if actual_size != segment.size:
                # Allow small tolerance for resume downloads
                size_tolerance = max(1, int(segment.size * 0.01))  # 1% or at least 1 byte
                if abs(actual_size - segment.size) > size_tolerance:
                    raise IntegrityError(
                        f"File size mismatch for {filepath}: "
                        f"expected {segment.size}, got {actual_size}",
                        segment=segment
                    )
            
            # Update segment size with actual size if within tolerance
            segment.size = actual_size
            
            # Additional integrity checks could be added here
            # (e.g., checksum verification if provided by server)
            
        except IntegrityError:
            # Re-raise integrity errors
            raise
        except Exception as e:
            # Convert other exceptions to integrity errors
            raise IntegrityError(
                f"Error verifying file integrity for {filepath}: {e}",
                segment=segment
            ) from e

    async def download_single_segment_with_retry(
        self, 
        segment: SegmentInfo, 
        output_dir: str
    ) -> SegmentInfo:
        """Download a single segment with retry logic.
        
        This method provides a public interface for downloading individual segments
        with built-in retry capabilities and resume support.
        
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
        
        return await self._download_single_segment_with_retry(segment, output_path)
    
    def get_error_summary(self) -> dict:
        """Get summary of download errors encountered.
        
        Returns:
            Dictionary with error statistics and details
        """
        return self._error_handler.get_error_summary()