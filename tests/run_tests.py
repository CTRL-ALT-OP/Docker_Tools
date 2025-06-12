#!/usr/bin/env python3
"""
Test runner script for Docker Tools test suite
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def run_tests(test_path=None, verbose=False, coverage=False, markers=None):
    """
    Run pytest with specified options
    
    Args:
        test_path: Specific test file or directory to run
        verbose: Enable verbose output
        coverage: Enable coverage reporting
        markers: Pytest markers to filter tests
    """
    cmd = ["python", "-m", "pytest"]
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add coverage
    if coverage:
        cmd.extend([
            "--cov=services",
            "--cov=models",
            "--cov=utils",
            "--cov=config",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Add markers
    if markers:
        cmd.extend(["-m", markers])
    
    # Add test path or current directory
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append(os.path.dirname(__file__))
    
    # Add color output
    cmd.append("--color=yes")
    
    # Show test durations
    cmd.append("--durations=10")
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run tests
    result = subprocess.run(cmd, cwd=parent_dir)
    
    return result.returncode


def list_tests():
    """List all available test files"""
    test_dir = Path(__file__).parent
    test_files = sorted(test_dir.glob("test_*.py"))
    
    print("Available test files:")
    print("-" * 80)
    for test_file in test_files:
        print(f"  {test_file.name}")
    
    print(f"\nTotal: {len(test_files)} test files")


def run_specific_test_class(test_file, class_name, verbose=False):
    """Run a specific test class"""
    cmd = ["python", "-m", "pytest", f"{test_file}::{class_name}"]
    
    if verbose:
        cmd.append("-v")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=parent_dir)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run Docker Tools test suite")
    parser.add_argument(
        "test_path",
        nargs="?",
        help="Specific test file or directory to run (default: all tests)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Enable coverage reporting"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available test files"
    )
    parser.add_argument(
        "-m", "--markers",
        help="Run tests matching given mark expression (e.g., 'not slow')"
    )
    parser.add_argument(
        "--class",
        dest="test_class",
        help="Run specific test class (use with test file)"
    )
    parser.add_argument(
        "-k",
        dest="keyword",
        help="Run tests matching keyword expression"
    )
    parser.add_argument(
        "--failed-first",
        action="store_true",
        help="Run failed tests first"
    )
    parser.add_argument(
        "--last-failed",
        action="store_true",
        help="Run only tests that failed last time"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_tests()
        return 0
    
    if args.test_class and args.test_path:
        return run_specific_test_class(args.test_path, args.test_class, args.verbose)
    
    # Build pytest command with additional options
    cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    if args.coverage:
        cmd.extend([
            "--cov=services",
            "--cov=models",
            "--cov=utils",
            "--cov=config",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    if args.markers:
        cmd.extend(["-m", args.markers])
    
    if args.keyword:
        cmd.extend(["-k", args.keyword])
    
    if args.failed_first:
        cmd.append("--failed-first")
    
    if args.last_failed:
        cmd.append("--last-failed")
    
    # Add test path
    if args.test_path:
        cmd.append(args.test_path)
    else:
        cmd.append(os.path.dirname(__file__))
    
    # Add color and durations
    cmd.extend(["--color=yes", "--durations=10"])
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    result = subprocess.run(cmd, cwd=parent_dir)
    
    if args.coverage and result.returncode == 0:
        print("\nCoverage report generated in htmlcov/index.html")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
