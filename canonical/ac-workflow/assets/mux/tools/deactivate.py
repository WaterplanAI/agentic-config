#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Deactivate MUX session.

Removes the mux-active marker file for clean session-end signaling.
When a strict-runtime activation artifact exists for the current pi session key,
this tool also removes the strict activation registry entry and session-local
activation file so package-local runtime enforcement does not leak after the
mux session closes.

Usage:
    uv run deactivate.py
    uv run deactivate.py --session-key <key>

Output (stdout):
    MUX_DEACTIVATED=true|false
    STRICT_RUNTIME_DEACTIVATED=true|false
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

STRICT_RUNTIME_REGISTRY_DIR = Path("outputs/session/mux-runtime")


def find_claude_pid() -> int | None:
    """Trace up process tree to find claude process PID."""
    try:
        pid = os.getpid()
        for _ in range(10):
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            line = result.stdout.strip()
            if not line:
                break
            parts = line.split()
            if len(parts) >= 3:
                _, ppid, comm = int(parts[0]), int(parts[1]), parts[2]
                if "claude" in comm.lower():
                    return pid
                pid = ppid
            else:
                break
    except Exception:
        pass
    return None


def find_project_root() -> Path:
    """Find project root by walking up to .git or CLAUDE.md."""
    current = Path.cwd()
    for _ in range(10):
        if (current / ".git").exists() or (current / "CLAUDE.md").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


def hash_session_key(session_key: str) -> str:
    """Return stable bounded hash for a runtime session key."""
    return hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:24]


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON dictionary from disk."""
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Deactivate mux session markers")
    parser.add_argument(
        "--session-key",
        default="",
        help="Opaque pi session key used to scope strict-runtime activation cleanup",
    )
    args = parser.parse_args()

    claude_pid = find_claude_pid()
    if not claude_pid:
        claude_pid = os.getpid()

    project_root = find_project_root()
    marker_file = project_root / f"outputs/session/{claude_pid}/mux-active"

    strict_deactivated = False
    strict_session_was = ""
    if args.session_key.strip():
        registry_path = project_root / STRICT_RUNTIME_REGISTRY_DIR / f"{hash_session_key(args.session_key.strip())}.json"
        if registry_path.exists():
            payload = load_json(registry_path)
            activation_file_value = payload.get("activation_file", "")
            session_dir_value = payload.get("session_dir", "")
            strict_session_was = str(session_dir_value) if isinstance(session_dir_value, str) else ""

            if isinstance(activation_file_value, str) and activation_file_value.strip():
                activation_file = project_root / activation_file_value
                if activation_file.exists():
                    activation_file.unlink()

            registry_path.unlink()
            strict_deactivated = True

    marker_removed = False
    marker_session = ""
    if marker_file.exists():
        marker_session = marker_file.read_text().strip().split("\n")[0]
        marker_file.unlink()
        marker_removed = True

    print(f"MUX_DEACTIVATED={'true' if marker_removed else 'false'}")
    if marker_removed:
        print(f"SESSION_WAS={marker_session}")
        print("MUX session marker removed. Observability cleanup complete.")
    else:
        print("WARNING: No active mux marker found")

    print(f"STRICT_RUNTIME_DEACTIVATED={'true' if strict_deactivated else 'false'}")
    if strict_deactivated:
        if strict_session_was:
            print(f"STRICT_RUNTIME_SESSION_WAS={strict_session_was}")
        print("Strict runtime activation artifacts removed.")
    else:
        print("WARNING: No strict runtime activation found for the provided session key")

    return 0


if __name__ == "__main__":
    sys.exit(main())
