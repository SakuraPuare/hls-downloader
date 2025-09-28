"""Interface definitions for HLS downloader components."""

from .detector import DetectorInterface
from .downloader import DownloaderInterface
from .merger import MergerInterface
from .progress import ProgressInterface

__all__ = [
    "DetectorInterface",
    "DownloaderInterface", 
    "MergerInterface",
    "ProgressInterface",
]
