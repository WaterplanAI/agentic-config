#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Deactivate MUX enforcement hooks.

Removes the mux-active marker file, returning to normal operation mode.

Usage:
    uv run deactivate.py

Output (stdout):
    MUX_DEACTIVATED=true
"""

import os
import subprocess
import sys
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


def main() -> int:
    claude_pid = find_claude_pid()
    if not claude_pid:
        claude_pid = os.getpid()

    agentic_root = find_agentic_root()
    marker_file = agentic_root / f"outputs/session/{claude_pid}/mux-active"

    if marker_file.exists():
        # Read session info before deleting
        session_info = marker_file.read_text().strip().split("\n")[0]
        marker_file.unlink()
        print(f"MUX_DEACTIVATED=true")
        print(f"SESSION_WAS={session_info}")
        print("✓ MUX enforcement hooks DEACTIVATED - normal operation restored")
    else:
        print("MUX_DEACTIVATED=false")
        print("⚠ No active MUX session found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
