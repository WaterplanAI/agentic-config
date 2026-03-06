#!/usr/bin/env python3
"""Unit tests for MUX skill-scoped hook scripts."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MUX_ORCHESTRATOR_HOOK = (
    PROJECT_ROOT
    / "plugins"
    / "ac-workflow"
    / "skills"
    / "mux"
    / "hooks"
    / "mux-orchestrator-guard.py"
)
MUX_SUBAGENT_HOOK = (
    PROJECT_ROOT
    / "plugins"
    / "ac-workflow"
    / "skills"
    / "mux-subagent"
    / "hooks"
    / "mux-subagent-guard.py"
)


def _load_module(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MUX_GUARD = _load_module(MUX_ORCHESTRATOR_HOOK, "mux_orchestrator_guard")
MUX_SUBAGENT_GUARD = _load_module(MUX_SUBAGENT_HOOK, "mux_subagent_guard")


def _run_main(
    module: ModuleType,
    payload: dict[str, Any] | None = None,
    *,
    raw_stdin: str | None = None,
) -> dict[str, Any]:
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(payload or {})

    original_stdin = sys.stdin
    original_stdout = sys.stdout
    output_buffer = io.StringIO()
    sys.stdin = io.StringIO(stdin_text)
    sys.stdout = output_buffer

    try:
        module.main()
    except SystemExit:
        # Hook scripts explicitly call sys.exit(0) in some error paths.
        pass
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout

    output = output_buffer.getvalue().strip()
    first_line = output.splitlines()[0]
    return json.loads(first_line)


def _decision(output: dict[str, Any]) -> str:
    return output["hookSpecificOutput"]["permissionDecision"]


def test_mux_read_allowlist_matches_runtime_paths() -> None:
    allowed_paths = [
        "plugins/ac-workflow/skills/mux/SKILL.md",
        "/Users/example/.claude/plugins/cache/ac-workflow/skills/mux-subagent/SKILL.md",
        "${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/researcher.md",
        "tmp/mux/20260304-1200-topic/.signals/research.done",
    ]

    for path in allowed_paths:
        assert MUX_GUARD.is_read_allowed(path), f"Expected allowlist match: {path}"


def test_mux_read_allowlist_denies_unrelated_paths() -> None:
    assert not MUX_GUARD.is_read_allowed("README.md")
    assert not MUX_GUARD.is_read_allowed("plugins/ac-workflow/scripts/spec-resolver.sh")


def test_mux_search_allowlist_matrix() -> None:
    assert MUX_GUARD.is_search_allowed({"path": "skills/mux"})
    assert MUX_GUARD.is_search_allowed({"path": "${CLAUDE_PLUGIN_ROOT}/skills"})
    assert not MUX_GUARD.is_search_allowed({"path": "docs"})


def test_mux_bash_whitelist_matrix() -> None:
    allowed, _ = MUX_GUARD.is_bash_allowed("mkdir -p tmp/mux/test")
    assert allowed

    allowed, _ = MUX_GUARD.is_bash_allowed(
        "uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py tmp/mux/test/.signals"
    )
    assert allowed

    allowed, _ = MUX_GUARD.is_bash_allowed("git status")
    assert not allowed


def test_mux_orchestrator_denies_read_outside_allowlist() -> None:
    output = _run_main(
        MUX_GUARD,
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
        },
    )
    assert _decision(output) == "deny"


def test_mux_orchestrator_task_background_validation() -> None:
    allowed = _run_main(
        MUX_GUARD,
        {"tool_name": "Task", "tool_input": {"run_in_background": True}},
    )
    assert _decision(allowed) == "allow"

    denied = _run_main(
        MUX_GUARD,
        {"tool_name": "Task", "tool_input": {"run_in_background": False}},
    )
    assert _decision(denied) == "deny"


def test_mux_orchestrator_allows_mux_ospec_skill() -> None:
    output = _run_main(
        MUX_GUARD,
        {
            "tool_name": "Skill",
            "tool_input": {
                "skill": "mux-ospec",
                "args": "lean specs/2026/03/main/001-example.md",
            },
        },
    )
    assert _decision(output) == "allow"


def test_mux_orchestrator_denies_non_allowlisted_skill() -> None:
    output = _run_main(
        MUX_GUARD,
        {
            "tool_name": "Skill",
            "tool_input": {
                "skill": "spec",
                "args": "PLAN specs/2026/03/main/001-example.md",
            },
        },
    )
    assert _decision(output) == "deny"
    assert "Only Skill(skill=\"mux-ospec\") is allowed" in output[
        "hookSpecificOutput"
    ]["permissionDecisionReason"]


def test_mux_orchestrator_fail_closed_on_invalid_json() -> None:
    output = _run_main(MUX_GUARD, raw_stdin="{invalid-json")
    assert _decision(output) == "deny"
    assert "fail-closed" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_mux_subagent_denies_taskoutput() -> None:
    output = _run_main(
        MUX_SUBAGENT_GUARD,
        {"tool_name": "TaskOutput", "tool_input": {}},
    )
    assert _decision(output) == "deny"


def test_mux_subagent_allows_non_forbidden_tool() -> None:
    output = _run_main(
        MUX_SUBAGENT_GUARD,
        {"tool_name": "Read", "tool_input": {"file_path": "README.md"}},
    )
    assert _decision(output) == "allow"


def test_mux_subagent_fail_closed_on_invalid_json() -> None:
    output = _run_main(MUX_SUBAGENT_GUARD, raw_stdin="{invalid-json")
    assert _decision(output) == "deny"
    assert "fail-closed" in output["hookSpecificOutput"]["permissionDecisionReason"]
