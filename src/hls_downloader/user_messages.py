"""User-friendly error messages and display utilities."""

import sys
from typing import Any, Dict, List, Optional

from loguru import logger

from .error_handler import DownloadError, ErrorType, HTTPError


class UserMessageDisplay:
    """Display user-friendly messages and error information."""
    
    def __init__(self, verbose: bool = False):
        """Initialize message display.
        
        Args:
            verbose: Whether to show verbose information
        """
        self.verbose = verbose
    
    def show_error(self, error: DownloadError, show_technical: bool = False) -> None:
        """Display user-friendly error message.
        
        Args:
            error: The download error to display
            show_technical: Whether to show technical details
        """
        # Get user-friendly message
        friendly_message = self._get_friendly_error_message(error)
        
        # Display main error message
        print(f"❌ {friendly_message}", file=sys.stderr)
        
        # Show segment context if available
        if error.segment:
            print(f"   Segment: {error.segment.index} ({error.segment.filename})", file=sys.stderr)
        
        # Show technical details if requested
        if show_technical or self.verbose:
            print(f"   Technical: {error}", file=sys.stderr)
            if error.original_error:
                print(f"   Original: {error.original_error}", file=sys.stderr)
    
    def show_error_summary(self, error_summary: Dict[str, Any]) -> None:
        """Display error summary at end of download.
        
        Args:
            error_summary: Error summary from ErrorHandler
        """
        total_errors = error_summary.get("total_errors", 0)
        
        if total_errors == 0:
            print("✅ Download completed successfully with no errors!")
            return
        
        print(f"\n⚠️  Download completed with {total_errors} error(s):")
        
        # Show error breakdown
        error_breakdown = error_summary.get("error_breakdown", {})
        for error_type, count in error_breakdown.items():
            friendly_type = self._get_friendly_error_type(error_type)
            print(f"   • {friendly_type}: {count}")
        
        # Show retry information
        active_retries = error_summary.get("active_retries", 0)
        if active_retries > 0:
            print(f"   • Segments with retries: {active_retries}")
        
        # Show recommendations
        self._show_error_recommendations(error_breakdown)
    
    def show_download_tips(self) -> None:
        """Show helpful tips for download issues."""
        print("\n💡 Tips for better downloads:")
        print("   • Use --debug for detailed error information")
        print("   • Try reducing --concurrent if you see many network errors")
        print("   • Use --retries to increase retry attempts for unstable connections")
        print("   • Check your internet connection if you see timeout errors")
    
    def show_ffmpeg_help(self) -> None:
        """Show help for ffmpeg installation."""
        print("\n🎬 FFmpeg is required for video merging:")
        print("   • macOS: brew install ffmpeg")
        print("   • Ubuntu/Debian: sudo apt install ffmpeg")
        print("   • Windows: Download from https://ffmpeg.org/download.html")
        print("   • Or use --no-merge to skip automatic merging")
    
    def show_resume_help(self, output_dir: str) -> None:
        """Show help for resuming downloads.
        
        Args:
            output_dir: Output directory path
        """
        print(f"\n🔄 To resume this download later:")
        print(f"   hls-downloader --resume -o \"{output_dir}\" <URL>")
        print("   Or use --check-resume to see resumable downloads")
    
    def _get_friendly_error_message(self, error: DownloadError) -> str:
        """Get user-friendly error message.
        
        Args:
            error: The download error
            
        Returns:
            User-friendly error message
        """
        if error.error_type == ErrorType.NETWORK_ERROR:
            return "Network connection failed - check your internet connection"
        
        elif error.error_type == ErrorType.TIMEOUT_ERROR:
            return "Request timed out - the server may be slow or overloaded"
        
        elif error.error_type == ErrorType.HTTP_ERROR:
            if isinstance(error, HTTPError):
                if error.status_code == 404:
                    return "Segment not found - the video may be incomplete or URL incorrect"
                elif error.status_code == 403:
                    return "Access denied - you may not have permission to download this content"
                elif error.status_code == 429:
                    return "Rate limited - too many requests, try reducing concurrent downloads"
                elif error.status_code >= 500:
                    return "Server error - the video server is experiencing issues"
                else:
                    return f"HTTP error {error.status_code} - server returned an error"
            return "HTTP request failed"
        
        elif error.error_type == ErrorType.FILE_SYSTEM_ERROR:
            error_str = str(error).lower()
            if "permission denied" in error_str:
                return "Permission denied - check file/directory permissions"
            elif "no space left" in error_str:
                return "Disk full - free up space and try again"
            elif "file exists" in error_str:
                return "File already exists - use --force-restart to overwrite"
            else:
                return "File system error - check disk space and permissions"
        
        elif error.error_type == ErrorType.INTEGRITY_ERROR:
            return "Downloaded file is corrupted - will retry automatically"
        
        else:
            return f"Unexpected error occurred: {error}"
    
    def _get_friendly_error_type(self, error_type: str) -> str:
        """Get user-friendly error type name.
        
        Args:
            error_type: Error type string
            
        Returns:
            User-friendly error type name
        """
        type_names = {
            "network_error": "Network errors",
            "timeout_error": "Timeout errors", 
            "http_error": "HTTP errors",
            "file_system_error": "File system errors",
            "integrity_error": "File corruption errors",
            "unknown_error": "Unknown errors"
        }
        return type_names.get(error_type, error_type.replace("_", " ").title())
    
    def _show_error_recommendations(self, error_breakdown: Dict[str, int]) -> None:
        """Show recommendations based on error types.
        
        Args:
            error_breakdown: Dictionary of error types and counts
        """
        recommendations = []
        
        if error_breakdown.get("network_error", 0) > 0:
            recommendations.append("• Check your internet connection stability")
            recommendations.append("• Try reducing --concurrent to lower network load")
        
        if error_breakdown.get("timeout_error", 0) > 0:
            recommendations.append("• Increase --timeout for slower connections")
            recommendations.append("• Try downloading during off-peak hours")
        
        if error_breakdown.get("http_error", 0) > 0:
            recommendations.append("• Verify the URL is correct and accessible")
            recommendations.append("• Some segments may be missing from the server")
        
        if error_breakdown.get("file_system_error", 0) > 0:
            recommendations.append("• Check available disk space")
            recommendations.append("• Verify write permissions to output directory")
        
        if recommendations:
            print("\n💡 Recommendations:")
            for rec in recommendations:
                print(f"   {rec}")


def display_startup_info(url: str, output_dir: str, config: Dict[str, Any]) -> None:
    """Display startup information.
    
    Args:
        url: Download URL
        output_dir: Output directory
        config: Download configuration
    """
    print(f"🚀 Starting HLS download")
    print(f"   URL: {url}")
    print(f"   Output: {output_dir}")
    print(f"   Concurrent: {config.get('max_concurrent', 'N/A')}")
    print(f"   Max retries: {config.get('max_retries', 'N/A')}")
    print()


def display_completion_info(
    total_segments: int,
    successful_segments: int,
    failed_segments: int,
    duration: float,
    output_file: Optional[str] = None
) -> None:
    """Display completion information.
    
    Args:
        total_segments: Total number of segments
        successful_segments: Number of successful downloads
        failed_segments: Number of failed downloads
        duration: Total download duration in seconds
        output_file: Path to merged output file
    """
    success_rate = (successful_segments / total_segments * 100) if total_segments > 0 else 0
    
    print(f"\n📊 Download Statistics:")
    print(f"   Total segments: {total_segments}")
    print(f"   Successful: {successful_segments}")
    print(f"   Failed: {failed_segments}")
    print(f"   Success rate: {success_rate:.1f}%")
    print(f"   Duration: {duration:.1f} seconds")
    
    if output_file:
        print(f"   Merged video: {output_file}")


def display_progress_info(completed: int, total: int, speed: float) -> None:
    """Display progress information for non-tqdm output.
    
    Args:
        completed: Number of completed segments
        total: Total number of segments
        speed: Current download speed (segments/second)
    """
    percentage = (completed / total * 100) if total > 0 else 0
    print(f"\r📥 Progress: {completed}/{total} ({percentage:.1f}%) - {speed:.1f} segments/sec", end="", flush=True)


def show_debug_info(message: str, **kwargs) -> None:
    """Show debug information when in debug mode.
    
    Args:
        message: Debug message
        **kwargs: Additional context data
    """
    logger.bind(**kwargs).debug(message)


def show_user_error(message: str, show_help: bool = True) -> None:
    """Show user error and optionally help.
    
    Args:
        message: Error message to show
        show_help: Whether to show help information
    """
    print(f"❌ Error: {message}", file=sys.stderr)
    
    if show_help:
        print("   Use --help for usage information", file=sys.stderr)


def show_warning(message: str) -> None:
    """Show warning message to user.
    
    Args:
        message: Warning message
    """
    print(f"⚠️  Warning: {message}", file=sys.stderr)


def show_success(message: str) -> None:
    """Show success message to user.
    
    Args:
        message: Success message
    """
    print(f"✅ {message}")


def show_info(message: str) -> None:
    """Show info message to user.
    
    Args:
        message: Info message
    """
    print(f"ℹ️  {message}")