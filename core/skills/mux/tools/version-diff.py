#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Compare two versioned artifacts for refinement tracking.

Shows what changed between versions to track artifact evolution.

Usage:
    uv run version-diff.py <v1_path> <v2_path>
    uv run version-diff.py <v1_path> <v2_path> --format unified
    uv run version-diff.py <v1_path> <v2_path> --format summary
    uv run version-diff.py <v1_path> <v2_path> --json

Examples:
    uv run version-diff.py deliverable/spec-v1.md deliverable/spec-v2.md
    uv run version-diff.py research/topic-v1.md research/topic-v2.md --format summary
"""

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any


def compute_diff_stats(v1_lines: list[str], v2_lines: list[str]) -> dict[str, Any]:
    """Compute statistics about differences between versions.

    Args:
        v1_lines: Lines from version 1
        v2_lines: Lines from version 2

    Returns:
        Dict with diff statistics
    """
    matcher = difflib.SequenceMatcher(None, v1_lines, v2_lines)

    added = 0
    removed = 0
    changed = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            changed += max(i2 - i1, j2 - j1)

    return {
        "v1_lines": len(v1_lines),
        "v2_lines": len(v2_lines),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": len(v1_lines) - removed - changed,
        "similarity": round(matcher.ratio(), 3),
    }


def format_unified_diff(
    v1_path: Path, v2_path: Path, v1_lines: list[str], v2_lines: list[str]
) -> str:
    """Generate unified diff output.

    Args:
        v1_path: Path to v1 file
        v2_path: Path to v2 file
        v1_lines: Lines from v1
        v2_lines: Lines from v2

    Returns:
        Unified diff string
    """
    diff = difflib.unified_diff(
        v1_lines,
        v2_lines,
        fromfile=str(v1_path),
        tofile=str(v2_path),
        lineterm="",
    )
    return "\n".join(diff)


def format_summary(stats: dict[str, Any]) -> str:
    """Generate human-readable summary.

    Args:
        stats: Diff statistics

    Returns:
        Summary string
    """
    return f"""Version Diff Summary:
  v1: {stats['v1_lines']} lines
  v2: {stats['v2_lines']} lines
  Added: +{stats['added']} lines
  Removed: -{stats['removed']} lines
  Changed: ~{stats['changed']} lines
  Unchanged: {stats['unchanged']} lines
  Similarity: {stats['similarity']*100:.1f}%"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare versioned artifacts")
    parser.add_argument("v1_path", type=Path, help="Path to version 1")
    parser.add_argument("v2_path", type=Path, help="Path to version 2")
    parser.add_argument(
        "--format",
        choices=["unified", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output statistics as JSON",
    )

    args = parser.parse_args()

    if not args.v1_path.exists():
        print(f"Error: {args.v1_path} not found", file=sys.stderr)
        return 1
    if not args.v2_path.exists():
        print(f"Error: {args.v2_path} not found", file=sys.stderr)
        return 1

    v1_lines = args.v1_path.read_text().splitlines()
    v2_lines = args.v2_path.read_text().splitlines()

    stats = compute_diff_stats(v1_lines, v2_lines)

    if args.json:
        stats["v1_path"] = str(args.v1_path)
        stats["v2_path"] = str(args.v2_path)
        print(json.dumps(stats, indent=2))
    elif args.format == "unified":
        print(format_unified_diff(args.v1_path, args.v2_path, v1_lines, v2_lines))
    else:
        print(format_summary(stats))

    return 0


if __name__ == "__main__":
    sys.exit(main())
