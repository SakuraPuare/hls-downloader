"""Command line interface for HLS downloader."""

import argparse
import asyncio
import sys
from pathlib import Path

from .download_manager import DownloadManager
from .models import DownloadConfig


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="HLS Downloader - Download and merge HLS stream segments"
    )

    parser.add_argument(
        "url",
        help="HLS segment URL template (e.g., 'https://example.com/segment{}.ts')",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="./downloads",
        help="Output directory for downloaded files (default: ./downloads)",
    )

    parser.add_argument(
        "-c",
        "--concurrent",
        type=int,
        default=10,
        help="Maximum concurrent downloads (default: 10)",
    )

    parser.add_argument(
        "-r",
        "--retries",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )

    parser.add_argument(
        "--no-merge", action="store_true", help="Skip automatic merging of segments"
    )

    parser.add_argument(
        "--cleanup", action="store_true", help="Delete segment files after merging"
    )

    parser.add_argument(
        "--format", default="mp4", help="Output video format (default: mp4)"
    )

    return parser


async def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Create download configuration from arguments
    config = DownloadConfig(
        max_concurrent=args.concurrent,
        max_retries=args.retries,
        timeout=args.timeout,
        auto_merge=not args.no_merge,
        cleanup_segments=args.cleanup,
        output_format=args.format,
    )

    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize download manager and start download
    manager = DownloadManager(config)

    try:
        await manager.download_hls(args.url, str(output_path))
        print("Download completed successfully!")
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)


def cli_main() -> None:
    """Synchronous wrapper for main async function."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
