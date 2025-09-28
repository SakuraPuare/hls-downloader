"""Interface for HLS segment downloaders."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models.segment import SegmentInfo
from ..models.stats import DownloadStats


class DownloaderInterface(ABC):
    """Interface for HLS segment downloading."""
    
    @abstractmethod
    async def download_segments(self, segments: List[SegmentInfo], output_dir: Path) -> DownloadStats:
        """Download multiple segments concurrently.
        
        Args:
            segments: List of segments to download
            output_dir: Directory to save segments
            
        Returns:
            Download statistics
        """
        pass
    
    @abstractmethod
    async def download_segment(self, segment: SegmentInfo, output_path: Path) -> bool:
        """Download a single segment.
        
        Args:
            segment: Segment to download
            output_path: Path to save the segment
            
        Returns:
            True if download successful
        """
        pass
