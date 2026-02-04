#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Blocking signal polling tool for swarm orchestrator.

Polls .signals/ directory for completion signals until expected count reached
or timeout expires. Returns JSON summary to stdout.

Usage:
    uv run poll-signals.py <session_dir> --expected N --timeout SECONDS --interval SECONDS

Examples:
    uv run poll-signals.py tmp/swarm/20260130-1234-session --expected 5
    uv run poll-signals.py session_dir --expected 10 --timeout 600 --interval 5
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def count_signals(signals_dir: Path) -> tuple[int, int]:
    """Count .done and .fail signals in directory.

    Args:
        signals_dir: Path to .signals directory

    Returns:
        Tuple of (complete_count, failed_count)
    """
    if not signals_dir.exists():
        return (0, 0)

    complete = len(list(signals_dir.glob("*.done")))
    failed = len(list(signals_dir.glob("*.fail")))

    return (complete, failed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll signal directory until expected count or timeout"
    )
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
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait (default: 300)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )

    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    signals_dir = session_dir / ".signals"

    start_time = time.time()
    elapsed = 0.0

    while elapsed < args.timeout:
        complete, failed = count_signals(signals_dir)
        total = complete + failed

        # Exit conditions
        if total >= args.expected:
            status = "success" if failed == 0 else "partial"
            result = {
                "complete": complete,
                "failed": failed,
                "status": status,
                "elapsed": round(elapsed, 2),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            print(json.dumps(result))
            return 0

        # Progress logging after threshold (helps debug mismatches)
        if elapsed > 60 and int(elapsed) % 30 == 0:
            progress = {
                "type": "progress",
                "complete": complete,
                "failed": failed,
                "expected": args.expected,
                "elapsed": round(elapsed, 2),
            }
            print(json.dumps(progress), file=sys.stderr, flush=True)

        # Wait before next check
        time.sleep(args.interval)
        elapsed = time.time() - start_time

    # Timeout reached
    complete, failed = count_signals(signals_dir)
    result = {
        "complete": complete,
        "failed": failed,
        "status": "timeout",
        "elapsed": round(elapsed, 2),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result))
    return 1


if __name__ == "__main__":
    sys.exit(main())
