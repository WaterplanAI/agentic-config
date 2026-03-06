#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Pretooluse hook for Claude Code that blocks git commit --no-verify.

Prevents bypassing pre-commit hooks (PII compliance, etc.) via --no-verify or -n flags.
Fail-closed principle: block operations if hook encounters errors.
"""

import json
import re
import sys
from typing import TypedDict


class ToolInput(TypedDict, total=False):
    """Tool parameters from Claude Code."""
    command: str


class HookInput(TypedDict):
    """JSON input received via stdin."""
    tool_name: str
    tool_input: ToolInput


class HookSpecificOutput(TypedDict, total=False):
    """Inner hook output structure."""
    hookEventName: str
    permissionDecision: str  # "allow" | "deny"
    permissionDecisionReason: str


class HookOutput(TypedDict):
    """JSON output returned via stdout."""
    hookSpecificOutput: HookSpecificOutput


# Patterns that bypass pre-commit hooks
NO_VERIFY_PATTERNS = [
    r"\bgit\s+commit\b.*--no-verify",
    r"\bgit\s+commit\b.*\s-n\b",         # Short flag (not -nm for message)
    r"\bgit\s+commit\b.*\s-[a-mo-z]*n",  # Combined short flags with -n
    r"\bgit\s+push\b.*--no-verify",
    r"\bgit\s+merge\b.*--no-verify",
    r"\bgit\s+rebase\b.*--no-verify",
    r"\bgit\s+cherry-pick\b.*--no-verify",
]


def is_no_verify_command(command: str) -> tuple[bool, str | None]:
    """
    Check if command attempts to bypass git hooks.

    Returns:
        (is_no_verify, matched_pattern): Tuple of detection result and pattern matched
    """
    for pattern in NO_VERIFY_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, pattern
    return False, None


def should_block_tool(tool_name: str, tool_input: ToolInput) -> tuple[bool, str | None]:
    """
    Determine if tool should be blocked.

    Returns:
        (should_block, message): Tuple of block decision and optional message
    """
    # Only inspect Bash commands
    if tool_name != "Bash":
        return False, None

    command = tool_input.get("command", "")
    is_bypass, _ = is_no_verify_command(command)

    if is_bypass:
        return True, (
            "Blocked: --no-verify bypasses pre-commit PII compliance hook. "
            "Remove --no-verify flag to proceed."
        )

    return False, None


def main() -> None:
    """Main hook execution."""
    try:
        # Read input from stdin
        input_data: HookInput = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Determine if should block
        should_block, message = should_block_tool(tool_name, tool_input)

        # Return decision in Claude Code hook format
        hook_output: HookSpecificOutput = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if should_block else "allow",
        }
        if message:
            hook_output["permissionDecisionReason"] = message

        output: HookOutput = {"hookSpecificOutput": hook_output}
        print(json.dumps(output))

    except Exception as e:
        # Fail-closed: if hook crashes, block the operation
        output: HookOutput = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Hook error (fail-closed): {e}",
            }
        }
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
