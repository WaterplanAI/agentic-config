#!/usr/bin/env python3
"""Behavior checks for pimux bridge authority."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTHORITY_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "authority.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);

if (payload.action === "bind") {
  process.stdout.write(JSON.stringify(runtime.bindBridgeAuthoritativeSession(payload.current)));
  process.exit(0);
}

if (payload.action === "evaluate") {
  process.stdout.write(JSON.stringify(runtime.evaluateBridgeAuthority(payload.binding, payload.current)));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the authority helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(AUTHORITY_RUNTIME),
            json.dumps(payload),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node authority helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return parsed


def session_identity(
    *,
    session_key: str = "session-key-1",
    session_file: str | None = "/tmp/child-session.json",
    leaf_id: str | None = "leaf-1",
    process_id: int = 101,
) -> dict[str, Any]:
    """Build a synthetic runtime session identity payload."""
    payload: dict[str, Any] = {
        "sessionKey": session_key,
        "processId": process_id,
    }
    if session_file is not None:
        payload["sessionFile"] = session_file
    if leaf_id is not None:
        payload["leafId"] = leaf_id
    return payload


def test_binding_captures_authoritative_child_identity() -> None:
    """The first direct child binding should preserve its session identity."""
    identity = session_identity()
    result = run_runtime({"action": "bind", "current": identity})
    assert result == {
        "authoritativeSessionKey": "session-key-1",
        "authoritativeSessionFile": "/tmp/child-session.json",
        "authoritativeLeafId": "leaf-1",
        "authoritativeProcessId": 101,
    }


def test_unbound_bridge_is_not_authoritative() -> None:
    """An unbound bridge should fail closed until the direct child claims it."""
    result = run_runtime({"action": "evaluate", "binding": {}, "current": session_identity()})
    assert result == {
        "isAuthoritative": False,
        "reason": "No authoritative pimux child session has been bound to this bridge yet.",
    }


def test_exact_bound_child_is_authoritative() -> None:
    """The bound direct child identity should evaluate as authoritative."""
    identity = session_identity()
    binding = run_runtime({"action": "bind", "current": identity})
    result = run_runtime({"action": "evaluate", "binding": binding, "current": identity})
    assert result == {"isAuthoritative": True}


def test_same_session_file_remains_authoritative_after_leaf_change() -> None:
    """A real child session may advance to a new leaf without losing bridge authority."""
    binding = run_runtime({"action": "bind", "current": session_identity(leaf_id="leaf-1", process_id=111)})
    advanced_turn = session_identity(leaf_id="leaf-2", process_id=111)
    result = run_runtime({"action": "evaluate", "binding": binding, "current": advanced_turn})
    assert result == {"isAuthoritative": True}


def test_nested_helper_is_rejected_when_session_file_differs() -> None:
    """A nested helper with another session file must be rejected even if it reuses the bridge env."""
    binding = run_runtime({"action": "bind", "current": session_identity(leaf_id="head-leaf", process_id=111)})
    nested_helper = session_identity(session_file="/tmp/helper-session.json", leaf_id="scout-leaf", process_id=222)
    result = run_runtime({"action": "evaluate", "binding": binding, "current": nested_helper})
    assert result == {
        "isAuthoritative": False,
        "reason": "Bridge is bound to session file /tmp/child-session.json, current session file is /tmp/helper-session.json.",
    }


def test_process_id_is_used_as_fallback_when_leaf_is_missing() -> None:
    """Without leaf identity, a different nested process should still be rejected."""
    bound_without_leaf = run_runtime(
        {
            "action": "bind",
            "current": session_identity(session_file=None, leaf_id=None, process_id=501),
        }
    )
    nested_helper = session_identity(session_file=None, leaf_id=None, process_id=777)
    result = run_runtime({"action": "evaluate", "binding": bound_without_leaf, "current": nested_helper})
    assert result == {
        "isAuthoritative": False,
        "reason": "Bridge is bound to process id 501, current process id is 777.",
    }
