#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Pretooluse hook for Claude Code that blocks public GSuite asset creation.

Prevents creating publicly accessible Drive files/folders via --extra JSON overrides.
The GSuite CLI share command hardcodes type="user", so public access can only be
achieved via --extra JSON containing type="anyone" or similar patterns.

Fail-open principle: allow operations if hook encounters errors.
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


# Patterns that create public assets (via --extra JSON override)
PUBLIC_ASSET_PATTERNS = [
    # JSON patterns that make assets public
    r'"type"\s*:\s*"anyone"',       # Double-quoted JSON
    r"'type'\s*:\s*'anyone'",       # Single-quoted JSON
    r'"visibility"\s*:\s*"public"',
    r'"withLink"\s*:\s*true',       # JSON boolean
    r"'withLink'\s*:\s*True",       # Python boolean
]


def is_public_asset_command(command: str) -> tuple[bool, str | None]:
    """
    Check if command attempts to create a public GSuite asset.

    Returns:
        (is_public, matched_pattern): Tuple of detection result and pattern matched
    """
    for pattern in PUBLIC_ASSET_PATTERNS:
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
    is_public, _ = is_public_asset_command(command)

    if is_public:
        return True, (
            "Blocked: Creating public GSuite assets is not allowed. "
            "Share with specific users/groups instead of type='anyone' or withLink=true."
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
        # Fail-open: if hook crashes, allow the operation
        output: HookOutput = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }
        print(json.dumps(output))
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
