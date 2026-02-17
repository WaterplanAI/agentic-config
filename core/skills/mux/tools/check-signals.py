#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
One-shot signal checker for swarm orchestrator.

Reads .signals/ directory and returns JSON summary of completion status.
No polling loop -- single check, immediate return.

Usage:
    uv run check-signals.py <session_dir> --expected N
    uv run check-signals.py <session_dir> --expected N --signals-dir <path>

Examples:
    uv run check-signals.py tmp/swarm/20260130-1234-session --expected 5
    uv run check-signals.py session_dir --expected 10 --signals-dir session_dir/.signals
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def count_signals(
    session_dir: Path, signals_dir: Path | None = None
) -> tuple[int, int]:
    """Count .done and .fail signals in directory.

    Postel's Law: be liberal in what you accept.
    1. Check .signals/ first (fast path, preferred convention)
    2. Fall back to recursive glob if .signals/ is empty/missing
    3. Exclude .agents/ subdirectory (internal signals)

    Args:
        session_dir: Root session directory
        signals_dir: Specific signals directory to restrict search (optional)

    Returns:
        Tuple of (complete_count, failed_count)
    """
    if signals_dir is not None:
        if not signals_dir.exists():
            return (0, 0)
        complete = len(list(signals_dir.glob("*.done")))
        failed = len(list(signals_dir.glob("*.fail")))
        return (complete, failed)

    preferred_dir = session_dir / ".signals"

    preferred_complete: list[Path] = []
    preferred_failed: list[Path] = []
    if preferred_dir.exists():
        preferred_complete = list(preferred_dir.glob("*.done"))
        preferred_failed = list(preferred_dir.glob("*.fail"))

    misplaced_complete = [
        f
        for f in session_dir.rglob("*.done")
        if ".agents" not in f.parts and ".signals" not in f.parts
    ]
    misplaced_failed = [
        f
        for f in session_dir.rglob("*.fail")
        if ".agents" not in f.parts and ".signals" not in f.parts
    ]

    if misplaced_complete or misplaced_failed:
        names = [f.name for f in misplaced_complete + misplaced_failed]
        print(
            f"WARNING: Found {len(names)} misplaced signal(s) outside .signals/: {names}",
            file=sys.stderr,
        )

    total_complete = len(preferred_complete) + len(misplaced_complete)
    total_failed = len(preferred_failed) + len(misplaced_failed)

    return (total_complete, total_failed)


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot signal check (no polling)")
    parser.add_argument(
        "session_dir",
        help="Session directory containing .signals/ subdirectory",
    )
    parser.add_argument(
        "--expected",
        type=int,
        required=True,
        help="Expected number of signals",
    )
    parser.add_argument(
        "--signals-dir",
        type=str,
        help="Restrict search to specific signals directory (no fallback)",
    )

    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    signals_dir = Path(args.signals_dir) if args.signals_dir else None

    complete, failed = count_signals(session_dir, signals_dir)
    total = complete + failed

    status = (
        "complete"
        if total >= args.expected and failed == 0
        else "partial"
        if total >= args.expected
        else "incomplete"
    )

    result = {
        "complete": complete,
        "failed": failed,
        "expected": args.expected,
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result))
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
