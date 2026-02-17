#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Signal file creation tool for swarm agents.

Creates completion signals that the orchestrator can verify without
reading agent output files directly.

Usage:
    uv run signal.py <signal_path> --path <output_path> --status <success|fail>
    uv run signal.py <signal_path> --path <output_path> --size <bytes> --status success
    uv run signal.py <signal_path> --path <output_path> --version 2 --previous <v1_path> --status success

Examples:
    uv run signal.py .signals/001-research.done --path research/001-topic.md --status success
    uv run signal.py .signals/002-audit.fail --path audits/002-gap.md --status fail --error "timeout"
    uv run signal.py .signals/001-research-v2.done --path research/001-topic-v2.md --version 2 --previous research/001-topic-v1.md --status success
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def atomic_write(path: Path, content: str):
    """Atomically write content to file using write-temp-rename pattern.

    Writes to temporary file, then atomically renames to target.
    Prevents partial reads during concurrent access.

    Args:
        path: Target file path
        content: String content to write
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (ensures same filesystem)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(content)

    # Atomic rename (replaces existing file atomically)
    os.replace(str(tmp_path), str(path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create signal file for swarm agent completion"
    )
    parser.add_argument(
        "signal_path",
        help="Path to signal file (e.g., .signals/001-name.done)",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to output file this signal represents",
    )
    parser.add_argument(
        "--status",
        choices=["success", "fail"],
        required=True,
        help="Completion status",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Size in bytes (auto-calculated if output file exists)",
    )
    parser.add_argument(
        "--error",
        help="Error message (only for status=fail)",
    )
    parser.add_argument(
        "--trace-id",
        help="Trace ID for distributed tracing (auto-read from .trace if omitted)",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=None,
        help="Artifact version number (for refinement loops)",
    )
    parser.add_argument(
        "--previous",
        default=None,
        help="Path to previous version (only for version > 1)",
    )

    args = parser.parse_args()

    signal_path = Path(args.signal_path)
    output_path = Path(args.path)

    # Detect skill-relative pollution (paths that look like they're relative to skill location)
    if ".claude/skills/" in str(signal_path) and "/tmp/swarm/" in str(signal_path):
        raise ValueError(
            f"Signal path appears skill-relative: {signal_path}\n"
            "Use absolute path from project root."
        )

    # Auto-calculate size if not provided and file exists
    size = args.size
    if size is None and output_path.exists():
        size = output_path.stat().st_size
    elif size is None:
        size = 0

    # Get trace ID: explicit > auto-detect from session
    trace_id = args.trace_id
    if trace_id is None:
        # Try to auto-detect from session .trace file
        # Walk up from signal path to find .trace
        parent = signal_path.parent
        if parent.name == ".signals":
            trace_file = parent.parent / ".trace"
            if trace_file.exists():
                trace_id = trace_file.read_text().strip()

    # Calculate final path with correct extension upfront
    final_signal_path = signal_path
    if args.status == "success" and not signal_path.suffix == ".done":
        final_signal_path = signal_path.with_suffix(".done")
    elif args.status == "fail" and not signal_path.suffix == ".fail":
        final_signal_path = signal_path.with_suffix(".fail")

    # Auto-correct signal path if not under .signals/
    if final_signal_path.parent.name != ".signals":
        # Insert .signals/ between parent dir and filename
        corrected_path = final_signal_path.parent / ".signals" / final_signal_path.name
        print(
            f"WARNING: Signal path '{final_signal_path}' is not under a .signals/ directory. "
            f"Auto-correcting to: {corrected_path}",
            file=sys.stderr,
        )
        final_signal_path = corrected_path

    # Ensure signal directory exists
    final_signal_path.parent.mkdir(parents=True, exist_ok=True)

    # Build signal content
    lines = [
        f"path: {args.path}",
        f"size: {size}",
        f"status: {args.status}",
        f"created_at: {datetime.now(timezone.utc).isoformat()}",
    ]

    if args.error:
        lines.append(f"error: {args.error}")

    if trace_id:
        lines.append(f"trace_id: {trace_id}")

    if args.version is not None:
        lines.append(f"version: {args.version}")

    if args.previous:
        lines.append(f"previous: {args.previous}")

    signal_content = "\n".join(lines) + "\n"

    # Atomically write signal file to final path
    # This eliminates the race condition where partial signals could be visible
    atomic_write(final_signal_path, signal_content)

    print(f"Signal created: {final_signal_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
