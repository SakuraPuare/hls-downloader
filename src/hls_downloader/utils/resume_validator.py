"""Resume validation and file integrity checking for HLS downloads."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx

from ..models.segment import SegmentInfo

logger = logging.getLogger(__name__)


class ResumeValidator:
    """Validates existing files and determines what needs to be downloaded for resume."""

    def __init__(self, timeout: int = 30):
        """Initialize resume validator.

        Args:
            timeout: HTTP request timeout for validation
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._setup_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup_client()

    async def _setup_client(self) -> None:
        """Setup HTTP client for validation requests."""
        timeout = httpx.Timeout(connect=10.0, read=self.timeout, write=10.0, pool=5.0)

        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, http2=False
        )

        logger.debug("Resume validator HTTP client initialized")

    async def _cleanup_client(self) -> None:
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("Resume validator HTTP client closed")

    def scan_existing_files(self, segments_dir: Path) -> dict[str, dict[str, any]]:
        """Scan directory for existing segment files.

        Args:
            segments_dir: Directory containing segment files

        Returns:
            Dictionary mapping filename to file info (size, mtime, etc.)
        """
        existing_files = {}

        if not segments_dir.exists():
            logger.debug(f"Segments directory does not exist: {segments_dir}")
            return existing_files

        try:
            for file_path in segments_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in [
                    ".ts",
                    ".m4s",
                    ".mp4",
                ]:
                    try:
                        stat = file_path.stat()
                        existing_files[file_path.name] = {
                            "path": file_path,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "is_empty": stat.st_size == 0,
                        }
                    except OSError as e:
                        logger.warning(f"Cannot stat file {file_path}: {e}")

            logger.info(f"Found {len(existing_files)} existing segment files")

        except OSError as e:
            logger.error(f"Cannot scan segments directory {segments_dir}: {e}")

        return existing_files

    async def validate_segments(
        self, segments: list[SegmentInfo], segments_dir: Path
    ) -> tuple[list[SegmentInfo], list[SegmentInfo], list[SegmentInfo]]:
        """Validate existing segments and categorize them.

        Args:
            segments: List of all segments that should be downloaded
            segments_dir: Directory containing segment files

        Returns:
            Tuple of (valid_segments, invalid_segments, missing_segments)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Scan existing files
        existing_files = self.scan_existing_files(segments_dir)

        valid_segments = []
        invalid_segments = []
        missing_segments = []

        # Categorize segments
        for segment in segments:
            if segment.filename not in existing_files:
                # File doesn't exist
                missing_segments.append(segment)
                continue

            file_info = existing_files[segment.filename]

            # Check if file is empty (definitely invalid)
            if file_info["is_empty"]:
                logger.debug(
                    f"Segment {segment.index} file is empty, marking as invalid"
                )
                invalid_segments.append(segment)
                continue

            # If we have expected size, compare it
            if segment.size is not None:
                if file_info["size"] != segment.size:
                    logger.debug(
                        f"Segment {segment.index} size mismatch: "
                        f"expected {segment.size}, got {file_info['size']}"
                    )
                    invalid_segments.append(segment)
                    continue

            # File exists and size looks good, mark as valid for now
            # We'll do deeper validation if requested
            segment.downloaded = True
            segment.size = file_info["size"]  # Update with actual size
            valid_segments.append(segment)

        logger.info(
            f"Segment validation: {len(valid_segments)} valid, "
            f"{len(invalid_segments)} invalid, {len(missing_segments)} missing"
        )

        return valid_segments, invalid_segments, missing_segments

    async def deep_validate_segments(
        self, segments: list[SegmentInfo], segments_dir: Path, max_concurrent: int = 5
    ) -> tuple[list[SegmentInfo], list[SegmentInfo]]:
        """Perform deep validation of segments by checking with server.

        This method validates segments by making HEAD requests to check
        if the local file size matches the server's content-length.

        Args:
            segments: List of segments to validate deeply
            segments_dir: Directory containing segment files
            max_concurrent: Maximum concurrent validation requests

        Returns:
            Tuple of (valid_segments, invalid_segments)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        if not segments:
            return [], []

        logger.info(f"Starting deep validation of {len(segments)} segments")

        semaphore = asyncio.Semaphore(max_concurrent)
        validation_tasks = []

        for segment in segments:
            task = asyncio.create_task(
                self._validate_single_segment(segment, segments_dir, semaphore)
            )
            validation_tasks.append(task)

        # Wait for all validations to complete
        validation_results = await asyncio.gather(
            *validation_tasks, return_exceptions=True
        )

        valid_segments = []
        invalid_segments = []

        for i, result in enumerate(validation_results):
            segment = segments[i]

            if isinstance(result, Exception):
                logger.warning(
                    f"Validation error for segment {segment.index}: {result}"
                )
                # On validation error, assume segment is invalid to be safe
                invalid_segments.append(segment)
            elif result:
                valid_segments.append(segment)
            else:
                invalid_segments.append(segment)

        logger.info(
            f"Deep validation completed: {len(valid_segments)} valid, "
            f"{len(invalid_segments)} invalid"
        )

        return valid_segments, invalid_segments

    async def _validate_single_segment(
        self, segment: SegmentInfo, segments_dir: Path, semaphore: asyncio.Semaphore
    ) -> bool:
        """Validate a single segment file.

        Args:
            segment: Segment to validate
            segments_dir: Directory containing segment files
            semaphore: Semaphore for concurrency control

        Returns:
            True if segment is valid, False otherwise
        """
        async with semaphore:
            try:
                file_path = segments_dir / segment.filename

                # Check if file exists
                if not file_path.exists():
                    logger.debug(f"Segment {segment.index} file does not exist")
                    return False

                # Get local file size
                local_size = file_path.stat().st_size

                # Check if file is empty
                if local_size == 0:
                    logger.debug(f"Segment {segment.index} file is empty")
                    return False

                # Make HEAD request to get server's content-length
                try:
                    response = await self._client.head(segment.url)
                    response.raise_for_status()

                    # Get content length from server
                    content_length = response.headers.get("content-length")
                    if content_length:
                        server_size = int(content_length)

                        # Compare sizes
                        if local_size != server_size:
                            logger.debug(
                                f"Segment {segment.index} size mismatch: "
                                f"local {local_size}, server {server_size}"
                            )
                            return False

                        # Update segment size if not set
                        if segment.size is None:
                            segment.size = local_size

                    # If we get here, validation passed
                    logger.debug(f"Segment {segment.index} validation passed")
                    return True

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.warning(
                            f"Segment {segment.index} not found on server (404)"
                        )
                        return False
                    else:
                        logger.warning(
                            f"HTTP error validating segment {segment.index}: {e}"
                        )
                        # For other HTTP errors, assume file is valid to avoid re-downloading
                        return True

                except httpx.RequestError as e:
                    logger.warning(
                        f"Network error validating segment {segment.index}: {e}"
                    )
                    # For network errors, assume file is valid to avoid re-downloading
                    return True

            except Exception as e:
                logger.error(f"Error validating segment {segment.index}: {e}")
                return False

    def cleanup_invalid_files(
        self, invalid_segments: list[SegmentInfo], segments_dir: Path
    ) -> int:
        """Remove invalid segment files from disk.

        Args:
            invalid_segments: List of invalid segments to remove
            segments_dir: Directory containing segment files

        Returns:
            Number of files successfully removed
        """
        removed_count = 0

        for segment in invalid_segments:
            file_path = segments_dir / segment.filename

            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Removed invalid segment file: {file_path}")
                    removed_count += 1

            except OSError as e:
                logger.warning(f"Failed to remove invalid file {file_path}: {e}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} invalid segment files")

        return removed_count

    def get_resume_summary(
        self,
        valid_segments: list[SegmentInfo],
        invalid_segments: list[SegmentInfo],
        missing_segments: list[SegmentInfo],
    ) -> dict[str, any]:
        """Generate summary of resume validation results.

        Args:
            valid_segments: List of valid segments
            invalid_segments: List of invalid segments
            missing_segments: List of missing segments

        Returns:
            Dictionary with resume summary information
        """
        total_segments = (
            len(valid_segments) + len(invalid_segments) + len(missing_segments)
        )
        segments_to_download = len(invalid_segments) + len(missing_segments)

        valid_bytes = sum(s.size or 0 for s in valid_segments)

        return {
            "total_segments": total_segments,
            "valid_segments": len(valid_segments),
            "invalid_segments": len(invalid_segments),
            "missing_segments": len(missing_segments),
            "segments_to_download": segments_to_download,
            "completion_percentage": (len(valid_segments) / total_segments * 100)
            if total_segments > 0
            else 0,
            "valid_bytes": valid_bytes,
            "can_resume": segments_to_download > 0 and len(valid_segments) > 0,
            "resume_benefit": (len(valid_segments) / total_segments * 100)
            if total_segments > 0
            else 0,
        }
