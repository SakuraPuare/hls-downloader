"""State persistence and recovery for HLS downloads."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from ..models.config import DownloadConfig
from ..models.stats import DownloadStats
from ..models.segment import SegmentInfo
from ..models.state import DownloadState

logger = logging.getLogger(__name__)


class StateManager:
    """Manages download state persistence and recovery."""

    STATE_FILE_NAME = ".hls_download_state.json"
    BACKUP_FILE_NAME = ".hls_download_state.backup.json"

    def __init__(self, output_dir: str):
        """Initialize state manager for a specific output directory.

        Args:
            output_dir: Directory where download state will be saved
        """
        self.output_dir = Path(output_dir)
        self.state_file = self.output_dir / self.STATE_FILE_NAME
        self.backup_file = self.output_dir / self.BACKUP_FILE_NAME

        logger.debug(f"StateManager initialized for directory: {self.output_dir}")

    def save_state(self, state: DownloadState) -> None:
        """Save download state to disk.

        Args:
            state: Download state to save

        Raises:
            OSError: If state cannot be saved to disk
        """
        try:
            # Update timestamp
            state.updated_at = time.time()

            # Create backup of existing state file
            if self.state_file.exists():
                # Copy to backup instead of rename to preserve original
                import shutil

                shutil.copy2(self.state_file, self.backup_file)

            # Convert state to dictionary for JSON serialization
            state_dict = self._state_to_dict(state)

            # Ensure output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Write state to file atomically
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.rename(self.state_file)

            logger.debug(f"Download state saved to {self.state_file}")

        except Exception as e:
            logger.error(f"Failed to save download state: {e}")
            # Try to restore backup if it exists
            if self.backup_file.exists() and not self.state_file.exists():
                try:
                    import shutil

                    shutil.copy2(self.backup_file, self.state_file)
                    logger.info("Restored state file from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")
            raise OSError(f"Cannot save download state: {e}") from e

    def load_state(self) -> Optional[DownloadState]:
        """Load download state from disk.

        Returns:
            Loaded download state, or None if no valid state found
        """
        # Try to load from main state file
        state = self._load_state_from_file(self.state_file)
        if state:
            return state

        # Try to load from backup file
        if self.backup_file.exists():
            logger.warning("Main state file corrupted, trying backup")
            state = self._load_state_from_file(self.backup_file)
            if state:
                # Restore backup as main file
                try:
                    self.backup_file.rename(self.state_file)
                    logger.info("Restored state from backup file")
                except Exception as e:
                    logger.error(f"Failed to restore backup file: {e}")
                return state

        logger.info("No valid download state found")
        return None

    def _load_state_from_file(self, file_path: Path) -> Optional[DownloadState]:
        """Load state from a specific file.

        Args:
            file_path: Path to the state file

        Returns:
            Loaded download state, or None if loading fails
        """
        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                state_dict = json.load(f)

            # Validate and convert dictionary to DownloadState
            state = self._dict_to_state(state_dict)

            logger.debug(f"Download state loaded from {file_path}")
            return state

        except Exception as e:
            logger.error(f"Failed to load state from {file_path}: {e}")
            return None

    def delete_state(self) -> None:
        """Delete saved download state files.

        This should be called when download is completed successfully
        or when user wants to start fresh.
        """
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.debug(f"Deleted state file: {self.state_file}")

            if self.backup_file.exists():
                self.backup_file.unlink()
                logger.debug(f"Deleted backup file: {self.backup_file}")

        except Exception as e:
            logger.warning(f"Failed to delete state files: {e}")

    def has_saved_state(self) -> bool:
        """Check if there is a saved download state.

        Returns:
            True if saved state exists, False otherwise
        """
        return self.state_file.exists() or self.backup_file.exists()

    def get_state_info(self) -> Optional[dict[str, Any]]:
        """Get basic information about saved state without loading it completely.

        Returns:
            Dictionary with state information, or None if no state exists
        """
        if not self.has_saved_state():
            return None

        try:
            file_to_check = (
                self.state_file if self.state_file.exists() else self.backup_file
            )

            with open(file_to_check, encoding="utf-8") as f:
                state_dict = json.load(f)

            return {
                "url": state_dict.get("url"),
                "status": state_dict.get("status"),
                "created_at": state_dict.get("created_at"),
                "updated_at": state_dict.get("updated_at"),
                "resume_count": state_dict.get("resume_count", 0),
                "total_segments": state_dict.get("stats", {}).get("total_segments", 0),
                "downloaded_segments": state_dict.get("stats", {}).get(
                    "downloaded_segments", 0
                ),
                "failed_segments": state_dict.get("stats", {}).get(
                    "failed_segments", 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get state info: {e}")
            return None

    def _state_to_dict(self, state: DownloadState) -> dict[str, Any]:
        """Convert DownloadState to dictionary for JSON serialization.

        Args:
            state: Download state to convert

        Returns:
            Dictionary representation of the state
        """
        return {
            "url": state.url,
            "output_dir": state.output_dir,
            "output_filename": state.output_filename,
            "config": asdict(state.config),
            "segments": [asdict(segment) for segment in state.segments],
            "stats": asdict(state.stats),
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "status": state.status,
            "resume_count": state.resume_count,
            "last_resume_at": state.last_resume_at,
            # Add metadata for debugging
            "_metadata": {
                "version": "1.0",
                "created_by": "hls-downloader",
                "python_version": "3.8+",
                "timestamp_format": "unix_epoch",
            },
        }

    def _dict_to_state(self, state_dict: dict[str, Any]) -> DownloadState:
        """Convert dictionary to DownloadState object.

        Args:
            state_dict: Dictionary representation of state

        Returns:
            DownloadState object

        Raises:
            ValueError: If state dictionary is invalid
        """
        try:
            # Validate required fields
            required_fields = [
                "url",
                "output_dir",
                "config",
                "segments",
                "stats",
                "status",
            ]
            for field in required_fields:
                if field not in state_dict:
                    raise ValueError(f"Missing required field: {field}")

            # Convert config
            config = DownloadConfig(**state_dict["config"])

            # Convert segments
            segments = []
            for segment_dict in state_dict["segments"]:
                segment = SegmentInfo(**segment_dict)
                segments.append(segment)

            # Convert stats
            stats = DownloadStats(**state_dict["stats"])

            # Create DownloadState
            return DownloadState(
                url=state_dict["url"],
                output_dir=state_dict["output_dir"],
                output_filename=state_dict.get("output_filename"),
                config=config,
                segments=segments,
                stats=stats,
                created_at=state_dict.get("created_at", time.time()),
                updated_at=state_dict.get("updated_at", time.time()),
                status=state_dict["status"],
                resume_count=state_dict.get("resume_count", 0),
                last_resume_at=state_dict.get("last_resume_at"),
            )

        except Exception as e:
            raise ValueError(f"Invalid state dictionary: {e}") from e

    def create_initial_state(
        self,
        url: str,
        output_dir: str,
        output_filename: Optional[str],
        config: DownloadConfig,
    ) -> DownloadState:
        """Create initial download state.

        Args:
            url: HLS segment URL template
            output_dir: Output directory for download
            output_filename: Optional custom filename
            config: Download configuration

        Returns:
            Initial download state
        """
        current_time = time.time()

        return DownloadState(
            url=url,
            output_dir=output_dir,
            output_filename=output_filename,
            config=config,
            segments=[],
            stats=DownloadStats(total_segments=0),
            created_at=current_time,
            updated_at=current_time,
            status="detecting",
            resume_count=0,
            last_resume_at=None,
        )

    def update_state_status(self, state: DownloadState, status: str) -> None:
        """Update state status and save.

        Args:
            state: Download state to update
            status: New status value
        """
        state.status = status
        state.updated_at = time.time()
        self.save_state(state)

        logger.info(f"Download status updated to: {status}")

    def update_state_segments(
        self, state: DownloadState, segments: list[SegmentInfo]
    ) -> None:
        """Update state with detected segments and save.

        Args:
            state: Download state to update
            segments: List of detected segments
        """
        state.segments = segments
        state.stats.total_segments = len(segments)
        state.updated_at = time.time()
        self.save_state(state)

        logger.info(f"State updated with {len(segments)} segments")

    def update_state_progress(
        self,
        state: DownloadState,
        downloaded_segments: list[SegmentInfo],
        failed_segments: list[SegmentInfo],
    ) -> None:
        """Update state with download progress and save.

        Args:
            state: Download state to update
            downloaded_segments: List of successfully downloaded segments
            failed_segments: List of failed segments
        """
        # Update segments in state
        segment_status = {}
        for segment in downloaded_segments:
            segment_status[segment.index] = segment
        for segment in failed_segments:
            segment_status[segment.index] = segment

        # Update segments list with current status
        for i, segment in enumerate(state.segments):
            if segment.index in segment_status:
                state.segments[i] = segment_status[segment.index]

        # Update statistics
        state.stats.downloaded_segments = len(downloaded_segments)
        state.stats.failed_segments = len(failed_segments)
        state.stats.downloaded_bytes = sum(s.size or 0 for s in downloaded_segments)

        state.updated_at = time.time()
        self.save_state(state)

        logger.debug(
            f"State progress updated: {len(downloaded_segments)} downloaded, "
            f"{len(failed_segments)} failed"
        )

    def mark_resume(self, state: DownloadState) -> None:
        """Mark state as being resumed.

        Args:
            state: Download state to mark as resumed
        """
        state.resume_count += 1
        state.last_resume_at = time.time()
        state.updated_at = time.time()
        self.save_state(state)

        logger.info(f"Download marked as resumed (resume count: {state.resume_count})")
