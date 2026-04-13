#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session directory creation tool for mux orchestrator.

Generates unique trace ID for distributed tracing across agents.
Creates mux-active marker for session observability.

NOTE: The mux-active marker is for observability and explicit shutdown signaling.
Strict runtime enforcement in pi is activated only when this tool is invoked with
`--strict-runtime`, which writes session-key-scoped activation artifacts the
workflow package runtime extension can consume.

Creates the standard session directory structure with all required subdirectories.

Usage:
    uv run session.py <topic_slug>
    uv run session.py <topic_slug> --base tmp/mux
    uv run session.py <topic_slug> --strict-runtime --session-key <key>

Output (stdout):
    SESSION_DIR=tmp/mux/20260129-1500-topic
    TRACE_ID=a1b2c3d4e5f67890
    LEDGER_PATH=tmp/mux/20260129-1500-topic/.mux-ledger.json
    MUX_ACTIVE=outputs/session/<pid>/mux-active
    STRICT_RUNTIME=true
    STRICT_RUNTIME_FILE=tmp/mux/20260129-1500-topic/.mux-runtime.json
    STRICT_RUNTIME_REGISTRY=outputs/session/mux-runtime/<hash>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ledger import init_ledger  # pyright: ignore[reportMissingImports]

STRICT_RUNTIME_VERSION = 1
STRICT_RUNTIME_FILE_NAME = ".mux-runtime.json"
STRICT_RUNTIME_REGISTRY_DIR = Path("outputs/session/mux-runtime")
STRICT_COORDINATOR_ALLOWED_WRITE_ROOTS = [".specs"]


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


def utc_now_iso() -> str:
    """Return an RFC-3339-like UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write JSON using write-temp-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(str(tmp_path), str(path))


def to_project_relative(project_root: Path, candidate: Path) -> str:
    """Render path relative to project root when possible."""
    try:
        return str(candidate.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(candidate.resolve())


def hash_session_key(session_key: str) -> str:
    """Return stable bounded hash for a runtime session key."""
    return hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:24]


def activate_mux_enforcement(session_dir: Path) -> Path | None:
    """Create mux-active marker for session observability.

    NOTE: This marker is for external observability and deactivation signaling.
    Strict runtime enforcement is activated only by the explicit strict-runtime
    artifacts written when `--strict-runtime` is used.

    Returns path to marker file or None if Claude PID not found.
    """
    claude_pid = find_claude_pid()
    if not claude_pid:
        # Fallback: use current PID (for local testing)
        claude_pid = os.getpid()

    project_root = find_project_root()
    marker_dir = project_root / f"outputs/session/{claude_pid}"
    marker_dir.mkdir(parents=True, exist_ok=True)

    marker_file = marker_dir / "mux-active"
    marker_file.write_text(f"{session_dir}\n{datetime.now().isoformat()}\n")

    return marker_file


def write_strict_runtime_activation(
    *,
    project_root: Path,
    session_dir: Path,
    ledger_path: Path,
    session_key: str | None,
) -> tuple[Path, Path | None, str]:
    """Write strict-runtime activation artifacts.

    Returns the session-local activation file path, optional session-key registry
    path, and the session-key hash used for registry addressing.
    """
    effective_session_key = session_key or f"session-dir:{session_dir}"
    session_key_hash = hash_session_key(effective_session_key)

    activation_file = session_dir / STRICT_RUNTIME_FILE_NAME
    registry_path: Path | None = None
    if session_key:
        registry_path = project_root / STRICT_RUNTIME_REGISTRY_DIR / f"{session_key_hash}.json"

    allowed_write_roots = STRICT_COORDINATOR_ALLOWED_WRITE_ROOTS.copy()
    activation_payload = {
        "version": STRICT_RUNTIME_VERSION,
        "mode": "strict",
        "activation_source": "session.py --strict-runtime",
        "session_key": session_key or "",
        "session_key_hash": session_key_hash,
        "session_dir": str(session_dir),
        "ledger_path": str(ledger_path),
        "activation_file": to_project_relative(project_root, activation_file),
        "registry_path": to_project_relative(project_root, registry_path) if registry_path is not None else "",
        "activated_at": utc_now_iso(),
        "allowed_write_roots": allowed_write_roots,
    }

    atomic_write_json(activation_file, activation_payload)
    if registry_path is not None:
        atomic_write_json(registry_path, activation_payload)

    return activation_file, registry_path, session_key_hash


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
        help="Project-root-relative base directory for mux sessions (default: tmp/mux)",
    )
    parser.add_argument(
        "--parent-trace",
        dest="parent_trace",
        help="Parent trace ID for child sessions (propagation)",
    )
    parser.add_argument(
        "--phase-id",
        default="phase-unknown",
        help="Phase identifier persisted in protocol ledger",
    )
    parser.add_argument(
        "--stage-id",
        default="stage-unknown",
        help="Stage identifier persisted in protocol ledger",
    )
    parser.add_argument(
        "--wave-id",
        default="wave-unknown",
        help="Wave identifier persisted in protocol ledger",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="Write explicit strict-runtime activation artifacts for the current pi session",
    )
    parser.add_argument(
        "--session-key",
        default="",
        help="Opaque pi session key used to scope strict-runtime activation",
    )

    args = parser.parse_args()

    # Generate session ID: YYYYMMDD-HHMM-topic
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    session_id = f"{timestamp}-{args.topic_slug}"
    # IMPORTANT: session_dir is intentionally RELATIVE to project root.
    # e.g., tmp/mux/20260209-1430-topic (NOT /tmp/mux/...).
    # Subagents must use this path as-is without prepending '/'.
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

    # Initialize authoritative control-plane ledger
    ledger_path = init_ledger(
        session_dir,
        session_id=session_id,
        phase_id=args.phase_id,
        stage_id=args.stage_id,
        wave_id=args.wave_id,
        actor="session.py",
    )

    # Create mux-active marker for session observability
    marker_file = activate_mux_enforcement(session_dir)
    project_root = find_project_root()

    # Output for shell consumption
    print(f"SESSION_DIR={session_dir}")
    print(f"TRACE_ID={trace_id}")
    print(f"LEDGER_PATH={ledger_path}")
    if marker_file:
        print(f"MUX_ACTIVE={to_project_relative(project_root, marker_file)}")
        print("MUX session marker created (observability).")
    else:
        print("MUX_ACTIVE=none (Claude PID not found, marker not created)")

    if args.strict_runtime:
        activation_file, registry_path, session_key_hash = write_strict_runtime_activation(
            project_root=project_root,
            session_dir=session_dir,
            ledger_path=ledger_path,
            session_key=args.session_key.strip() or None,
        )
        print("STRICT_RUNTIME=true")
        print(f"STRICT_RUNTIME_FILE={to_project_relative(project_root, activation_file)}")
        if registry_path is not None:
            print(f"STRICT_RUNTIME_REGISTRY={to_project_relative(project_root, registry_path)}")
        else:
            print("STRICT_RUNTIME_REGISTRY=none (session key not provided)")
        print(f"STRICT_RUNTIME_SESSION_KEY_HASH={session_key_hash}")
    else:
        print("STRICT_RUNTIME=false")

    return 0


if __name__ == "__main__":
    sys.exit(main())
