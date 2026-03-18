#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: restricts Write/Edit to allowed project paths.

Config-driven via safety.yaml (write_scope section).
Default category decisions: ASK. Fail-close on errors.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, is_in_prefixes, load_config, resolve_path

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


def _extract_path(tool_name: str, tool_input: dict) -> str | None:
    if tool_name in ("Write", "Edit"):
        return tool_input.get("file_path")
    if tool_name == "NotebookEdit":
        return tool_input.get("notebook_path")
    return None


def _check_write(
    path: str,
    blocked_write_files: list[str],
    ask_user_prefixes: list[str],
    blocked_write_prefixes: list[str],
    allowed_write_prefixes: list[str],
    git_hooks_segment: str,
) -> tuple[str, str | None]:
    """Returns (decision, reason). decision: 'allow', 'deny', or 'ask'."""
    resolved = resolve_path(path)

    # Block specific files
    for blocked_file in blocked_write_files:
        if resolved == os.path.realpath(os.path.expanduser(blocked_file)):
            return "deny", f"Write to {blocked_file} is blocked (tamper protection)"

    # Ask user for sensitive directories
    for prefix in ask_user_prefixes:
        real_prefix = os.path.realpath(os.path.expanduser(prefix.rstrip("/")))
        if resolved.startswith(real_prefix + "/") or resolved == real_prefix:
            return "ask", f"Write to {path} targets sensitive directory -- confirm?"

    # Block specific prefixes
    for prefix in blocked_write_prefixes:
        real_prefix = os.path.realpath(os.path.expanduser(prefix.rstrip("/")))
        if resolved.startswith(real_prefix + "/") or resolved == real_prefix:
            return "deny", f"Write to {prefix} is blocked (protected directory)"

    # Block .git/hooks/ injection
    if git_hooks_segment in resolved:
        return "deny", "Write to .git/hooks/ is blocked (hook injection prevention)"

    # If in allowed prefixes, allow
    if is_in_prefixes(path, allowed_write_prefixes):
        return "allow", None

    return "deny", f"Write to {path} is blocked (outside allowed project directories)"


@fail_close
def main() -> None:
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name not in WRITE_TOOLS:
        allow()
        return

    path = _extract_path(tool_name, tool_input)
    if not path:
        allow()
        return

    config = load_config()
    ws = config.get("write_scope", {})
    if not isinstance(ws, dict):
        ws = {}

    allowed_write_prefixes: list[str] = ws.get("allowed_write_prefixes", [
        "~/projects/", "~/.claude/", "~/.claude-secondary/", "/private/tmp/", "/tmp/",
    ])
    blocked_write_prefixes: list[str] = ws.get("blocked_write_prefixes", [
        "~/.ssh/", "~/.aws/", "~/.config/gh/", "~/.docker/", "~/.gnupg/",
        "~/Library/LaunchAgents/", "~/Library/LaunchDaemons/",
        "/etc/", "/usr/", "/bin/", "/sbin/",
    ])
    blocked_write_files: list[str] = ws.get("blocked_write_files", [
        "~/.claude/settings.json", "~/.claude/settings.local.json",
        "~/.claude-secondary/settings.json",
        "~/.bashrc", "~/.zshrc", "~/.zprofile", "~/.profile", "~/.bash_profile",
        "~/.npmrc", "~/.netrc", "~/.gitconfig", "~/.pypirc", "~/.pythonrc",
        "~/.ssh/authorized_keys",
    ])
    ask_user_prefixes: list[str] = ws.get("ask_user_prefixes", [
        "~/.claude/hooks/", "~/.claude-secondary/hooks/",
    ])
    git_hooks_segment: str = ws.get("git_hooks_segment", "/.git/hooks/")

    result, reason = _check_write(
        path, blocked_write_files, ask_user_prefixes,
        blocked_write_prefixes, allowed_write_prefixes, git_hooks_segment,
    )
    if result == "deny":
        deny(f"BLOCKED: {reason}")
    elif result == "ask":
        ask(reason or "")
    else:
        allow()


if __name__ == "__main__":
    main()
