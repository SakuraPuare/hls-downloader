"""Video merger for combining HLS segments using ffmpeg."""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoMergerError(Exception):
    """Base exception for video merger errors."""

    pass


class FFmpegNotFoundError(VideoMergerError):
    """Raised when ffmpeg is not available."""

    pass


class MergeError(VideoMergerError):
    """Raised when video merge operation fails."""

    pass


class VideoMerger:
    """Video merger for combining HLS segments using ffmpeg."""

    def __init__(self):
        """Initialize the video merger."""
        self._ffmpeg_path: Optional[str] = None
        self._check_ffmpeg_available()

    def _check_ffmpeg_available(self) -> bool:
        """
        Check if ffmpeg is available in the system.

        Returns:
            bool: True if ffmpeg is available, False otherwise.

        Raises:
            FFmpegNotFoundError: If ffmpeg is not found.
        """
        try:
            # Try to find ffmpeg in PATH
            self._ffmpeg_path = shutil.which("ffmpeg")
            if self._ffmpeg_path is None:
                raise FFmpegNotFoundError(
                    "ffmpeg not found in PATH. Please install ffmpeg:\n"
                    "- macOS: brew install ffmpeg\n"
                    "- Ubuntu/Debian: sudo apt install ffmpeg\n"
                    "- Windows: Download from https://ffmpeg.org/download.html"
                )

            # Test ffmpeg by running version command
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise FFmpegNotFoundError(
                    f"ffmpeg found but not working properly: {result.stderr}"
                )

            logger.info(f"ffmpeg found at: {self._ffmpeg_path}")
            return True

        except subprocess.TimeoutExpired:
            raise FFmpegNotFoundError("ffmpeg version check timed out")
        except FileNotFoundError:
            raise FFmpegNotFoundError("ffmpeg executable not found")

    def _generate_concat_file(self, segment_files: list[str]) -> str:
        """
        Generate a concat file list for ffmpeg.

        Args:
            segment_files: List of segment file paths.

        Returns:
            str: Path to the generated concat file.

        Raises:
            ValueError: If segment_files is empty or contains invalid paths.
        """
        if not segment_files:
            raise ValueError("segment_files cannot be empty")

        # Validate all segment files exist
        missing_files = []
        for file_path in segment_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)

        if missing_files:
            raise ValueError(f"Missing segment files: {missing_files}")

        # Create temporary concat file
        concat_fd, concat_path = tempfile.mkstemp(suffix=".txt", prefix="hls_concat_")

        try:
            with os.fdopen(concat_fd, "w", encoding="utf-8") as f:
                for file_path in segment_files:
                    # Convert to absolute path and escape for ffmpeg
                    abs_path = os.path.abspath(file_path)
                    # Escape single quotes and backslashes for ffmpeg concat format
                    escaped_path = abs_path.replace("'", "'\"'\"'").replace(
                        "\\", "\\\\"
                    )
                    f.write(f"file '{escaped_path}'\n")

            logger.info(
                f"Generated concat file: {concat_path} with {len(segment_files)} segments"
            )
            return concat_path

        except Exception:
            # Clean up the file descriptor if writing fails
            try:
                os.unlink(concat_path)
            except OSError:
                pass
            raise

    async def merge_segments(
        self,
        segment_dir: str,
        output_file: str,
        cleanup_segments: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> None:
        """
        Merge HLS segments into a single video file.

        Args:
            segment_dir: Directory containing segment files.
            output_file: Path for the output video file.
            cleanup_segments: Whether to delete segment files after merge.
            progress_callback: Optional callback for progress updates.

        Raises:
            ValueError: If parameters are invalid.
            MergeError: If merge operation fails.
        """
        if not os.path.isdir(segment_dir):
            raise ValueError(f"segment_dir does not exist: {segment_dir}")

        if not output_file:
            raise ValueError("output_file cannot be empty")

        # Find all segment files (typically .ts files)
        segment_files = []
        segment_extensions = {".ts", ".m4s", ".mp4"}

        for file_path in sorted(Path(segment_dir).iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in segment_extensions:
                segment_files.append(str(file_path))

        if not segment_files:
            raise ValueError(f"No segment files found in {segment_dir}")

        logger.info(f"Found {len(segment_files)} segment files to merge")

        # Generate concat file
        concat_file = None
        try:
            concat_file = self._generate_concat_file(segment_files)

            # Prepare output directory
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run ffmpeg merge
            await self._run_ffmpeg_merge(concat_file, output_file, progress_callback)

            logger.info(
                f"Successfully merged {len(segment_files)} segments to {output_file}"
            )

            # Cleanup segments if requested
            if cleanup_segments:
                await self._cleanup_segments(segment_files)
                logger.info(f"Cleaned up {len(segment_files)} segment files")

        finally:
            # Always cleanup concat file
            if concat_file and os.path.exists(concat_file):
                try:
                    os.unlink(concat_file)
                except OSError as e:
                    logger.warning(f"Failed to cleanup concat file {concat_file}: {e}")

    async def _run_ffmpeg_merge(
        self,
        concat_file: str,
        output_file: str,
        progress_callback: Optional[callable] = None,
    ) -> None:
        """
        Run ffmpeg to merge segments.

        Args:
            concat_file: Path to the concat file.
            output_file: Path for the output video file.
            progress_callback: Optional callback for progress updates.

        Raises:
            MergeError: If ffmpeg execution fails.
        """
        # Build ffmpeg command
        cmd = [
            self._ffmpeg_path,
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c",
            "copy",  # Copy streams without re-encoding for speed
            "-y",  # Overwrite output file
            output_file,
        ]

        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")

        try:
            # Run ffmpeg asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            # Monitor progress if callback provided
            if progress_callback:
                await self._monitor_ffmpeg_progress(process, progress_callback)

            # Wait for completion
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = (
                    stderr.decode("utf-8", errors="replace")
                    if stderr
                    else "Unknown error"
                )
                raise MergeError(
                    f"ffmpeg failed with return code {process.returncode}: {error_msg}"
                )

            logger.info("ffmpeg merge completed successfully")

        except asyncio.TimeoutError:
            raise MergeError("ffmpeg merge operation timed out")
        except Exception as e:
            raise MergeError(f"ffmpeg execution failed: {str(e)}")

    async def _monitor_ffmpeg_progress(
        self, process: asyncio.subprocess.Process, progress_callback: callable
    ) -> None:
        """
        Monitor ffmpeg progress and call progress callback.

        Args:
            process: The ffmpeg subprocess.
            progress_callback: Callback function for progress updates.
        """
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace").strip()

                # Parse ffmpeg progress output
                # ffmpeg outputs progress info like: "time=00:01:23.45"
                if "time=" in line_str:
                    try:
                        time_part = line_str.split("time=")[1].split()[0]
                        # Convert time to seconds for progress callback
                        time_parts = time_part.split(":")
                        if len(time_parts) == 3:
                            hours, minutes, seconds = time_parts
                            total_seconds = (
                                int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                            )
                            progress_callback(total_seconds)
                    except (ValueError, IndexError):
                        # Ignore parsing errors
                        pass

        except Exception as e:
            logger.warning(f"Error monitoring ffmpeg progress: {e}")

    async def _cleanup_segments(self, segment_files: list[str]) -> None:
        """
        Clean up segment files after successful merge.

        Args:
            segment_files: List of segment file paths to delete.
        """
        for file_path in segment_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError as e:
                logger.warning(f"Failed to delete segment file {file_path}: {e}")

    @property
    def is_available(self) -> bool:
        """Check if ffmpeg is available."""
        return self._ffmpeg_path is not None

    @property
    def ffmpeg_path(self) -> Optional[str]:
        """Get the path to ffmpeg executable."""
        return self._ffmpeg_path
