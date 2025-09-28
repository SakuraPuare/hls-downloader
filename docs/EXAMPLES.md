# Usage Examples and Best Practices

This document provides practical examples and best practices for using HLS Downloader effectively.

## Table of Contents

- [Basic Examples](#basic-examples)
- [Advanced Usage](#advanced-usage)
- [Performance Optimization](#performance-optimization)
- [Production Use Cases](#production-use-cases)
- [Python API Examples](#python-api-examples)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)

## Basic Examples

### Simple Download

Download HLS segments and merge into MP4:

```bash
hls-downloader "https://example.com/segment{}.ts"
```

**What happens:**
- Detects available segments (1.ts, 2.ts, 3.ts, ...)
- Downloads with 10 concurrent connections
- Merges into `downloads/merged_video.mp4`
- Keeps original segments

### Custom Output Directory

```bash
hls-downloader "https://example.com/video_{:03d}.ts" -o ./my_videos
```

**Result:**
- Downloads to `./my_videos/segments/`
- Merged video: `./my_videos/merged_video.mp4`
- Handles zero-padded numbers (001.ts, 002.ts, ...)

### Different Video Format

```bash
hls-downloader "https://example.com/part{}.ts" --format mkv
```

**Benefits of MKV:**
- Better codec support
- Preserves metadata
- Handles complex streams better

## Advanced Usage

### High-Speed Downloads

For fast connections and stable servers:

```bash
hls-downloader "https://example.com/seg{}.ts" \
  -c 30 \
  --timeout 60 \
  --chunk-size 16384 \
  -o ./fast_download
```

**Configuration explained:**
- `-c 30`: 30 concurrent downloads
- `--timeout 60`: 60-second timeout for slow segments
- `--chunk-size 16384`: Larger chunks for efficiency

### Conservative Downloads

For slow/unstable connections:

```bash
hls-downloader "https://example.com/seg{}.ts" \
  -c 3 \
  -r 5 \
  --timeout 120 \
  --chunk-size 4096
```

**Configuration explained:**
- `-c 3`: Only 3 concurrent downloads
- `-r 5`: Retry up to 5 times
- `--timeout 120`: Long timeout for stability
- `--chunk-size 4096`: Smaller chunks

### Download Without Merging

Keep segments separate for manual processing:

```bash
hls-downloader "https://example.com/seg{}.ts" \
  --no-merge \
  -o ./segments_only
```

**Use cases:**
- Custom post-processing
- Quality analysis
- Selective merging

### Clean Download

Automatically clean up segments after merging:

```bash
hls-downloader "https://example.com/seg{}.ts" \
  --cleanup \
  --format mp4 \
  -o ./clean_download
```

**Result:**
- Downloads segments
- Merges to MP4
- Deletes original segments
- Saves disk space

## Performance Optimization

### Benchmark Different Settings

Test optimal settings for your connection:

```bash
# Test 1: Conservative
time hls-downloader "url" -c 5 -o ./test1

# Test 2: Moderate  
time hls-downloader "url" -c 15 -o ./test2

# Test 3: Aggressive
time hls-downloader "url" -c 30 -o ./test3
```

Compare download times and choose the best performing configuration.

### Monitor Performance

Use verbose mode to monitor performance:

```bash
hls-downloader "https://example.com/seg{}.ts" \
  --verbose \
  -c 20 \
  -o ./monitored_download
```

**Output includes:**
- Real-time download speed
- Segment completion rate
- Error statistics
- ETA calculations

### Optimize for SSD vs HDD

**For SSD storage:**
```bash
hls-downloader "url" \
  -c 25 \
  --chunk-size 16384 \
  -o /path/to/ssd
```

**For HDD storage:**
```bash
hls-downloader "url" \
  -c 10 \
  --chunk-size 8192 \
  -o /path/to/hdd
```

## Production Use Cases

### Automated Download Script

Create a script for regular downloads:

```bash
#!/bin/bash
# download_stream.sh

URL="$1"
OUTPUT_DIR="$2"
DATE=$(date +%Y%m%d_%H%M%S)

if [ -z "$URL" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <url> <output_dir>"
    exit 1
fi

# Create timestamped directory
FULL_OUTPUT="$OUTPUT_DIR/download_$DATE"

# Download with production settings
hls-downloader "$URL" \
  -o "$FULL_OUTPUT" \
  -c 15 \
  -r 3 \
  --timeout 60 \
  --cleanup \
  --format mp4 \
  --log-file "$FULL_OUTPUT/download.log" \
  --verbose

# Check if successful
if [ $? -eq 0 ]; then
    echo "Download completed: $FULL_OUTPUT"
    # Optional: notify completion
    # notify-send "Download completed" "$FULL_OUTPUT"
else
    echo "Download failed: $FULL_OUTPUT"
    exit 1
fi
```

Usage:
```bash
chmod +x download_stream.sh
./download_stream.sh "https://example.com/seg{}.ts" ./downloads
```

### Batch Processing

Download multiple streams:

```bash
#!/bin/bash
# batch_download.sh

URLS=(
    "https://stream1.com/seg{}.ts"
    "https://stream2.com/part{}.ts"
    "https://stream3.com/video_{:03d}.ts"
)

for i in "${!URLS[@]}"; do
    echo "Downloading stream $((i+1))/${#URLS[@]}"
    
    hls-downloader "${URLS[$i]}" \
      -o "./batch_downloads/stream_$((i+1))" \
      -c 10 \
      --cleanup \
      --format mp4
    
    if [ $? -ne 0 ]; then
        echo "Failed to download stream $((i+1))"
        # Continue with next stream or exit
        # exit 1
    fi
done

echo "Batch download completed"
```

### Resume-Aware Script

Script that automatically resumes interrupted downloads:

```bash
#!/bin/bash
# smart_download.sh

URL="$1"
OUTPUT_DIR="$2"

if [ -z "$URL" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <url> <output_dir>"
    exit 1
fi

# Check if resumable download exists
if hls-downloader --check-resume -o "$OUTPUT_DIR" > /dev/null 2>&1; then
    echo "Resumable download found. Resuming..."
    hls-downloader --resume -o "$OUTPUT_DIR" --verbose
else
    echo "Starting new download..."
    hls-downloader "$URL" -o "$OUTPUT_DIR" -c 15 --cleanup --verbose
fi
```

### Configuration Management

Save and reuse configurations:

```bash
# Save optimal settings for your environment
hls-downloader "test_url" \
  -c 20 \
  -r 3 \
  --timeout 60 \
  --cleanup \
  --format mp4 \
  --save-config

# Later downloads use saved settings
hls-downloader "https://example.com/seg{}.ts" -o ./download1
hls-downloader "https://example.com/seg{}.ts" -o ./download2
```

## Python API Examples

### Basic API Usage

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

async def basic_download():
    # Create configuration
    config = DownloadConfig(
        max_concurrent=15,
        auto_merge=True,
        cleanup_segments=True,
        output_format="mp4"
    )
    
    # Initialize manager
    manager = DownloadManager(config)
    
    # Download
    result = await manager.download_hls(
        url="https://example.com/segment{}.ts",
        output_dir="./downloads"
    )
    
    print(f"Success: {result['successful_segments']}/{result['total_segments']}")
    if result.get('merged_video_path'):
        print(f"Video: {result['merged_video_path']}")

asyncio.run(basic_download())
```

### Progress Monitoring

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

class ProgressTracker:
    def __init__(self):
        self.last_progress = 0
    
    def update(self, current, total):
        progress = (current / total) * 100
        if progress - self.last_progress >= 5:  # Update every 5%
            print(f"Progress: {progress:.1f}% ({current}/{total})")
            self.last_progress = progress

async def monitored_download():
    config = DownloadConfig(max_concurrent=20)
    manager = DownloadManager(config)
    tracker = ProgressTracker()
    
    # This is a conceptual example - actual progress monitoring
    # would require custom implementation or using the CLI
    result = await manager.download_hls(
        "https://example.com/segment{}.ts",
        "./downloads"
    )
    
    return result

asyncio.run(monitored_download())
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
            max_concurrent=15,
            max_retries=5,
            timeout=60
        )
        
        manager = DownloadManager(config)
        result = await manager.download_hls(
            "https://example.com/segment{}.ts",
            "./downloads"
        )
        
        print("Download successful!")
        return result
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        
    except FFmpegNotFoundError:
        print("FFmpeg not found. Segments downloaded but not merged.")
        
    except DownloadError as e:
        print(f"Download failed: {e}")
        
        # Check if resume is possible
        if manager.has_resumable_download("./downloads"):
            print("Download can be resumed later.")
            
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(robust_download())
```

### Batch Downloads with API

```python
import asyncio
from pathlib import Path
from hls_downloader import DownloadManager, DownloadConfig

async def batch_download():
    streams = [
        ("https://stream1.com/seg{}.ts", "./downloads/stream1"),
        ("https://stream2.com/part{}.ts", "./downloads/stream2"),
        ("https://stream3.com/video{}.ts", "./downloads/stream3"),
    ]
    
    config = DownloadConfig(
        max_concurrent=10,  # Lower for multiple simultaneous downloads
        cleanup_segments=True,
        output_format="mp4"
    )
    
    results = []
    
    for url, output_dir in streams:
        try:
            print(f"Downloading: {url}")
            manager = DownloadManager(config)
            result = await manager.download_hls(url, output_dir)
            results.append((url, "success", result))
            print(f"Completed: {output_dir}")
            
        except Exception as e:
            results.append((url, "failed", str(e)))
            print(f"Failed: {url} - {e}")
    
    # Summary
    successful = sum(1 for _, status, _ in results if status == "success")
    print(f"\nBatch completed: {successful}/{len(streams)} successful")
    
    return results

asyncio.run(batch_download())
```

## Best Practices

### 1. Start Conservative

Always start with conservative settings and optimize:

```bash
# Start here
hls-downloader "url" -c 5 -r 3

# Then optimize
hls-downloader "url" -c 15 -r 3

# Finally tune
hls-downloader "url" -c 25 -r 3 --timeout 60
```

### 2. Use Resume for Large Downloads

For downloads with many segments:

```bash
# Enable resume-friendly settings
hls-downloader "url" \
  -o ./large_download \
  -c 15 \
  --verbose \
  --log-file ./large_download/download.log

# If interrupted, resume with:
hls-downloader --resume -o ./large_download
```

### 3. Monitor System Resources

```bash
# Monitor during download
htop &  # or top on macOS
hls-downloader "url" --verbose

# Check disk space
df -h
```

### 4. Save Configurations

```bash
# For fast connections
hls-downloader "url" -c 25 --timeout 60 --save-config

# For slow connections  
hls-downloader "url" -c 5 --timeout 120 --save-config
```

### 5. Use Appropriate Output Formats

```bash
# For compatibility
hls-downloader "url" --format mp4

# For quality preservation
hls-downloader "url" --format mkv

# For no re-encoding
hls-downloader "url" --format ts
```

### 6. Handle Errors Gracefully

```bash
# Production script pattern
if ! hls-downloader "url" -o ./download --verbose; then
    echo "Download failed, checking resume..."
    if hls-downloader --check-resume -o ./download; then
        echo "Resume possible"
        hls-downloader --resume -o ./download
    else
        echo "Cannot resume, manual intervention needed"
        exit 1
    fi
fi
```

## Common Patterns

### Pattern 1: Test-Then-Download

```bash
# Test with single connection first
hls-downloader "url" -c 1 -o ./test --no-merge

# If successful, do full download
if [ $? -eq 0 ]; then
    rm -rf ./test
    hls-downloader "url" -c 20 -o ./full_download --cleanup
fi
```

### Pattern 2: Quality-First Download

```bash
# Download without merging first
hls-downloader "url" --no-merge -o ./segments

# Inspect quality
ffprobe ./segments/segment_001.ts

# Merge with appropriate settings
ffmpeg -f concat -safe 0 -i ./segments/concat_list.txt \
  -c:v libx264 -crf 18 -c:a aac high_quality.mp4
```

### Pattern 3: Backup-Aware Download

```bash
# Create backup of segments before merging
hls-downloader "url" --no-merge -o ./download
cp -r ./download/segments ./download/segments_backup

# Merge with cleanup
cd ./download
ffmpeg -f concat -safe 0 -i segments/concat_list.txt -c copy merged.mp4

# Remove segments only if merge successful
if [ $? -eq 0 ]; then
    rm -rf segments
    echo "Merge successful, segments removed"
else
    echo "Merge failed, segments preserved"
fi
```

### Pattern 4: Network-Adaptive Download

```bash
#!/bin/bash
# Adaptive download based on network speed

# Test network speed (simplified)
SPEED=$(curl -o /dev/null -s -w '%{speed_download}' http://speedtest.wdc01.softlayer.com/downloads/test10.zip)
SPEED_MBPS=$(echo "scale=2; $SPEED / 1024 / 1024 * 8" | bc)

echo "Detected speed: ${SPEED_MBPS} Mbps"

# Adjust concurrency based on speed
if (( $(echo "$SPEED_MBPS > 50" | bc -l) )); then
    CONCURRENCY=30
elif (( $(echo "$SPEED_MBPS > 20" | bc -l) )); then
    CONCURRENCY=15
else
    CONCURRENCY=5
fi

echo "Using concurrency: $CONCURRENCY"

hls-downloader "$1" -c $CONCURRENCY -o "$2"
```

These examples and patterns should help you use HLS Downloader effectively in various scenarios. Remember to always test with small downloads first and gradually optimize your settings based on your specific network conditions and requirements.