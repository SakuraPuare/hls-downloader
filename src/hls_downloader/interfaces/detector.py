"""Interface for HLS segment detectors."""

from abc import ABC, abstractmethod
from typing import List

from ..models.segment import SegmentInfo


class DetectorInterface(ABC):
    """Interface for HLS segment detection."""
    
    @abstractmethod
    async def detect_segments(self, url_template: str, start_index: int = 1) -> List[SegmentInfo]:
        """Detect available segments from URL template.
        
        Args:
            url_template: URL template with number placeholder
            start_index: Starting index for detection
            
        Returns:
            List of detected segments
        """
        pass
    
    @abstractmethod
    async def check_segment_exists(self, url: str) -> bool:
        """Check if a single segment exists.
        
        Args:
            url: Segment URL to check
            
        Returns:
            True if segment exists
        """
        pass
