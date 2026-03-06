#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill-scoped PreToolUse hook for MUX orchestrator.

This hook is attached via mux SKILL.md frontmatter (skill-scoped).
It enforces orchestrator-only delegation constraints.
Subagents have their own hook in mux-subagent/hooks/mux-subagent-guard.py.

ENFORCEMENT LAYERS:
1. Read - DENY with allowlist (skill files, signals, agent defs)
2. Write/Edit/NotebookEdit - DENY (delegate via Task)
3. Grep/Glob - DENY with allowlist (plugin skills/, .claude/hooks/)
4. WebSearch/WebFetch - DENY (delegate to researcher)
5. TaskOutput - DENY (use signals)
6. Skill - Allowlisted direct call (only mux-ospec), otherwise DENY
7. Bash - Whitelist (mkdir -p, uv run tools/*)
8. Task - Validate run_in_background=True

Fail-closed: deny operations if hook encounters errors.
"""

import json
import re
import sys
from typing import TypedDict


class ToolInput(TypedDict, total=False):
    """Tool parameters from Claude Code."""

    file_path: str
    command: str
    run_in_background: bool
    pattern: str
    path: str
    skill: str
    args: str


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


# Read allowlist: paths orchestrator may read
READ_ALLOWLIST_PATTERNS = [
    r"(?:^|/)\$\{CLAUDE_PLUGIN_ROOT\}/skills/mux(?:/|$)",  # Placeholder form
    r"(?:^|/)\$\{CLAUDE_PLUGIN_ROOT\}/skills/mux-subagent(?:/|$)",
    r"(?:^|/)skills/mux(?:/|$)",  # Runtime-resolved plugin paths
    r"(?:^|/)skills/mux-subagent(?:/|$)",
    r"(?:^|/)plugins/cache/.*/skills/mux(?:/|$)",  # Plugin cache paths
    r"(?:^|/)plugins/cache/.*/skills/mux-subagent(?:/|$)",
    r"(?:^|/)\.signals(?:/|$)",  # Signal metadata files
    r"(?:^|/)tmp/mux/.*/\.signals(?:/|$)",  # Session signal directories
]

# Grep/Glob allowlist: paths orchestrator may search
SEARCH_ALLOWLIST_PATTERNS = [
    r"(?:^|/)\$\{CLAUDE_PLUGIN_ROOT\}/skills(?:/|$)",  # Placeholder form
    r"(?:^|/)skills(?:/|$)",  # Runtime-resolved plugin paths
    r"(?:^|/)plugins/cache/.*/skills(?:/|$)",  # Plugin cache paths
    r"(?:^|/)\.claude/hooks(?:/|$)",  # Hook discovery
]

# Bash command whitelist (regex patterns)
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",  # Create directories
    r"^uv\s+run\s+.*tools/",  # Any tools/ invocation
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/",  # MUX skill tools (explicit)
]

# Tools that are always DENIED for orchestrator
FORBIDDEN_TOOLS = {
    "Write",
    "Edit",
    "NotebookEdit",
    "WebSearch",
    "WebFetch",
    "TaskOutput",
}

# Direct Skill() invocations allowed for orchestrator
ALLOWED_DIRECT_SKILLS = {"mux-ospec"}

# Tools that are always ALLOWED for orchestrator
ALLOWED_TOOLS = {
    "AskUserQuestion",
    "mcp__voicemode__converse",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "SendMessage",
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


def is_read_allowed(file_path: str) -> bool:
    """Check if file path matches Read allowlist."""
    for pattern in READ_ALLOWLIST_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def is_search_allowed(tool_input: ToolInput) -> bool:
    """Check if Grep/Glob path matches search allowlist."""
    # Check 'path' parameter (used by both Grep and Glob)
    search_path = tool_input.get("path", "")
    if not search_path:
        return False
    for pattern in SEARCH_ALLOWLIST_PATTERNS:
        if re.search(pattern, search_path):
            return True
    return False


def is_bash_allowed(command: str) -> tuple[bool, str]:
    """Check if Bash command matches whitelist.

    Returns (allowed, reason).
    """
    command = command.strip()
    for pattern in BASH_WHITELIST_PATTERNS:
        if re.match(pattern, command):
            return True, f"Matches whitelist: {pattern}"
    return False, "Command not in MUX whitelist. Allowed: mkdir -p, uv run tools/*"


def main() -> None:
    """Main hook execution."""
    try:
        input_data: HookInput = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input: ToolInput = input_data.get("tool_input", {})

        # === LAYER 1: Read with allowlist ===
        if tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            if is_read_allowed(file_path):
                print(json.dumps(make_decision("allow")))
            else:
                print(json.dumps(make_decision(
                    "deny",
                    f"MUX VIOLATION: Read is FORBIDDEN for orchestrator. "
                    f"Use extract-summary.py or delegate via Task(). "
                    f"Blocked path: {file_path}"
                )))
            return

        # === LAYER 2: Grep/Glob with allowlist ===
        if tool_name in {"Grep", "Glob"}:
            if is_search_allowed(tool_input):
                print(json.dumps(make_decision("allow")))
            else:
                print(json.dumps(make_decision(
                    "deny",
                    f"MUX VIOLATION: {tool_name} is FORBIDDEN for orchestrator. "
                    "Delegate via Task(run_in_background=True). "
                    "Allowed paths: ${CLAUDE_PLUGIN_ROOT}/skills/, .claude/hooks/"
                )))
            return

        # === LAYER 3: Skill allowlist ===
        if tool_name == "Skill":
            skill_name = tool_input.get("skill", "")
            if skill_name in ALLOWED_DIRECT_SKILLS:
                print(json.dumps(make_decision("allow")))
            else:
                print(json.dumps(make_decision(
                    "deny",
                    "MUX VIOLATION: Skill is FORBIDDEN for orchestrator. "
                    "Only Skill(skill=\"mux-ospec\") is allowed directly. "
                    "Delegate everything else via Task(run_in_background=True)."
                )))
            return

        # === LAYER 4: Forbidden tools - DENY ===
        if tool_name in FORBIDDEN_TOOLS:
            print(json.dumps(make_decision(
                "deny",
                f"MUX VIOLATION: {tool_name} is FORBIDDEN for orchestrator. "
                "Delegate via Task(run_in_background=True)."
            )))
            return

        # === LAYER 5: Bash whitelist ===
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            allowed, reason = is_bash_allowed(command)
            if allowed:
                print(json.dumps(make_decision("allow")))
            else:
                print(json.dumps(make_decision(
                    "deny",
                    f"MUX VIOLATION: {reason}"
                )))
            return

        # === LAYER 6: Task validation ===
        if tool_name == "Task":
            run_in_bg = tool_input.get("run_in_background", None)
            if run_in_bg is True:
                print(json.dumps(make_decision("allow")))
            elif run_in_bg is False:
                print(json.dumps(make_decision(
                    "deny",
                    "MUX VIOLATION: Task MUST use run_in_background=True. "
                    "Blocking on agents defeats MUX architecture."
                )))
            else:
                print(json.dumps(make_decision(
                    "askFirst",
                    "MUX WARNING: Task should use run_in_background=True. "
                    "Confirm this is intentional."
                )))
            return

        # === LAYER 7: Always allowed tools ===
        if tool_name in ALLOWED_TOOLS:
            print(json.dumps(make_decision("allow")))
            return

        # === DEFAULT: Unknown tool - askFirst as safety net ===
        print(json.dumps(make_decision(
            "askFirst",
            f"MUX MODE: {tool_name} requires approval. Is this a valid MUX action?"
        )))

    except Exception as e:
        # Fail-closed: block on error
        print(json.dumps(make_decision(
            "deny",
            f"MUX orchestrator hook error (fail-closed): {e}"
        )))
        sys.exit(0)


if __name__ == "__main__":
    main()
