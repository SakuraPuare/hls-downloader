"""Configuration for comprehensive integration tests.

This module provides configuration settings and utilities for running
comprehensive integration tests across different scenarios.
"""

import os
from dataclasses import dataclass
from typing import Optional

from src.hls_downloader.models import DownloadConfig


@dataclass
class TestEnvironmentConfig:
    """Configuration for test environment settings."""

    # Network settings
    enable_network_tests: bool = False
    network_timeout: int = 30
    max_network_retries: int = 2

    # Performance settings
    enable_performance_tests: bool = True
    performance_timeout: int = 60
    memory_limit_mb: int = 500

    # Test data settings
    use_real_urls: bool = False
    mock_network_delays: bool = True
    simulate_failures: bool = True

    # Output settings
    save_benchmark_results: bool = False
    generate_reports: bool = False
    cleanup_test_files: bool = True


@dataclass
class TestScenarioConfig:
    """Configuration for specific test scenarios."""

    name: str
    description: str
    download_config: DownloadConfig
    segment_count: int
    expected_duration: float
    memory_limit_mb: float
    success_rate_threshold: float = 0.95


# Predefined test scenarios
TEST_SCENARIOS = {
    "basic_user": TestScenarioConfig(
        name="Basic User",
        description="Typical first-time user with default settings",
        download_config=DownloadConfig(
            max_concurrent=4,
            max_retries=3,
            timeout=30,
            auto_merge=True,
            cleanup_segments=True,
        ),
        segment_count=10,
        expected_duration=5.0,
        memory_limit_mb=100.0,
    ),
    "power_user": TestScenarioConfig(
        name="Power User",
        description="Experienced user with optimized settings",
        download_config=DownloadConfig(
            max_concurrent=10,
            max_retries=5,
            timeout=60,
            auto_merge=False,
            cleanup_segments=False,
        ),
        segment_count=50,
        expected_duration=10.0,
        memory_limit_mb=200.0,
    ),
    "mobile_user": TestScenarioConfig(
        name="Mobile User",
        description="Mobile user with conservative settings",
        download_config=DownloadConfig(
            max_concurrent=2,
            max_retries=2,
            timeout=20,
            auto_merge=True,
            cleanup_segments=True,
        ),
        segment_count=8,
        expected_duration=8.0,
        memory_limit_mb=50.0,
    ),
    "slow_network": TestScenarioConfig(
        name="Slow Network",
        description="User on slow/unstable network",
        download_config=DownloadConfig(
            max_concurrent=1,
            max_retries=5,
            timeout=60,
            auto_merge=True,
            cleanup_segments=True,
        ),
        segment_count=5,
        expected_duration=15.0,
        memory_limit_mb=75.0,
        success_rate_threshold=0.8,  # Lower threshold for slow network
    ),
    "batch_processing": TestScenarioConfig(
        name="Batch Processing",
        description="Batch processing multiple videos",
        download_config=DownloadConfig(
            max_concurrent=6,
            max_retries=3,
            timeout=45,
            auto_merge=True,
            cleanup_segments=True,
        ),
        segment_count=25,
        expected_duration=12.0,
        memory_limit_mb=150.0,
    ),
}


# URL patterns for testing different streaming services
TEST_URL_PATTERNS = {
    "simple_numeric": {
        "pattern": "http://example.com/segment{}.ts",
        "description": "Simple numeric pattern",
        "examples": [
            "http://example.com/segment1.ts",
            "http://example.com/segment123.ts",
        ],
    },
    "zero_padded": {
        "pattern": "http://example.com/segment{:04d}.ts",
        "description": "Zero-padded numeric pattern",
        "examples": [
            "http://example.com/segment0001.ts",
            "http://example.com/segment0123.ts",
        ],
    },
    "complex_path": {
        "pattern": "https://cdn.example.com/live/stream/2023/12/segment{}.ts",
        "description": "Complex path structure",
        "examples": [
            "https://cdn.example.com/live/stream/2023/12/segment1.ts",
            "https://cdn.example.com/live/stream/2023/12/segment456.ts",
        ],
    },
    "with_query": {
        "pattern": "http://example.com/segment{}.ts?token=abc123&quality=high",
        "description": "Pattern with query parameters",
        "examples": [
            "http://example.com/segment1.ts?token=abc123&quality=high",
            "http://example.com/segment789.ts?token=abc123&quality=high",
        ],
    },
    "cntv_style": {
        "pattern": "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{}.ts",
        "description": "CNTV-style real-world pattern",
        "examples": [
            "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts"
        ],
    },
}


# Network simulation configurations
NETWORK_SCENARIOS = {
    "stable": {
        "description": "Stable network connection",
        "failure_rate": 0.0,
        "latency_ms": 50,
        "bandwidth_mbps": 10.0,
    },
    "unstable": {
        "description": "Unstable network with intermittent failures",
        "failure_rate": 0.1,
        "latency_ms": 200,
        "bandwidth_mbps": 2.0,
    },
    "slow": {
        "description": "Slow network connection",
        "failure_rate": 0.05,
        "latency_ms": 500,
        "bandwidth_mbps": 0.5,
    },
    "mobile": {
        "description": "Mobile network conditions",
        "failure_rate": 0.15,
        "latency_ms": 300,
        "bandwidth_mbps": 1.0,
    },
}


# Performance benchmarks
PERFORMANCE_BENCHMARKS = {
    "detection_speed": {
        "description": "Segment detection performance",
        "max_duration_seconds": 5.0,
        "max_memory_mb": 50.0,
    },
    "download_throughput": {
        "description": "Download throughput performance",
        "min_mbps": 1.0,
        "max_memory_mb": 100.0,
    },
    "concurrent_efficiency": {
        "description": "Concurrent download efficiency",
        "min_speedup_factor": 2.0,  # Should be at least 2x faster than sequential
        "max_memory_mb": 200.0,
    },
    "large_scale": {
        "description": "Large scale download performance",
        "max_duration_seconds": 30.0,
        "max_memory_mb": 300.0,
        "segment_count": 100,
    },
}


def get_test_environment_config() -> TestEnvironmentConfig:
    """Get test environment configuration from environment variables."""
    return TestEnvironmentConfig(
        enable_network_tests=os.getenv("ENABLE_NETWORK_TESTS", "false").lower()
        == "true",
        network_timeout=int(os.getenv("NETWORK_TIMEOUT", "30")),
        max_network_retries=int(os.getenv("MAX_NETWORK_RETRIES", "2")),
        enable_performance_tests=os.getenv("ENABLE_PERFORMANCE_TESTS", "true").lower()
        == "true",
        performance_timeout=int(os.getenv("PERFORMANCE_TIMEOUT", "60")),
        memory_limit_mb=int(os.getenv("MEMORY_LIMIT_MB", "500")),
        use_real_urls=os.getenv("USE_REAL_URLS", "false").lower() == "true",
        mock_network_delays=os.getenv("MOCK_NETWORK_DELAYS", "true").lower() == "true",
        simulate_failures=os.getenv("SIMULATE_FAILURES", "true").lower() == "true",
        save_benchmark_results=os.getenv("SAVE_BENCHMARK_RESULTS", "false").lower()
        == "true",
        generate_reports=os.getenv("GENERATE_REPORTS", "false").lower() == "true",
        cleanup_test_files=os.getenv("CLEANUP_TEST_FILES", "true").lower() == "true",
    )


def get_scenario_config(scenario_name: str) -> Optional[TestScenarioConfig]:
    """Get configuration for a specific test scenario."""
    return TEST_SCENARIOS.get(scenario_name)


def get_all_scenarios() -> dict[str, TestScenarioConfig]:
    """Get all available test scenarios."""
    return TEST_SCENARIOS.copy()


def get_url_pattern_config(pattern_name: str) -> Optional[dict]:
    """Get configuration for a specific URL pattern."""
    return TEST_URL_PATTERNS.get(pattern_name)


def get_all_url_patterns() -> dict[str, dict]:
    """Get all available URL patterns."""
    return TEST_URL_PATTERNS.copy()


def get_network_scenario_config(scenario_name: str) -> Optional[dict]:
    """Get configuration for a specific network scenario."""
    return NETWORK_SCENARIOS.get(scenario_name)


def get_all_network_scenarios() -> dict[str, dict]:
    """Get all available network scenarios."""
    return NETWORK_SCENARIOS.copy()


def get_performance_benchmark_config(benchmark_name: str) -> Optional[dict]:
    """Get configuration for a specific performance benchmark."""
    return PERFORMANCE_BENCHMARKS.get(benchmark_name)


def get_all_performance_benchmarks() -> dict[str, dict]:
    """Get all available performance benchmarks."""
    return PERFORMANCE_BENCHMARKS.copy()


def validate_test_environment() -> list[str]:
    """Validate test environment and return list of issues."""
    issues = []

    # Check Python version

    # Check required packages
    required_packages = ["pytest", "pytest-asyncio", "aioresponses", "psutil"]
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            issues.append(f"Required package not found: {package}")

    # Check disk space (at least 1GB for test files)
    import shutil

    free_space = shutil.disk_usage(".").free
    if free_space < 1024 * 1024 * 1024:  # 1GB
        issues.append("Insufficient disk space for comprehensive tests (need 1GB+)")

    # Check memory (at least 2GB available)
    try:
        import psutil

        available_memory = psutil.virtual_memory().available
        if available_memory < 2 * 1024 * 1024 * 1024:  # 2GB
            issues.append("Insufficient memory for comprehensive tests (need 2GB+)")
    except ImportError:
        # psutil is optional for basic tests
        pass

    return issues


def print_test_configuration():
    """Print current test configuration."""
    config = get_test_environment_config()

    print("Test Environment Configuration:")
    print("=" * 40)
    print(f"Network tests enabled: {config.enable_network_tests}")
    print(f"Performance tests enabled: {config.enable_performance_tests}")
    print(f"Use real URLs: {config.use_real_urls}")
    print(f"Mock network delays: {config.mock_network_delays}")
    print(f"Simulate failures: {config.simulate_failures}")
    print(f"Save benchmark results: {config.save_benchmark_results}")
    print(f"Generate reports: {config.generate_reports}")
    print(f"Cleanup test files: {config.cleanup_test_files}")
    print()

    print("Available Test Scenarios:")
    print("-" * 25)
    for name, scenario in TEST_SCENARIOS.items():
        print(f"  {name}: {scenario.description}")
    print()

    print("Available URL Patterns:")
    print("-" * 23)
    for name, pattern in TEST_URL_PATTERNS.items():
        print(f"  {name}: {pattern['description']}")
    print()

    print("Available Network Scenarios:")
    print("-" * 28)
    for name, scenario in NETWORK_SCENARIOS.items():
        print(f"  {name}: {scenario['description']}")
    print()

    # Validate environment
    issues = validate_test_environment()
    if issues:
        print("Environment Issues:")
        print("-" * 19)
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print("✅ Test environment validation passed")


if __name__ == "__main__":
    print_test_configuration()
