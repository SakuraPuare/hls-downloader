"""Download manager for coordinating HLS download process."""

import logging
import time
from pathlib import Path
from typing import Any, Optional

from .detector import HLSDetector
from .downloader import AsyncDownloader
from .merger import FFmpegNotFoundError, VideoMerger, VideoMergerError
from .models import DownloadConfig, DownloadStats, SegmentInfo
from .progress_display import ProgressDisplay
from .resume_validator import ResumeValidator
from .state_manager import DownloadState, StateManager

logger = logging.getLogger(__name__)


class DownloadManagerError(Exception):
    """Base exception for download manager errors."""

    pass


class ConfigurationError(DownloadManagerError):
    """Raised when configuration is invalid."""

    pass


class DownloadManager:
    """Coordinates the entire HLS download process."""

    def __init__(self, config: Optional[DownloadConfig] = None):
        """Initialize download manager with configuration.

        Args:
            config: Download configuration. If None, uses default configuration.
        """
        self.config = config or DownloadConfig()
        self._validate_config(self.config)

        # Initialize components
        self._detector: Optional[HLSDetector] = None
        self._downloader: Optional[AsyncDownloader] = None
        self._merger: Optional[VideoMerger] = None
        self._progress_display: Optional[ProgressDisplay] = None
        self._state_manager: Optional[StateManager] = None
        self._resume_validator: Optional[ResumeValidator] = None

        # Download state
        self._segments: list[SegmentInfo] = []
        self._download_stats: Optional[DownloadStats] = None
        self._output_directory: Optional[Path] = None
        self._segments_directory: Optional[Path] = None
        self._current_state: Optional[DownloadState] = None

        logger.info(f"DownloadManager initialized with config: {self.config}")

    async def download_hls(
        self,
        url: str,
        output_dir: str,
        output_filename: Optional[str] = None,
        force_restart: bool = False,
    ) -> dict[str, Any]:
        """Download HLS stream to specified directory with resume support.

        Args:
            url: HLS segment URL template (e.g., "http://example.com/segment1.ts")
            output_dir: Directory to save the downloaded video
            output_filename: Optional custom filename for output video
            force_restart: If True, ignore existing state and start fresh

        Returns:
            Dictionary with download results and statistics

        Raises:
            DownloadManagerError: If download process fails
            ConfigurationError: If configuration is invalid
        """
        if not url or not url.startswith(("http://", "https://")):
            raise DownloadManagerError("Invalid URL provided")

        if not output_dir:
            raise DownloadManagerError("Output directory cannot be empty")

        logger.info(f"Starting HLS download from {url} to {output_dir}")

        try:
            # Setup output directory structure
            await self._setup_output_directory(output_dir)

            # Initialize components including state manager
            await self._initialize_components()

            # Check for existing state and handle resume
            resume_info = await self._check_and_handle_resume(
                url, output_dir, output_filename, force_restart
            )

            if resume_info["resumed"]:
                logger.info(f"Resuming download: {resume_info['message']}")
            else:
                logger.info("Starting fresh download")

            # Phase 1: Detect segments (skip if resuming with valid state)
            if not self._current_state or not self._current_state.segments:
                logger.info("Phase 1: Detecting available segments...")
                segments = await self._detect_segments(url)

                if not segments:
                    raise DownloadManagerError("No segments found for the provided URL")

                logger.info(f"Found {len(segments)} segments to download")

                # Update state with detected segments
                if self._current_state:
                    self._state_manager.update_state_segments(
                        self._current_state, segments
                    )
                    self._state_manager.update_state_status(
                        self._current_state, "downloading"
                    )
            else:
                logger.info(
                    f"Using {len(self._current_state.segments)} segments from saved state"
                )
                segments = self._current_state.segments

            # Phase 2: Download segments with resume support
            logger.info("Phase 2: Downloading segments...")
            download_results = await self._download_segments_with_resume(segments)

            # Update state after download
            if self._current_state:
                successful_segments = [s for s in download_results if s.downloaded]
                failed_segments = [s for s in download_results if not s.downloaded]
                self._state_manager.update_state_progress(
                    self._current_state, successful_segments, failed_segments
                )
                self._state_manager.update_state_status(self._current_state, "merging")

            # Phase 3: Merge segments (if enabled)
            output_file_path = None
            if self.config.auto_merge:
                logger.info("Phase 3: Merging segments...")
                output_file_path = await self._merge_segments(output_filename)

            # Mark download as completed and cleanup state
            if self._current_state:
                self._state_manager.update_state_status(
                    self._current_state, "completed"
                )
                # Delete state file on successful completion
                self._state_manager.delete_state()

            # Generate final results
            results = self._generate_results(download_results, output_file_path)
            results.update(resume_info)  # Include resume information

            logger.info("HLS download completed successfully")
            return results

        except Exception as e:
            # Update state to failed if we have one
            if self._current_state and self._state_manager:
                try:
                    self._state_manager.update_state_status(
                        self._current_state, "failed"
                    )
                except Exception as state_error:
                    logger.warning(f"Failed to update state to failed: {state_error}")

            logger.error(f"HLS download failed: {e}")
            if isinstance(e, (DownloadManagerError, ConfigurationError)):
                raise
            else:
                raise DownloadManagerError(f"Download failed: {str(e)}") from e

        finally:
            # Cleanup components
            await self._cleanup_components()

    async def _initialize_components(self) -> None:
        """Initialize all download components."""
        logger.debug("Initializing download components...")

        # Initialize state manager
        if self._output_directory:
            self._state_manager = StateManager(str(self._output_directory))

        # Initialize resume validator
        self._resume_validator = ResumeValidator(timeout=self.config.timeout)

        # Initialize detector
        self._detector = HLSDetector(
            timeout=self.config.timeout,
            max_concurrent_checks=min(self.config.max_concurrent, 20),
        )

        # Initialize downloader
        self._downloader = AsyncDownloader(self.config)

        # Initialize merger (check ffmpeg availability)
        try:
            self._merger = VideoMerger()
            logger.info("Video merger initialized successfully")
        except FFmpegNotFoundError as e:
            if self.config.auto_merge:
                logger.error(f"Auto-merge enabled but ffmpeg not available: {e}")
                raise DownloadManagerError(
                    f"ffmpeg required for auto-merge: {e}"
                ) from e
            else:
                logger.warning(f"ffmpeg not available, auto-merge disabled: {e}")
                self._merger = None

        # Initialize progress display
        self._progress_display = ProgressDisplay()

        logger.debug("All components initialized successfully")

    async def _cleanup_components(self) -> None:
        """Cleanup all download components."""
        logger.debug("Cleaning up download components...")

        # Cleanup progress display
        if self._progress_display:
            self._progress_display.close_all_progress()
            self._progress_display = None

        # Cleanup resume validator
        if self._resume_validator:
            # ResumeValidator cleanup is handled by context manager
            self._resume_validator = None

        # Cleanup downloader
        if self._downloader:
            # AsyncDownloader cleanup is handled by context manager
            self._downloader = None

        # Cleanup detector
        if self._detector:
            # HLSDetector cleanup is handled by context manager
            self._detector = None

        # Merger doesn't need explicit cleanup
        self._merger = None

        # State manager doesn't need explicit cleanup
        self._state_manager = None

        logger.debug("Component cleanup completed")

    async def _detect_segments(self, url: str) -> list[SegmentInfo]:
        """Detect available HLS segments.

        Args:
            url: HLS segment URL template

        Returns:
            List of detected segment information
        """
        if not self._detector:
            raise DownloadManagerError("Detector not initialized")

        async with self._detector:
            segments = await self._detector.detect_segments(url)

            # Update segments with proper file paths
            for segment in segments:
                segment.filename = f"segment_{segment.index:06d}.ts"

            self._segments = segments
            return segments

    async def _download_segments(
        self, segments: list[SegmentInfo]
    ) -> list[SegmentInfo]:
        """Download all segments with progress tracking.

        Args:
            segments: List of segments to download

        Returns:
            List of download results
        """
        if not self._downloader or not self._progress_display:
            raise DownloadManagerError("Downloader or progress display not initialized")

        # Setup progress display
        self._progress_display.create_main_progress(
            total=len(segments), desc="下载HLS切片"
        )

        # Initialize download statistics
        self._download_stats = DownloadStats(
            total_segments=len(segments), start_time=time.time()
        )

        try:
            # Download segments using async context manager
            async with self._downloader:
                results = await self._downloader.download_segments(
                    segments, str(self._segments_directory)
                )

            # Update final statistics
            successful_downloads = [s for s in results if s.downloaded]
            failed_downloads = [s for s in results if not s.downloaded]

            self._download_stats.downloaded_segments = len(successful_downloads)
            self._download_stats.failed_segments = len(failed_downloads)
            self._download_stats.downloaded_bytes = sum(
                s.size or 0 for s in successful_downloads
            )

            elapsed_time = time.time() - self._download_stats.start_time
            self._download_stats.update_speed(elapsed_time)

            # Update progress display with final stats
            self._progress_display.update_stats(self._download_stats)

            logger.info(
                f"Download completed: {len(successful_downloads)}/{len(segments)} "
                f"segments successful"
            )

            if failed_downloads:
                logger.warning(f"{len(failed_downloads)} segments failed to download")
                for failed_segment in failed_downloads:
                    logger.warning(
                        f"Failed segment: {failed_segment.index} - {failed_segment.url}"
                    )

            return results

        except Exception as e:
            if self._progress_display:
                self._progress_display.set_error_status(f"下载失败: {str(e)}")
            raise

    async def _merge_segments(
        self, output_filename: Optional[str] = None
    ) -> Optional[str]:
        """Merge downloaded segments into a single video file.

        Args:
            output_filename: Optional custom filename for output video

        Returns:
            Path to the merged video file, or None if merge failed/disabled
        """
        if not self.config.auto_merge or not self._merger:
            logger.info("Auto-merge disabled or merger not available")
            return None

        if not self._segments_directory or not self._output_directory:
            raise DownloadManagerError("Output directories not initialized")

        # Generate output filename
        if not output_filename:
            timestamp = int(time.time())
            output_filename = f"hls_video_{timestamp}.{self.config.output_format}"
        elif not output_filename.endswith(f".{self.config.output_format}"):
            output_filename = f"{output_filename}.{self.config.output_format}"

        output_file_path = self._output_directory / output_filename

        try:
            # Create progress callback for merge operation
            def merge_progress_callback(seconds: float):
                if self._progress_display:
                    # Update progress display with merge status
                    pass  # Could implement merge progress display here

            # Perform merge
            await self._merger.merge_segments(
                segment_dir=str(self._segments_directory),
                output_file=str(output_file_path),
                cleanup_segments=self.config.cleanup_segments,
                progress_callback=merge_progress_callback,
            )

            logger.info(f"Video merged successfully: {output_file_path}")
            return str(output_file_path)

        except VideoMergerError as e:
            logger.error(f"Video merge failed: {e}")
            # Don't raise exception, just return None to indicate merge failure
            return None

    def _generate_results(
        self, download_results: list[SegmentInfo], output_file_path: Optional[str]
    ) -> dict[str, Any]:
        """Generate final download results summary.

        Args:
            download_results: Results from segment downloads
            output_file_path: Path to merged video file (if any)

        Returns:
            Dictionary with comprehensive download results
        """
        successful_downloads = [s for s in download_results if s.downloaded]
        failed_downloads = [s for s in download_results if not s.downloaded]

        results = {
            "success": len(failed_downloads) == 0,
            "total_segments": len(download_results),
            "successful_segments": len(successful_downloads),
            "failed_segments": len(failed_downloads),
            "output_directory": str(self._output_directory)
            if self._output_directory
            else None,
            "segments_directory": str(self._segments_directory)
            if self._segments_directory
            else None,
            "merged_video_path": output_file_path,
            "download_stats": {
                "total_bytes": sum(s.size or 0 for s in successful_downloads),
                "average_speed": self._download_stats.average_speed
                if self._download_stats
                else 0.0,
                "total_time": time.time()
                - (
                    self._download_stats.start_time
                    if self._download_stats
                    else time.time()
                ),
            },
            "configuration": {
                "max_concurrent": self.config.max_concurrent,
                "max_retries": self.config.max_retries,
                "auto_merge": self.config.auto_merge,
                "cleanup_segments": self.config.cleanup_segments,
                "output_format": self.config.output_format,
            },
        }

        # Add error information if there were failures
        if failed_downloads:
            results["failed_segment_details"] = [
                {"index": s.index, "url": s.url, "filename": s.filename}
                for s in failed_downloads
            ]

        # Add downloader error summary if available
        if self._downloader:
            error_summary = self._downloader.get_error_summary()
            if error_summary.get("total_errors", 0) > 0:
                results["error_summary"] = error_summary

        return results

    async def _setup_output_directory(self, output_dir: str) -> None:
        """Setup output directory structure for downloads.

        Args:
            output_dir: Base output directory path

        Raises:
            DownloadManagerError: If directory setup fails
        """
        try:
            # Create main output directory
            self._output_directory = Path(output_dir).resolve()
            self._output_directory.mkdir(parents=True, exist_ok=True)

            # Create subdirectory for segments
            self._segments_directory = self._output_directory / "segments"
            self._segments_directory.mkdir(parents=True, exist_ok=True)

            # Verify directories are writable
            test_file = self._output_directory / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except (OSError, PermissionError) as e:
                raise DownloadManagerError(f"Output directory not writable: {e}")

            logger.info(f"Output directory setup completed: {self._output_directory}")
            logger.debug(f"Segments directory: {self._segments_directory}")

        except Exception as e:
            if isinstance(e, DownloadManagerError):
                raise
            else:
                raise DownloadManagerError(
                    f"Failed to setup output directory: {e}"
                ) from e

    def _validate_config(self, config: DownloadConfig) -> None:
        """Validate download configuration.

        Args:
            config: Configuration to validate

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Additional validation specific to download manager
            if config.max_concurrent <= 0:
                raise ConfigurationError("max_concurrent must be greater than 0")

            if config.max_concurrent > 100:
                logger.warning(
                    f"High concurrency setting ({config.max_concurrent}) may cause "
                    "performance issues or rate limiting"
                )

            if config.timeout <= 0:
                raise ConfigurationError("timeout must be greater than 0")

            if config.chunk_size <= 0:
                raise ConfigurationError("chunk_size must be greater than 0")

            # Use the built-in validation from DownloadConfig
            if not config.validate():
                raise ConfigurationError("Configuration validation failed")

            logger.debug("Configuration validation passed")

        except ValueError as e:
            raise ConfigurationError(f"Invalid configuration: {e}") from e

    def get_download_stats(self) -> Optional[DownloadStats]:
        """Get current download statistics.

        Returns:
            Current download statistics, or None if download not started
        """
        return self._download_stats

    def get_segments_info(self) -> list[SegmentInfo]:
        """Get information about detected segments.

        Returns:
            List of segment information
        """
        return self._segments.copy()

    def update_config(self, **kwargs) -> None:
        """Update configuration parameters.

        Args:
            **kwargs: Configuration parameters to update

        Raises:
            ConfigurationError: If updated configuration is invalid
        """
        # Create new config with updated values
        config_dict = {
            "max_concurrent": kwargs.get("max_concurrent", self.config.max_concurrent),
            "max_retries": kwargs.get("max_retries", self.config.max_retries),
            "timeout": kwargs.get("timeout", self.config.timeout),
            "chunk_size": kwargs.get("chunk_size", self.config.chunk_size),
            "auto_merge": kwargs.get("auto_merge", self.config.auto_merge),
            "cleanup_segments": kwargs.get(
                "cleanup_segments", self.config.cleanup_segments
            ),
            "output_format": kwargs.get("output_format", self.config.output_format),
        }

        try:
            new_config = DownloadConfig(**config_dict)
            self._validate_config(new_config)
        except ValueError as e:
            raise ConfigurationError(f"Invalid configuration update: {e}") from e

        old_config = self.config
        self.config = new_config

        logger.info(f"Configuration updated from {old_config} to {new_config}")

    async def _check_and_handle_resume(
        self,
        url: str,
        output_dir: str,
        output_filename: Optional[str],
        force_restart: bool,
    ) -> dict[str, Any]:
        """Check for existing state and handle resume logic.

        Args:
            url: HLS segment URL template
            output_dir: Output directory
            output_filename: Optional custom filename
            force_restart: Whether to ignore existing state

        Returns:
            Dictionary with resume information
        """
        resume_info = {
            "resumed": False,
            "message": "Starting fresh download",
            "existing_segments": 0,
            "total_segments": 0,
            "resume_percentage": 0.0,
        }

        if force_restart:
            # Delete existing state if force restart
            if self._state_manager and self._state_manager.has_saved_state():
                self._state_manager.delete_state()
                logger.info("Existing state deleted due to force restart")
            return resume_info

        # Check for existing state
        if not self._state_manager or not self._state_manager.has_saved_state():
            # No existing state, create new one
            self._current_state = (
                self._state_manager.create_initial_state(
                    url, output_dir, output_filename, self.config
                )
                if self._state_manager
                else None
            )
            return resume_info

        # Load existing state
        existing_state = self._state_manager.load_state()
        if not existing_state:
            logger.warning("Failed to load existing state, starting fresh")
            self._current_state = self._state_manager.create_initial_state(
                url, output_dir, output_filename, self.config
            )
            return resume_info

        # Validate state compatibility
        if existing_state.url != url:
            logger.warning(
                f"URL mismatch in existing state: {existing_state.url} vs {url}, "
                "starting fresh"
            )
            self._state_manager.delete_state()
            self._current_state = self._state_manager.create_initial_state(
                url, output_dir, output_filename, self.config
            )
            return resume_info

        # State is compatible, proceed with resume
        self._current_state = existing_state
        self._state_manager.mark_resume(self._current_state)

        # Validate existing segments if we have them
        if self._current_state.segments:
            resume_info.update(await self._validate_resume_state())

        return resume_info

    async def _validate_resume_state(self) -> dict[str, Any]:
        """Validate existing segments for resume.

        Returns:
            Dictionary with validation results
        """
        if not self._current_state or not self._resume_validator:
            return {"resumed": False, "message": "Cannot validate resume state"}

        logger.info("Validating existing segments for resume...")

        async with self._resume_validator:
            # Validate segments
            (
                valid_segments,
                invalid_segments,
                missing_segments,
            ) = await self._resume_validator.validate_segments(
                self._current_state.segments, self._segments_directory
            )

            # Clean up invalid files
            if invalid_segments:
                removed_count = self._resume_validator.cleanup_invalid_files(
                    invalid_segments, self._segments_directory
                )
                logger.info(f"Cleaned up {removed_count} invalid segment files")

            # Get resume summary
            summary = self._resume_validator.get_resume_summary(
                valid_segments, invalid_segments, missing_segments
            )

            # Update current state with validated segments
            # Mark valid segments as downloaded
            for segment in self._current_state.segments:
                segment.downloaded = any(
                    v.index == segment.index for v in valid_segments
                )

            # Update statistics
            self._current_state.stats.downloaded_segments = len(valid_segments)
            self._current_state.stats.failed_segments = 0  # Reset failed count
            self._current_state.stats.downloaded_bytes = summary["valid_bytes"]

            # Save updated state
            self._state_manager.save_state(self._current_state)

            return {
                "resumed": summary["can_resume"],
                "message": f"Resuming: {summary['valid_segments']}/{summary['total_segments']} segments already downloaded ({summary['completion_percentage']:.1f}%)",
                "existing_segments": summary["valid_segments"],
                "total_segments": summary["total_segments"],
                "resume_percentage": summary["completion_percentage"],
                "segments_to_download": summary["segments_to_download"],
            }

    async def _download_segments_with_resume(
        self, segments: list[SegmentInfo]
    ) -> list[SegmentInfo]:
        """Download segments with resume support.

        Args:
            segments: List of segments to download

        Returns:
            List of download results
        """
        if not self._downloader or not self._progress_display:
            raise DownloadManagerError("Downloader or progress display not initialized")

        # Filter out already downloaded segments
        segments_to_download = [s for s in segments if not s.downloaded]
        already_downloaded = [s for s in segments if s.downloaded]

        logger.info(
            f"Resume download: {len(already_downloaded)} already downloaded, "
            f"{len(segments_to_download)} to download"
        )

        if not segments_to_download:
            logger.info("All segments already downloaded, skipping download phase")
            return segments

        # Setup progress display
        main_progress = self._progress_display.create_main_progress(
            total=len(segments), desc="下载HLS切片"
        )

        # Update progress for already downloaded segments
        if already_downloaded:
            main_progress.update(len(already_downloaded))

        # Initialize download statistics
        self._download_stats = DownloadStats(
            total_segments=len(segments),
            downloaded_segments=len(already_downloaded),
            start_time=time.time(),
        )

        try:
            # Download remaining segments using async context manager
            async with self._downloader:
                new_results = await self._downloader.download_segments(
                    segments_to_download, str(self._segments_directory)
                )

            # Combine results
            all_results = already_downloaded + new_results

            # Update final statistics
            successful_downloads = [s for s in all_results if s.downloaded]
            failed_downloads = [s for s in all_results if not s.downloaded]

            self._download_stats.downloaded_segments = len(successful_downloads)
            self._download_stats.failed_segments = len(failed_downloads)
            self._download_stats.downloaded_bytes = sum(
                s.size or 0 for s in successful_downloads
            )

            elapsed_time = time.time() - self._download_stats.start_time
            self._download_stats.update_speed(elapsed_time)

            # Update progress display with final stats
            self._progress_display.update_stats(self._download_stats)

            logger.info(
                f"Download completed: {len(successful_downloads)}/{len(segments)} "
                f"segments successful (including {len(already_downloaded)} resumed)"
            )

            if failed_downloads:
                logger.warning(f"{len(failed_downloads)} segments failed to download")
                for failed_segment in failed_downloads:
                    logger.warning(
                        f"Failed segment: {failed_segment.index} - {failed_segment.url}"
                    )

            return all_results

        except Exception as e:
            if self._progress_display:
                self._progress_display.set_error_status(f"下载失败: {str(e)}")
            raise

    async def resume_download(
        self, url: str, output_dir: str, output_filename: Optional[str] = None
    ) -> dict[str, Any]:
        """Resume a previously interrupted download.

        Args:
            url: Original HLS segment URL template
            output_dir: Directory containing partial download
            output_filename: Optional custom filename for output video

        Returns:
            Dictionary with download results and statistics

        Note:
            This is a convenience method that calls download_hls with resume logic.
        """
        logger.info(f"Resuming HLS download from {url} in {output_dir}")
        return await self.download_hls(
            url, output_dir, output_filename, force_restart=False
        )

    def has_resumable_download(self, output_dir: str) -> bool:
        """Check if there's a resumable download in the specified directory.

        Args:
            output_dir: Directory to check for resumable download

        Returns:
            True if resumable download exists, False otherwise
        """
        state_manager = StateManager(output_dir)
        return state_manager.has_saved_state()

    def get_resume_info(self, output_dir: str) -> Optional[dict[str, Any]]:
        """Get information about resumable download in the specified directory.

        Args:
            output_dir: Directory to check for resumable download

        Returns:
            Dictionary with resume information, or None if no resumable download
        """
        state_manager = StateManager(output_dir)
        return state_manager.get_state_info()
