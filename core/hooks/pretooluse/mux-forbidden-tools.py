#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Pretooluse hook that enforces MUX delegation protocol.

ENFORCEMENT LAYERS:
1. Session init gate - Block all tools if MUX skill detected but session not initialized
2. Forbidden tools - Block Read/Write/Edit/Grep/Glob/etc (must delegate)
3. Bash whitelist - Only allow mkdir -p, uv run tools/*, uv run .claude/skills/mux/tools/*
4. User approval - Require confirmation for all allowed tools (askFirst)

Session-scoped via mux-active marker file.
Fail-closed: deny operations if hook encounters errors.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Tools that MUST be delegated via Task()
FORBIDDEN_TOOLS = {
    "Read", "Write", "Edit", "Grep", "Glob",
    "WebSearch", "WebFetch", "NotebookEdit",
    "TaskOutput",  # Never block on agent completion
}

# Tools that are always allowed (core MUX operations)
ALWAYS_ALLOWED_TOOLS = {
    "Task",  # Delegation is the whole point
    "AskUserQuestion",  # User interaction
    "mcp__voicemode__converse",  # Voice updates
    "TaskCreate", "TaskUpdate", "TaskList",  # Task tracking
}

# Bash commands whitelist (regex patterns)
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",  # Create directories
    r"^uv\s+run\s+.*tools/",  # MUX tools
    r"^uv\s+run\s+\.claude/skills/mux/tools/",  # MUX skill tools
]


def find_agentic_root() -> Path:
    """Find agentic-config installation root or project root."""
    current = Path.cwd()
    for _ in range(10):
        if (current / "VERSION").exists() and (current / "core").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


def find_claude_pid() -> int | None:
    """Trace up process tree to find claude process PID."""
    try:
        pid = os.getpid()
        for _ in range(10):
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                capture_output=True, text=True
            )
            line = result.stdout.strip()
            if not line:
                break
            parts = line.split()
            if len(parts) >= 3:
                current_pid, ppid, comm = int(parts[0]), int(parts[1]), parts[2]
                if "claude" in comm.lower():
                    return current_pid
                pid = ppid
            else:
                break
    except Exception:
        pass
    return None


def is_mux_active() -> bool:
    """Check if MUX skill is active for current Claude session."""
    claude_pid = find_claude_pid()
    if not claude_pid:
        return False
    agentic_root = find_agentic_root()
    marker = agentic_root / f"outputs/session/{claude_pid}/mux-active"
    return marker.exists()


def is_bash_command_allowed(command: str) -> tuple[bool, str]:
    """Check if Bash command matches whitelist.

    Returns (allowed, reason).
    """
    command = command.strip()

    # Check against whitelist patterns
    for pattern in BASH_WHITELIST_PATTERNS:
        if re.match(pattern, command):
            return True, f"Matches whitelist: {pattern}"

    return False, f"Command not in MUX whitelist. Allowed: mkdir -p, uv run tools/*"


def make_decision(decision: str, reason: str = "") -> dict:
    """Create hook output with decision."""
    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if reason:
        output["hookSpecificOutput"]["permissionDecisionReason"] = reason
    return output


def main() -> None:
    """Main hook execution."""
    try:
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Only enforce when MUX is active (marker exists)
        if not is_mux_active():
            print(json.dumps(make_decision("allow")))
            return

        # === LAYER 1: Forbidden tools - BLOCK ===
        if tool_name in FORBIDDEN_TOOLS:
            print(json.dumps(make_decision(
                "deny",
                f"🚫 MUX VIOLATION: {tool_name} is FORBIDDEN. Delegate via Task(run_in_background=True)."
            )))
            return

        # === LAYER 2: Always allowed tools - ASK FIRST (adds friction) ===
        if tool_name in ALWAYS_ALLOWED_TOOLS:
            print(json.dumps(make_decision(
                "askFirst",
                f"🔒 MUX MODE: Confirm {tool_name} usage. Did you output the preamble ritual?"
            )))
            return

        # === LAYER 3: Bash whitelist validation ===
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            allowed, reason = is_bash_command_allowed(command)
            if allowed:
                print(json.dumps(make_decision(
                    "askFirst",
                    f"🔒 MUX MODE: Confirm Bash command. {reason}"
                )))
            else:
                print(json.dumps(make_decision(
                    "deny",
                    f"🚫 MUX VIOLATION: {reason}"
                )))
            return

        # === LAYER 4: Unknown tools - ASK FIRST (safety) ===
        print(json.dumps(make_decision(
            "askFirst",
            f"🔒 MUX MODE: {tool_name} requires approval. Is this a valid MUX action?"
        )))

    except Exception as e:
        # Fail-closed: block on error to enforce MUX compliance
        print(json.dumps(make_decision(
            "deny",
            f"🚫 MUX hook error (fail-closed): {e}"
        )))
        sys.exit(0)


if __name__ == "__main__":
    main()
