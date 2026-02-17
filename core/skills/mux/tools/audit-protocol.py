#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Protocol audit tool for swarm sessions.

Detects violations in 3 phases:
1. PRE-FLIGHT: Validate agent definitions before execution
2. RUNTIME: Analyze session transcript for violations (if available)
3. POST-EXECUTION: Check signals and outputs for protocol compliance

Usage:
    uv run audit-protocol.py <session_dir> --phase preflight
    uv run audit-protocol.py <session_dir> --phase runtime --transcript <file>
    uv run audit-protocol.py <session_dir> --phase post
    uv run audit-protocol.py <session_dir> --phase all

Output:
    JSON with violations array and severity counts
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TypedDict


class Violation(TypedDict):
    phase: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    rule: str
    detail: str
    location: str


def audit_preflight(session_dir: Path) -> list[Violation]:
    """Validate session structure and agent readiness."""
    violations: list[Violation] = []

    # Check required directories exist
    required_dirs = [".signals", "research", "audits", "consolidated"]
    for d in required_dirs:
        if not (session_dir / d).exists():
            violations.append({
                "phase": "preflight",
                "severity": "HIGH",
                "rule": "missing_directory",
                "detail": f"Required directory '{d}' not found",
                "location": str(session_dir / d),
            })

    # Check trace file exists
    if not (session_dir / ".trace").exists():
        violations.append({
            "phase": "preflight",
            "severity": "MEDIUM",
            "rule": "missing_trace",
            "detail": "Trace ID file not found - tracing disabled",
            "location": str(session_dir / ".trace"),
        })

    return violations


def audit_runtime(transcript_path: Path) -> list[Violation]:
    """Analyze session transcript for runtime violations."""
    violations: list[Violation] = []

    if not transcript_path.exists():
        return violations

    content = transcript_path.read_text()

    # Check for TaskOutput usage (CRITICAL)
    taskoutput_pattern = re.compile(r'TaskOutput\s*\(', re.MULTILINE)
    for match in taskoutput_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        violations.append({
            "phase": "runtime",
            "severity": "CRITICAL",
            "rule": "taskoutput_usage",
            "detail": "TaskOutput usage detected - violates signal-based protocol",
            "location": f"{transcript_path}:{line_num}",
        })

    # Check for block=True (CRITICAL)
    block_pattern = re.compile(r'block\s*=\s*True', re.MULTILINE)
    for match in block_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        violations.append({
            "phase": "runtime",
            "severity": "CRITICAL",
            "rule": "blocking_task",
            "detail": "Blocking task detected (block=True)",
            "location": f"{transcript_path}:{line_num}",
        })

    # Check for missing run_in_background (HIGH)
    task_pattern = re.compile(r'Task\s*\([^)]+\)', re.MULTILINE | re.DOTALL)
    for match in task_pattern.finditer(content):
        task_call = match.group()
        if "run_in_background" not in task_call:
            line_num = content[:match.start()].count('\n') + 1
            violations.append({
                "phase": "runtime",
                "severity": "HIGH",
                "rule": "missing_background",
                "detail": "Task() without run_in_background=True",
                "location": f"{transcript_path}:{line_num}",
            })

    return violations


def audit_post(session_dir: Path) -> list[Violation]:
    """Check signals and outputs for protocol compliance."""
    violations: list[Violation] = []
    signals_dir = session_dir / ".signals"

    if not signals_dir.exists():
        return violations

    for signal_file in signals_dir.glob("*.done"):
        content = signal_file.read_text()

        # Check required fields
        required_fields = ["path:", "size:", "status:"]
        for field in required_fields:
            if field not in content:
                violations.append({
                    "phase": "post",
                    "severity": "MEDIUM",
                    "rule": "incomplete_signal",
                    "detail": f"Signal missing required field: {field.rstrip(':')}",
                    "location": str(signal_file),
                })

        # Check for trace_id (after Phase 2 implementation)
        if "trace_id:" not in content:
            violations.append({
                "phase": "post",
                "severity": "LOW",
                "rule": "missing_trace_id",
                "detail": "Signal missing trace_id field",
                "location": str(signal_file),
            })

    # Check for .fail signals
    for fail_file in signals_dir.glob("*.fail"):
        violations.append({
            "phase": "post",
            "severity": "HIGH",
            "rule": "failed_signal",
            "detail": f"Agent signaled failure: {fail_file.name}",
            "location": str(fail_file),
        })

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit swarm session for protocol violations")
    parser.add_argument("session_dir", help="Session directory to audit")
    parser.add_argument(
        "--phase",
        choices=["preflight", "runtime", "post", "all"],
        default="all",
        help="Which audit phase to run (default: all)",
    )
    parser.add_argument(
        "--transcript",
        help="Path to session transcript (for runtime phase)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()
    session_dir = Path(args.session_dir)

    all_violations: list[Violation] = []

    if args.phase in ("preflight", "all"):
        all_violations.extend(audit_preflight(session_dir))

    if args.phase in ("runtime", "all"):
        if args.transcript:
            all_violations.extend(audit_runtime(Path(args.transcript)))

    if args.phase in ("post", "all"):
        all_violations.extend(audit_post(session_dir))

    # Count by severity
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for v in all_violations:
        severity_counts[v["severity"]] += 1

    result = {
        "session": str(session_dir),
        "phase": args.phase,
        "violations": all_violations,
        "counts": severity_counts,
        "total": len(all_violations),
        "status": "FAIL" if severity_counts["CRITICAL"] > 0 else "WARN" if len(all_violations) > 0 else "PASS",
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Session: {session_dir}")
        print(f"Phase: {args.phase}")
        print(f"Status: {result['status']}")
        print(f"Total violations: {len(all_violations)}")
        print(f"  CRITICAL: {severity_counts['CRITICAL']}")
        print(f"  HIGH: {severity_counts['HIGH']}")
        print(f"  MEDIUM: {severity_counts['MEDIUM']}")
        print(f"  LOW: {severity_counts['LOW']}")

        if all_violations:
            print("\nViolations:")
            for v in all_violations:
                print(f"  [{v['severity']}] {v['rule']}: {v['detail']}")
                print(f"         at {v['location']}")

    return 1 if severity_counts["CRITICAL"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
