# API Documentation

This document provides comprehensive API documentation for the HLS Downloader library, allowing you to integrate it programmatically into your Python applications.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Classes](#core-classes)
- [Configuration](#configuration)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Installation

```bash
pip install hls-downloader
```

## Quick Start

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

async def main():
    # Create configuration
    config = DownloadConfig(
        max_concurrent=20,
        auto_merge=True,
        cleanup_segments=True
    )
    
    # Initialize manager
    manager = DownloadManager(config)
    
    # Download HLS stream
    result = await manager.download_hls(
        url="https://example.com/segment{}.ts",
        output_dir="./downloads"
    )
    
    print(f"Downloaded {result['total_segments']} segments")
    print(f"Merged video: {result['merged_video_path']}")

# Run the download
asyncio.run(main())
```

## Core Classes

### DownloadManager

The main class for coordinating HLS downloads.

#### Constructor

```python
DownloadManager(config: Optional[DownloadConfig] = None)
```

**Parameters:**
- `config` (DownloadConfig, optional): Download configuration. Uses defaults if None.

#### Methods

##### download_hls()

```python
async def download_hls(
    self,
    url: str,
    output_dir: str,
    force_restart: bool = False
) -> dict[str, Any]
```

Download HLS segments and optionally merge them.

**Parameters:**
- `url` (str): HLS segment URL template with `{}` placeholder
- `output_dir` (str): Directory to save downloaded files
- `force_restart` (bool): Ignore existing state and start fresh

**Returns:**
- `dict`: Download results containing:
  - `total_segments` (int): Total number of segments
  - `successful_segments` (int): Successfully downloaded segments
  - `failed_segments` (int): Failed segment downloads
  - `merged_video_path` (str, optional): Path to merged video file
  - `resumed` (bool): Whether download was resumed

**Raises:**
- `DownloadManagerError`: General download errors
- `ConfigurationError`: Invalid configuration
- `VideoMergerError`: Video merging errors

##### has_resumable_download()

```python
def has_resumable_download(self, output_dir: str) -> bool
```

Check if there's a resumable download in the specified directory.

**Parameters:**
- `output_dir` (str): Directory to check

**Returns:**
- `bool`: True if resumable download exists

##### get_resume_info()

```python
def get_resume_info(self, output_dir: str) -> Optional[dict[str, Any]]
```

Get information about resumable download.

**Parameters:**
- `output_dir` (str): Directory to check

**Returns:**
- `dict` or `None`: Resume information or None if not available

### HLSDetector

Detects available HLS segments using binary search algorithm.

#### Constructor

```python
HLSDetector(config: DownloadConfig)
```

#### Methods

##### detect_segments()

```python
async def detect_segments(self, url_template: str) -> list[str]
```

Detect all available segment URLs.

**Parameters:**
- `url_template` (str): URL template with `{}` placeholder

**Returns:**
- `list[str]`: List of available segment URLs

### AsyncDownloader

Handles concurrent downloading of segments.

#### Constructor

```python
AsyncDownloader(config: DownloadConfig)
```

#### Methods

##### download_segments()

```python
async def download_segments(
    self,
    segments: list[SegmentInfo],
    output_dir: str,
    progress_callback: Optional[callable] = None
) -> DownloadStats
```

Download multiple segments concurrently.

**Parameters:**
- `segments` (list[SegmentInfo]): Segments to download
- `output_dir` (str): Output directory
- `progress_callback` (callable, optional): Progress update callback

**Returns:**
- `DownloadStats`: Download statistics

### VideoMerger

Merges downloaded segments into a single video file.

#### Constructor

```python
VideoMerger(config: DownloadConfig)
```

#### Methods

##### merge_segments()

```python
async def merge_segments(
    self,
    segments_dir: str,
    output_file: str,
    progress_callback: Optional[callable] = None
) -> str
```

Merge segments into a video file.

**Parameters:**
- `segments_dir` (str): Directory containing segments
- `output_file` (str): Output video file path
- `progress_callback` (callable, optional): Progress update callback

**Returns:**
- `str`: Path to merged video file

##### check_ffmpeg_available()

```python
def check_ffmpeg_available(self) -> bool
```

Check if FFmpeg is available on the system.

**Returns:**
- `bool`: True if FFmpeg is available

## Configuration

### DownloadConfig

Configuration class for customizing download behavior.

```python
@dataclass
class DownloadConfig:
    max_concurrent: int = 10          # Maximum concurrent downloads (1-100)
    max_retries: int = 3              # Maximum retry attempts (0-10)
    timeout: int = 30                 # Request timeout in seconds (1-300)
    chunk_size: int = 8192           # Download chunk size in bytes
    auto_merge: bool = True          # Automatically merge segments
    cleanup_segments: bool = False    # Delete segments after merging
    output_format: str = "mp4"       # Output video format
```

#### Validation

The configuration automatically validates values:

```python
config = DownloadConfig(max_concurrent=50)  # Valid
config = DownloadConfig(max_concurrent=200)  # Raises ValueError
```

#### Methods

##### validate()

```python
def validate(self) -> bool
```

Validate configuration and return True if valid.

## Data Models

### SegmentInfo

Information about a single segment.

```python
@dataclass
class SegmentInfo:
    url: str                         # Segment URL
    index: int                       # Segment index
    filename: str                    # Local filename
    size: Optional[int] = None       # File size in bytes
    downloaded: bool = False         # Download status
    file_path: Optional[str] = None  # Full file path
```

### DownloadStats

Statistics about the download process.

```python
@dataclass
class DownloadStats:
    total_segments: int              # Total number of segments
    downloaded_segments: int         # Successfully downloaded
    failed_segments: int             # Failed downloads
    total_bytes: int                 # Total bytes downloaded
    start_time: float               # Download start time
    end_time: Optional[float]       # Download end time
    average_speed: float            # Average download speed (bytes/sec)
```

#### Methods

##### calculate_speed()

```python
def calculate_speed(self) -> float
```

Calculate current download speed in bytes per second.

##### get_eta()

```python
def get_eta(self) -> Optional[float]
```

Get estimated time to completion in seconds.

### DownloadState

Represents the current state of a download for resume functionality.

```python
@dataclass
class DownloadState:
    url: str                        # Original URL template
    total_segments: int             # Total segments detected
    downloaded_segments: list[int]  # List of downloaded segment indices
    failed_segments: list[int]      # List of failed segment indices
    created_at: float              # State creation timestamp
    updated_at: float              # Last update timestamp
    resume_count: int = 0          # Number of times resumed
```

## Error Handling

### Exception Hierarchy

```
HLSDownloaderError (base)
├── ConfigurationError
├── DownloadManagerError
├── DetectionError
├── DownloadError
├── VideoMergerError
│   └── FFmpegNotFoundError
└── ValidationError
```

### Common Exceptions

#### ConfigurationError

Raised when configuration is invalid.

```python
from hls_downloader.exceptions import ConfigurationError

try:
    config = DownloadConfig(max_concurrent=200)
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

#### DownloadError

Raised during download failures.

```python
from hls_downloader.exceptions import DownloadError

try:
    await manager.download_hls(url, output_dir)
except DownloadError as e:
    print(f"Download failed: {e}")
    # Check if resume is possible
    if manager.has_resumable_download(output_dir):
        print("Download can be resumed")
```

#### FFmpegNotFoundError

Raised when FFmpeg is not available for merging.

```python
from hls_downloader.exceptions import FFmpegNotFoundError

try:
    await merger.merge_segments(segments_dir, output_file)
except FFmpegNotFoundError:
    print("Please install FFmpeg to merge video segments")
```

## Examples

### Basic Download

```python
import asyncio
from hls_downloader import DownloadManager

async def basic_download():
    manager = DownloadManager()
    result = await manager.download_hls(
        "https://example.com/segment{}.ts",
        "./downloads"
    )
    print(f"Download completed: {result['merged_video_path']}")

asyncio.run(basic_download())
```

### Custom Configuration

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

async def custom_download():
    config = DownloadConfig(
        max_concurrent=20,
        max_retries=5,
        timeout=60,
        auto_merge=True,
        cleanup_segments=True,
        output_format="mkv"
    )
    
    manager = DownloadManager(config)
    result = await manager.download_hls(
        "https://example.com/video_{:03d}.ts",
        "./my_videos"
    )
    
    print(f"Downloaded {result['total_segments']} segments")
    if result.get('merged_video_path'):
        print(f"Merged video: {result['merged_video_path']}")

asyncio.run(custom_download())
```

### Progress Monitoring

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

class ProgressMonitor:
    def __init__(self):
        self.last_update = 0
    
    def on_progress(self, stats):
        """Progress callback function"""
        if stats.downloaded_segments > self.last_update:
            speed = stats.calculate_speed()
            eta = stats.get_eta()
            print(f"Progress: {stats.downloaded_segments}/{stats.total_segments}")
            print(f"Speed: {speed/1024:.1f} KB/s")
            if eta:
                print(f"ETA: {eta:.0f} seconds")
            self.last_update = stats.downloaded_segments

async def monitored_download():
    config = DownloadConfig(max_concurrent=15)
    manager = DownloadManager(config)
    monitor = ProgressMonitor()
    
    # Note: Progress monitoring requires custom implementation
    # This is a conceptual example
    result = await manager.download_hls(
        "https://example.com/segment{}.ts",
        "./downloads"
    )

asyncio.run(monitored_download())
```

### Resume Functionality

```python
import asyncio
from hls_downloader import DownloadManager

async def resume_download():
    manager = DownloadManager()
    output_dir = "./downloads"
    
    # Check if resume is possible
    if manager.has_resumable_download(output_dir):
        print("Resumable download found")
        
        # Get resume information
        info = manager.get_resume_info(output_dir)
        if info:
            print(f"URL: {info['url']}")
            print(f"Progress: {info['downloaded_segments']}/{info['total_segments']}")
            
            # Resume the download
            result = await manager.download_hls(
                info['url'],
                output_dir
            )
            
            if result.get('resumed'):
                print("Download resumed successfully")
    else:
        print("No resumable download found")

asyncio.run(resume_download())
```

### Error Handling

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig
from hls_downloader.exceptions import (
    DownloadError, 
    FFmpegNotFoundError, 
    ConfigurationError
)

async def robust_download():
    try:
        config = DownloadConfig(
            max_concurrent=10,
            max_retries=3,
            auto_merge=True
        )
        
        manager = DownloadManager(config)
        result = await manager.download_hls(
            "https://example.com/segment{}.ts",
            "./downloads"
        )
        
        print("Download successful!")
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        
    except FFmpegNotFoundError:
        print("FFmpeg not found. Install FFmpeg to merge videos.")
        print("Segments downloaded but not merged.")
        
    except DownloadError as e:
        print(f"Download failed: {e}")
        
        # Check if we can resume
        if manager.has_resumable_download("./downloads"):
            print("Download can be resumed later.")
            
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(robust_download())
```

### Batch Downloads

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

async def batch_download():
    config = DownloadConfig(max_concurrent=5)  # Lower concurrency for multiple downloads
    manager = DownloadManager(config)
    
    urls = [
        "https://example.com/video1/segment{}.ts",
        "https://example.com/video2/segment{}.ts",
        "https://example.com/video3/segment{}.ts",
    ]
    
    for i, url in enumerate(urls):
        try:
            print(f"Downloading video {i+1}/{len(urls)}")
            result = await manager.download_hls(
                url,
                f"./downloads/video_{i+1}"
            )
            print(f"Video {i+1} completed: {result['merged_video_path']}")
            
        except Exception as e:
            print(f"Video {i+1} failed: {e}")
            continue

asyncio.run(batch_download())
```

## Best Practices

1. **Configuration**: Always validate your configuration before starting downloads
2. **Error Handling**: Implement comprehensive error handling for production use
3. **Resume Support**: Always check for resumable downloads before starting fresh
4. **Resource Management**: Use appropriate concurrency levels based on your system
5. **Progress Monitoring**: Implement progress callbacks for long-running downloads
6. **Cleanup**: Use `cleanup_segments=True` to save disk space after merging

## Thread Safety

The HLS Downloader uses asyncio and is designed to be used within a single event loop. It is not thread-safe and should not be used across multiple threads without proper synchronization.

For multi-threaded applications, create separate `DownloadManager` instances for each thread or use proper async coordination mechanisms.