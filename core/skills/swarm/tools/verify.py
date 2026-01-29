#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Signal verification tool for swarm orchestrator.

Provides various verification operations without reading output files.

Usage:
    uv run verify.py <session_dir> --action count
    uv run verify.py <session_dir> --action failures
    uv run verify.py <session_dir> --action paths
    uv run verify.py <session_dir> --action sizes
    uv run verify.py <session_dir> --action total-size
    uv run verify.py <session_dir> --action summary

Actions:
    count:      Number of completed signals (.done files)
    failures:   List of failed signals (.fail files) with errors
    paths:      List of output paths from signals
    sizes:      List of sizes from signals
    total-size: Sum of all output sizes in bytes
    summary:    Combined summary of all above
"""

import argparse
import sys
from pathlib import Path


def parse_signal(signal_path: Path) -> dict[str, str]:
    """Parse a signal file into key-value pairs."""
    data = {}
    if signal_path.exists():
        for line in signal_path.read_text().strip().split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                data[key] = value
    return data


def count_completions(signals_dir: Path) -> int:
    """Count .done signal files."""
    return len(list(signals_dir.glob("*.done")))


def list_failures(signals_dir: Path) -> list[dict[str, str]]:
    """List all .fail signals with their error messages."""
    failures = []
    for fail_file in signals_dir.glob("*.fail"):
        data = parse_signal(fail_file)
        failures.append({
            "signal": fail_file.name,
            "path": data.get("path", ""),
            "error": data.get("error", "unknown"),
        })
    return failures


def get_paths(signals_dir: Path) -> list[str]:
    """Extract all output paths from .done signals."""
    paths = []
    for done_file in sorted(signals_dir.glob("*.done")):
        data = parse_signal(done_file)
        if "path" in data:
            paths.append(data["path"])
    return paths


def get_sizes(signals_dir: Path) -> list[tuple[str, int]]:
    """Extract all output sizes from .done signals."""
    sizes = []
    for done_file in sorted(signals_dir.glob("*.done")):
        data = parse_signal(done_file)
        if "size" in data:
            sizes.append((done_file.stem, int(data["size"])))
    return sizes


def get_total_size(signals_dir: Path) -> int:
    """Sum all output sizes from .done signals."""
    total = 0
    for done_file in signals_dir.glob("*.done"):
        data = parse_signal(done_file)
        if "size" in data:
            total += int(data["size"])
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify swarm completion via signal files"
    )
    parser.add_argument(
        "session_dir",
        help="Path to session directory",
    )
    parser.add_argument(
        "--action",
        choices=["count", "failures", "paths", "sizes", "total-size", "summary"],
        default="summary",
        help="Verification action to perform (default: summary)",
    )

    args = parser.parse_args()
    session_dir = Path(args.session_dir)
    signals_dir = session_dir / ".signals"

    if not signals_dir.exists():
        print(f"ERROR: Signals directory not found: {signals_dir}", file=sys.stderr)
        return 1

    if args.action == "count":
        print(count_completions(signals_dir))

    elif args.action == "failures":
        failures = list_failures(signals_dir)
        if failures:
            for f in failures:
                print(f"{f['signal']}: {f['error']}")
        else:
            print("No failures")

    elif args.action == "paths":
        for path in get_paths(signals_dir):
            print(path)

    elif args.action == "sizes":
        for name, size in get_sizes(signals_dir):
            print(f"{name}: {size}")

    elif args.action == "total-size":
        print(get_total_size(signals_dir))

    elif args.action == "summary":
        completed = count_completions(signals_dir)
        failures = list_failures(signals_dir)
        total_size = get_total_size(signals_dir)
        paths = get_paths(signals_dir)

        print(f"completed: {completed}")
        print(f"failed: {len(failures)}")
        print(f"total_size: {total_size}")
        print(f"paths: {len(paths)}")
        if failures:
            print("failures:")
            for f in failures:
                print(f"  - {f['signal']}: {f['error']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
