#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Pretooluse hook for Claude Code that enforces dry-run mode.

Blocks file-writing operations when session status contains dry_run: true.
Session is scoped by Claude Code PID for parallel agent isolation.
Fail-open principle: allow operations if hook encounters errors.

Usage:
    uv run --no-project --script dry-run-guard.py <project_root>

The project_root argument is required to resolve paths correctly when
Claude's CWD differs from the project root (e.g., after cd commands).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

# Project root passed as CLI argument (set by hook command in settings.json)
# Falls back to CWD if not provided (legacy behavior)
PROJECT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

try:
    import yaml
except ImportError:
    # Fail-open if dependencies missing
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def find_agentic_root() -> Path:
    """Find agentic-config installation root by walking up tree for VERSION marker."""
    current_dir = Path.cwd()
    max_depth = 10
    depth = 0

    # Walk up directory tree looking for VERSION marker
    while depth < max_depth:
        if (current_dir / "VERSION").exists() and (current_dir / "core").is_dir():
            return current_dir

        # Move up one directory
        parent_dir = current_dir.parent
        if parent_dir == current_dir:
            break  # Reached filesystem root
        current_dir = parent_dir
        depth += 1

    # Fallback 1: git repo root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            if (git_root / "VERSION").exists():
                return git_root
    except Exception:
        pass

    # Fallback 2: current directory
    return Path.cwd()


def find_claude_pid() -> int | None:
    """Trace up process tree to find claude process PID."""
    try:
        pid = os.getpid()
        for _ in range(10):  # Max 10 levels
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


def get_session_status_path() -> Path:
    """Get session-specific status file path based on Claude PID."""
    agentic_root = find_agentic_root()
    claude_pid = find_claude_pid()
    if claude_pid:
        return agentic_root / f"outputs/session/{claude_pid}/status.yml"
    # Fallback to shared path if Claude PID not found
    return agentic_root / "outputs/session/status.yml"


class ToolInput(TypedDict, total=False):
    """Tool parameters from Claude Code."""
    file_path: str
    command: str


class HookInput(TypedDict):
    """JSON input received via stdin."""
    tool_name: str
    tool_input: ToolInput


class HookSpecificOutput(TypedDict, total=False):
    """Inner hook output structure."""
    hookEventName: str
    permissionDecision: str  # "allow" | "deny" | "ask"
    permissionDecisionReason: str


class HookOutput(TypedDict):
    """JSON output returned via stdout."""
    hookSpecificOutput: HookSpecificOutput


# Read-only Bash commands (safe during dry-run)
SAFE_BASH_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "which", "pwd", "env", "date",
    "uname", "wc", "sort", "uniq", "cut", "tr", "sed", "awk", "basename",
    "dirname", "realpath", "readlink", "file", "stat", "test", "[", "[[",
    "git status", "git diff", "git log", "git branch", "git show", "git rev-parse",
    "echo", "printf", "true", "false", "yes", "no"
}

# File-writing patterns in Bash (dangerous during dry-run)
WRITE_PATTERNS = [
    ">", ">>",  # Redirects
    "cp ", "mv ", "rm ", "touch ", "mkdir ",  # File ops
    "tee ", "dd ", "install ",  # Write tools
    "git add", "git commit", "git push", "git tag", "git stash",  # Git writes
    "npm install", "yarn install", "pip install", "cargo build",  # Package managers
]


def is_dry_run_enabled() -> bool:
    """Check if dry-run mode is enabled in session status."""
    try:
        status_file = get_session_status_path()
        if not status_file.exists():
            return False

        with status_file.open("r") as f:
            data = yaml.safe_load(f)

        return bool(data.get("dry_run", False))
    except Exception:
        # Fail-open: if we can't read status, assume dry-run is disabled
        return False


def is_session_status_file(file_path: str | None) -> bool:
    """Check if file is the session status file (exception to dry-run blocking)."""
    if not file_path:
        return False

    try:
        path = Path(file_path).resolve()
        status_path = get_session_status_path().resolve()
        return path == status_path
    except Exception:
        return False


def is_bash_write_command(command: str) -> bool:
    """Analyze Bash command to detect file-writing operations."""
    # Quick check for write patterns
    for pattern in WRITE_PATTERNS:
        if pattern in command:
            return True

    # Check if it's a known safe command (exact match or starts with safe command)
    for safe_cmd in SAFE_BASH_COMMANDS:
        if command.strip() == safe_cmd or command.strip().startswith(f"{safe_cmd} "):
            return False

    # Conservative: if we're unsure, treat as potentially writing
    # Exception: pure variable assignment, cd, export, source are safe
    safe_keywords = ["cd ", "export ", "source ", "set ", "unset ", "alias ", "type "]
    if any(command.strip().startswith(kw) for kw in safe_keywords):
        return False

    # If command is very simple (no special chars), likely safe read
    if len(command.strip().split()) == 1:
        return False

    return False  # Default to allowing (fail-open)


def should_block_tool(tool_name: str, tool_input: ToolInput) -> tuple[bool, str | None]:
    """
    Determine if tool should be blocked based on dry-run status.

    Returns:
        (should_block, message): Tuple of block decision and optional message
    """
    # Check dry-run status
    if not is_dry_run_enabled():
        return False, None

    # Exception: always allow session status file modifications
    file_path = tool_input.get("file_path")
    if is_session_status_file(file_path):
        return False, None

    # Block Write tool
    if tool_name == "Write":
        return True, f"Blocked by dry-run mode. Would write to: {file_path}"

    # Block Edit tool
    if tool_name == "Edit":
        return True, f"Blocked by dry-run mode. Would edit: {file_path}"

    # Block NotebookEdit tool
    if tool_name == "NotebookEdit":
        notebook_path = tool_input.get("notebook_path") or file_path
        return True, f"Blocked by dry-run mode. Would edit notebook: {notebook_path}"

    # Analyze Bash commands for file-writing operations
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if is_bash_write_command(command):
            return True, f"Blocked by dry-run mode. Would execute: {command[:100]}"

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
