# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with HLS Downloader.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Problems](#installation-problems)
- [Network Issues](#network-issues)
- [Performance Problems](#performance-problems)
- [File System Issues](#file-system-issues)
- [Video Merging Problems](#video-merging-problems)
- [Resume Issues](#resume-issues)
- [Debug Mode](#debug-mode)
- [System-Specific Issues](#system-specific-issues)

## Quick Diagnostics

Before diving into specific issues, run these quick checks:

### 1. Basic System Check

```bash
# Check Python version (requires 3.9+)
python --version

# Check if hls-downloader is installed
hls-downloader --version

# Check FFmpeg availability
ffmpeg -version

# Test basic functionality
hls-downloader --show-config
```

### 2. Test with Debug Mode

```bash
hls-downloader "your_url" --debug --log-file debug.log
```

This creates detailed logs that help identify the root cause.

### 3. Verify URL Format

```bash
# Test if your URL format is correct
curl -I "https://example.com/segment1.ts"  # Replace with your actual URL
```

## Installation Problems

### Issue: "hls-downloader: command not found"

**Symptoms:**
- Command not recognized after installation
- "No such file or directory" error

**Diagnosis:**
```bash
# Check if package is installed
pip show hls-downloader

# Check Python scripts directory
python -m site --user-base
```

**Solutions:**

1. **Reinstall the package:**
   ```bash
   pip uninstall hls-downloader
   pip install hls-downloader
   ```

2. **Use module syntax:**
   ```bash
   python -m hls_downloader "your_url"
   ```

3. **Check PATH environment:**
   ```bash
   # Add Python scripts to PATH (Linux/macOS)
   export PATH="$HOME/.local/bin:$PATH"
   
   # Windows
   set PATH=%APPDATA%\Python\Python39\Scripts;%PATH%
   ```

### Issue: "ModuleNotFoundError" when importing

**Symptoms:**
- Import errors in Python scripts
- Missing dependency errors

**Diagnosis:**
```bash
# Check installed packages
pip list | grep -E "(httpx|tqdm|asyncio)"

# Check Python environment
which python
which pip
```

**Solutions:**

1. **Install in correct environment:**
   ```bash
   # If using virtual environment
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   pip install hls-downloader
   ```

2. **Install with all dependencies:**
   ```bash
   pip install --force-reinstall hls-downloader
   ```

### Issue: FFmpeg not found

**Symptoms:**
- "FFmpeg not found" error during merging
- Video merging fails

**Diagnosis:**
```bash
# Check if FFmpeg is installed
ffmpeg -version
which ffmpeg  # Linux/macOS
where ffmpeg  # Windows
```

**Solutions:**

1. **Install FFmpeg:**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows (Chocolatey)
   choco install ffmpeg
   ```

2. **Skip merging if FFmpeg unavailable:**
   ```bash
   hls-downloader "url" --no-merge
   ```

3. **Manual FFmpeg installation:**
   - Download from [FFmpeg official website](https://ffmpeg.org/download.html)
   - Add to system PATH

## Network Issues

### Issue: Connection timeouts

**Symptoms:**
- "Request timeout" errors
- Downloads hang or fail frequently
- Slow download speeds

**Diagnosis:**
```bash
# Test network connectivity
ping example.com
curl -I "https://example.com/segment1.ts"

# Check with verbose output
hls-downloader "url" --verbose --timeout 60
```

**Solutions:**

1. **Increase timeout:**
   ```bash
   hls-downloader "url" --timeout 60  # 60 seconds
   ```

2. **Reduce concurrency:**
   ```bash
   hls-downloader "url" -c 5  # Only 5 concurrent downloads
   ```

3. **Increase retries:**
   ```bash
   hls-downloader "url" -r 5  # Retry up to 5 times
   ```

4. **Test with single connection:**
   ```bash
   hls-downloader "url" -c 1  # Single connection for testing
   ```

### Issue: SSL/TLS certificate errors

**Symptoms:**
- "SSL certificate verify failed" errors
- HTTPS connection failures

**Diagnosis:**
```bash
# Test SSL connection
curl -v "https://example.com/segment1.ts"
openssl s_client -connect example.com:443
```

**Solutions:**

1. **Update certificates:**
   ```bash
   # macOS
   brew install ca-certificates
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ca-certificates
   ```

2. **Check system time:**
   ```bash
   date  # Ensure system time is correct
   ```

### Issue: HTTP 403/404 errors

**Symptoms:**
- "Forbidden" or "Not Found" errors
- Authentication failures

**Diagnosis:**
```bash
# Test individual segments
curl -I "https://example.com/segment1.ts"
curl -I "https://example.com/segment0.ts"  # Try starting from 0

# Check with browser developer tools
```

**Solutions:**

1. **Verify URL pattern:**
   ```bash
   # Try different starting numbers
   hls-downloader "https://example.com/segment{}.ts"  # starts from 1
   # If that fails, the stream might start from 0 or use different numbering
   ```

2. **Check authentication requirements:**
   - Some streams require cookies or headers
   - Use browser developer tools to inspect network requests

3. **Try different URL formats:**
   ```bash
   # Zero-padded numbers
   hls-downloader "https://example.com/segment{:03d}.ts"
   
   # Different file extensions
   hls-downloader "https://example.com/segment{}.m4s"
   ```

## Performance Problems

### Issue: Very slow downloads

**Symptoms:**
- Download speed much slower than expected
- High CPU usage
- Memory consumption issues

**Diagnosis:**
```bash
# Monitor system resources
htop  # Linux/macOS
taskmgr  # Windows

# Test with verbose output
hls-downloader "url" --verbose -c 10
```

**Solutions:**

1. **Optimize concurrency:**
   ```bash
   # Start conservative and increase
   hls-downloader "url" -c 5   # Low concurrency
   hls-downloader "url" -c 20  # Higher concurrency
   hls-downloader "url" -c 50  # Very high concurrency
   ```

2. **Adjust chunk size:**
   ```bash
   # Larger chunks for fast connections
   hls-downloader "url" --chunk-size 16384
   
   # Smaller chunks for slow connections
   hls-downloader "url" --chunk-size 4096
   ```

3. **Use faster storage:**
   ```bash
   # Download to SSD instead of HDD
   hls-downloader "url" -o /path/to/ssd/storage
   ```

### Issue: High memory usage

**Symptoms:**
- System becomes unresponsive
- Out of memory errors
- Swap usage increases

**Diagnosis:**
```bash
# Monitor memory usage
free -h  # Linux
vm_stat  # macOS
```

**Solutions:**

1. **Reduce concurrency:**
   ```bash
   hls-downloader "url" -c 5  # Lower concurrent downloads
   ```

2. **Smaller chunk size:**
   ```bash
   hls-downloader "url" --chunk-size 4096
   ```

3. **Disable verbose output:**
   ```bash
   hls-downloader "url"  # No --verbose flag
   ```

## File System Issues

### Issue: Permission denied errors

**Symptoms:**
- "Permission denied" when creating directories
- Cannot write to output directory
- Access denied errors

**Diagnosis:**
```bash
# Check directory permissions
ls -la /path/to/output/directory
stat /path/to/output/directory

# Check available space
df -h /path/to/output/directory
```

**Solutions:**

1. **Use different output directory:**
   ```bash
   hls-downloader "url" -o ~/Downloads/hls
   ```

2. **Create directory with proper permissions:**
   ```bash
   mkdir -p ~/Downloads/hls
   chmod 755 ~/Downloads/hls
   hls-downloader "url" -o ~/Downloads/hls
   ```

3. **Check disk space:**
   ```bash
   df -h  # Ensure sufficient free space
   ```

### Issue: Disk space errors

**Symptoms:**
- "No space left on device" errors
- Downloads fail partway through
- System becomes unresponsive

**Diagnosis:**
```bash
# Check available space
df -h
du -sh /path/to/downloads  # Check download directory size
```

**Solutions:**

1. **Clean up space:**
   ```bash
   # Remove old downloads
   rm -rf ~/Downloads/old_videos
   
   # Clean system cache
   sudo apt autoremove  # Ubuntu/Debian
   brew cleanup         # macOS
   ```

2. **Use different storage location:**
   ```bash
   hls-downloader "url" -o /path/to/larger/drive
   ```

3. **Enable cleanup after merge:**
   ```bash
   hls-downloader "url" --cleanup  # Removes segments after merging
   ```

## Video Merging Problems

### Issue: FFmpeg merge failures

**Symptoms:**
- Segments download successfully but merge fails
- "Codec not supported" errors
- Output video is corrupted

**Diagnosis:**
```bash
# Check FFmpeg version and codecs
ffmpeg -version
ffmpeg -codecs | grep -E "(h264|aac)"

# Test manual merge
cd segments_directory
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy test_output.mp4
```

**Solutions:**

1. **Try different output format:**
   ```bash
   hls-downloader "url" --format mkv  # More codec support
   hls-downloader "url" --format ts   # Keep original format
   ```

2. **Manual merge with re-encoding:**
   ```bash
   # Download without auto-merge
   hls-downloader "url" --no-merge
   
   # Manual merge with re-encoding
   cd segments_directory
   ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -c:a aac output.mp4
   ```

3. **Check segment integrity:**
   ```bash
   # Verify segments are valid
   ffprobe segment_001.ts
   ```

### Issue: Audio/video sync problems

**Symptoms:**
- Audio and video are out of sync
- Playback issues in merged video

**Solutions:**

1. **Use container format that preserves timing:**
   ```bash
   hls-downloader "url" --format mkv
   ```

2. **Force re-encoding:**
   ```bash
   # Manual merge with sync correction
   ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -c:a aac -async 1 output.mp4
   ```

## Resume Issues

### Issue: Resume not working

**Symptoms:**
- Resume command starts from beginning
- "No resumable download found" error
- State file corruption

**Diagnosis:**
```bash
# Check for state files
ls -la /path/to/download/directory/.hls_downloader_state*

# Check resume info
hls-downloader --check-resume -o /path/to/download/directory
```

**Solutions:**

1. **Verify correct directory:**
   ```bash
   # Make sure you're using the same output directory
   hls-downloader --check-resume -o ./exact/same/path
   ```

2. **Force restart if state is corrupted:**
   ```bash
   hls-downloader "url" -o ./directory --force-restart
   ```

3. **Manual state cleanup:**
   ```bash
   # Remove corrupted state files
   rm /path/to/download/.hls_downloader_state*
   ```

### Issue: Resume with different URL

**Symptoms:**
- URL mismatch errors during resume
- Cannot resume with modified URL

**Solutions:**

1. **Use exact same URL:**
   ```bash
   # Check what URL was used originally
   hls-downloader --check-resume -o ./directory
   ```

2. **Force restart with new URL:**
   ```bash
   hls-downloader "new_url" -o ./directory --force-restart
   ```

## Debug Mode

### Enabling Debug Mode

```bash
# Enable debug output
hls-downloader "url" --debug

# Save debug logs to file
hls-downloader "url" --debug --log-file debug.log

# Structured JSON logs
hls-downloader "url" --debug --structured-logs --log-file debug.json
```

### Reading Debug Logs

Debug logs contain detailed information about:

- **Segment detection process**
- **HTTP requests and responses**
- **Download progress and errors**
- **File system operations**
- **FFmpeg commands and output**

### Common Debug Patterns

**Segment detection issues:**
```
DEBUG: Testing segment 1: https://example.com/segment1.ts
DEBUG: Segment 1 exists: True
DEBUG: Testing segment 100: https://example.com/segment100.ts
DEBUG: Segment 100 exists: False
DEBUG: Binary search range: 1-100
```

**Network issues:**
```
ERROR: Request timeout for https://example.com/segment50.ts
DEBUG: Retrying segment 50 (attempt 2/3)
DEBUG: Using exponential backoff: 2.0 seconds
```

**File system issues:**
```
ERROR: Permission denied: /restricted/path/segment1.ts
DEBUG: Attempting to create directory: /restricted/path
ERROR: Cannot create directory: Permission denied
```

## System-Specific Issues

### macOS Issues

**Issue: "Developer cannot be verified" error**

**Solution:**
```bash
# Allow unsigned binaries (if using downloaded FFmpeg)
sudo spctl --master-disable
# Or install via Homebrew
brew install ffmpeg
```

**Issue: Network restrictions**

**Solution:**
```bash
# Check firewall settings
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Temporarily disable if needed
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off
```

### Windows Issues

**Issue: Antivirus blocking downloads**

**Solution:**
- Add hls-downloader to antivirus exceptions
- Temporarily disable real-time protection
- Use Windows Defender exclusions

**Issue: Path length limitations**

**Solution:**
```bash
# Use shorter output paths
hls-downloader "url" -o C:\HLS

# Enable long path support (Windows 10+)
# Run as administrator:
# New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

### Linux Issues

**Issue: Missing system libraries**

**Solution:**
```bash
# Install required libraries
sudo apt update
sudo apt install python3-dev libssl-dev libffi-dev

# For CentOS/RHEL
sudo yum install python3-devel openssl-devel libffi-devel
```

**Issue: SELinux restrictions**

**Solution:**
```bash
# Check SELinux status
sestatus

# Temporarily disable if needed
sudo setenforce 0

# Or create proper SELinux policies
```

## Getting Additional Help

If these troubleshooting steps don't resolve your issue:

### 1. Gather Information

Before seeking help, collect:

```bash
# System information
uname -a                    # System details
python --version           # Python version
hls-downloader --version   # Tool version
ffmpeg -version            # FFmpeg version

# Error reproduction
hls-downloader "url" --debug --log-file error.log
```

### 2. Create Minimal Test Case

```bash
# Test with simple, known-working URL
hls-downloader "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8" --debug
```

### 3. Report Issues

When reporting issues, include:

- **Complete command line used**
- **Full error messages**
- **Debug logs (if applicable)**
- **System information**
- **Steps to reproduce**

### 4. Community Resources

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/hlsdownloader/hls-downloader/issues)
- **Discussions**: [Ask questions and share tips](https://github.com/hlsdownloader/hls-downloader/discussions)
- **Documentation**: [Complete documentation](https://github.com/hlsdownloader/hls-downloader/docs)

## Prevention Tips

### Regular Maintenance

```bash
# Keep tools updated
pip install --upgrade hls-downloader
brew upgrade ffmpeg  # macOS

# Clean up old downloads
find ~/Downloads -name "*.ts" -mtime +30 -delete
```

### Best Practices

1. **Always test with small downloads first**
2. **Use resume functionality for large downloads**
3. **Monitor system resources during downloads**
4. **Keep debug logs for troubleshooting**
5. **Regularly update dependencies**