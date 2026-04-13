#!/usr/bin/env python3
"""Behavior checks for pimux launcher-exit reporting."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_EXIT_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "launcher-exit.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);
await runtime.reportManagedLauncherExit(payload);
process.exit(0);
""".strip()


def run_runtime(payload: dict[str, Any]) -> None:
    """Execute the launcher-exit helper through Node."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(LAUNCHER_EXIT_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node launcher-exit helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def create_bridge(tmp_path: Path) -> Path:
    """Create a minimal bridge directory with launch metadata."""
    bridge_dir = tmp_path / "bridge"
    (bridge_dir / "child").mkdir(parents=True)
    (bridge_dir / "parent").mkdir(parents=True)
    (bridge_dir / ".signals").mkdir(parents=True)
    (bridge_dir / "reports").mkdir(parents=True)
    (bridge_dir / "bridge.json").write_text(
        json.dumps(
            {
                "protocolVersion": 1,
                "launchId": "launch-123",
                "bridgeDir": str(bridge_dir),
                "createdAt": "2026-04-13T18:00:00Z",
                "agentId": "stage-child",
                "sessionName": "pi-stage-child",
                "cwd": "/repo",
                "model": "openai-codex/gpt-5.3-codex",
                "promptPreview": "Run review",
                "parentAgentId": "parent",
                "rootAgentId": "parent",
                "rootOwnerSessionKey": "session-root",
                "parentSessionKey": "session-parent",
                "notificationMode": "notify-and-follow-up",
                "stateRoot": "/repo/tmp/pimux",
                "extensionPath": "/repo/.pi/extensions/pimux/index.ts",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return bridge_dir


def read_events(bridge_dir: Path) -> list[dict[str, Any]]:
    """Read bridge events from ndjson."""
    events_path = bridge_dir / "events.ndjson"
    assert events_path.exists()
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_nonzero_launcher_exit_synthesizes_failure_report_and_exited_event(tmp_path: Path) -> None:
    """A startup failure should reach the parent as failure + exited evidence."""
    bridge_dir = create_bridge(tmp_path)
    log_path = bridge_dir / "child" / "pi.log"
    log_path.write_text("Error: Tool 'pimux' conflicts with another loaded extension.\n", encoding="utf-8")

    run_runtime({"bridgeDir": str(bridge_dir), "exitStatus": 1, "logPath": str(log_path)})

    events = read_events(bridge_dir)
    assert [event["type"] for event in events] == ["failure", "exited"]
    failure_event = events[0]
    assert failure_event["direction"] == "child_to_parent"
    assert failure_event["summary"] == "stage-child exited before terminal handoff (status 1)"
    report_path = Path(failure_event["reportPath"])
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "## Managed child launcher failure" in report_text
    assert "- Exit Status: 1" in report_text
    assert "conflicts with another loaded extension" in report_text



def test_zero_exit_without_terminal_report_synthesizes_exited_only(tmp_path: Path) -> None:
    """A quiet exit without terminal report should still create exited evidence for protocol violation handling."""
    bridge_dir = create_bridge(tmp_path)

    run_runtime({"bridgeDir": str(bridge_dir), "exitStatus": 0})

    events = read_events(bridge_dir)
    assert len(events) == 1
    assert events[0]["direction"] == "system"
    assert events[0]["type"] == "exited"
    assert events[0]["summary"] == "stage-child exited before managed terminal settlement was finalized"
