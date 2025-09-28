"""Download state data model."""

from dataclasses import dataclass
from typing import Optional

from .config import DownloadConfig
from .segment import SegmentInfo
from .stats import DownloadStats


@dataclass
class DownloadState:
    """Complete download state for persistence."""

    # Basic download information
    url: str
    output_dir: str
    output_filename: Optional[str]

    # Configuration
    config: DownloadConfig

    # Segments information
    segments: list[SegmentInfo]

    # Download statistics
    stats: DownloadStats

    # State metadata
    created_at: float
    updated_at: float
    status: str  # 'detecting', 'downloading', 'merging', 'completed', 'failed'

    # Resume information
    resume_count: int = 0
    last_resume_at: Optional[float] = None
