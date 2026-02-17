#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.0"]
# ///
"""
Worker-Monitor Pattern Example: Monitor 2 background workers analyzing a directory.

This script demonstrates the mandatory worker-monitor pairing pattern where:
1. Worker agents run in background (run_in_background=True)
2. A monitor agent tracks their completion
3. Monitor knows the EXPECTED count of workers
4. Both are delegated (agent_type specified) with proper IDs

Usage:
    uv run monitor_workers.py <directory> --expected 2

Architecture:
    - 2 Worker agents scan directory parts in parallel
    - 1 Monitor agent polls for completion signals
    - Monitor waits for EXPECTED=2 workers to complete
    - Summary generated from combined worker findings
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class WorkerMonitorCoordinator:
    """Coordinates worker-monitor pairs for directory analysis."""

    def __init__(self, target_dir: Path, expected_count: int = 2):
        """Initialize coordinator.

        Args:
            target_dir: Directory to analyze
            expected_count: Number of workers to monitor
        """
        self.target_dir = Path(target_dir)
        self.expected_count = expected_count
        self.session_dir = Path("/tmp/swarm-session")
        self.signals_dir = self.session_dir / ".signals"
        self.signals_dir.mkdir(parents=True, exist_ok=True)

        # Worker tracking
        self.workers = {
            "worker-dir-analyzer-001": {
                "task_id": "worker-dir-analyzer-001",
                "agent_type": "worker",
                "role": "Directory structure analyzer",
                "status": "pending",
            },
            "worker-file-scanner-002": {
                "task_id": "worker-file-scanner-002",
                "agent_type": "worker",
                "role": "File content scanner",
                "status": "pending",
            },
        }

        # Monitor configuration
        self.monitor = {
            "task_id": "monitor-coordinator-001",
            "agent_type": "monitor",
            "expected_count": expected_count,
            "instructions": f"Monitor {expected_count} workers (worker-dir-analyzer-001, worker-file-scanner-002) analyzing {target_dir}",
            "status": "pending",
        }

        self.results = {"workers": {}, "summary": {}}

    def launch_workers(self) -> dict[str, dict]:
        """Simulate launching worker agents in background.

        In production, these would be actual Task() calls with run_in_background=True
        and agent_type='worker'.

        Returns:
            Dictionary of launched workers
        """
        print("\n=== LAUNCHING WORKERS ===")
        launch_info = {}

        for worker_id, worker_config in self.workers.items():
            print(f"\n[WORKER] Launching {worker_id}")
            print(f"  Role: {worker_config['role']}")
            print(f"  Task ID: {worker_config['task_id']}")
            print(f"  Agent Type: {worker_config['agent_type']}")
            print(f"  Run in Background: True")
            print(f"  Instructions: Analyze {self.target_dir} and create completion signal")

            launch_info[worker_id] = {
                "launched_at": datetime.now(timezone.utc).isoformat(),
                "agent_type": "worker",
            }
            self.workers[worker_id]["status"] = "working"

        return launch_info

    def launch_monitor(self) -> dict:
        """Launch monitor agent that oversees workers.

        In production, this would be a Task() call with:
        - run_in_background=True
        - agent_type='monitor'
        - expected_count=2
        - Instructions referencing both worker task IDs

        Returns:
            Monitor launch info
        """
        print("\n=== LAUNCHING MONITOR ===")
        print(f"\n[MONITOR] Launching {self.monitor['task_id']}")
        print(f"  Role: Director agent monitoring workers")
        print(f"  Agent Type: {self.monitor['agent_type']}")
        print(f"  Expected Worker Count: {self.monitor['expected_count']}")
        print(f"  Monitoring Task IDs: worker-dir-analyzer-001, worker-file-scanner-002")
        print(f"  Instructions: {self.monitor['instructions']}")
        print(f"  Run in Background: True")

        monitor_info = {
            "launched_at": datetime.now(timezone.utc).isoformat(),
            "agent_type": "monitor",
            "expected_count": self.expected_count,
        }
        self.monitor["status"] = "working"

        return monitor_info

    def simulate_worker_analysis(self, worker_id: str, delay: float = 2.0):
        """Simulate worker analysis by creating completion signals.

        Args:
            worker_id: Worker identifier
            delay: Simulated analysis time in seconds
        """
        time.sleep(delay)

        worker_name = self.workers[worker_id]["role"]
        signal_file = self.signals_dir / f"{worker_id}.done"

        # Simulate analysis findings
        if "dir" in worker_id.lower():
            findings = {
                "worker_id": worker_id,
                "analysis_type": "directory_structure",
                "target": str(self.target_dir),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "total_files": 247,
                    "total_directories": 34,
                    "max_depth": 6,
                    "largest_file_mb": 12.5,
                },
                "summary": "Directory structure analyzed: 247 files across 34 directories",
            }
        else:
            findings = {
                "worker_id": worker_id,
                "analysis_type": "file_content_scan",
                "target": str(self.target_dir),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "python_files": 89,
                    "config_files": 23,
                    "test_files": 45,
                    "code_lines_total": 14250,
                },
                "summary": "File content scanned: 89 Python files, 45 tests, 23 config files",
            }

        signal_file.write_text(json.dumps(findings, indent=2))
        self.workers[worker_id]["status"] = "completed"

        print(f"\n[SIGNAL] Worker {worker_id} completed")
        print(f"  Signal file: {signal_file}")
        print(f"  Findings: {findings['summary']}")

        self.results["workers"][worker_id] = findings

    def poll_for_completion(self, timeout: float = 30.0, interval: float = 1.0):
        """Monitor polls for worker completion signals.

        Implements the blocking poll pattern from poll-signals.py but
        integrated with worker completion tracking.

        Args:
            timeout: Maximum time to wait in seconds
            interval: Polling interval in seconds

        Returns:
            Poll result summary
        """
        print("\n=== MONITOR POLLING FOR COMPLETION ===")
        print(f"[MONITOR] Polling {self.signals_dir} for signals")
        print(f"  Expected workers: {self.expected_count}")
        print(f"  Timeout: {timeout}s, Interval: {interval}s")

        start_time = time.time()
        elapsed = 0.0
        poll_iterations = 0

        while elapsed < timeout:
            poll_iterations += 1

            # Count completion signals
            done_signals = list(self.signals_dir.glob("*.done"))
            fail_signals = list(self.signals_dir.glob("*.fail"))
            total_signals = len(done_signals) + len(fail_signals)

            if poll_iterations == 1 or elapsed > 5:
                print(
                    f"\n  [Poll #{poll_iterations}] Elapsed: {elapsed:.1f}s | "
                    f"Complete: {len(done_signals)} | Failed: {len(fail_signals)} | "
                    f"Expected: {self.expected_count}"
                )

            # Check if expected count reached
            if total_signals >= self.expected_count:
                completion_status = "success" if len(fail_signals) == 0 else "partial"
                result = {
                    "status": completion_status,
                    "complete": len(done_signals),
                    "failed": len(fail_signals),
                    "expected": self.expected_count,
                    "elapsed": round(elapsed, 2),
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "polling_iterations": poll_iterations,
                }

                print(f"\n[MONITOR] Completion detected!")
                print(f"  Status: {result['status']}")
                print(f"  Workers completed: {result['complete']}/{result['expected']}")
                print(f"  Total poll time: {result['elapsed']}s")

                self.monitor["status"] = "completed"
                return result

            # Wait before next poll
            time.sleep(interval)
            elapsed = time.time() - start_time

        # Timeout reached
        done_signals = list(self.signals_dir.glob("*.done"))
        fail_signals = list(self.signals_dir.glob("*.fail"))

        result = {
            "status": "timeout",
            "complete": len(done_signals),
            "failed": len(fail_signals),
            "expected": self.expected_count,
            "elapsed": round(elapsed, 2),
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "polling_iterations": poll_iterations,
        }

        print(f"\n[MONITOR] Polling timeout reached after {poll_iterations} iterations")
        print(f"  Status: {result['status']}")
        print(f"  Workers completed: {result['complete']}/{result['expected']}")

        self.monitor["status"] = "timeout"
        return result

    def generate_summary(self, poll_result: dict) -> dict:
        """Generate combined summary from all worker findings.

        Args:
            poll_result: Result from monitor polling

        Returns:
            Combined analysis summary
        """
        print("\n=== GENERATING SUMMARY ===")

        summary = {
            "analysis_target": str(self.target_dir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitor_status": poll_result["status"],
            "workers_completed": poll_result["complete"],
            "workers_expected": poll_result["expected"],
            "total_poll_time_seconds": poll_result["elapsed"],
            "polling_iterations": poll_result.get("polling_iterations", 0),
            "worker_findings": [],
            "combined_metrics": {
                "total_files": 0,
                "total_directories": 0,
                "python_files": 0,
                "test_files": 0,
                "config_files": 0,
                "total_code_lines": 0,
            },
            "completion_status": "SUCCESS" if poll_result["status"] == "success" else "PARTIAL",
        }

        # Aggregate worker findings
        for worker_id, findings in self.results["workers"].items():
            summary["worker_findings"].append({
                "worker_id": worker_id,
                "role": self.workers[worker_id]["role"],
                "analysis_type": findings.get("analysis_type", "unknown"),
                "summary": findings.get("summary", ""),
                "metrics": findings.get("metrics", {}),
            })

            # Combine metrics
            metrics = findings.get("metrics", {})
            if "total_files" in metrics:
                summary["combined_metrics"]["total_files"] += metrics["total_files"]
            if "total_directories" in metrics:
                summary["combined_metrics"]["total_directories"] += (
                    metrics["total_directories"]
                )
            if "python_files" in metrics:
                summary["combined_metrics"]["python_files"] += metrics["python_files"]
            if "test_files" in metrics:
                summary["combined_metrics"]["test_files"] += metrics["test_files"]
            if "config_files" in metrics:
                summary["combined_metrics"]["config_files"] += metrics["config_files"]
            if "code_lines_total" in metrics:
                summary["combined_metrics"]["total_code_lines"] += metrics[
                    "code_lines_total"
                ]

        self.results["summary"] = summary
        return summary

    def run(self):
        """Execute full worker-monitor orchestration flow."""
        print("\n" + "=" * 70)
        print("WORKER-MONITOR ORCHESTRATION EXAMPLE")
        print("=" * 70)
        print(f"Target Directory: {self.target_dir}")
        print(f"Expected Workers: {self.expected_count}")

        # Phase 1: Launch workers
        self.launch_workers()

        # Phase 2: Launch monitor (MUST be in same message as workers)
        self.launch_monitor()

        # Phase 3: Simulate background worker execution
        print("\n=== SIMULATING BACKGROUND WORKER EXECUTION ===")
        import threading

        worker_threads = []
        for i, (worker_id, worker_config) in enumerate(self.workers.items()):
            # Stagger worker completion times
            delay = 2.0 + (i * 1.5)
            thread = threading.Thread(
                target=self.simulate_worker_analysis, args=(worker_id, delay)
            )
            thread.daemon = True
            thread.start()
            worker_threads.append(thread)

        # Phase 4: Monitor polls for completion
        poll_result = self.poll_for_completion()

        # Wait for all worker threads to finish
        for thread in worker_threads:
            thread.join()

        # Phase 5: Generate summary
        summary = self.generate_summary(poll_result)

        # Phase 6: Output results
        return self._format_output(summary)

    def _format_output(self, summary: dict) -> int:
        """Format and output final results.

        Args:
            summary: Analysis summary

        Returns:
            Exit code
        """
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(json.dumps(summary, indent=2))

        print("\n=== COMPLETION REPORT ===")
        print(f"Status: {summary['completion_status']}")
        print(f"Workers Completed: {summary['workers_completed']}/{summary['workers_expected']}")
        print(f"Total Analysis Time: {summary['total_poll_time_seconds']}s")
        print(f"Polling Iterations: {summary['polling_iterations']}")
        print(f"\nCombined Metrics:")
        for key, value in summary["combined_metrics"].items():
            print(f"  {key}: {value}")

        if summary["completion_status"] == "SUCCESS":
            print("\nAll workers completed successfully!")
            return 0
        else:
            print("\nSome workers did not complete (see details above)")
            return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor 2 background workers analyzing a directory"
    )
    # Default uses current directory; $PROJECT_ROOT in docs refers to repo root
    parser.add_argument(
        "directory", nargs="?", default="."
    )
    parser.add_argument(
        "--expected", type=int, default=2, help="Expected number of workers (default: 2)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Polling timeout in seconds (default: 30)",
    )

    args = parser.parse_args()

    coordinator = WorkerMonitorCoordinator(args.directory, args.expected)
    return coordinator.run()


if __name__ == "__main__":
    sys.exit(main())
