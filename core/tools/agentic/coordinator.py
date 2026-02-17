#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Coordinator skeleton (Layer 3): sequences orchestrators per-phase.

Reference implementation for Layer 3 in the composition hierarchy.
Calls Layer 2 orchestrators (not executors) and tracks phase dependencies,
checkpoints, and escalation.

NEVER reads/writes source files. NEVER calls executors directly.

Usage:
    uv run core/tools/agentic/coordinator.py config.json
    uv run core/tools/agentic/coordinator.py config.json --max-depth 5
    uv run core/tools/agentic/coordinator.py config.json --session-dir /path/to/session

Exit codes:
    0  - all phases passed
    1  - unrecoverable failure
    2  - depth limit exceeded (passthrough)
    3  - human input required
    10 - needs refinement (quality gate failed)
    12 - partial success
    20 - interrupted
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import shared library (same package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_PARTIAL_SUCCESS,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    NON_ABSORBABLE_EXIT_CODES,
    get_project_root,
)
from lib.observability import (
    Timer,
    emit_event,
    init_session,
    propagate_trace_id,
    run_streaming,
    signal_completion,
    write_consolidated_report,
    write_live_report,
)


# -- Session management -------------------------------------------------------


def init_session_coordinator(base_dir: Path, topic: str) -> Path:
    """Create coordinator session directory with state initialization."""
    state = {
        "state": "INIT",
        "current_phase": 0,
        "total_phases": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_checkpoint": None,
        "depth_used": 0,
        "depth_max": 0,
    }
    subdirs = ["phases", "sentinel", "refinements", "resolutions", "checkpoints", "reports", ".signals"]
    return init_session(
        base_dir=base_dir,
        topic=topic,
        subdirs=subdirs,
        session_state=state,
        topic_max_len=80,
        lowercase_topic=False,
    )


def write_checkpoint(session_dir: Path, completed: list[dict], pending: list[str], depth_used: int, depth_max: int) -> Path:
    """Write checkpoint file for resume. Returns checkpoint path."""
    import os as _os
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    checkpoint_path = session_dir / "checkpoints" / f"cp-{timestamp}.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    trace_id = (session_dir / ".trace").read_text().strip() if (session_dir / ".trace").exists() else _os.urandom(8).hex()

    checkpoint = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "session_dir": str(session_dir),
        "trace_id": trace_id,
        "completed_phases": completed,
        "pending_phases": pending,
        "depth_used": depth_used,
        "depth_max": depth_max,
    }
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    return checkpoint_path


# -- Phase execution ----------------------------------------------------------


def run_orchestrator(
    orchestrator_path: Path,
    modifier: str,
    target: str,
    max_depth: int,
    cwd: str | None,
    session_dir: Path | None = None,
) -> tuple[int, dict | None]:
    """Execute a Layer 2 orchestrator with streaming. Returns (exit_code, manifest)."""
    cmd: list[str] = [
        "uv", "run", str(orchestrator_path),
        modifier, target,
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])
    if session_dir:
        cmd.extend(["--session-dir", str(session_dir)])

    try:
        exit_code, stdout = run_streaming(cmd, timeout=1800, label=f"orchestrator:{modifier}")
    except subprocess.TimeoutExpired:
        emit_event("L3", f"orchestrator:{modifier}", "TIMEOUT", detail="1800s limit")
        return EXIT_TIMEOUT, None
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED, None

    manifest: dict | None = None
    if stdout.strip():
        try:
            manifest = json.loads(stdout)
        except json.JSONDecodeError:
            pass

    return exit_code, manifest


def execute_phases(
    phases: list[dict],
    project_root: Path,
    max_depth: int,
    cwd: str | None,
    session_dir: Path | None,
) -> tuple[int, list[dict]]:
    """Execute phases sequentially with observability."""
    results: list[dict] = []

    for i, phase in enumerate(phases):
        phase_name = phase.get("name", f"phase-{i+1:02d}")
        orchestrator_rel = phase["orchestrator"]
        modifier = phase.get("modifier", "full")
        target = phase["target"]
        depends_on = phase.get("depends_on", [])

        # Check dependencies
        completed_names = {r["name"] for r in results if r["exit_code"] == EXIT_SUCCESS}
        unmet = [d for d in depends_on if d not in completed_names]
        if unmet:
            emit_event("L3", phase_name, "SKIP", detail=f"unmet deps: {unmet}")
            results.append({"name": phase_name, "status": "skipped", "exit_code": EXIT_FAILURE, "error": f"unmet deps: {unmet}"})
            continue

        emit_event("L3", phase_name, "STARTING")
        write_live_report(session_dir, "L3", phase_name, "STARTING")

        orchestrator_path = project_root / orchestrator_rel
        if not orchestrator_path.is_file():
            results.append({"name": phase_name, "status": "failed", "exit_code": EXIT_FAILURE, "error": f"orchestrator not found: {orchestrator_rel}"})
            continue

        with Timer() as t:
            exit_code, manifest = run_orchestrator(orchestrator_path, modifier, target, max_depth, cwd, session_dir=session_dir)

        # Non-absorbable: propagate
        if exit_code in NON_ABSORBABLE_EXIT_CODES:
            emit_event("L3", phase_name, f"ABORT:exit={exit_code}", elapsed_ms=t.elapsed_ms)
            signal_completion(session_dir, "L3", phase_name, "fail", elapsed_seconds=t.elapsed_seconds)
            results.append({"name": phase_name, "status": "failed", "exit_code": exit_code})
            return exit_code, results

        # Retry once on failure -- but NOT on timeout (A-05)
        if exit_code == EXIT_FAILURE and exit_code not in (EXIT_TIMEOUT,):
            emit_event("L3", phase_name, "RETRY")
            with Timer() as t:
                exit_code, manifest = run_orchestrator(orchestrator_path, modifier, target, max_depth, cwd, session_dir=session_dir)
            if exit_code in NON_ABSORBABLE_EXIT_CODES:
                results.append({"name": phase_name, "status": "failed", "exit_code": exit_code})
                return exit_code, results

        result_entry: dict = {
            "name": phase_name,
            "status": "success" if exit_code == EXIT_SUCCESS else "failed",
            "exit_code": exit_code,
        }
        if manifest:
            result_entry["manifest"] = manifest
        results.append(result_entry)

        signal_completion(session_dir, "L3", phase_name, "done" if exit_code == EXIT_SUCCESS else "fail", elapsed_seconds=t.elapsed_seconds)

        # Checkpoint after each phase
        if session_dir:
            completed_phases = [r for r in results if r["exit_code"] == EXIT_SUCCESS]
            pending_names = [p.get("name", f"phase-{j+1:02d}") for j, p in enumerate(phases) if j > i]
            write_checkpoint(session_dir, completed_phases, pending_names, i + 1, max_depth)

        status = "COMPLETE" if exit_code == EXIT_SUCCESS else f"FAILED:exit={exit_code}"
        emit_event("L3", phase_name, status, elapsed_ms=t.elapsed_ms)
        write_live_report(session_dir, "L3", phase_name, status, elapsed_seconds=t.elapsed_seconds)

    failed = sum(1 for r in results if r["exit_code"] != EXIT_SUCCESS)
    if failed == 0:
        signal_completion(session_dir, "L3", "coordinator", "done")
        return EXIT_SUCCESS, results
    if failed < len(results):
        signal_completion(session_dir, "L3", "coordinator", "partial")
        return EXIT_PARTIAL_SUCCESS, results
    signal_completion(session_dir, "L3", "coordinator", "fail")
    return EXIT_FAILURE, results


# -- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Layer 3 coordinator: sequences orchestrators per-phase"
    )
    parser.add_argument("config", metavar="CONFIG", help="Path to phase config JSON file")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=5)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--session-dir", dest="session_dir", default=None, help="Session directory for checkpoints")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Load phase config
    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"ERROR: Config not found: {config_path}", file=sys.stderr)
        return EXIT_FAILURE

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid config JSON: {e}", file=sys.stderr)
        return EXIT_FAILURE

    phases = config.get("phases", [])
    if not phases:
        print("ERROR: No phases defined in config", file=sys.stderr)
        return EXIT_FAILURE

    try:
        project_root = get_project_root(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    # Initialize session
    session_dir: Path | None = None
    if args.session_dir:
        session_dir = Path(args.session_dir)
        # R-16: Ensure all required subdirs exist
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        (session_dir / "reports").mkdir(parents=True, exist_ok=True)
        (session_dir / ".signals").mkdir(parents=True, exist_ok=True)
        propagate_trace_id(session_dir)

    # Execute phases
    exit_code, results = execute_phases(phases, project_root, args.max_depth, args.cwd, session_dir)

    # Generate consolidated report
    if session_dir:
        write_consolidated_report(session_dir)

    # Output phase report
    report = {
        "coordinator": config.get("name", "coordinator"),
        "phases": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["exit_code"] == EXIT_SUCCESS),
            "failed": sum(1 for r in results if r["exit_code"] != EXIT_SUCCESS),
            "exit_code": exit_code,
        },
    }
    print(json.dumps(report, indent=2))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
