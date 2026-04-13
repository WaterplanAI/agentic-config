#!/usr/bin/env python3
"""Rendering checks for pimux parent-facing bridge messages."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENDER_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "render.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);

if (payload.action === "render") {
  const content = await runtime.buildParentDeliveryContent(payload.event, payload.launch, payload.options);
  process.stdout.write(content);
  process.exit(0);
}

if (payload.action === "child-message") {
  process.stdout.write(runtime.buildChildMessageContent(payload.event));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_render(payload: dict[str, Any]) -> str:
    """Execute the render helper through Node and return the rendered content."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(RENDER_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node render helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return result.stdout


def test_parent_delivery_content_shows_bridge_route_for_outbound_messages() -> None:
    """Outbound messages should render a compact, directional bridge summary."""
    content = run_render(
        {
            "action": "render",
            "event": {
                "direction": "parent_to_child",
                "type": "instruction",
                "from": {"agentId": "planner"},
                "to": {"agentId": "worker"},
                "summary": "Inspect render.ts",
                "message": "Inspect render.ts and report the user-visible message flow.",
            },
            "launch": {
                "agentId": "worker",
                "promptPreview": "Fix the message UI",
                "goal": "Fix the message UI",
                "parentAgentId": "planner",
            },
        }
    )

    assert content.startswith("[pimux instruction] planner -> worker")
    assert "Goal: Fix the message UI" in content
    assert "Route: planner -> worker" in content
    assert "Summary: Inspect render.ts" in content
    assert "Message: Inspect render.ts and report the user-visible message flow." in content


def test_child_delivery_content_preserves_exact_parent_payload() -> None:
    """Child-side delivery should expose the raw parent payload without wrapper text."""
    content = run_render(
        {
            "action": "child-message",
            "event": {
                "direction": "parent_to_child",
                "type": "instruction",
                "from": {"agentId": "planner"},
                "to": {"agentId": "worker"},
                "summary": "Inspect render.ts",
                "message": "down:nested-test:l2a1",
            },
        }
    )

    assert content == "down:nested-test:l2a1"
