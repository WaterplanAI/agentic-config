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

STRICT_RUNTIME_VERSION = 1
STRICT_RUNTIME_FILE_NAME = ".mux-runtime.json"
STRICT_RUNTIME_LEDGER_FILE_NAME = ".mux-ledger.json"
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


def is_within_root(candidate: Path, root: Path) -> bool:
    """Return whether candidate resolves inside root (or equals root)."""
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_project_relative_path(project_root: Path, candidate_path: str) -> Path | None:
    """Resolve candidate_path and ensure it stays within project_root."""
    normalized = candidate_path.strip()
    if not normalized:
        return None

    raw_path = Path(normalized)
    if raw_path.is_absolute():
        return None

    resolved_path = (project_root / raw_path).resolve()
    if not is_within_root(resolved_path, project_root):
        return None
    return resolved_path


def resolve_safe_activation_file(
    *,
    project_root: Path,
    registry_path: Path,
    payload: dict[str, Any],
    session_key: str,
) -> Path | None:
    """Resolve a safe strict-runtime activation file path from registry payload."""
    if payload.get("version") != STRICT_RUNTIME_VERSION:
        return None
    if payload.get("mode") != "strict":
        return None

    payload_session_key = payload.get("session_key")
    if not isinstance(payload_session_key, str) or payload_session_key != session_key:
        return None

    payload_session_key_hash = payload.get("session_key_hash")
    if not isinstance(payload_session_key_hash, str) or payload_session_key_hash != hash_session_key(session_key):
        return None

    payload_registry_path = payload.get("registry_path")
    if isinstance(payload_registry_path, str) and payload_registry_path.strip():
        resolved_registry_path = resolve_project_relative_path(project_root, payload_registry_path)
        if resolved_registry_path is None or resolved_registry_path != registry_path.resolve():
            return None

    payload_session_dir = payload.get("session_dir")
    if not isinstance(payload_session_dir, str):
        return None
    resolved_session_dir = resolve_project_relative_path(project_root, payload_session_dir)
    if resolved_session_dir is None:
        return None

    expected_ledger_path = resolved_session_dir / STRICT_RUNTIME_LEDGER_FILE_NAME
    if not expected_ledger_path.exists():
        return None

    expected_activation_path = (resolved_session_dir / STRICT_RUNTIME_FILE_NAME).resolve()
    payload_activation_file = payload.get("activation_file")
    if isinstance(payload_activation_file, str) and payload_activation_file.strip():
        resolved_activation_path = resolve_project_relative_path(project_root, payload_activation_file)
        if resolved_activation_path is None or resolved_activation_path != expected_activation_path:
            return None

    if not expected_activation_path.exists():
        return None

    activation_payload = load_json(expected_activation_path)
    if activation_payload.get("version") != STRICT_RUNTIME_VERSION:
        return None
    if activation_payload.get("mode") != "strict":
        return None
    if activation_payload.get("session_key") != session_key:
        return None
    if activation_payload.get("session_key_hash") != hash_session_key(session_key):
        return None
    if activation_payload.get("session_dir") != payload_session_dir:
        return None
    if activation_payload.get("ledger_path") != payload.get("ledger_path"):
        return None
    if activation_payload.get("activation_file") != payload_activation_file:
        return None

    return expected_activation_path


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
    strict_activation_file_removed = False
    strict_session_was = ""
    strict_session_key = args.session_key.strip()
    if strict_session_key:
        registry_path = project_root / STRICT_RUNTIME_REGISTRY_DIR / f"{hash_session_key(strict_session_key)}.json"
        if registry_path.exists():
            payload = load_json(registry_path)
            session_dir_value = payload.get("session_dir", "")
            strict_session_was = str(session_dir_value) if isinstance(session_dir_value, str) else ""

            activation_file = resolve_safe_activation_file(
                project_root=project_root,
                registry_path=registry_path,
                payload=payload,
                session_key=strict_session_key,
            )
            if activation_file is not None and activation_file.exists():
                activation_file.unlink()
                strict_activation_file_removed = True

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
        if strict_activation_file_removed:
            print("Strict runtime activation artifacts removed.")
        else:
            print("Strict runtime registry removed; activation file cleanup skipped.")
    else:
        print("WARNING: No strict runtime activation found for the provided session key")

    return 0


if __name__ == "__main__":
    sys.exit(main())
