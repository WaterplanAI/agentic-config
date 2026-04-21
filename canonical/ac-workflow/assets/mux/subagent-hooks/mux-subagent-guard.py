#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill-scoped PreToolUse hook for MUX subagents.

This hook ONLY fires when the mux-subagent skill is active (loaded via frontmatter).
It does NOT fire for the orchestrator -- that has its own hooks in mux.md.

ENFORCEMENT LAYERS:
1. TaskOutput - DENY (subagents must use signal files, not TaskOutput)
2. Everything else - ALLOW (subagents need full tool access including Skill to do their work)

Fail-closed: deny operations if hook encounters errors.
"""

import json
import sys
from typing import TypedDict


class ToolInput(TypedDict, total=False):
    """Tool parameters from Claude Code."""

    file_path: str
    command: str
    run_in_background: bool


class HookInput(TypedDict):
    """JSON input received via stdin."""

    tool_name: str
    tool_input: ToolInput


class HookSpecificOutput(TypedDict, total=False):
    """Inner hook output structure."""

    hookEventName: str
    permissionDecision: str  # "allow" | "deny" | "askFirst"
    permissionDecisionReason: str


class HookOutput(TypedDict):
    """JSON output returned via stdout."""

    hookSpecificOutput: HookSpecificOutput


# Tools that are always DENIED for subagents
FORBIDDEN_TOOLS = {
    "TaskOutput",
}

# Denial reasons per tool
DENIAL_REASONS: dict[str, str] = {
    "TaskOutput": (
        "MUX SUBAGENT VIOLATION: TaskOutput is FORBIDDEN. "
        "Write results to your report file, create a signal via signal.py, "
        "then return exactly: 0"
    ),
}


def make_decision(decision: str, reason: str = "") -> HookOutput:
    """Create hook output with decision."""
    hook_output: HookSpecificOutput = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
    }
    if reason:
        hook_output["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": hook_output}


def main() -> None:
    """Main hook execution."""
    try:
        input_data: HookInput = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")

        # === Forbidden tools - DENY ===
        if tool_name in FORBIDDEN_TOOLS:
            reason = DENIAL_REASONS.get(
                tool_name,
                f"MUX SUBAGENT VIOLATION: {tool_name} is FORBIDDEN for subagents.",
            )
            print(json.dumps(make_decision("deny", reason)))
            return

        # === Everything else - ALLOW ===
        # Subagents need Read, Write, Edit, Grep, Glob, Bash, WebSearch, WebFetch, etc.
        print(json.dumps(make_decision("allow")))

    except Exception as e:
        # Fail-closed: block on error
        print(json.dumps(make_decision(
            "deny",
            f"MUX subagent hook error (fail-closed): {e}"
        )))
        sys.exit(0)


if __name__ == "__main__":
    main()
