"""Async downloader for HLS segments."""

import asyncio
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import httpx

from .error_handler import ErrorHandler, IntegrityError
from .models import DownloadConfig, DownloadStats, SegmentInfo

logger = logging.getLogger(__name__)


class AsyncDownloader:
    """Async downloader for HLS segments with concurrent download control and monitoring."""

    def __init__(self, config: DownloadConfig):
        """Initialize the async downloader with configuration.

        Args:
            config: Download configuration settings
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._error_handler = ErrorHandler(
            max_retries=config.max_retries, base_delay=1.0
        )

        # Download statistics and monitoring
        self._stats = DownloadStats(total_segments=0)
        self._download_speeds = deque(maxlen=10)  # Keep last 10 speed measurements
        self._active_downloads = 0
        self._download_lock = asyncio.Lock()

        # Task queue management
        self._download_queue: asyncio.Queue = asyncio.Queue()
        self._completed_segments: list[SegmentInfo] = []
        self._failed_segments: list[SegmentInfo] = []

        # Adaptive concurrency control
        self._adaptive_concurrency = config.max_concurrent
        self._performance_window = deque(
            maxlen=5
        )  # Track performance over 5 measurements
        self._last_adjustment_time = 0.0
        self._adjustment_interval = 30.0  # Adjust every 30 seconds

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
            keepalive_expiry=30.0,
        )

        # Configure timeout settings
        timeout = httpx.Timeout(
            connect=10.0, read=self.config.timeout, write=10.0, pool=5.0
        )

        # Create client with optimized settings
        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            http2=False,  # Disable HTTP/2 to avoid h2 dependency
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
        self, segments: list[SegmentInfo], output_dir: str
    ) -> list[SegmentInfo]:
        """Download multiple segments concurrently with monitoring and adaptive control.

        Args:
            segments: List of segment information to download
            output_dir: Directory to save downloaded segments

        Returns:
            List of updated segment information with download status
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Initialize statistics
        self._stats = DownloadStats(
            total_segments=len(segments), start_time=time.time()
        )
        self._completed_segments.clear()
        self._failed_segments.clear()

        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting download of {len(segments)} segments to {output_dir}")

        # Use task queue for better control
        await self._populate_download_queue(segments)

        # Start download workers with adaptive concurrency
        workers = []
        for worker_id in range(self._adaptive_concurrency):
            worker = asyncio.create_task(self._download_worker(worker_id, output_path))
            workers.append(worker)

        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitor_and_adjust())

        # Wait for all downloads to complete
        await self._download_queue.join()

        # Cancel monitoring and workers
        monitor_task.cancel()
        for worker in workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*workers, monitor_task, return_exceptions=True)

        # Combine results
        all_segments = self._completed_segments + self._failed_segments

        # Update final statistics
        self._stats.downloaded_segments = len(self._completed_segments)
        self._stats.failed_segments = len(self._failed_segments)
        elapsed_time = time.time() - self._stats.start_time
        self._stats.update_speed(elapsed_time)

        logger.info(
            f"Download completed: {self._stats.downloaded_segments}/"
            f"{self._stats.total_segments} successful "
            f"(avg speed: {self._stats.average_speed:.2f} bytes/s)"
        )

        return all_segments

    async def _download_single_segment_with_retry(
        self, segment: SegmentInfo, output_dir: Path
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

        return await self._error_handler.handle_with_retry(download_operation, segment)

    async def _download_single_segment(
        self, segment: SegmentInfo, output_dir: Path
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
                    logger.debug(
                        f"Found partial file for segment {segment.index}, resuming from byte {existing_size}"
                    )
                    resume_from = existing_size

            # Prepare headers for resume support
            headers = {}
            if resume_from > 0:
                headers["Range"] = f"bytes={resume_from}-"

            # Stream download to avoid loading entire file into memory
            async with self._client.stream(
                "GET", segment.url, headers=headers
            ) as response:
                response.raise_for_status()

                # Handle partial content response
                if resume_from > 0 and response.status_code == 206:
                    logger.debug(f"Server supports resume for segment {segment.index}")
                    file_mode = "ab"  # Append mode for resume
                elif resume_from > 0 and response.status_code == 200:
                    logger.debug(
                        f"Server doesn't support resume for segment {segment.index}, restarting download"
                    )
                    file_mode = "wb"  # Overwrite mode
                    resume_from = 0
                else:
                    file_mode = "wb"  # Normal download

                # Get content length if available
                content_length = response.headers.get("content-length")
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
        self, filepath: Path, segment: SegmentInfo
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
                    f"Downloaded file does not exist: {filepath}", segment=segment
                )

            # Check file size
            actual_size = filepath.stat().st_size

            # If we don't have expected size, just check file is not empty
            if segment.size is None:
                if actual_size == 0:
                    raise IntegrityError(
                        f"Downloaded file is empty: {filepath}", segment=segment
                    )
                # Update segment size with actual size
                segment.size = actual_size
                return

            # Verify size matches expected (with small tolerance for resume downloads)
            if actual_size != segment.size:
                # Allow small tolerance for resume downloads
                size_tolerance = max(
                    1, int(segment.size * 0.01)
                )  # 1% or at least 1 byte
                if abs(actual_size - segment.size) > size_tolerance:
                    raise IntegrityError(
                        f"File size mismatch for {filepath}: "
                        f"expected {segment.size}, got {actual_size}",
                        segment=segment,
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
                f"Error verifying file integrity for {filepath}: {e}", segment=segment
            ) from e

    async def download_single_segment_with_retry(
        self, segment: SegmentInfo, output_dir: str
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

    async def _populate_download_queue(self, segments: list[SegmentInfo]) -> None:
        """Populate the download queue with segments.

        Args:
            segments: List of segments to add to the queue
        """
        for segment in segments:
            await self._download_queue.put(segment)

    async def _download_worker(self, worker_id: int, output_dir: Path) -> None:
        """Worker task for processing download queue.

        Args:
            worker_id: Unique identifier for this worker
            output_dir: Directory to save downloaded segments
        """
        logger.debug(f"Download worker {worker_id} started")

        try:
            while True:
                try:
                    # Get next segment from queue with timeout
                    segment = await asyncio.wait_for(
                        self._download_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check if there are more segments to process
                    if self._download_queue.empty():
                        break
                    continue

                # Track active downloads
                async with self._download_lock:
                    self._active_downloads += 1

                try:
                    # Download the segment with speed tracking
                    start_time = time.time()
                    result = await self._download_single_segment_with_retry(
                        segment, output_dir
                    )
                    end_time = time.time()

                    # Calculate download speed
                    if result.size and result.downloaded:
                        download_time = end_time - start_time
                        if download_time > 0:
                            speed = result.size / download_time
                            self._download_speeds.append(speed)

                    # Update statistics and results
                    async with self._download_lock:
                        if result.downloaded:
                            self._completed_segments.append(result)
                            self._stats.downloaded_segments += 1
                            self._stats.downloaded_bytes += result.size or 0
                        else:
                            self._failed_segments.append(result)
                            self._stats.failed_segments += 1

                        self._active_downloads -= 1

                except Exception as e:
                    logger.error(
                        f"Worker {worker_id} error processing segment {segment.index}: {e}"
                    )
                    segment.downloaded = False
                    async with self._download_lock:
                        self._failed_segments.append(segment)
                        self._stats.failed_segments += 1
                        self._active_downloads -= 1

                finally:
                    # Mark task as done
                    self._download_queue.task_done()

        except asyncio.CancelledError:
            logger.debug(f"Download worker {worker_id} cancelled")

        logger.debug(f"Download worker {worker_id} finished")

    async def _monitor_and_adjust(self) -> None:
        """Monitor download performance and adjust concurrency adaptively."""
        logger.debug("Starting download monitoring and adaptive adjustment")

        try:
            while True:
                await asyncio.sleep(5.0)  # Monitor every 5 seconds

                current_time = time.time()

                # Calculate current performance metrics
                if len(self._download_speeds) >= 3:  # Need some data points
                    avg_speed = sum(self._download_speeds) / len(self._download_speeds)
                    self._performance_window.append(avg_speed)

                    # Adjust concurrency if enough time has passed
                    if (
                        current_time - self._last_adjustment_time
                    ) >= self._adjustment_interval:
                        await self._adjust_concurrency()
                        self._last_adjustment_time = current_time

                # Log current status
                async with self._download_lock:
                    logger.debug(
                        f"Download status: {self._stats.downloaded_segments}/"
                        f"{self._stats.total_segments} completed, "
                        f"{self._active_downloads} active, "
                        f"concurrency: {self._adaptive_concurrency}"
                    )

        except asyncio.CancelledError:
            logger.debug("Download monitoring cancelled")

    async def _adjust_concurrency(self) -> None:
        """Adjust concurrency based on performance metrics."""
        if len(self._performance_window) < 3:
            return  # Not enough data

        # Calculate performance trend
        recent_speeds = list(self._performance_window)[-3:]
        if len(recent_speeds) < 3:
            return

        # Simple trend analysis: compare first half with second half
        first_half_avg = sum(recent_speeds[:2]) / 2
        second_half_avg = recent_speeds[-1]

        performance_ratio = (
            second_half_avg / first_half_avg if first_half_avg > 0 else 1.0
        )

        old_concurrency = self._adaptive_concurrency

        # Adjust based on performance trend
        if performance_ratio > 1.1:  # Performance improving
            # Increase concurrency if not at maximum
            if self._adaptive_concurrency < self.config.max_concurrent:
                self._adaptive_concurrency = min(
                    self._adaptive_concurrency + 1, self.config.max_concurrent
                )
        elif performance_ratio < 0.9:  # Performance degrading
            # Decrease concurrency if not at minimum
            if self._adaptive_concurrency > 2:
                self._adaptive_concurrency = max(self._adaptive_concurrency - 1, 2)

        if self._adaptive_concurrency != old_concurrency:
            logger.info(
                f"Adjusted concurrency from {old_concurrency} to "
                f"{self._adaptive_concurrency} (performance ratio: {performance_ratio:.2f})"
            )

            # Update semaphore (create new one with new limit)
            self._semaphore = asyncio.Semaphore(self._adaptive_concurrency)

    def get_download_stats(self) -> DownloadStats:
        """Get current download statistics.

        Returns:
            Current download statistics
        """
        # Update average speed if we have recent measurements
        if self._download_speeds:
            current_avg_speed = sum(self._download_speeds) / len(self._download_speeds)
            self._stats.average_speed = current_avg_speed

        return self._stats

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get detailed performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "adaptive_concurrency": self._adaptive_concurrency,
            "max_concurrency": self.config.max_concurrent,
            "active_downloads": self._active_downloads,
            "recent_speeds": list(self._download_speeds),
            "average_speed": sum(self._download_speeds) / len(self._download_speeds)
            if self._download_speeds
            else 0.0,
            "performance_window": list(self._performance_window),
            "queue_size": self._download_queue.qsize(),
            "completed_count": len(self._completed_segments),
            "failed_count": len(self._failed_segments),
        }
