"""Interface for progress display."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models.stats import DownloadStats


class ProgressInterface(ABC):
    """Interface for progress display systems."""
    
    @abstractmethod
    def create_progress_bar(self, total: int, description: str = "") -> None:
        """Create a progress bar.
        
        Args:
            total: Total number of items
            description: Description for the progress bar
        """
        pass
    
    @abstractmethod
    def update_progress(self, increment: int = 1) -> None:
        """Update progress by increment.
        
        Args:
            increment: Amount to increment progress
        """
        pass
    
    @abstractmethod
    def update_stats(self, stats: DownloadStats) -> None:
        """Update display with download statistics.
        
        Args:
            stats: Current download statistics
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close and clean up the progress display."""
        pass
