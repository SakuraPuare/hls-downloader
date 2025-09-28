# Frequently Asked Questions (FAQ)

## Table of Contents

- [Installation Issues](#installation-issues)
- [Usage Questions](#usage-questions)
- [Performance Issues](#performance-issues)
- [Error Messages](#error-messages)
- [Configuration](#configuration)
- [Resume Functionality](#resume-functionality)
- [Video Merging](#video-merging)
- [Advanced Usage](#advanced-usage)

## Installation Issues

### Q: How do I install FFmpeg?

**A:** FFmpeg is required for video merging. Install it using your system's package manager:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
- Download from [FFmpeg official website](https://ffmpeg.org/download.html)
- Or use Chocolatey: `choco install ffmpeg`
- Or use Scoop: `scoop install ffmpeg`

### Q: I get "command not found" when running hls-downloader

**A:** This usually means the package wasn't installed correctly or the executable isn't in your PATH.

**Solutions:**
1. Reinstall using pip: `pip install --force-reinstall hls-downloader`
2. Use python module syntax: `python -m hls_downloader`
3. Check if it's installed: `pip show hls-downloader`

### Q: Can I use this with Python 3.8?

**A:** No, HLS Downloader requires Python 3.9 or higher due to modern async features and type hints. Please upgrade your Python version.

## Usage Questions

### Q: What URL format should I use?

**A:** The URL must contain a `{}` placeholder where segment numbers will be inserted:

**Correct formats:**
- `https://example.com/segment{}.ts`
- `https://example.com/video_{:03d}.ts` (for zero-padded numbers)
- `https://example.com/part{}.m4s`

**Incorrect formats:**
- `https://example.com/segment1.ts` (no placeholder)
- `https://example.com/segment*.ts` (wrong placeholder)

### Q: How does segment detection work?

**A:** The downloader uses a binary search algorithm:

1. **Quick probe**: Tests exponentially increasing numbers (1, 10, 100, 1000...)
2. **Binary search**: Finds the exact last segment within the detected range
3. **Batch verification**: Checks multiple segments simultaneously for efficiency

This approach is much faster than checking every segment sequentially.

### Q: Can I download segments without merging?

**A:** Yes, use the `--no-merge` flag:

```bash
hls-downloader "https://example.com/seg{}.ts" --no-merge
```

This will download all segments but skip the FFmpeg merging step.

### Q: How do I specify the output filename?

**A:** The output filename is automatically generated based on the URL and format. For custom naming:

```bash
# This creates files in ./my_video/ directory
hls-downloader "https://example.com/seg{}.ts" -o ./my_video --format mp4
```

The final video will be named based on the URL pattern and saved as `merged_video.mp4`.

## Performance Issues

### Q: Downloads are too slow. How can I speed them up?

**A:** Try these optimizations:

1. **Increase concurrency:**
   ```bash
   hls-downloader "url" -c 20  # Use 20 concurrent downloads
   ```

2. **Increase timeout for slow servers:**
   ```bash
   hls-downloader "url" --timeout 60
   ```

3. **Use faster storage (SSD):**
   ```bash
   hls-downloader "url" -o /path/to/ssd/storage
   ```

4. **Monitor performance:**
   ```bash
   hls-downloader "url" --verbose  # Shows speed and statistics
   ```

### Q: What's the optimal concurrency setting?

**A:** It depends on several factors:

- **Fast connection + stable server**: 20-50 concurrent downloads
- **Average connection**: 10-20 concurrent downloads  
- **Slow/unstable connection**: 5-10 concurrent downloads
- **Server rate limiting**: Start with 5 and increase gradually

Monitor with `--verbose` and adjust based on actual performance.

### Q: The downloader uses too much memory/CPU

**A:** Reduce resource usage:

1. **Lower concurrency:** `-c 5`
2. **Smaller chunk size:** `--chunk-size 4096`
3. **Disable verbose output** (saves CPU on display updates)

## Error Messages

### Q: "FFmpeg not found" error

**A:** Install FFmpeg (see installation section above) or skip merging:

```bash
hls-downloader "url" --no-merge  # Skip merging
```

### Q: "Permission denied" error

**A:** This is usually a file system permissions issue:

1. **Check directory permissions:**
   ```bash
   ls -la /path/to/output/directory
   ```

2. **Use a different output directory:**
   ```bash
   hls-downloader "url" -o ~/Downloads/hls
   ```

3. **Create directory first:**
   ```bash
   mkdir -p ./my_downloads
   hls-downloader "url" -o ./my_downloads
   ```

### Q: "Request timeout" errors

**A:** Network or server issues:

1. **Increase timeout:**
   ```bash
   hls-downloader "url" --timeout 60
   ```

2. **Reduce concurrency:**
   ```bash
   hls-downloader "url" -c 5
   ```

3. **Increase retries:**
   ```bash
   hls-downloader "url" -r 5
   ```

### Q: "URL must contain '{}' placeholder" error

**A:** Your URL format is incorrect. Make sure it contains `{}`:

**Wrong:** `https://example.com/segment1.ts`  
**Correct:** `https://example.com/segment{}.ts`

### Q: "No segments found" error

**A:** The detector couldn't find any valid segments:

1. **Check URL manually:** Try accessing `segment1.ts`, `segment0.ts`, etc. in your browser
2. **Different numbering:** Some streams start from 0 or use different patterns
3. **Authentication required:** Some streams require cookies or headers
4. **Use debug mode:** `--debug` to see detailed detection logs

## Configuration

### Q: How do I save my preferred settings?

**A:** Use the `--save-config` option:

```bash
hls-downloader "url" -c 20 --timeout 60 --cleanup --save-config
```

This saves your settings to `~/.hls_downloader/config.json`.

### Q: Where is the configuration file stored?

**A:** Default location: `~/.hls_downloader/config.json`

You can also specify a custom location:
```bash
hls-downloader "url" --config ./my-config.json
```

### Q: What settings can I configure?

**A:** All major options can be saved:

```json
{
  "max_concurrent": 20,
  "max_retries": 3,
  "timeout": 60,
  "chunk_size": 8192,
  "auto_merge": true,
  "cleanup_segments": true,
  "output_format": "mp4"
}
```

### Q: How do I reset to default settings?

**A:** Delete the configuration file:

```bash
rm ~/.hls_downloader/config.json
```

Or create a new one with defaults:
```bash
hls-downloader --save-config  # Uses current defaults
```

## Resume Functionality

### Q: How do I resume an interrupted download?

**A:** Use the `--resume` option:

```bash
hls-downloader --resume -o ./path/to/interrupted/download
```

The URL will be automatically detected from the saved state.

### Q: How do I check if a download can be resumed?

**A:** Use the `--check-resume` option:

```bash
hls-downloader --check-resume -o ./download/directory
```

This shows detailed information about the resumable download.

### Q: Can I resume with different settings?

**A:** Yes, but be careful with certain settings:

**Safe to change:**
- Concurrency (`-c`)
- Timeout (`--timeout`)
- Retries (`-r`)
- Verbose/debug flags

**Avoid changing:**
- Output format (`--format`)
- Cleanup settings (`--cleanup`)
- URL (detected automatically)

### Q: Resume isn't working properly

**A:** Common issues and solutions:

1. **State file corrupted:** Use `--force-restart` to start fresh
2. **Different URL:** Make sure you're using the same URL pattern
3. **Moved files:** Don't move or rename downloaded segments
4. **Permissions:** Ensure write access to the download directory

### Q: How do I force a fresh download?

**A:** Use the `--force-restart` option:

```bash
hls-downloader "url" -o ./directory --force-restart
```

This ignores any existing state and starts from scratch.

## Video Merging

### Q: Merging fails with "codec not supported"

**A:** Try different output formats:

```bash
hls-downloader "url" --format mkv  # More codec support
hls-downloader "url" --format ts   # Keep original format
```

### Q: Can I merge manually if auto-merge fails?

**A:** Yes, the segments are saved and you can merge manually:

```bash
# Download without merging
hls-downloader "url" --no-merge

# Manual merge with FFmpeg
ffmpeg -f concat -safe 0 -i segments/concat_list.txt -c copy output.mp4
```

### Q: Merged video has sync issues

**A:** This can happen with some streams:

1. **Try different format:**
   ```bash
   hls-downloader "url" --format mkv
   ```

2. **Use ts format (no re-encoding):**
   ```bash
   hls-downloader "url" --format ts
   ```

3. **Manual merge with re-encoding:**
   ```bash
   ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -c:a aac output.mp4
   ```

### Q: How do I keep segments after merging?

**A:** Don't use the `--cleanup` flag:

```bash
hls-downloader "url"  # Keeps segments
hls-downloader "url" --cleanup  # Deletes segments after merge
```

## Advanced Usage

### Q: Can I use this programmatically in Python?

**A:** Yes! See the [API Documentation](API.md) for details:

```python
import asyncio
from hls_downloader import DownloadManager, DownloadConfig

async def download():
    config = DownloadConfig(max_concurrent=20)
    manager = DownloadManager(config)
    result = await manager.download_hls("url", "./output")
    return result

asyncio.run(download())
```

### Q: How do I download multiple streams?

**A:** Run separate commands or use the API:

```bash
# Sequential downloads
hls-downloader "stream1_url" -o ./video1
hls-downloader "stream2_url" -o ./video2

# Or use a script for parallel downloads
```

### Q: Can I customize the segment detection algorithm?

**A:** The detection algorithm is optimized and not directly configurable, but you can:

1. **Use debug mode** to see detection process: `--debug`
2. **Modify timeout** for slow servers: `--timeout 60`
3. **For custom needs**, use the Python API to implement custom detection

### Q: How do I handle streams with authentication?

**A:** Currently, basic authentication in URLs is supported:

```bash
hls-downloader "https://user:pass@example.com/segment{}.ts"
```

For complex authentication (cookies, headers), you'll need to use the Python API and customize the HTTP client.

### Q: Can I download only specific segment ranges?

**A:** This feature isn't built-in, but you can:

1. **Use the Python API** to implement custom segment filtering
2. **Download all segments** then manually select the ones you need
3. **Modify the URL pattern** to target specific ranges if the server supports it

### Q: How do I troubleshoot network issues?

**A:** Use these debugging techniques:

1. **Enable debug logging:**
   ```bash
   hls-downloader "url" --debug --log-file debug.log
   ```

2. **Test individual segments:**
   ```bash
   curl -I "https://example.com/segment1.ts"  # Test first segment
   ```

3. **Check network connectivity:**
   ```bash
   ping example.com
   traceroute example.com
   ```

4. **Monitor system resources:**
   ```bash
   htop  # Monitor CPU/memory usage during download
   ```

## Still Need Help?

If your question isn't answered here:

1. **Check the logs** with `--debug --log-file debug.log`
2. **Search existing issues** on [GitHub Issues](https://github.com/hlsdownloader/hls-downloader/issues)
3. **Create a new issue** with:
   - Your command line
   - Error messages
   - Debug logs (if applicable)
   - System information (OS, Python version)

## Contributing to FAQ

Found a common issue not covered here? Please contribute by:

1. Opening an issue or pull request
2. Adding your question and solution
3. Helping other users in discussions