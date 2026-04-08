#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Signal and ledger verification helpers for mux orchestration.

Legacy summary/count modes remain available for smoke compatibility.
Phase 003 adds a ledger-aware gate mode that treats verification as explicit,
persisted control-plane evidence.

Usage:
    uv run verify.py <session_dir> --action count
    uv run verify.py <session_dir> --action failures
    uv run verify.py <session_dir> --action paths
    uv run verify.py <session_dir> --action sizes
    uv run verify.py <session_dir> --action total-size
    uv run verify.py <session_dir> --action summary
    uv run verify.py <session_dir> --action gate --summary-evidence <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ledger import (  # pyright: ignore[reportMissingImports]
    LedgerError,
    apply_verification_gate,
    load_ledger,
    validate_declared_dispatch,
)


def parse_signal(signal_path: Path) -> dict[str, str]:
    """Parse a signal file into key-value pairs."""
    data: dict[str, str] = {}
    if signal_path.exists():
        for line in signal_path.read_text().strip().split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                data[key] = value
    return data


def find_signals(session_dir: Path, signals_dir: Path | None, pattern: str) -> list[Path]:
    """Find signal files using Postel's Law fallback.

    1. Check .signals/ first (fast path, preferred convention)
    2. Fall back to recursive glob if .signals/ is empty/missing
    3. Exclude .agents/ subdirectory (internal signals)

    Args:
        session_dir: Root session directory
        signals_dir: Specific signals directory to restrict search (optional)
        pattern: Glob pattern (e.g., "*.done", "*.fail")

    Returns:
        List of matching signal file paths
    """
    if signals_dir is not None:
        # Restricted mode: only check specified directory
        if not signals_dir.exists():
            return []
        return list(signals_dir.glob(pattern))

    # Unrestricted mode: ALWAYS check both .signals/ AND recursive
    # This fixes the bug where some signals land in .signals/ and others
    # are misplaced at the session root -- previously the fallback only ran
    # when .signals/ was completely empty.
    preferred_dir = session_dir / ".signals"

    # Collect from .signals/ (preferred location)
    preferred: list[Path] = []
    if preferred_dir.exists():
        preferred = list(preferred_dir.glob(pattern))

    # Collect misplaced signals (recursive, excluding .agents/ and .signals/)
    misplaced = [
        file_path
        for file_path in session_dir.rglob(pattern)
        if ".agents" not in file_path.parts and ".signals" not in file_path.parts
    ]

    if misplaced:
        names = [file_path.name for file_path in misplaced]
        print(
            f"WARNING: Found {len(names)} misplaced signal(s) outside .signals/: {names}",
            file=sys.stderr,
        )

    return preferred + misplaced


def count_completions(session_dir: Path, signals_dir: Path | None = None) -> int:
    """Count .done signal files."""
    return len(find_signals(session_dir, signals_dir, "*.done"))


def list_failures(session_dir: Path, signals_dir: Path | None = None) -> list[dict[str, str]]:
    """List all .fail signals with their error messages."""
    failures = []
    for fail_file in find_signals(session_dir, signals_dir, "*.fail"):
        data = parse_signal(fail_file)
        failures.append(
            {
                "signal": fail_file.name,
                "path": data.get("path", ""),
                "error": data.get("error", "unknown"),
            }
        )
    return failures


def get_paths(session_dir: Path, signals_dir: Path | None = None) -> list[str]:
    """Extract all output paths from .done signals."""
    paths = []
    for done_file in sorted(find_signals(session_dir, signals_dir, "*.done")):
        data = parse_signal(done_file)
        if "path" in data:
            paths.append(data["path"])
    return paths


def get_sizes(session_dir: Path, signals_dir: Path | None = None) -> list[tuple[str, int]]:
    """Extract all output sizes from .done signals."""
    sizes = []
    for done_file in sorted(find_signals(session_dir, signals_dir, "*.done")):
        data = parse_signal(done_file)
        if "size" in data:
            sizes.append((done_file.stem, int(data["size"])))
    return sizes


def get_total_size(session_dir: Path, signals_dir: Path | None = None) -> int:
    """Sum all output sizes from .done signals."""
    total = 0
    for done_file in find_signals(session_dir, signals_dir, "*.done"):
        data = parse_signal(done_file)
        if "size" in data:
            total += int(data["size"])
    return total


def resolve_artifact_path(path_value: str) -> Path:
    """Resolve project-root-relative artifact paths against the current CWD."""
    artifact = Path(path_value)
    if artifact.is_absolute():
        return artifact
    return Path.cwd() / artifact


def artifact_path_descriptor(path_value: str | Path) -> str:
    """Normalize artifact descriptor to project-root-relative when possible."""
    artifact = Path(path_value)
    if isinstance(path_value, str) and not artifact.is_absolute():
        return path_value

    resolved_artifact = artifact.resolve()
    project_root = Path.cwd().resolve()
    try:
        return str(resolved_artifact.relative_to(project_root))
    except ValueError:
        return str(resolved_artifact)


def _format_modified_at(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _parse_iso8601_timestamp(raw: str) -> datetime:
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _summary_metadata_mismatches(evidence: dict[str, Any], report_path: Path) -> list[str]:
    report_stat = report_path.stat()
    report_content = report_path.read_text()
    report_modified_at = datetime.fromtimestamp(report_stat.st_mtime, tz=timezone.utc)

    mismatches: list[str] = []

    size_bytes = evidence.get("size_bytes")
    if not isinstance(size_bytes, int):
        mismatches.append("summary evidence missing integer size_bytes metadata")
    elif size_bytes != report_stat.st_size:
        mismatches.append("summary evidence size_bytes does not match report artifact")

    word_count = evidence.get("word_count")
    current_word_count = len(report_content.split())
    if not isinstance(word_count, int):
        mismatches.append("summary evidence missing integer word_count metadata")
    elif word_count != current_word_count:
        mismatches.append("summary evidence word_count does not match report artifact")

    modified_at = evidence.get("modified_at")
    expected_modified_at = _format_modified_at(report_stat.st_mtime)
    if not isinstance(modified_at, str):
        mismatches.append("summary evidence missing modified_at metadata")
    elif modified_at != expected_modified_at:
        mismatches.append("summary evidence modified_at does not match report artifact")

    generated_at = evidence.get("generated_at")
    if not isinstance(generated_at, str):
        mismatches.append("summary evidence missing generated_at metadata")
    else:
        try:
            generated_at_dt = _parse_iso8601_timestamp(generated_at)
        except ValueError:
            mismatches.append("summary evidence generated_at is not valid ISO-8601")
        else:
            if generated_at_dt < report_modified_at:
                mismatches.append(
                    "summary evidence generated_at predates report artifact modification"
                )

    return mismatches


def load_summary_evidence(path: Path) -> dict[str, Any]:
    """Load and minimally validate machine-readable summary evidence JSON."""
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid summary evidence JSON: {error}") from error

    if not isinstance(raw, dict):
        raise ValueError("Summary evidence must be a JSON object")

    required_fields = [
        "report_path",
        "resolved_report_path",
        "executive_summary_found",
        "generated_at",
    ]
    for field in required_fields:
        if field not in raw:
            raise ValueError(f"Summary evidence missing field: {field}")

    return raw


def _summary_matches_declared_report(
    evidence: dict[str, Any],
    declared_report_path: str,
) -> bool:
    declared_report_abs = resolve_artifact_path(declared_report_path).resolve()

    candidates: list[Path] = []
    report_path = evidence.get("report_path")
    if isinstance(report_path, str) and report_path:
        candidates.append(resolve_artifact_path(report_path).resolve())

    resolved_report_path = evidence.get("resolved_report_path")
    if isinstance(resolved_report_path, str) and resolved_report_path:
        candidates.append(Path(resolved_report_path).expanduser().resolve())

    return any(candidate == declared_report_abs for candidate in candidates)


def run_gate(
    session_dir: Path,
    *,
    summary_evidence_path: Path | None,
    actor: str,
) -> tuple[dict[str, Any], int]:
    """Run ledger-aware verification gate and persist final gate state."""
    ledger = load_ledger(session_dir)

    if ledger["control_state"] != "DISPATCH":
        return (
            {
                "gate_status": "error",
                "control_state": ledger["control_state"],
                "reason": "gate requires control_state=DISPATCH",
            },
            1,
        )

    declared_dispatch = ledger["declared_dispatch"]
    dispatch_valid, dispatch_error = validate_declared_dispatch(declared_dispatch)
    if not dispatch_valid:
        updated = apply_verification_gate(
            session_dir,
            verification_status="fail",
            checked_artifacts=[],
            summary_path="",
            actor=actor,
            reason="verification moved to recovery due to invalid declared dispatch",
            recovery_trigger=dispatch_error,
            recovery_plan="repair declared_dispatch payload and redeclare",
        )
        return (
            {
                "gate_status": "recover",
                "control_state": updated["control_state"],
                "verification_status": updated["verification"]["status"],
                "reason": dispatch_error,
            },
            1,
        )

    prerequisites = ledger["prerequisites"]
    prereq_status = prerequisites["status"].strip().lower()
    missing_prerequisites = list(prerequisites["missing"])
    if prereq_status not in {"ready", "satisfied", "pass"} or missing_prerequisites:
        updated = apply_verification_gate(
            session_dir,
            verification_status="blocked",
            checked_artifacts=[],
            summary_path="",
            actor=actor,
            reason="verification blocked: prerequisites incomplete",
            blocker_reason="missing prerequisite evidence",
            missing_prerequisites=missing_prerequisites or prerequisites["required"],
        )
        return (
            {
                "gate_status": "block",
                "control_state": updated["control_state"],
                "verification_status": updated["verification"]["status"],
                "missing_prerequisites": missing_prerequisites,
            },
            1,
        )

    report_path_value = declared_dispatch["report_path"]
    signal_path_value = declared_dispatch["signal_path"]

    report_path = resolve_artifact_path(report_path_value)
    signal_path = resolve_artifact_path(signal_path_value)

    checked_artifacts: list[str] = []
    missing_evidence: list[str] = []
    inconsistent_evidence: list[str] = []

    report_exists = report_path.exists()
    if report_exists:
        checked_artifacts.append(report_path_value)
    else:
        missing_evidence.append(f"missing report artifact: {report_path_value}")

    if signal_path.exists():
        checked_artifacts.append(signal_path_value)
        signal_data = parse_signal(signal_path)

        signal_report_path = signal_data.get("path", "")
        if not signal_report_path:
            inconsistent_evidence.append("signal artifact missing path field")
        elif resolve_artifact_path(signal_report_path).resolve() != report_path.resolve():
            inconsistent_evidence.append(
                "signal path does not match declared report path"
            )

        signal_status = signal_data.get("status", "")
        if signal_status != "success":
            inconsistent_evidence.append(
                f"signal status must be success, found: {signal_status or 'missing'}"
            )
    else:
        missing_evidence.append(f"missing signal artifact: {signal_path_value}")

    summary_path = summary_evidence_path
    if summary_path is None and ledger["verification"]["summary_path"]:
        summary_path = resolve_artifact_path(ledger["verification"]["summary_path"])

    summary_path_value = ""
    if summary_path is None:
        missing_evidence.append("missing summary evidence path")
    elif not summary_path.exists():
        missing_evidence.append(f"missing summary evidence artifact: {summary_path}")
    else:
        summary_path_value = artifact_path_descriptor(summary_path)
        checked_artifacts.append(summary_path_value)
        try:
            summary_evidence = load_summary_evidence(summary_path)
        except ValueError as error:
            inconsistent_evidence.append(str(error))
        else:
            if summary_evidence.get("executive_summary_found") is not True:
                missing_evidence.append("summary evidence missing Executive Summary section")

            if not _summary_matches_declared_report(summary_evidence, report_path_value):
                inconsistent_evidence.append(
                    "summary evidence report path does not match declared dispatch"
                )
            elif report_exists:
                inconsistent_evidence.extend(
                    _summary_metadata_mismatches(summary_evidence, report_path)
                )

    if inconsistent_evidence:
        updated = apply_verification_gate(
            session_dir,
            verification_status="fail",
            checked_artifacts=checked_artifacts,
            summary_path=summary_path_value,
            actor=actor,
            reason="verification moved to recovery: inconsistent evidence",
            recovery_trigger="; ".join(inconsistent_evidence),
            recovery_plan="reconcile report/signal/summary artifacts and rerun verification",
        )
        return (
            {
                "gate_status": "recover",
                "control_state": updated["control_state"],
                "verification_status": updated["verification"]["status"],
                "checked_artifacts": checked_artifacts,
                "missing_evidence": missing_evidence,
                "inconsistent_evidence": inconsistent_evidence,
            },
            1,
        )

    if missing_evidence:
        updated = apply_verification_gate(
            session_dir,
            verification_status="blocked",
            checked_artifacts=checked_artifacts,
            summary_path=summary_path_value,
            actor=actor,
            reason="verification blocked: missing evidence",
            blocker_reason="required report/signal/summary evidence is missing",
            missing_prerequisites=missing_evidence,
        )
        return (
            {
                "gate_status": "block",
                "control_state": updated["control_state"],
                "verification_status": updated["verification"]["status"],
                "checked_artifacts": checked_artifacts,
                "missing_evidence": missing_evidence,
            },
            1,
        )

    updated = apply_verification_gate(
        session_dir,
        verification_status="pass",
        checked_artifacts=checked_artifacts,
        summary_path=summary_path_value,
        actor=actor,
        reason="verification passed with declared report/signal/summary evidence",
    )
    return (
        {
            "gate_status": "advance",
            "control_state": updated["control_state"],
            "verification_status": updated["verification"]["status"],
            "checked_artifacts": checked_artifacts,
            "missing_evidence": [],
            "inconsistent_evidence": [],
        },
        0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify mux completion and gate state via signals + protocol ledger"
    )
    parser.add_argument(
        "session_dir",
        help="Path to session directory (project-root-relative)",
    )
    parser.add_argument(
        "--action",
        choices=["count", "failures", "paths", "sizes", "total-size", "summary", "gate"],
        default="summary",
        help="Verification action to perform (default: summary)",
    )
    parser.add_argument(
        "--signals-dir",
        type=str,
        help="Restrict search to specific signals directory (no fallback)",
    )
    parser.add_argument(
        "--summary-evidence",
        type=str,
        help=(
            "Path to extract-summary machine-readable evidence JSON "
            "(project-root-relative, for --action gate)"
        ),
    )
    parser.add_argument(
        "--actor",
        default="verify.py",
        help="Actor name for persisted gate transitions (for --action gate)",
    )

    args = parser.parse_args()
    session_dir = Path(args.session_dir)
    signals_dir = Path(args.signals_dir) if args.signals_dir else None

    if args.action == "count":
        print(count_completions(session_dir, signals_dir))

    elif args.action == "failures":
        failures = list_failures(session_dir, signals_dir)
        if failures:
            for failure in failures:
                print(f"{failure['signal']}: {failure['error']}")
        else:
            print("No failures")

    elif args.action == "paths":
        for path in get_paths(session_dir, signals_dir):
            print(path)

    elif args.action == "sizes":
        for name, size in get_sizes(session_dir, signals_dir):
            print(f"{name}: {size}")

    elif args.action == "total-size":
        print(get_total_size(session_dir, signals_dir))

    elif args.action == "summary":
        completed = count_completions(session_dir, signals_dir)
        failures = list_failures(session_dir, signals_dir)
        total_size = get_total_size(session_dir, signals_dir)
        paths = get_paths(session_dir, signals_dir)

        print(f"completed: {completed}")
        print(f"failed: {len(failures)}")
        print(f"total_size: {total_size}")
        print(f"paths: {len(paths)}")
        if failures:
            print("failures:")
            for failure in failures:
                print(f"  - {failure['signal']}: {failure['error']}")

    elif args.action == "gate":
        summary_evidence_path = Path(args.summary_evidence) if args.summary_evidence else None
        try:
            result, exit_code = run_gate(
                session_dir,
                summary_evidence_path=summary_evidence_path,
                actor=args.actor,
            )
        except (LedgerError, ValueError, OSError, json.JSONDecodeError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        print(json.dumps(result, indent=2, sort_keys=True))
        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
