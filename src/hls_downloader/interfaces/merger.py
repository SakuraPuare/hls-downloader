"""Interface for video mergers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class MergerInterface(ABC):
    """Interface for video segment merging."""
    
    @abstractmethod
    async def merge_segments(self, segment_files: List[Path], output_path: Path) -> bool:
        """Merge segment files into a single video.
        
        Args:
            segment_files: List of segment file paths
            output_path: Path for the merged output file
            
        Returns:
            True if merge successful
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the merger is available (e.g., ffmpeg installed).
        
        Returns:
            True if merger is available
        """
        pass
