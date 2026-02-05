#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session directory creation tool for mux orchestrator.

Generates unique trace ID for distributed tracing across agents.
Creates mux-active marker for hook enforcement.

Creates the standard session directory structure with all required subdirectories.

Usage:
    uv run session.py <topic_slug>
    uv run session.py <topic_slug> --base tmp/mux

Output (stdout):
    SESSION_DIR=tmp/mux/20260129-1500-topic
    TRACE_ID=a1b2c3d4e5f67890
    MUX_ACTIVE=outputs/session/<pid>/mux-active
"""

import argparse
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


def find_claude_pid() -> int | None:
    """Trace up process tree to find claude process PID."""
    try:
        pid = os.getpid()
        for _ in range(10):
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                capture_output=True, text=True
            )
            line = result.stdout.strip()
            if not line:
                break
            parts = line.split()
            if len(parts) >= 3:
                current_pid, ppid, comm = int(parts[0]), int(parts[1]), parts[2]
                if "claude" in comm.lower():
                    return current_pid
                pid = ppid
            else:
                break
    except Exception:
        pass
    return None


def find_agentic_root() -> Path:
    """Find agentic-config installation root or project root."""
    current = Path.cwd()
    for _ in range(10):
        if (current / "VERSION").exists() and (current / "core").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


def activate_mux_enforcement(session_dir: Path) -> Path | None:
    """Create mux-active marker for hook enforcement.

    Returns path to marker file or None if Claude PID not found.
    """
    claude_pid = find_claude_pid()
    if not claude_pid:
        # Fallback: use current PID (for local testing)
        claude_pid = os.getpid()

    agentic_root = find_agentic_root()
    marker_dir = agentic_root / f"outputs/session/{claude_pid}"
    marker_dir.mkdir(parents=True, exist_ok=True)

    marker_file = marker_dir / "mux-active"
    marker_file.write_text(f"{session_dir}\n{datetime.now().isoformat()}\n")

    return marker_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create mux session directory structure"
    )
    parser.add_argument(
        "topic_slug",
        help="Topic slug for session ID (e.g., 'auth-research')",
    )
    parser.add_argument(
        "--base",
        default="tmp/mux",
        help="Base directory for mux sessions (default: tmp/mux)",
    )
    parser.add_argument(
        "--parent-trace",
        dest="parent_trace",
        help="Parent trace ID for child sessions (propagation)",
    )

    args = parser.parse_args()

    # Generate session ID: YYYYMMDD-HHMM-topic
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    session_id = f"{timestamp}-{args.topic_slug}"
    session_dir = Path(args.base) / session_id

    # Create directory structure
    subdirs = ["research", "audits", "consolidated", "spy", ".signals", ".agents"]
    for subdir in subdirs:
        (session_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Generate or propagate trace ID
    if args.parent_trace:
        # Child session: use parent trace with new span
        trace_id = args.parent_trace
    else:
        # Root session: generate new trace ID (16 hex chars)
        trace_id = uuid.uuid4().hex[:16]

    # Store trace ID in session
    trace_file = session_dir / ".trace"
    trace_file.write_text(f"{trace_id}\n")

    # CRITICAL: Activate MUX enforcement hooks
    marker_file = activate_mux_enforcement(session_dir)

    # Output for shell consumption
    print(f"SESSION_DIR={session_dir}")
    print(f"TRACE_ID={trace_id}")
    if marker_file:
        print(f"MUX_ACTIVE={marker_file}")
        print("✓ MUX enforcement hooks ACTIVATED - forbidden tools will be BLOCKED")
    else:
        print("⚠ MUX_ACTIVE=none (Claude PID not found, hooks may not enforce)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
