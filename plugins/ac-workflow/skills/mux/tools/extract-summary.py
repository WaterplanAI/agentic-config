#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Bounded summary extraction from MUX subagent output files.

Outputs structured metadata + table of contents + executive summary.
Designed as the ONLY sanctioned way for the MUX orchestrator to access
subagent report content without polluting its context window.

Output format:
    ## File Metadata
    - Path: <path>
    - Size: <bytes>
    - Words: <count>
    - Modified: <timestamp>

    ## Table of Contents
    - <all markdown headers from the file>

    ## Executive Summary
    <content of the Executive Summary section, or fallback>

Usage:
    uv run extract-summary.py <file>
    uv run extract-summary.py <file> --max-bytes 2048
    uv run extract-summary.py <file> --metadata
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_headers(content: str) -> list[str]:
    """Extract all markdown headers from content."""
    headers: list[str] = []
    for line in content.split("\n"):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            indent = "  " * (level - 1)
            headers.append(f"{indent}- {text}")
    return headers


def extract_executive_summary(content: str, max_bytes: int) -> str:
    """Extract the Executive Summary section content, capped at max_bytes."""
    lines = content.split("\n")

    # Find Executive Summary section
    exec_start = -1
    exec_end = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Executive Summary", line):
            exec_start = i + 1
            continue
        if exec_start >= 0 and (line.startswith("## ") or line.strip() == "---"):
            exec_end = i
            break

    if exec_start >= 0:
        section_lines = lines[exec_start:exec_end]
        # Strip leading/trailing blank lines
        while section_lines and not section_lines[0].strip():
            section_lines.pop(0)
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()
        result = "\n".join(section_lines)
        return result[:max_bytes] if len(result) > max_bytes else result

    # Fallback: first 40 lines (no Executive Summary found)
    return ""


def format_file_metadata(file_path: Path) -> str:
    """Format file metadata section."""
    stat = file_path.stat()
    size = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    content = file_path.read_text()
    words = len(content.split())

    lines = [
        "## File Metadata",
        f"- Path: {file_path}",
        f"- Size: {size} bytes",
        f"- Words: {words}",
        f"- Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract bounded summary from MUX subagent output file"
    )
    parser.add_argument(
        "file",
        help="Path to markdown file with TOC + Executive Summary",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=1024,
        help="Maximum Executive Summary size in bytes (default: 1024)",
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Include file metadata section (size, word count, modified)",
    )

    args = parser.parse_args()
    file_path = Path(args.file).resolve()

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        return 1

    content = file_path.read_text()
    output_parts: list[str] = []

    # File Metadata (always included)
    output_parts.append(format_file_metadata(file_path))

    # Table of Contents (all markdown headers)
    headers = extract_headers(content)
    toc_section = "## Table of Contents"
    if headers:
        toc_section += "\n" + "\n".join(headers)
    else:
        toc_section += "\nNo markdown headers found"
    output_parts.append(toc_section)

    # Executive Summary
    exec_summary = extract_executive_summary(content, args.max_bytes)
    exec_section = "## Executive Summary"
    if exec_summary:
        exec_section += "\n" + exec_summary
    else:
        exec_section += "\nNo Executive Summary section found"
    output_parts.append(exec_section)

    print("\n\n".join(output_parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
