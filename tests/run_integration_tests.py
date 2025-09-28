#!/usr/bin/env python3
"""Test runner for comprehensive integration tests.

This script provides a convenient way to run all integration tests
with proper configuration and reporting.
"""

import argparse
import subprocess
import sys
import time


def run_test_suite(test_pattern, markers=None, verbose=False, save_results=False):
    """Run a specific test suite with given parameters."""
    cmd = ["python", "-m", "pytest"]

    # Add test pattern
    cmd.append(test_pattern)

    # Add markers if specified
    if markers:
        cmd.extend(["-m", markers])

    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add other useful options
    cmd.extend(
        [
            "--tb=short",  # Short traceback format
            "--strict-markers",  # Strict marker checking
            "--strict-config",  # Strict config checking
        ]
    )

    # Save results if requested
    if save_results:
        timestamp = int(time.time())
        results_file = f"test_results_{timestamp}.json"
        cmd.extend(["--json-report", f"--json-report-file={results_file}"])

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=False)
    end_time = time.time()

    duration = end_time - start_time
    print("-" * 60)
    print(f"Test suite completed in {duration:.2f} seconds")
    print(f"Exit code: {result.returncode}")

    return result.returncode == 0


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive integration tests for HLS downloader"
    )

    parser.add_argument(
        "--suite",
        choices=[
            "all",
            "comprehensive",
            "url-patterns",
            "performance",
            "user-scenarios",
            "network-simulation",
            "end-to-end",
        ],
        default="all",
        help="Test suite to run",
    )

    parser.add_argument(
        "--markers", help="Pytest markers to filter tests (e.g., 'not slow')"
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.add_argument(
        "--save-results", action="store_true", help="Save test results to JSON file"
    )

    parser.add_argument(
        "--quick", action="store_true", help="Run quick tests only (exclude slow tests)"
    )

    parser.add_argument(
        "--network", action="store_true", help="Include network-dependent tests"
    )

    args = parser.parse_args()

    # Determine test patterns and markers
    test_patterns = []
    markers = args.markers or ""

    if args.quick and not args.markers:
        markers = "not slow"

    if not args.network and markers:
        markers += " and not integration"
    elif not args.network:
        markers = "not integration"

    # Map suite choices to test files
    suite_mapping = {
        "comprehensive": ["tests/test_comprehensive_integration.py"],
        "url-patterns": ["tests/test_url_pattern_compatibility.py"],
        "performance": ["tests/test_performance_benchmarks.py"],
        "user-scenarios": ["tests/test_user_scenario_regression.py"],
        "network-simulation": [
            "tests/test_comprehensive_integration.py::TestNetworkExceptionSimulation"
        ],
        "end-to-end": ["tests/test_comprehensive_integration.py::TestEndToEndDownload"],
        "all": [
            "tests/test_comprehensive_integration.py",
            "tests/test_url_pattern_compatibility.py",
            "tests/test_performance_benchmarks.py",
            "tests/test_user_scenario_regression.py",
        ],
    }

    test_patterns = suite_mapping.get(args.suite, ["tests/"])

    print("HLS Downloader - Comprehensive Integration Test Runner")
    print("=" * 60)
    print(f"Suite: {args.suite}")
    print(f"Patterns: {test_patterns}")
    if markers:
        print(f"Markers: {markers}")
    print(f"Verbose: {args.verbose}")
    print(f"Save results: {args.save_results}")
    print("=" * 60)

    # Run tests
    all_passed = True

    for pattern in test_patterns:
        print(f"\nRunning tests: {pattern}")
        success = run_test_suite(
            pattern,
            markers=markers,
            verbose=args.verbose,
            save_results=args.save_results,
        )

        if not success:
            all_passed = False
            print(f"❌ Tests failed for: {pattern}")
        else:
            print(f"✅ Tests passed for: {pattern}")

    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All test suites passed!")
        sys.exit(0)
    else:
        print("💥 Some test suites failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
