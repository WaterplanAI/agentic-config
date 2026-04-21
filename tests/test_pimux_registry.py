#!/usr/bin/env python3
"""Pure helper checks for pimux session scoping and tree metadata."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "registry.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);

if (payload.action === "scope") {
  process.stdout.write(JSON.stringify(runtime.filterStatusesByScope(payload.statuses, payload.scope, payload.options)));
  process.exit(0);
}

if (payload.action === "tree") {
  process.stdout.write(JSON.stringify({
    nodes: runtime.buildTreeNodes(payload.statuses),
    lines: runtime.buildTreeLines(runtime.buildTreeNodes(payload.statuses)),
  }));
  process.exit(0);
}

if (payload.action === "summary") {
  process.stdout.write(JSON.stringify(runtime.formatAgentSummary(payload.status)));
  process.exit(0);
}

if (payload.action === "dashboard") {
  process.stdout.write(JSON.stringify(runtime.dashboardLines(payload.statuses)));
  process.exit(0);
}

if (payload.action === "details") {
  process.stdout.write(JSON.stringify(runtime.formatAgentDetails(payload.status)));
  process.exit(0);
}

if (payload.action === "closeout-blockers") {
  process.stdout.write(JSON.stringify(runtime.findBlockingDirectChildrenForCloseout(payload.statuses, payload.agentId)));
  process.exit(0);
}

if (payload.action === "terminal-kind-suggestion") {
  process.stdout.write(JSON.stringify(runtime.suggestSupervisorTerminalReportKind(payload.statuses, payload.agentId) ?? null));
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
    root_agent_id: str,
    root_owner_session_key: str,
    parent_agent_id: str | None = None,
    effective_status: str = "running",
    bridge_state: str = "running",
    created_at: str = "2026-04-12T10:00:00Z",
    role: str | None = None,
    goal: str | None = None,
    visual_mode: str = "headless",
) -> dict[str, Any]:
    """Build a synthetic resolved-status payload."""
    record: dict[str, Any] = {
        "agentId": agent_id,
        "sessionName": f"pi-{agent_id}",
        "cwd": "/repo",
        "model": "openai-codex/gpt-5.3-codex",
        "promptPreview": goal or agent_id,
        "rootAgentId": root_agent_id,
        "rootOwnerSessionKey": root_owner_session_key,
        "status": "running",
        "visualMode": visual_mode,
        "createdAt": created_at,
        "updatedAt": created_at,
        "openCount": 0,
        "runDir": f"/tmp/pimux/agents/{agent_id}",
        "launcherPath": f"/tmp/pimux/agents/{agent_id}/launch.sh",
        "promptPath": f"/tmp/pimux/agents/{agent_id}/prompt.txt",
        "manifestPath": f"/tmp/pimux/agents/{agent_id}/agent.json",
        "launchPacketPath": f"/tmp/pimux/agents/{agent_id}/launch.md",
    }
    if parent_agent_id is not None:
        record["parentAgentId"] = parent_agent_id
    if role is not None:
        record["role"] = role
    if goal is not None:
        record["goal"] = goal
    return {
        "record": record,
        "hasSession": effective_status == "running",
        "effectiveStatus": effective_status,
        "bridgeSettlementState": bridge_state,
    }


def test_session_scope_filters_to_current_session_hierarchy() -> None:
    """Session scope should keep only the current hierarchy roots and descendants."""
    statuses = [
        status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
        status("child-a", root_agent_id="root-a", root_owner_session_key="session-a", parent_agent_id="root-a"),
        status("root-b", root_agent_id="root-b", root_owner_session_key="session-b"),
    ]
    result = run_runtime(
        {
            "action": "scope",
            "statuses": statuses,
            "scope": "session",
            "options": {
                "ownerSessionKey": "session-a",
                "sessionRootAgentIds": ["root-a"],
            },
        }
    )
    assert [item["record"]["agentId"] for item in result] == ["root-a", "child-a"]


def test_tree_nodes_include_parent_child_metadata() -> None:
    """Tree helpers should preserve structured node metadata for navigation."""
    statuses = [
        status(
            "root-a",
            root_agent_id="root-a",
            root_owner_session_key="session-a",
            role="orchestrator",
            goal="Coordinate UX improvements",
        ),
        status(
            "child-a",
            root_agent_id="root-a",
            root_owner_session_key="session-a",
            parent_agent_id="root-a",
            role="worker",
            goal="Improve tree output",
        ),
    ]
    result = run_runtime({"action": "tree", "statuses": statuses})
    assert result["lines"][0].startswith("root-a | orchestrator · Coordinate UX improvements | [LIVE] | [ROOT]")
    assert result["lines"][1].startswith("└─ child-a | worker · Improve tree output | [LIVE]")
    assert len(result["nodes"]) == 1
    root = result["nodes"][0]
    assert root["agentId"] == "root-a"
    assert root["displayLabel"] == "orchestrator · Coordinate UX improvements"
    assert root["children"][0]["agentId"] == "child-a"
    assert root["children"][0]["parentAgentId"] == "root-a"
    assert root["children"][0]["depth"] == 1


def test_agent_summary_keeps_agent_id_visible_and_adds_selection_context() -> None:
    """Summary lines should stay targetable while surfacing role, goal, state, and session."""
    result = run_runtime(
        {
            "action": "summary",
            "status": status(
                "worker-tree-ux",
                root_agent_id="root-a",
                root_owner_session_key="session-a",
                role="worker",
                goal="Improve hierarchy output",
                visual_mode="iterm-opened",
            ),
        }
    )
    assert result.startswith("worker-tree-ux | worker · Improve hierarchy output")
    assert "[LIVE]" in result
    assert "[OPEN]" in result
    assert "session=pi-worker-tree-ux" in result


def test_dashboard_lines_include_agent_counts_and_settlement_totals() -> None:
    """Dashboard header should summarize live, open, and settled agents at a glance."""
    result = run_runtime(
        {
            "action": "dashboard",
            "statuses": [
                status(
                    "root-a",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    visual_mode="iterm-opened",
                ),
                status(
                    "child-a",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    parent_agent_id="root-a",
                    effective_status="missing",
                    bridge_state="settled_completion",
                ),
            ],
        }
    )
    assert result[0] == "pimux | 2 agents | live=1 | open=1 | settled=1"



def test_closeout_blockers_require_direct_children_to_reach_settled_completion() -> None:
    """Direct children that are not settled_completion should block parent closeout."""
    statuses = [
        status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
        status(
            "child-ok",
            root_agent_id="root-a",
            root_owner_session_key="session-a",
            parent_agent_id="root-a",
            effective_status="missing",
            bridge_state="settled_completion",
        ),
        status(
            "child-blocking",
            root_agent_id="root-a",
            root_owner_session_key="session-a",
            parent_agent_id="root-a",
            bridge_state="running",
        ),
    ]
    result = run_runtime({"action": "closeout-blockers", "statuses": statuses, "agentId": "root-a"})
    assert [item["record"]["agentId"] for item in result] == ["child-blocking"]



def test_supervisor_terminal_kind_guidance_matches_direct_child_outcomes() -> None:
    """Supervisors should get a deterministic non-success terminal suggestion when children settle non-successfully."""
    waiting = run_runtime(
        {
            "action": "terminal-kind-suggestion",
            "agentId": "root-a",
            "statuses": [
                status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
                status(
                    "child-question",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    parent_agent_id="root-a",
                    effective_status="missing",
                    bridge_state="settled_waiting_on_parent",
                ),
            ],
        }
    )
    blocked = run_runtime(
        {
            "action": "terminal-kind-suggestion",
            "agentId": "root-a",
            "statuses": [
                status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
                status(
                    "child-blocked",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    parent_agent_id="root-a",
                    effective_status="missing",
                    bridge_state="settled_blocked",
                ),
            ],
        }
    )
    failed = run_runtime(
        {
            "action": "terminal-kind-suggestion",
            "agentId": "root-a",
            "statuses": [
                status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
                status(
                    "child-broken",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    parent_agent_id="root-a",
                    effective_status="terminated",
                    bridge_state="protocol_violation",
                ),
            ],
        }
    )
    unsettled = run_runtime(
        {
            "action": "terminal-kind-suggestion",
            "agentId": "root-a",
            "statuses": [
                status("root-a", root_agent_id="root-a", root_owner_session_key="session-a"),
                status(
                    "child-running",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    parent_agent_id="root-a",
                    bridge_state="running",
                ),
            ],
        }
    )

    assert waiting == "question"
    assert blocked == "blocker"
    assert failed == "failure"
    assert unsettled is None



def test_agent_details_include_recent_bridge_events_when_available() -> None:
    """Status details should expose recent bridge activity without requiring capture polling."""
    result = run_runtime(
        {
            "action": "details",
            "status": {
                **status(
                    "worker-tree-ux",
                    root_agent_id="root-a",
                    root_owner_session_key="session-a",
                    effective_status="missing",
                    bridge_state="settled_completion",
                ),
                "recentBridgeEvents": [
                    "2026-04-13T14:00:00Z | instruction | planner -> worker-tree-ux | down:worker-tree-ux",
                    "2026-04-13T14:00:01Z | closeout | worker-tree-ux -> planner | done:down:worker-tree-ux",
                ],
            },
        }
    )
    assert "recentBridgeEvents:" in result
    assert any("instruction | planner -> worker-tree-ux | down:worker-tree-ux" in line for line in result)
    assert any("closeout | worker-tree-ux -> planner | done:down:worker-tree-ux" in line for line in result)
