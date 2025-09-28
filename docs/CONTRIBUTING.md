# Contributing Guide

Thank you for your interest in contributing to HLS Downloader! This guide will help you get started with contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style and Standards](#code-style-and-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Issue Guidelines](#issue-guidelines)
- [Documentation](#documentation)
- [Release Process](#release-process)

## Getting Started

### Ways to Contribute

- **Bug Reports**: Report issues you encounter
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Fix bugs or implement features
- **Documentation**: Improve or add documentation
- **Testing**: Add test cases or improve test coverage
- **Performance**: Optimize performance or memory usage

### Before You Start

1. **Check existing issues** to avoid duplicating work
2. **Discuss major changes** in an issue before implementing
3. **Read the code of conduct** (if applicable)
4. **Understand the project structure** and architecture

## Development Setup

### Prerequisites

- Python 3.9 or higher
- uv (recommended) or pip
- FFmpeg (for testing video merging)
- Git

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/hlsdownloader/hls-downloader.git
cd hls-downloader

# Create virtual environment and install dependencies
uv sync --dev

# Or with pip
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

### Verify Setup

```bash
# Run tests
uv run pytest

# Check code style
uv run ruff check src tests
uv run black --check src tests

# Run type checking
uv run mypy src
```

### Project Structure

```
hls-downloader/
├── src/hls_downloader/          # Main package
│   ├── core/                    # Core functionality
│   │   ├── detector.py          # Segment detection
│   │   ├── downloader.py        # Download logic
│   │   ├── manager.py           # Main coordinator
│   │   ├── merger.py            # Video merging
│   │   └── progress.py          # Progress display
│   ├── models/                  # Data models
│   ├── exceptions/              # Custom exceptions
│   ├── utils/                   # Utility functions
│   └── cli.py                   # Command line interface
├── tests/                       # Test suite
├── docs/                        # Documentation
└── pyproject.toml              # Project configuration
```

## Code Style and Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 88 characters (Black default)
- **Import sorting**: isort compatible
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for all public functions and classes

### Code Formatting

We use automated tools for consistent formatting:

```bash
# Format code
uv run black src tests

# Sort imports
uv run ruff check --fix src tests

# Check formatting
uv run black --check src tests
uv run ruff check src tests
```

### Type Checking

All code must pass mypy type checking:

```bash
uv run mypy src
```

### Example Code Style

```python
"""Module docstring describing the module purpose."""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..models.config import DownloadConfig
from ..exceptions.base import HLSDownloaderError


class ExampleClass:
    """Example class following project conventions.
    
    This class demonstrates the coding style and documentation
    standards used in the project.
    
    Args:
        config: Download configuration object
        output_dir: Directory for output files
    """
    
    def __init__(self, config: DownloadConfig, output_dir: str) -> None:
        """Initialize the example class."""
        self.config = config
        self.output_dir = Path(output_dir)
        self._internal_state: Dict[str, Any] = {}
    
    async def process_data(
        self, 
        data: List[str], 
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Process data asynchronously.
        
        Args:
            data: List of data items to process
            callback: Optional callback function for progress updates
            
        Returns:
            Dictionary containing processing results
            
        Raises:
            HLSDownloaderError: If processing fails
        """
        results = {}
        
        for i, item in enumerate(data):
            try:
                result = await self._process_item(item)
                results[item] = result
                
                if callback:
                    callback(i + 1, len(data))
                    
            except Exception as e:
                raise HLSDownloaderError(f"Failed to process {item}: {e}") from e
        
        return results
    
    async def _process_item(self, item: str) -> str:
        """Process a single item (private method)."""
        # Implementation details
        await asyncio.sleep(0.1)  # Simulate async work
        return f"processed_{item}"
```

## Testing

### Test Structure

Tests are organized to mirror the source structure:

```
tests/
├── test_cli.py                 # CLI tests
├── test_detector.py            # Detector tests
├── test_downloader.py          # Downloader tests
├── test_manager.py             # Manager tests
├── test_merger.py              # Merger tests
├── test_models.py              # Model tests
├── integration/                # Integration tests
└── conftest.py                 # Test configuration
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_detector.py

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run only unit tests
uv run pytest -m "not integration"

# Run only integration tests
uv run pytest -m integration
```

### Writing Tests

#### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

from hls_downloader.core.detector import HLSDetector
from hls_downloader.models.config import DownloadConfig
from hls_downloader.exceptions.detector import DetectionError


class TestHLSDetector:
    """Test cases for HLS detector."""
    
    @pytest.fixture
    def detector(self):
        """Create detector instance for testing."""
        config = DownloadConfig()
        return HLSDetector(config)
    
    @pytest.mark.asyncio
    async def test_detect_segments_success(self, detector):
        """Test successful segment detection."""
        url_template = "https://example.com/segment{}.ts"
        
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.side_effect = [True, True, True, False]
            
            segments = await detector.detect_segments(url_template)
            
            assert len(segments) == 3
            assert segments[0] == "https://example.com/segment1.ts"
            assert segments[2] == "https://example.com/segment3.ts"
    
    @pytest.mark.asyncio
    async def test_detect_segments_no_segments(self, detector):
        """Test detection when no segments exist."""
        url_template = "https://example.com/segment{}.ts"
        
        with patch.object(detector, '_check_segment_exists') as mock_check:
            mock_check.return_value = False
            
            with pytest.raises(DetectionError, match="No segments found"):
                await detector.detect_segments(url_template)
```

#### Integration Tests

```python
import pytest
import tempfile
from pathlib import Path

from hls_downloader.core.manager import DownloadManager
from hls_downloader.models.config import DownloadConfig


@pytest.mark.integration
class TestDownloadManagerIntegration:
    """Integration tests for download manager."""
    
    @pytest.mark.asyncio
    async def test_full_download_process(self):
        """Test complete download process with real HTTP requests."""
        # Use a test HLS stream
        url = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = DownloadConfig(
                max_concurrent=5,
                auto_merge=False  # Skip merge for faster testing
            )
            
            manager = DownloadManager(config)
            result = await manager.download_hls(url, temp_dir)
            
            assert result['total_segments'] > 0
            assert result['successful_segments'] > 0
            assert result['failed_segments'] == 0
            
            # Check that files were created
            segments_dir = Path(temp_dir) / "segments"
            assert segments_dir.exists()
            assert len(list(segments_dir.glob("*.ts"))) > 0
```

### Test Guidelines

1. **Use descriptive test names** that explain what is being tested
2. **Test both success and failure cases**
3. **Mock external dependencies** (HTTP requests, file system, etc.)
4. **Use fixtures** for common test setup
5. **Mark integration tests** with `@pytest.mark.integration`
6. **Test edge cases** and boundary conditions
7. **Keep tests focused** on a single behavior

## Submitting Changes

### Workflow

1. **Fork the repository** on GitHub
2. **Create a feature branch** from `main`
3. **Make your changes** following the coding standards
4. **Add tests** for your changes
5. **Update documentation** if needed
6. **Run the test suite** to ensure everything passes
7. **Submit a pull request**

### Branch Naming

Use descriptive branch names:

- `feature/add-resume-functionality`
- `bugfix/fix-timeout-handling`
- `docs/update-api-documentation`
- `refactor/improve-error-handling`

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(detector): add binary search optimization

Implement binary search algorithm for faster segment detection.
This reduces detection time from O(n) to O(log n) for large
segment ranges.

Closes #123
```

```
fix(downloader): handle connection timeout properly

- Add proper timeout handling in download retry logic
- Improve error messages for timeout scenarios
- Add tests for timeout edge cases

Fixes #456
```

### Pull Request Guidelines

#### Before Submitting

```bash
# Ensure all tests pass
uv run pytest

# Check code style
uv run black --check src tests
uv run ruff check src tests

# Run type checking
uv run mypy src

# Update documentation if needed
```

#### PR Description Template

```markdown
## Description
Brief description of the changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added tests for new functionality
- [ ] Updated existing tests if needed

## Documentation
- [ ] Updated README if needed
- [ ] Updated API documentation if needed
- [ ] Added docstrings for new functions/classes

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review of the code completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Changes generate no new warnings
```

## Issue Guidelines

### Bug Reports

Use the bug report template:

```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. With URL '...'
3. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Environment:**
- OS: [e.g. macOS 12.0]
- Python version: [e.g. 3.9.7]
- HLS Downloader version: [e.g. 1.0.0]
- FFmpeg version: [e.g. 4.4.0]

**Additional context**
Add any other context about the problem here.
Include debug logs if available.
```

### Feature Requests

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
A clear and concise description of what the problem is.

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context or screenshots about the feature request here.
```

## Documentation

### Types of Documentation

1. **Code Documentation**: Docstrings and inline comments
2. **API Documentation**: `docs/API.md`
3. **User Documentation**: README, FAQ, examples
4. **Developer Documentation**: This contributing guide

### Documentation Standards

- **Use clear, concise language**
- **Provide examples** for complex concepts
- **Keep documentation up-to-date** with code changes
- **Use proper markdown formatting**
- **Include code examples** that actually work

### Building Documentation

```bash
# Check documentation links
uv run python -m doctest docs/API.md

# Validate markdown
markdownlint docs/
```

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with new features and fixes
3. **Run full test suite** including integration tests
4. **Update documentation** if needed
5. **Create release PR** and get approval
6. **Tag release** after merging
7. **Build and publish** to PyPI

### Creating a Release

```bash
# Update version
vim pyproject.toml

# Update changelog
vim CHANGELOG.md

# Commit changes
git add .
git commit -m "chore: prepare release v1.2.0"

# Create tag
git tag -a v1.2.0 -m "Release v1.2.0"

# Push changes and tag
git push origin main
git push origin v1.2.0
```

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Request Reviews**: Code review and feedback

### Code Review Process

1. **Automated checks** must pass (tests, linting, type checking)
2. **At least one maintainer review** required
3. **Address feedback** promptly and professionally
4. **Squash commits** if requested before merging

### Maintainer Responsibilities

Maintainers will:

- **Review PRs** in a timely manner
- **Provide constructive feedback**
- **Help with technical questions**
- **Maintain project standards**
- **Release new versions**

## Recognition

Contributors will be recognized in:

- **CONTRIBUTORS.md** file
- **Release notes** for significant contributions
- **GitHub contributors** page

Thank you for contributing to HLS Downloader! Your efforts help make this tool better for everyone.