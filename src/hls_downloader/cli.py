"""Command line interface for HLS downloader."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from .download_manager import DownloadManager
from .models import DownloadConfig
from .logging_config import LoggingConfig
from .user_messages import UserMessageDisplay, show_user_error, show_success, show_info


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing config file {config_path}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading config file {config_path}: {e}", file=sys.stderr)
        return {}


def save_config_file(config_path: Path, config: Dict[str, Any]) -> bool:
    """Save configuration to JSON file."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config file {config_path}: {e}", file=sys.stderr)
        return False


def get_default_config_path() -> Path:
    """Get default configuration file path."""
    home = Path.home()
    return home / '.hls_downloader' / 'config.json'


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="HLS Downloader - Download and merge HLS stream segments",
        epilog="""
Examples:
  %(prog)s "https://example.com/segment{}.ts"
  %(prog)s "https://example.com/video_{:03d}.ts" -o ./my_video -c 20
  %(prog)s "https://example.com/part{}.ts" --no-merge --cleanup
  %(prog)s --save-config  # Save current settings as default
  %(prog)s --show-config  # Show current configuration
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Positional argument
    parser.add_argument(
        "url",
        nargs='?',
        help="HLS segment URL template (e.g., 'https://example.com/segment{}.ts')",
    )

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        "-o", "--output",
        default="./downloads",
        help="Output directory for downloaded files (default: ./downloads)",
    )
    output_group.add_argument(
        "--format",
        default="mp4",
        choices=["mp4", "mkv", "avi", "mov", "ts"],
        help="Output video format (default: mp4)",
    )

    # Download options
    download_group = parser.add_argument_group('Download Options')
    download_group.add_argument(
        "-c", "--concurrent",
        type=int,
        default=10,
        metavar="N",
        help="Maximum concurrent downloads (1-100, default: 10)",
    )
    download_group.add_argument(
        "-r", "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Maximum retry attempts (0-10, default: 3)",
    )
    download_group.add_argument(
        "--timeout",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Request timeout in seconds (1-300, default: 30)",
    )
    download_group.add_argument(
        "--chunk-size",
        type=int,
        default=8192,
        metavar="BYTES",
        help="Download chunk size in bytes (default: 8192)",
    )

    # Processing options
    process_group = parser.add_argument_group('Processing Options')
    process_group.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip automatic merging of segments",
    )
    process_group.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete segment files after merging",
    )

    # Configuration options
    config_group = parser.add_argument_group('Configuration Options')
    config_group.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (default: ~/.hls_downloader/config.json)",
    )
    config_group.add_argument(
        "--save-config",
        action="store_true",
        help="Save current settings as default configuration",
    )
    config_group.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and exit",
    )

    # Resume options
    resume_group = parser.add_argument_group('Resume Options')
    resume_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted download in output directory",
    )
    resume_group.add_argument(
        "--force-restart",
        action="store_true",
        help="Ignore existing state and start fresh download",
    )
    resume_group.add_argument(
        "--check-resume",
        action="store_true",
        help="Check if there's a resumable download and show info",
    )

    # Logging options
    logging_group = parser.add_argument_group('Logging Options')
    logging_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    logging_group.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with detailed logging",
    )
    logging_group.add_argument(
        "--log-file",
        type=Path,
        help="Save logs to file (with automatic rotation)",
    )
    logging_group.add_argument(
        "--structured-logs",
        action="store_true",
        help="Use structured JSON logging format",
    )
    
    # Utility options
    parser.add_argument(
        "--version",
        action="version",
        version="HLS Downloader 1.0.0",
    )

    return parser


def merge_config(base_config: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Merge configuration from file with CLI arguments."""
    # CLI arguments take precedence over config file
    merged = base_config.copy()
    
    # Map CLI arguments to config keys
    arg_mapping = {
        'concurrent': 'max_concurrent',
        'retries': 'max_retries',
        'timeout': 'timeout',
        'chunk_size': 'chunk_size',
        'format': 'output_format',
        'no_merge': ('auto_merge', lambda x: not x),  # Invert the boolean
        'cleanup': 'cleanup_segments',
    }
    
    for cli_arg, config_key in arg_mapping.items():
        if hasattr(cli_args, cli_arg):
            value = getattr(cli_args, cli_arg)
            if value is not None:
                if isinstance(config_key, tuple):
                    # Handle special cases like boolean inversion
                    key, transform = config_key
                    merged[key] = transform(value)
                else:
                    merged[config_key] = value
    
    return merged


def validate_arguments(args: argparse.Namespace) -> bool:
    """Validate command line arguments."""
    errors = []
    
    # Validate concurrent downloads
    if args.concurrent < 1 or args.concurrent > 100:
        errors.append("Concurrent downloads must be between 1 and 100")
    
    # Validate retries
    if args.retries < 0 or args.retries > 10:
        errors.append("Retries must be between 0 and 10")
    
    # Validate timeout
    if args.timeout < 1 or args.timeout > 300:
        errors.append("Timeout must be between 1 and 300 seconds")
    
    # Validate chunk size
    if args.chunk_size < 1 or args.chunk_size > 1024 * 1024:
        errors.append("Chunk size must be between 1 and 1048576 bytes")
    
    # Validate URL format if provided
    if args.url and '{}' not in args.url:
        errors.append("URL must contain '{}' placeholder for segment numbers")
    
    if errors:
        for error in errors:
            show_user_error(error, show_help=False)
        return False
    
    return True


def show_config(config: DownloadConfig, config_path: Optional[Path] = None) -> None:
    """Display current configuration."""
    print("Current Configuration:")
    print("=" * 50)
    print(f"Max Concurrent Downloads: {config.max_concurrent}")
    print(f"Max Retries: {config.max_retries}")
    print(f"Timeout: {config.timeout} seconds")
    print(f"Chunk Size: {config.chunk_size} bytes")
    print(f"Auto Merge: {config.auto_merge}")
    print(f"Cleanup Segments: {config.cleanup_segments}")
    print(f"Output Format: {config.output_format}")
    
    if config_path:
        print(f"\nConfig file: {config_path}")
        if config_path.exists():
            print("Status: Found")
        else:
            print("Status: Not found (using defaults)")


def show_resume_info(output_dir: str, manager: DownloadManager) -> None:
    """Display resume information for a directory."""
    if not manager.has_resumable_download(output_dir):
        print(f"No resumable download found in: {output_dir}")
        return
    
    info = manager.get_resume_info(output_dir)
    if not info:
        print(f"Cannot read resume information from: {output_dir}")
        return
    
    print("Resumable Download Found:")
    print("=" * 50)
    print(f"URL: {info['url']}")
    print(f"Status: {info['status']}")
    print(f"Total Segments: {info['total_segments']}")
    print(f"Downloaded: {info['downloaded_segments']}")
    print(f"Failed: {info['failed_segments']}")
    
    if info['total_segments'] > 0:
        completion = (info['downloaded_segments'] / info['total_segments']) * 100
        print(f"Completion: {completion:.1f}%")
    
    # Show timestamps if available
    if info.get('created_at'):
        import datetime
        created = datetime.datetime.fromtimestamp(info['created_at'])
        print(f"Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if info.get('updated_at'):
        import datetime
        updated = datetime.datetime.fromtimestamp(info['updated_at'])
        print(f"Last Updated: {updated.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if info.get('resume_count', 0) > 0:
        print(f"Resume Count: {info['resume_count']}")
    
    print(f"\nTo resume: {sys.argv[0]} --resume -o \"{output_dir}\" \"{info['url']}\"")


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging first
    logging_config = LoggingConfig.from_cli_args(
        verbose=args.verbose,
        debug=args.debug,
        log_file=str(args.log_file) if args.log_file else None,
        structured=args.structured_logs
    )
    logging_config.setup_logging()
    
    # Initialize user message display
    message_display = UserMessageDisplay(verbose=args.verbose or args.debug)

    # Determine config file path
    config_path = args.config if args.config else get_default_config_path()
    
    # Load configuration from file
    file_config = load_config_file(config_path)
    
    # Merge file config with CLI arguments
    merged_config = merge_config(file_config, args)
    
    # Create download configuration
    try:
        config = DownloadConfig(**merged_config)
    except (TypeError, ValueError) as e:
        show_user_error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Initialize download manager for special commands that need it
    manager = DownloadManager(config)
    
    # Handle special commands
    if args.show_config:
        show_config(config, config_path)
        return
    
    if args.save_config:
        config_dict = {
            'max_concurrent': config.max_concurrent,
            'max_retries': config.max_retries,
            'timeout': config.timeout,
            'chunk_size': config.chunk_size,
            'auto_merge': config.auto_merge,
            'cleanup_segments': config.cleanup_segments,
            'output_format': config.output_format,
        }
        if save_config_file(config_path, config_dict):
            show_success(f"Configuration saved to {config_path}")
        else:
            show_user_error("Failed to save configuration", show_help=False)
            sys.exit(1)
        return
    
    if args.check_resume:
        show_resume_info(args.output, manager)
        return
    
    # Validate arguments
    if not validate_arguments(args):
        sys.exit(1)
    
    # Handle resume mode
    if args.resume:
        # For resume, try to get URL from existing state if not provided
        if not args.url:
            if manager.has_resumable_download(args.output):
                resume_info = manager.get_resume_info(args.output)
                if resume_info and resume_info.get('url'):
                    args.url = resume_info['url']
                    show_info(f"Resuming download: {args.url}")
                else:
                    show_user_error("Cannot determine URL from existing state", show_help=False)
                    sys.exit(1)
            else:
                show_user_error(f"No resumable download found in {args.output}", show_help=False)
                sys.exit(1)
    
    # URL is required for download
    if not args.url:
        show_user_error("URL is required for download")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        show_user_error(f"Error creating output directory: {e}", show_help=False)
        sys.exit(1)

    try:
        if args.verbose:
            print(f"Starting download with configuration:")
            show_config(config)
            print(f"\nDownloading from: {args.url}")
            print(f"Output directory: {output_path}")
            
            # Show resume info if applicable
            if args.resume and manager.has_resumable_download(str(output_path)):
                print("\nResume Information:")
                show_resume_info(str(output_path), manager)
            
            print("-" * 50)
        
        # Start download with appropriate resume settings
        result = await manager.download_hls(
            args.url, 
            str(output_path),
            force_restart=args.force_restart
        )
        
        # Show results
        if result.get("resumed"):
            print(f"Download resumed and completed successfully!")
            print(f"Resumed {result.get('existing_segments', 0)} existing segments")
        else:
            print("Download completed successfully!")
        
        if args.verbose:
            print(f"Total segments: {result.get('total_segments', 0)}")
            print(f"Successful: {result.get('successful_segments', 0)}")
            if result.get('failed_segments', 0) > 0:
                print(f"Failed: {result.get('failed_segments', 0)}")
            if result.get('merged_video_path'):
                print(f"Merged video: {result['merged_video_path']}")
        
    except KeyboardInterrupt:
        show_user_error("Download interrupted by user", show_help=False)
        message_display.show_resume_help(args.output)
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        show_user_error(f"Download failed: {e}", show_help=False)
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            message_display.show_download_tips()
        sys.exit(1)


def cli_main() -> None:
    """Synchronous wrapper for main async function."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
