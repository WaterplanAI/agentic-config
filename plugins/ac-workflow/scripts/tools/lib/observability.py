"""Observability patterns for the agentic composition hierarchy (L0-L4).

Provides 7 composable patterns:
  P1: run_streaming     - Streaming subprocess with stderr forwarding
  P2: signal_completion - Signal file writes at layer boundaries
  P3: get_trace_id / propagate_trace_id / build_child_env_with_trace
  P4: Timer             - Elapsed time context manager
  P5: emit_event        - Structured JSON-line progress events
  P6: write_live_report - Append-only session live report
  P7: write_consolidated_report - Post-hoc execution report
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import IO

from . import DEPTH_ENV_VAR, write_signal

# -- P4: Timer ----------------------------------------------------------------


class Timer:
    """Context manager for elapsed time tracking.

    Usage:
        with Timer() as t:
            do_work()
        print(t.elapsed_ms)
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float | None = None

    def __enter__(self) -> Timer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self._end = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        """Elapsed milliseconds (final after exit, running if still in context)."""
        end = self._end if self._end is not None else time.monotonic()
        return int((end - self._start) * 1000)

    @property
    def elapsed_seconds(self) -> float:
        """Elapsed seconds as float."""
        return self.elapsed_ms / 1000.0

    @property
    def running_elapsed_ms(self) -> int:
        """Always returns current running elapsed, even after exit."""
        return int((time.monotonic() - self._start) * 1000)


# -- P1: Streaming Subprocess ------------------------------------------------


def _forward_stderr(stream: IO[str], prefix: str) -> None:
    """Forward stderr line-by-line to parent stderr with prefix."""
    try:
        for line in stream:
            print(f"{prefix} {line}", end="", file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


def run_streaming(
    cmd: list[str],
    *,
    timeout: int,
    label: str,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run subprocess with streaming stderr and captured stdout.

    Child stderr is forwarded line-by-line to parent stderr with [label] prefix.
    Child stdout is captured and returned for manifest/JSON parsing.

    Returns:
        Tuple of (exit_code, captured_stdout).

    Raises:
        subprocess.TimeoutExpired: If timeout exceeded.
        KeyboardInterrupt: If user interrupts.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stderr_thread = Thread(
        target=_forward_stderr,
        args=(proc.stderr, f"[{label}]"),
        daemon=True,
    )
    stderr_thread.start()
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    except KeyboardInterrupt:
        proc.kill()
        proc.wait()
        raise
    stderr_thread.join(timeout=2)
    return proc.returncode, stdout or ""


# -- P3: Trace ID Propagation ------------------------------------------------

TRACE_ENV_VAR = "AGENTIC_TRACE_ID"


def get_trace_id() -> str | None:
    """Read trace ID from environment variable."""
    return os.environ.get(TRACE_ENV_VAR)


def propagate_trace_id(session_dir: Path | None = None) -> str:
    """Ensure a trace ID exists and is set in the environment.

    Priority: AGENTIC_TRACE_ID env > session_dir/.trace file > generate new.
    Sets the env var and writes to .trace file if session_dir provided.

    Returns:
        The trace ID string.
    """
    trace_id = os.environ.get(TRACE_ENV_VAR)

    if not trace_id and session_dir is not None:
        trace_file = session_dir / ".trace"
        if trace_file.is_file():
            trace_id = trace_file.read_text(encoding="utf-8").strip()

    if not trace_id:
        trace_id = os.urandom(8).hex()

    os.environ[TRACE_ENV_VAR] = trace_id

    if session_dir is not None:
        trace_file = session_dir / ".trace"
        if not trace_file.exists():
            trace_file.write_text(trace_id + "\n", encoding="utf-8")

    return trace_id


def build_child_env_with_trace(
    current_depth: int,
    trace_id: str | None = None,
) -> dict[str, str]:
    """Build subprocess-scoped environment with depth and trace ID.

    Does NOT mutate os.environ (fixes R-07 race condition).

    Returns:
        New env dict for subprocess use.
    """
    env = os.environ.copy()
    env[DEPTH_ENV_VAR] = str(current_depth + 1)
    if trace_id:
        env[TRACE_ENV_VAR] = trace_id
    elif TRACE_ENV_VAR in os.environ:
        env[TRACE_ENV_VAR] = os.environ[TRACE_ENV_VAR]
    return env


# -- P2: Signal Activation ---------------------------------------------------


def signal_completion(
    session_dir: Path | None,
    layer: str,
    name: str,
    status: str,
    artifact_path: str | None = None,
    trace_id: str | None = None,
    elapsed_seconds: float | None = None,
) -> Path | None:
    """Write a signal file at layer boundary. No-op if session_dir is None.

    Wraps lib.write_signal() with convenience defaults.
    """
    if session_dir is None:
        return None

    artifact_size: int | None = None
    if artifact_path:
        try:
            artifact_size = Path(artifact_path).stat().st_size
        except OSError:
            artifact_size = None

    effective_trace_id = trace_id or get_trace_id()

    signal_path = write_signal(
        session_dir=session_dir,
        layer=layer,
        name=name,
        status=status,
        artifact_path=artifact_path,
        artifact_size=artifact_size,
        trace_id=effective_trace_id,
    )

    return signal_path


# -- P5: Structured Progress Events ------------------------------------------


def emit_event(
    layer: str,
    stage: str,
    status: str,
    *,
    elapsed_ms: int | None = None,
    detail: str | None = None,
    depth: int | None = None,
) -> None:
    """Emit a structured progress event to stderr.

    Writes both a JSON-line (prefixed with @) and a human-readable line.
    """
    event: dict[str, object] = {
        "layer": layer,
        "stage": stage,
        "status": status,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    trace_id = get_trace_id()
    if trace_id:
        event["trace_id"] = trace_id
    if elapsed_ms is not None:
        event["elapsed_ms"] = elapsed_ms
    if detail:
        event["detail"] = detail
    if depth is not None:
        event["depth"] = depth

    # JSON-line (machine-readable)
    print(f"@{json.dumps(event, separators=(',', ':'))}", file=sys.stderr, flush=True)

    # Human-readable (backwards compatible)
    elapsed_str = f" ({elapsed_ms / 1000:.1f}s)" if elapsed_ms is not None else ""
    detail_str = f" - {detail}" if detail else ""
    print(f"[{stage}] {status}{elapsed_str}{detail_str}", file=sys.stderr, flush=True)


# -- P6: Live Report ---------------------------------------------------------


def write_live_report(
    session_dir: Path | None,
    layer: str,
    stage: str,
    status: str,
    *,
    elapsed_seconds: float | None = None,
    detail: str | None = None,
) -> None:
    """Append one line to session/.live-report (thread-safe via flock)."""
    if session_dir is None:
        return

    report_path = session_dir / ".live-report"
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    elapsed_str = f" ({elapsed_seconds:.1f}s)" if elapsed_seconds is not None else ""
    detail_str = f" - {detail}" if detail else ""
    line = f"[{timestamp}] [{layer}] [{stage}] {status}{elapsed_str}{detail_str}\n"

    try:
        with open(report_path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(line)
            fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        pass  # Best-effort; do not crash on report write failure


# -- P7: Consolidated Execution Report ---------------------------------------


def write_consolidated_report(session_dir: Path) -> Path:
    """Generate execution-report.md from signals, live-report, and trace.

    Returns:
        Path to the generated report.
    """
    reports_dir = session_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "execution-report.md"

    lines: list[str] = ["# Execution Report", ""]

    # Trace ID
    trace_file = session_dir / ".trace"
    if trace_file.is_file():
        trace_id = trace_file.read_text(encoding="utf-8").strip()
        lines.append(f"**Trace ID:** `{trace_id}`")
        lines.append("")

    # Signal summary table
    signals_dir = session_dir / ".signals"
    if signals_dir.is_dir():
        signal_files = sorted(signals_dir.glob("*"))
        if signal_files:
            lines.append("## Signals")
            lines.append("")
            lines.append("| Layer | Name | Status | Created |")
            lines.append("|-------|------|--------|---------|")
            for sf in signal_files:
                if sf.name.startswith("."):
                    continue
                content: dict[str, str] = {}
                for sline in sf.read_text(encoding="utf-8").strip().splitlines():
                    if ": " in sline:
                        k, _, v = sline.partition(": ")
                        content[k.strip()] = v.strip()
                lines.append(
                    f"| {content.get('layer', '?')} "
                    f"| {content.get('name', sf.name)} "
                    f"| {content.get('status', '?')} "
                    f"| {content.get('created_at', '?')} |"
                )
            lines.append("")

    # Live report timeline
    live_report = session_dir / ".live-report"
    if live_report.is_file():
        lines.append("## Timeline")
        lines.append("")
        lines.append("```")
        lines.append(live_report.read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("")

    lines.append(f"*Generated at {datetime.now(timezone.utc).isoformat()}*")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# -- Session initialization ---------------------------------------------------


def init_session(
    base_dir: Path | None,
    topic: str,
    subdirs: list[str] | None = None,
    session_state: dict[str, str | int | None] | None = None,
    topic_max_len: int = 80,
    lowercase_topic: bool = False,
) -> Path:
    """Create session directory structure with trace ID propagation.

    Args:
        base_dir: Base directory for session. If None, uses tmp/campaigns.
        topic: Topic string for directory name (sanitized).
        subdirs: List of subdirectory names to create. Defaults to minimal set.
        session_state: Optional session state dict to write as .session-state file.
        topic_max_len: Max length for sanitized topic (default: 80).
        lowercase_topic: Whether to lowercase topic before sanitization (default: False).

    Returns:
        Path to created session directory.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    topic_str = topic.lower() if lowercase_topic else topic
    safe_topic = re.sub(r"[^a-zA-Z0-9_-]", "-", topic_str)[:topic_max_len].strip("-")

    if base_dir is None:
        base_dir = Path("tmp") / "campaigns"

    session_dir = base_dir / f"{timestamp}-{safe_topic}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories (default minimal set)
    if subdirs is None:
        subdirs = ["phases", "refinements", "resolutions", "checkpoints", "reports", ".signals"]
    for subdir in subdirs:
        (session_dir / subdir).mkdir(exist_ok=True, parents=True)

    # Write trace ID
    propagate_trace_id(session_dir)

    # Write session state if provided
    if session_state is not None:
        state_content = "\n".join(f"{k}: {v}" for k, v in session_state.items()) + "\n"
        (session_dir / ".session-state").write_text(state_content)

    return session_dir
