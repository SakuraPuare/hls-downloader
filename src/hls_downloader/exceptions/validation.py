"""Validation exceptions."""

from .base import HLSDownloaderError


class ValidationError(HLSDownloaderError):
    """Raised when validation fails."""
    pass
