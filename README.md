# HLS Downloader

A modern, high-performance HLS (HTTP Live Streaming) segment downloader with concurrent downloading, automatic segment detection, and video merging capabilities.

## Features

- 🚀 **Concurrent Downloads**: Download multiple segments simultaneously with configurable concurrency
- 🔍 **Smart Detection**: Automatically detect available segments using binary search algorithm
- 📊 **Modern Progress Display**: Real-time progress bars with speed, ETA, and statistics
- 🔄 **Resume Support**: Resume interrupted downloads from where they left off
- 🎬 **Auto Merge**: Automatically merge segments into a single video file using FFmpeg
- ⚡ **High Performance**: Async/await architecture for optimal performance
- 🛡️ **Robust Error Handling**: Comprehensive retry mechanisms and error recovery
- 🔧 **Configurable**: Extensive configuration options via CLI or config file

## Installation

### Prerequisites

- Python 3.9 or higher
- FFmpeg (for video merging)

### Install FFmpeg

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [FFmpeg official website](https://ffmpeg.org/download.html) or use [Chocolatey](https://chocolatey.org/):
```bash
choco install ffmpeg
```

### Install HLS Downloader

**Using uv (recommended):**
```bash
uv add hls-downloader
```

**Using pip:**
```bash
pip install hls-downloader
```

**From source:**
```bash
git clone https://github.com/hlsdownloader/hls-downloader.git
cd hls-downloader
uv sync --dev
```

## Quick Start

### Basic Usage

Download HLS segments and merge into a video:

```bash
hls-downloader "https://example.com/segment{}.ts"
```

### Common Usage Patterns

**Download with custom output directory:**
```bash
hls-downloader "https://example.com/video_{:03d}.ts" -o ./my_videos
```

**High-speed download with more concurrent connections:**
```bash
hls-downloader "https://example.com/part{}.ts" -c 20
```

**Download without merging (keep segments):**
```bash
hls-downloader "https://example.com/segment{}.ts" --no-merge
```

**Resume interrupted download:**
```bash
hls-downloader --resume -o ./downloads
```

## Command Line Options

### Basic Options

| Option | Description | Default |
|--------|-------------|---------|
| `url` | HLS segment URL template with `{}` placeholder | Required |
| `-o, --output` | Output directory for downloaded files | `./downloads` |
| `--format` | Output video format (mp4, mkv, avi, mov, ts) | `mp4` |

### Download Options

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --concurrent` | Maximum concurrent downloads (1-100) | `10` |
| `-r, --retries` | Maximum retry attempts (0-10) | `3` |
| `--timeout` | Request timeout in seconds (1-300) | `30` |
| `--chunk-size` | Download chunk size in bytes | `8192` |

### Processing Options

| Option | Description |
|--------|-------------|
| `--no-merge` | Skip automatic merging of segments |
| `--cleanup` | Delete segment files after merging |

### Resume Options

| Option | Description |
|--------|-------------|
| `--resume` | Resume interrupted download in output directory |
| `--force-restart` | Ignore existing state and start fresh download |
| `--check-resume` | Check if there's a resumable download and show info |

### Configuration Options

| Option | Description |
|--------|-------------|
| `--config` | Path to configuration file |
| `--save-config` | Save current settings as default configuration |
| `--show-config` | Show current configuration and exit |

### Logging Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose output |
| `--debug` | Enable debug mode with detailed logging |
| `--log-file` | Save logs to file (with automatic rotation) |
| `--structured-logs` | Use structured JSON logging format |

## Configuration File

Create a configuration file to save your preferred settings:

```bash
hls-downloader --save-config
```

This creates `~/.hls_downloader/config.json` with your current settings:

```json
{
  "max_concurrent": 10,
  "max_retries": 3,
  "timeout": 30,
  "chunk_size": 8192,
  "auto_merge": true,
  "cleanup_segments": false,
  "output_format": "mp4"
}
```

## URL Format Examples

The URL must contain a `{}` placeholder where segment numbers will be inserted:

- `https://example.com/segment{}.ts` → `segment1.ts`, `segment2.ts`, etc.
- `https://example.com/video_{:03d}.ts` → `video_001.ts`, `video_002.ts`, etc.
- `https://example.com/part{}.m4s` → `part1.m4s`, `part2.m4s`, etc.

## Advanced Usage

### Resume Interrupted Downloads

Check if there's a resumable download:
```bash
hls-downloader --check-resume -o ./my_download
```

Resume the download:
```bash
hls-downloader --resume -o ./my_download
```

### High-Performance Downloads

For fast connections, increase concurrency:
```bash
hls-downloader "https://example.com/seg{}.ts" -c 50 --timeout 60
```

### Debug Mode

Enable detailed logging for troubleshooting:
```bash
hls-downloader "https://example.com/seg{}.ts" --debug --log-file debug.log
```

### Custom Configuration

Use a custom configuration file:
```bash
hls-downloader "https://example.com/seg{}.ts" --config ./my-config.json
```

## Performance Tips

1. **Optimize Concurrency**: Start with 10-20 concurrent downloads and adjust based on your network
2. **Use SSD Storage**: Download to SSD for better I/O performance
3. **Monitor Resources**: Use `--verbose` to monitor download speeds and adjust settings
4. **Network Stability**: For unstable connections, reduce concurrency and increase timeout
5. **Resume Feature**: Always use resume for large downloads to avoid starting over

## Troubleshooting

### Common Issues

**FFmpeg not found:**
```
Error: FFmpeg not found. Please install FFmpeg to merge video segments.
```
Solution: Install FFmpeg using your system's package manager.

**Permission denied:**
```
Error creating output directory: Permission denied
```
Solution: Check directory permissions or use a different output directory.

**Network timeout:**
```
Download failed: Request timeout
```
Solution: Increase timeout with `--timeout 60` or reduce concurrency.

**Invalid URL format:**
```
URL must contain '{}' placeholder for segment numbers
```
Solution: Ensure your URL contains `{}` where segment numbers should be inserted.

### Getting Help

1. Use `--verbose` for detailed output
2. Use `--debug` for comprehensive logging
3. Check the log file if using `--log-file`
4. Review the [FAQ section](docs/FAQ.md) for common solutions

## API Documentation

For programmatic usage, see the [API Documentation](docs/API.md).

## Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/hlsdownloader/hls-downloader/issues)
- 💬 [Discussions](https://github.com/hlsdownloader/hls-downloader/discussions)