#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook for Claude Code that enforces dry-run mode.

Blocks file-writing operations when session status contains dry_run: true.
Session resolution prefers the Claude-compatible CLAUDE_SESSION_ID exposed by Pi
hook-compat, then falls back to a discovered Claude PID, then the shared status
path for legacy sessions.
Fail-open principle: allow operations if hook encounters errors.

Plugin context: Uses project working directory (CWD) for session status
resolution. CLAUDE_PLUGIN_ROOT is available but not needed for session paths
since outputs/ lives in the project directory, not the plugin cache.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

try:
    import yaml
except ImportError:
    # Fail-open if dependencies missing
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                }
            }
        )
    )
    sys.exit(0)


SAFE_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
PYTHON_WRITE_HINTS = (
    "open(",
    "write_text(",
    "write_bytes(",
    ".write(",
    "json.dump(",
    "yaml.safe_dump(",
)
NODE_WRITE_HINTS = (
    "writefilesync(",
    "writefile(",
    "appendfilesync(",
    "appendfile(",
    "mkdirsync(",
    "rmsync(",
    "rename(",
    "renamesync(",
    "copyfilesync(",
    "createwritestream(",
)
PERL_WRITE_HINTS = ("open(", "print ", "unlink ", "rename ")
RUBY_WRITE_HINTS = (
    "file.write(",
    "file.binwrite(",
    "file.open(",
    "io.write(",
    "fileutils.",
)
PHP_WRITE_HINTS = (
    "file_put_contents(",
    "fopen(",
    "mkdir(",
    "rename(",
    "unlink(",
)


def find_claude_pid() -> int | None:
    """Trace up process tree to find claude process PID."""
    try:
        pid = os.getpid()
        for _ in range(10):
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
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


def normalize_session_id(raw_value: str | None) -> str | None:
    """Return a safe session identifier or None."""
    if raw_value is None:
        return None

    normalized = raw_value.strip()
    if not normalized:
        return None

    if SAFE_SESSION_ID_PATTERN.fullmatch(normalized):
        return normalized

    return None


def get_session_status_candidates() -> list[Path]:
    """Return status file candidates in lookup priority order."""
    project_root = Path.cwd()
    candidates: list[Path] = []

    session_id = normalize_session_id(os.environ.get("CLAUDE_SESSION_ID"))
    if session_id:
        candidates.append(project_root / f"outputs/session/{session_id}/status.yml")

    claude_pid = find_claude_pid()
    if claude_pid is not None:
        pid_path = project_root / f"outputs/session/{claude_pid}/status.yml"
        if pid_path not in candidates:
            candidates.append(pid_path)

    shared_path = project_root / "outputs/session/shared/status.yml"
    if shared_path not in candidates:
        candidates.append(shared_path)

    return candidates


def get_existing_session_status_path() -> Path | None:
    """Return the first existing status path, if any."""
    for status_path in get_session_status_candidates():
        if status_path.exists():
            return status_path
    return None


class ToolInput(TypedDict, total=False):
    """Tool parameters from Claude Code."""

    file_path: str
    notebook_path: str
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


SAFE_BASH_COMMANDS = {
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "which",
    "pwd",
    "env",
    "date",
    "uname",
    "wc",
    "sort",
    "uniq",
    "cut",
    "tr",
    "sed",
    "awk",
    "basename",
    "dirname",
    "realpath",
    "readlink",
    "file",
    "stat",
    "test",
    "[",
    "[[",
    "git status",
    "git diff",
    "git log",
    "git branch",
    "git show",
    "git rev-parse",
    "echo",
    "printf",
    "true",
    "false",
    "yes",
    "no",
}

WRITE_PATTERNS = [
    ">",
    ">>",
    " cp ",
    " mv ",
    " rm ",
    " touch ",
    " mkdir ",
    " tee ",
    " dd ",
    " install ",
    " git add",
    " git commit",
    " git push",
    " git tag",
    " git stash",
    " npm install",
    " yarn install",
    " pnpm install",
    " pip install",
    " cargo build",
]

SAFE_BASH_PREFIXES = (
    "cd ",
    "export ",
    "source ",
    "set ",
    "unset ",
    "alias ",
    "type ",
)


def is_dry_run_enabled() -> bool:
    """Check if dry-run mode is enabled in the resolved session status."""
    try:
        status_file = get_existing_session_status_path()
        if status_file is None:
            return False

        with status_file.open("r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle) or {}

        if not isinstance(data, dict):
            return False

        return bool(data.get("dry_run", False))
    except Exception:
        # Fail-open: if we can't read status, assume dry-run is disabled
        return False


def is_session_status_file(file_path: str | None) -> bool:
    """Check if file is one of the current session status file candidates."""
    if not file_path:
        return False

    try:
        resolved_path = Path(file_path).resolve()
        return any(resolved_path == candidate.resolve() for candidate in get_session_status_candidates())
    except Exception:
        return False


def contains_write_hints(command: str, interpreter_tokens: tuple[str, ...], write_hints: tuple[str, ...]) -> bool:
    """Return True when a command invokes an interpreter with write-like code."""
    lowered = command.lower()
    return any(token in lowered for token in interpreter_tokens) and any(hint in lowered for hint in write_hints)


def is_interpreter_write_command(command: str) -> bool:
    """Detect common interpreter-mediated write operations."""
    return any(
        (
            contains_write_hints(
                command,
                ("python -c", "python3 -c", "uv run python", "python <<", "python3 <<", "python - <<", "python3 - <<"),
                PYTHON_WRITE_HINTS,
            ),
            contains_write_hints(command, ("node -e", "node --eval"), NODE_WRITE_HINTS),
            contains_write_hints(command, ("perl -e",), PERL_WRITE_HINTS),
            contains_write_hints(command, ("ruby -e",), RUBY_WRITE_HINTS),
            contains_write_hints(command, ("php -r",), PHP_WRITE_HINTS),
        )
    )


def is_bash_write_command(command: str) -> bool:
    """Analyze Bash command to detect file-writing operations."""
    normalized = f" {command.strip().lower()} "

    if is_interpreter_write_command(command):
        return True

    for pattern in WRITE_PATTERNS:
        if pattern in normalized:
            return True

    stripped = command.strip()
    for safe_cmd in SAFE_BASH_COMMANDS:
        if stripped == safe_cmd or stripped.startswith(f"{safe_cmd} "):
            return False

    if any(stripped.startswith(prefix) for prefix in SAFE_BASH_PREFIXES):
        return False

    if len(stripped.split()) == 1:
        return False

    return False


def should_block_tool(tool_name: str, tool_input: ToolInput) -> tuple[bool, str | None]:
    """Determine if the tool should be blocked based on dry-run status."""
    if not is_dry_run_enabled():
        return False, None

    file_path = tool_input.get("file_path")
    if is_session_status_file(file_path):
        return False, None

    if tool_name == "Write":
        return True, f"Blocked by dry-run mode. Would write to: {file_path}"

    if tool_name == "Edit":
        return True, f"Blocked by dry-run mode. Would edit: {file_path}"

    if tool_name == "NotebookEdit":
        notebook_path = tool_input.get("notebook_path") or file_path
        return True, f"Blocked by dry-run mode. Would edit notebook: {notebook_path}"

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if is_bash_write_command(command):
            return True, f"Blocked by dry-run mode. Would execute: {command[:100]}"

    return False, None


def main() -> None:
    """Main hook execution."""
    try:
        input_data: HookInput = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        should_block, message = should_block_tool(tool_name, tool_input)

        hook_output: HookSpecificOutput = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if should_block else "allow",
        }
        if message:
            hook_output["permissionDecisionReason"] = message

        output: HookOutput = {"hookSpecificOutput": hook_output}
        print(json.dumps(output))

    except Exception as error:
        output: HookOutput = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }
        print(json.dumps(output))
        print(f"Hook error: {error}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
