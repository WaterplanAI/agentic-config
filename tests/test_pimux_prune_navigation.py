#!/usr/bin/env python3
"""Behavior and surface checks for pimux prune and interactive navigation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_PACKAGE_DIR = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux"
REGISTRY_RUNTIME = PIMUX_PACKAGE_DIR / "registry.ts"
PIMUX_INDEX = PIMUX_PACKAGE_DIR / "index.ts"
PIMUX_SCHEMA = PIMUX_PACKAGE_DIR / "schema.ts"
PIMUX_COMMANDS = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "references" / "commands.md"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);

if (payload.action === "flatten") {
  const nodes = runtime.buildTreeNodes(payload.statuses);
  process.stdout.write(JSON.stringify(runtime.flattenTreeNodes(nodes)));
  process.exit(0);
}

if (payload.action === "prune-helper") {
  process.stdout.write(JSON.stringify({
    thresholdMs: runtime.parseAgeThresholdMs(payload.olderThan, payload.fallback),
    candidates: payload.statuses.filter((status) => runtime.shouldPruneStatus(status, payload.mode)).map((status) => status.record.agentId),
    labels: payload.statuses.map((status) => runtime.formatPruneCandidate(status)),
  }));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any]) -> Any:
    """Execute the registry helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(REGISTRY_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node registry helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def status(
    agent_id: str,
    *,
    root_agent_id: str = "root-a",
    root_owner_session_key: str = "session-a",
    record_status: str = "running",
    effective_status: str = "running",
    bridge_state: str = "running",
    parent_agent_id: str | None = None,
    updated_at: str = "2026-04-10T10:00:00Z",
    terminated_at: str | None = None,
) -> dict[str, Any]:
    """Build a synthetic resolved-status payload."""
    record: dict[str, Any] = {
        "agentId": agent_id,
        "sessionName": f"pi-{agent_id}",
        "cwd": "/repo",
        "model": "openai-codex/gpt-5.3-codex",
        "promptPreview": agent_id,
        "rootAgentId": root_agent_id,
        "rootOwnerSessionKey": root_owner_session_key,
        "status": record_status,
        "visualMode": "headless",
        "createdAt": updated_at,
        "updatedAt": updated_at,
        "openCount": 0,
        "runDir": f"/tmp/pimux/agents/{agent_id}",
        "launcherPath": f"/tmp/pimux/agents/{agent_id}/launch.sh",
        "promptPath": f"/tmp/pimux/agents/{agent_id}/prompt.txt",
        "manifestPath": f"/tmp/pimux/agents/{agent_id}/agent.json",
        "launchPacketPath": f"/tmp/pimux/agents/{agent_id}/launch.md",
    }
    if parent_agent_id is not None:
        record["parentAgentId"] = parent_agent_id
    if terminated_at is not None:
        record["terminatedAt"] = terminated_at
    return {
        "record": record,
        "hasSession": effective_status == "running",
        "effectiveStatus": effective_status,
        "bridgeSettlementState": bridge_state,
    }


def test_flatten_tree_nodes_produces_navigation_labels() -> None:
    """Flattened tree nodes should preserve hierarchy shape for navigation."""
    statuses = [
        status("root-a"),
        status("child-a", parent_agent_id="root-a"),
        status("grandchild-a", parent_agent_id="child-a"),
        status("child-b", parent_agent_id="root-a"),
    ]
    result = run_runtime({"action": "flatten", "statuses": statuses})
    assert [entry["node"]["agentId"] for entry in result] == ["root-a", "child-a", "grandchild-a", "child-b"]
    assert result[0]["label"].startswith("root-a")
    assert "[ROOT]" in result[0]["label"]
    assert result[1]["label"].startswith("├─ child-a")
    assert result[2]["label"].startswith("│  └─ grandchild-a")
    assert result[3]["label"].startswith("└─ child-b")


def test_manual_prune_mode_includes_exited_missing_and_terminated() -> None:
    """Manual prune should consider exited, missing, and terminated entries."""
    statuses = [
        status("running", record_status="running", effective_status="running"),
        status("exited", record_status="exited", effective_status="exited"),
        status("terminated", record_status="terminated", effective_status="terminated", terminated_at="2026-04-10T12:00:00Z"),
        status("missing", record_status="running", effective_status="missing"),
    ]
    result = run_runtime({"action": "prune-helper", "olderThan": "1d", "mode": "manual", "statuses": statuses})
    assert result["thresholdMs"] == 86_400_000
    assert result["candidates"] == ["exited", "terminated", "missing"]
    assert any(label.startswith("terminated | recorded=terminated") for label in result["labels"])


def test_auto_prune_mode_excludes_exited_but_includes_terminated_and_missing() -> None:
    """Auto-prune should only target terminated or missing entries."""
    statuses = [
        status("exited", record_status="exited", effective_status="exited"),
        status("terminated", record_status="terminated", effective_status="terminated", terminated_at="2026-04-10T12:00:00Z"),
        status("missing", record_status="running", effective_status="missing"),
    ]
    result = run_runtime({"action": "prune-helper", "olderThan": "1d", "mode": "auto", "statuses": statuses})
    assert result["candidates"] == ["terminated", "missing"]


def test_navigation_and_prune_surfaces_are_wired_in_extension_and_docs() -> None:
    """The extension and docs should expose navigate/prune plus 1d auto-prune."""
    index_text = PIMUX_INDEX.read_text()
    schema_text = PIMUX_SCHEMA.read_text()
    commands_text = PIMUX_COMMANDS.read_text()

    assert '"navigate"' in index_text
    assert 'case "navigate":' in index_text
    assert 'case "prune":' in index_text
    assert 'olderThan: "1d"' in index_text
    assert 'mode: "auto"' in index_text

    assert '"prune"' in schema_text

    assert '- `navigate`' in commands_text
    assert '- `prune`' in commands_text
    assert '- `smoke-nested`' in commands_text
    assert 'Auto-prune removes `terminated` or `missing` pimux registry entries aged at least `1d`.' in commands_text
    assert '/pimux smoke-nested' in commands_text
