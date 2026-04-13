#!/usr/bin/env python3
"""Behavior checks for pimux settlement and parent-delivery decisions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTLEMENT_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "settlement.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);

if (payload.action === "evaluate") {
  process.stdout.write(JSON.stringify(runtime.evaluateBridgeSettlement(payload.events)));
  process.exit(0);
}

if (payload.action === "delivery") {
  process.stdout.write(JSON.stringify({
    deliver: runtime.shouldDeliverBridgeEventToParent(payload.event),
    trigger: runtime.shouldTriggerTurnForEvent(payload.event, payload.launch),
  }));
  process.exit(0);
}

if (payload.action === "settled-trigger") {
  process.stdout.write(JSON.stringify({
    trigger: runtime.shouldTriggerTurnForSettledState(payload.state, payload.launch),
  }));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the settlement helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(SETTLEMENT_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node settlement helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return parsed


def event(
    event_id: str,
    event_type: str,
    *,
    direction: str = "child_to_parent",
    requires_response: bool | None = None,
) -> dict[str, Any]:
    """Build a synthetic bridge event payload."""
    payload: dict[str, Any] = {
        "eventId": event_id,
        "direction": direction,
        "type": event_type,
    }
    if requires_response is not None:
        payload["requiresResponse"] = requires_response
    return payload


def test_settlement_waits_for_exit_even_when_closeout_exists() -> None:
    """A closeout declaration is non-terminal until the child exits."""
    result = run_runtime({"action": "evaluate", "events": [event("closeout-1", "closeout")]})
    assert result["settledState"] == "running"


def test_settlement_completes_only_after_closeout_and_exit() -> None:
    """Successful settlement should require closeout plus explicit exit evidence."""
    result = run_runtime(
        {
            "action": "evaluate",
            "events": [
                event("closeout-1", "closeout"),
                event("exited-1", "exited", direction="system"),
            ],
        }
    )
    assert result["settledState"] == "settled_completion"
    assert result["terminalEvent"]["eventId"] == "closeout-1"


def test_settlement_maps_declared_non_success_terminal_reports() -> None:
    """Declared non-success terminal reports should settle honestly after exit."""
    cases = [
        ("failure", "settled_failure"),
        ("blocker", "settled_blocked"),
        ("question", "settled_waiting_on_parent"),
    ]
    for terminal_type, expected_state in cases:
        result = run_runtime(
            {
                "action": "evaluate",
                "events": [
                    event("terminal-1", terminal_type),
                    event("exited-1", "exited", direction="system"),
                ],
            }
        )
        assert result["settledState"] == expected_state


def test_settlement_marks_undeclared_exit_as_protocol_violation() -> None:
    """Exit without a declared terminal report must not settle as success."""
    result = run_runtime({"action": "evaluate", "events": [event("exited-1", "exited", direction="system")]})
    assert result == {
        "settledState": "protocol_violation",
        "protocolViolationReason": "Child exited without a valid terminal declaration.",
    }


def test_settlement_flags_closeout_sequence_protocol_violations() -> None:
    """Multiple closeouts or post-closeout reports should be protocol violations."""
    multiple_closeouts = run_runtime(
        {
            "action": "evaluate",
            "events": [
                event("closeout-1", "closeout"),
                event("closeout-2", "closeout"),
                event("exited-1", "exited", direction="system"),
            ],
        }
    )
    assert multiple_closeouts["settledState"] == "protocol_violation"
    assert multiple_closeouts["protocolViolationReason"] == "Multiple closeout declarations were emitted."

    post_closeout_report = run_runtime(
        {
            "action": "evaluate",
            "events": [
                event("closeout-1", "closeout"),
                event("progress-1", "progress"),
                event("exited-1", "exited", direction="system"),
            ],
        }
    )
    assert post_closeout_report["settledState"] == "protocol_violation"
    assert post_closeout_report["protocolViolationReason"] == "Post-closeout child report detected: progress (progress-1)"


def test_delivery_keeps_progress_non_follow_up_by_default() -> None:
    """Progress remains visible but should not trigger follow-up unless requested."""
    default_progress = run_runtime(
        {
            "action": "delivery",
            "event": event("progress-1", "progress"),
            "launch": {"notificationMode": "notify-and-follow-up"},
        }
    )
    assert default_progress == {"deliver": True, "trigger": False}

    requested_progress = run_runtime(
        {
            "action": "delivery",
            "event": event("progress-2", "progress", requires_response=True),
            "launch": {"notificationMode": "notify-and-follow-up"},
        }
    )
    assert requested_progress == {"deliver": True, "trigger": True}



def test_parent_to_child_messages_are_visible_without_forcing_follow_up() -> None:
    """Outbound bridge messages should surface in the parent interface without triggering a new turn."""
    instruction = run_runtime(
        {
            "action": "delivery",
            "event": event("instruction-1", "instruction", direction="parent_to_child"),
            "launch": {"notificationMode": "notify-and-follow-up"},
        }
    )
    assert instruction == {"deliver": True, "trigger": False}

    launched = run_runtime(
        {
            "action": "delivery",
            "event": event("launched-1", "launched", direction="system"),
            "launch": {"notificationMode": "notify-and-follow-up"},
        }
    )
    assert launched == {"deliver": False, "trigger": False}


def test_direct_terminal_reports_are_suppressed_until_settlement() -> None:
    """Terminal child reports should be surfaced through settled-state delivery, not duplicated immediately."""
    for terminal_type in ("closeout", "failure", "blocker", "question"):
        decision = run_runtime(
            {
                "action": "delivery",
                "event": event(f"{terminal_type}-1", terminal_type),
                "launch": {"notificationMode": "notify-and-follow-up"},
            }
        )
        assert decision == {"deliver": False, "trigger": False}


def test_settled_completion_always_triggers_follow_up() -> None:
    """The only supported notification mode should follow up on settled completion."""
    decision = run_runtime(
        {
            "action": "settled-trigger",
            "state": "settled_completion",
            "launch": {"notificationMode": "notify-and-follow-up"},
        }
    )
    assert decision == {"trigger": True}
