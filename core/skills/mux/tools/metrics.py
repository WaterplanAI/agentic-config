#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Metrics collection for swarm observability.

Collects and exports session metrics for monitoring and alerting.
Target: <5ms collection overhead per session.

Usage:
    uv run metrics.py collect <session_dir>
    uv run metrics.py export <sessions_base> --format json
    uv run metrics.py export <sessions_base> --format prometheus
    uv run metrics.py summary <sessions_base>

Metrics collected:
    - session_duration_seconds
    - workers_total
    - workers_completed
    - workers_failed
    - signals_total
    - artifacts_total_bytes
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def collect_session_metrics(session_dir: Path) -> dict[str, Any]:
    """Collect metrics from a single session.

    Args:
        session_dir: Path to session directory

    Returns:
        Dict with session metrics
    """
    signals_dir = session_dir / ".signals"
    metrics: dict[str, Any] = {
        "session_id": session_dir.name,
        "timestamp": datetime.now().isoformat(),
    }

    # Parse session timestamp from directory name (YYYYMMDD-HHMM-topic)
    try:
        parts = session_dir.name.split("-")
        if len(parts) >= 2:
            date_str = parts[0]  # YYYYMMDD
            time_str = parts[1]  # HHMM
            metrics[
                "started_at"
            ] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:]}:00"
    except (IndexError, ValueError):
        pass

    # Count signals
    done_signals = list(signals_dir.glob("*.done")) if signals_dir.exists() else []
    fail_signals = list(signals_dir.glob("*.fail")) if signals_dir.exists() else []

    metrics["workers_completed"] = len(done_signals)
    metrics["workers_failed"] = len(fail_signals)
    metrics["workers_total"] = len(done_signals) + len(fail_signals)
    metrics["signals_total"] = metrics["workers_total"]

    # Calculate total artifact size
    total_bytes = 0
    for signal_file in done_signals:
        try:
            content = signal_file.read_text()
            for line in content.split("\n"):
                if line.startswith("size:"):
                    total_bytes += int(line.split(":")[1].strip())
        except (ValueError, IndexError):
            pass

    metrics["artifacts_total_bytes"] = total_bytes

    # Get trace ID if available
    trace_file = session_dir / ".trace"
    if trace_file.exists():
        metrics["trace_id"] = trace_file.read_text().strip()

    # Calculate duration if session appears complete
    if metrics["workers_total"] > 0:
        # Use most recent signal mtime as end time
        all_signals = done_signals + fail_signals
        if all_signals:
            latest_mtime = max(s.stat().st_mtime for s in all_signals)
            if "started_at" in metrics:
                try:
                    start = datetime.fromisoformat(metrics["started_at"])
                    end = datetime.fromtimestamp(latest_mtime)
                    metrics["duration_seconds"] = (end - start).total_seconds()
                except (ValueError, TypeError):
                    pass

    return metrics


def export_prometheus(sessions: list[dict[str, Any]]) -> str:
    """Export metrics in Prometheus format.

    Args:
        sessions: List of session metrics

    Returns:
        Prometheus exposition format string
    """
    lines = [
        "# HELP swarm_workers_total Total workers in session",
        "# TYPE swarm_workers_total gauge",
        "# HELP swarm_workers_completed Completed workers in session",
        "# TYPE swarm_workers_completed gauge",
        "# HELP swarm_workers_failed Failed workers in session",
        "# TYPE swarm_workers_failed gauge",
        "# HELP swarm_artifacts_bytes Total artifact size in bytes",
        "# TYPE swarm_artifacts_bytes gauge",
        "# HELP swarm_duration_seconds Session duration in seconds",
        "# TYPE swarm_duration_seconds gauge",
    ]

    for session in sessions:
        session_id = session.get("session_id", "unknown")
        labels = f'session="{session_id}"'

        if "workers_total" in session:
            lines.append(f'swarm_workers_total{{{labels}}} {session["workers_total"]}')
        if "workers_completed" in session:
            lines.append(
                f'swarm_workers_completed{{{labels}}} {session["workers_completed"]}'
            )
        if "workers_failed" in session:
            lines.append(
                f'swarm_workers_failed{{{labels}}} {session["workers_failed"]}'
            )
        if "artifacts_total_bytes" in session:
            lines.append(
                f'swarm_artifacts_bytes{{{labels}}} {session["artifacts_total_bytes"]}'
            )
        if "duration_seconds" in session:
            lines.append(
                f'swarm_duration_seconds{{{labels}}} {session["duration_seconds"]}'
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Swarm metrics collection")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # collect command
    collect_parser = subparsers.add_parser(
        "collect", help="Collect metrics from session"
    )
    collect_parser.add_argument("session_dir", type=Path, help="Session directory")
    collect_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # export command
    export_parser = subparsers.add_parser(
        "export", help="Export metrics from all sessions"
    )
    export_parser.add_argument(
        "sessions_base", type=Path, help="Base directory (e.g., tmp/swarm)"
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "prometheus"],
        default="json",
        help="Export format",
    )
    export_parser.add_argument(
        "--limit", type=int, default=50, help="Max sessions to export"
    )

    # summary command
    summary_parser = subparsers.add_parser("summary", help="Show metrics summary")
    summary_parser.add_argument("sessions_base", type=Path, help="Base directory")

    args = parser.parse_args()

    if args.command == "collect":
        metrics = collect_session_metrics(args.session_dir)
        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            for k, v in metrics.items():
                print(f"{k}: {v}")
        return 0

    elif args.command == "export":
        sessions = []
        session_dirs = sorted(
            args.sessions_base.glob("*-*-*"), key=lambda p: p.name, reverse=True
        )
        for session_dir in session_dirs[: args.limit]:
            if session_dir.is_dir():
                sessions.append(collect_session_metrics(session_dir))

        if args.format == "prometheus":
            print(export_prometheus(sessions))
        else:
            print(json.dumps(sessions, indent=2))
        return 0

    elif args.command == "summary":
        session_dirs = list(args.sessions_base.glob("*-*-*"))
        total_workers = 0
        total_completed = 0
        total_failed = 0

        for session_dir in session_dirs:
            if session_dir.is_dir():
                metrics = collect_session_metrics(session_dir)
                total_workers += metrics.get("workers_total", 0)
                total_completed += metrics.get("workers_completed", 0)
                total_failed += metrics.get("workers_failed", 0)

        print(f"Total sessions: {len(session_dirs)}")
        print(f"Total workers: {total_workers}")
        print(f"Completed: {total_completed}")
        print(f"Failed: {total_failed}")
        print(f"Success rate: {total_completed/max(total_workers, 1)*100:.1f}%")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
