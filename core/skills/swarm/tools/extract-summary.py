#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Bounded summary extraction from swarm output files.

Returns TOC + Executive Summary only, hard capped at specified bytes.
Enforces the output protocol format requirement.

Expected file structure:
    # Title
    ## Table of Contents
    ...
    ## Executive Summary
    ...
    ---
    ## Section 1 (not extracted)

Usage:
    uv run extract-summary.py <file>
    uv run extract-summary.py <file> --max-bytes 2048
"""

import argparse
import sys
from pathlib import Path


def extract_summary(content: str, max_bytes: int) -> str:
    """Extract Title + TOC + Executive Summary, capped at max_bytes."""
    lines = content.split("\n")

    # Strategy 1: Extract up to first --- separator (preferred)
    result_lines = []
    for line in lines:
        if line.strip() == "---":
            result_lines.append(line)
            break
        result_lines.append(line)
    else:
        # No --- found, try strategy 2
        result_lines = []

    if result_lines:
        result = "\n".join(result_lines)
        return result[:max_bytes]

    # Strategy 2: Extract up to first ## heading after Executive Summary
    exec_found = False
    result_lines = []
    for line in lines:
        if "## Executive Summary" in line:
            exec_found = True
            result_lines.append(line)
            continue

        if exec_found and line.startswith("## "):
            # Found next section after Executive Summary, stop here
            break

        result_lines.append(line)

    if exec_found:
        result = "\n".join(result_lines)
        return result[:max_bytes]

    # Strategy 3: Fallback - first 40 lines
    result = "\n".join(lines[:40])
    return result[:max_bytes]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract bounded summary from swarm output file"
    )
    parser.add_argument(
        "file",
        help="Path to markdown file with TOC + Executive Summary",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=1024,
        help="Maximum output size in bytes (default: 1024)",
    )

    args = parser.parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        return 1

    content = file_path.read_text()
    summary = extract_summary(content, args.max_bytes)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
