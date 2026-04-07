#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: restricts Playwright usage.

Supports the current Playwright surfaces used in this repository:
- Playwright MCP tool names (`mcp__playwright__*`, `mcp__plugin_playwright_playwright__*`)
- Bash commands that invoke `playwright-cli`

Config-driven via safety.yaml (playwright section).
Default category decisions: ASK. Fail-close on errors.
"""

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, load_config

MCP_PREFIXES = ["mcp__playwright__", "mcp__plugin_playwright_playwright__"]
_PLAYWRIGHT_CLI_NAME = "playwright-cli"
_PLAYWRIGHT_CLI_WRAPPERS = {"command", "env", "exec", "sudo"}
_PLAYWRIGHT_CLI_GLOBAL_FLAGS = {"--headed"}
_PLAYWRIGHT_CLI_FLAGS_WITH_VALUES = {"-s", "--session"}
_SHELL_CONTROL_TOKENS = {";", "&&", "||", "|", "&"}
_URL_ACTIONS = {"open", "goto", "tab-new"}

DEFAULT_ALLOWED_DOMAINS = {
    "localhost", "127.0.0.1", "github.com", "gitlab.com", "pypi.org",
    "www.npmjs.com", "docs.aws.amazon.com", "docs.python.org",
    "stackoverflow.com", "developer.mozilla.org", "www.google.com",
    "serper.dev", "serpapi.com",
}

DEFAULT_ALWAYS_BLOCKED = {"browser_evaluate", "browser_fill_form", "browser_run_code"}

DEFAULT_ALWAYS_ALLOWED = {
    "browser_snapshot", "browser_take_screenshot", "browser_click",
    "browser_close", "browser_resize", "browser_tabs",
    "browser_console_messages", "browser_network_requests",
    "browser_press_key", "browser_hover", "browser_wait_for",
    "browser_navigate_back", "browser_install", "browser_handle_dialog",
    "browser_select_option", "browser_drag", "browser_type",
}

CLI_ACTION_TO_POLICY_ACTION = {
    "open": "browser_navigate",
    "goto": "browser_navigate",
    "tab-new": "browser_navigate",
    "go-back": "browser_navigate_back",
    "go-forward": "browser_navigate_back",
    "reload": "browser_navigate_back",
    "snapshot": "browser_snapshot",
    "screenshot": "browser_take_screenshot",
    "click": "browser_click",
    "check": "browser_click",
    "uncheck": "browser_click",
    "dblclick": "browser_click",
    "fill": "browser_fill_form",
    "type": "browser_type",
    "select": "browser_select_option",
    "hover": "browser_hover",
    "upload": "browser_file_upload",
    "press": "browser_press_key",
    "keydown": "browser_press_key",
    "keyup": "browser_press_key",
    "tab-list": "browser_tabs",
    "tab-select": "browser_tabs",
    "list": "browser_tabs",
    "tab-close": "browser_close",
    "close": "browser_close",
    "close-all": "browser_close",
    "console": "browser_console_messages",
    "network": "browser_network_requests",
    "run-code": "browser_run_code",
    "resize": "browser_resize",
    "dialog-accept": "browser_handle_dialog",
    "dialog-dismiss": "browser_handle_dialog",
}

CATEGORY_BY_ACTION = {
    "browser_evaluate": "browser-evaluate",
    "browser_fill_form": "browser-fill-form",
    "browser_run_code": "browser-evaluate",
    "browser_file_upload": "browser-file-upload",
}


@dataclass(frozen=True)
class PlaywrightInvocation:
    """Normalized Playwright action extracted from a tool call."""

    action: str
    raw_action: str
    source: str
    url: str = ""


def _get_mcp_action(tool_name: str) -> str | None:
    """Return the Playwright MCP action name for a tool name."""
    for prefix in MCP_PREFIXES:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):]
    return None


def _is_domain_allowed(url: str, allowed_domains: set[str]) -> bool:
    """Return True when the URL hostname matches the allowlist."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        bare_host = hostname.removeprefix("www.")
        return hostname in allowed_domains or bare_host in allowed_domains or f"www.{bare_host}" in allowed_domains
    except Exception:
        return False


def _is_env_assignment(token: str) -> bool:
    """Return True when a token is a shell environment assignment."""
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) is not None


def _split_shell_segments(command: str) -> list[list[str]]:
    """Split a shell command into argv segments separated by control operators."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        fallback_tokens = command.split()
        return [fallback_tokens] if fallback_tokens else []

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SHELL_CONTROL_TOKENS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)

    if current:
        segments.append(current)
    return segments


def _trim_cli_wrappers(args: list[str]) -> list[str]:
    """Remove shell wrappers and leading env assignments before command lookup."""
    idx = 0
    while idx < len(args):
        token = args[idx]
        if _is_env_assignment(token):
            idx += 1
            continue
        if token in _PLAYWRIGHT_CLI_WRAPPERS:
            idx += 1
            continue
        break
    return args[idx:]


def _extract_cli_action(args: list[str]) -> tuple[str | None, list[str]]:
    """Extract the playwright-cli action and its trailing args."""
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token in _PLAYWRIGHT_CLI_FLAGS_WITH_VALUES and idx + 1 < len(args):
            idx += 2
            continue
        if any(token.startswith(f"{flag}=") for flag in _PLAYWRIGHT_CLI_FLAGS_WITH_VALUES):
            idx += 1
            continue
        if token in _PLAYWRIGHT_CLI_GLOBAL_FLAGS:
            idx += 1
            continue
        if token.startswith("-"):
            idx += 1
            continue
        return token, args[idx + 1 :]
    return None, []


def _extract_cli_url(action: str, action_args: list[str]) -> str:
    """Return the URL carried by a navigation-style playwright-cli action."""
    if action not in _URL_ACTIONS:
        return ""
    for arg in action_args:
        if not arg.startswith("-"):
            return arg
    return ""


def _resolve_cli_invocation(segment_args: list[str]) -> PlaywrightInvocation | None:
    """Return a normalized Playwright invocation from a bash segment."""
    trimmed_args = _trim_cli_wrappers(segment_args)
    if not trimmed_args:
        return None

    command_name = os.path.basename(trimmed_args[0])
    if command_name != _PLAYWRIGHT_CLI_NAME:
        return None

    raw_action, action_args = _extract_cli_action(trimmed_args[1:])
    if raw_action is None:
        return PlaywrightInvocation(action="unknown-mcp-action", raw_action="playwright-cli", source="bash")

    normalized_action = CLI_ACTION_TO_POLICY_ACTION.get(raw_action, "unknown-mcp-action")
    return PlaywrightInvocation(
        action=normalized_action,
        raw_action=raw_action,
        source="bash",
        url=_extract_cli_url(raw_action, action_args),
    )


def _resolve_playwright_invocations(tool_name: str, tool_input: dict[str, Any]) -> list[PlaywrightInvocation]:
    """Normalize any Playwright-relevant actions from a tool call payload."""
    mcp_action = _get_mcp_action(tool_name)
    if mcp_action is not None:
        return [
            PlaywrightInvocation(
                action=mcp_action,
                raw_action=mcp_action,
                source="mcp",
                url=str(tool_input.get("url", "")),
            )
        ]

    if tool_name != "Bash":
        return []

    command = str(tool_input.get("command", ""))
    invocations: list[PlaywrightInvocation] = []
    for segment_args in _split_shell_segments(command):
        invocation = _resolve_cli_invocation(segment_args)
        if invocation is not None:
            invocations.append(invocation)
    return invocations


def _format_action_label(invocation: PlaywrightInvocation) -> str:
    """Return a human-readable action label for policy messages."""
    if invocation.source == "bash":
        return f"playwright-cli {invocation.raw_action}"
    return invocation.raw_action


def _decide_from_category(
    config: dict[str, Any],
    category: str,
    deny_message: str,
    ask_message: str,
) -> tuple[str, str]:
    """Resolve allow/ask/deny for a configured Playwright category."""
    decision = get_category_decision(config, "playwright", category)
    if decision == "deny":
        return "deny", deny_message
    if decision == "ask":
        return "ask", ask_message
    return "allow", ""


def _evaluate_invocation(invocation: PlaywrightInvocation, config: dict[str, Any]) -> tuple[str, str]:
    """Return the policy decision for a normalized Playwright invocation."""
    action_label = _format_action_label(invocation)
    pw = config.get("playwright", {})
    if not isinstance(pw, dict):
        pw = {}

    always_blocked = set(pw.get("always_blocked_tools", list(DEFAULT_ALWAYS_BLOCKED)))
    always_allowed = set(pw.get("always_allowed_tools", list(DEFAULT_ALWAYS_ALLOWED)))
    allowed_domains = set(pw.get("allowed_domains", list(DEFAULT_ALLOWED_DOMAINS)))

    if invocation.action in always_blocked:
        return "deny", f"BLOCKED: {action_label} is always blocked (arbitrary code execution / credential risk)"

    if invocation.action in always_allowed:
        return "allow", ""

    if invocation.url and not _is_domain_allowed(invocation.url, allowed_domains):
        return _decide_from_category(
            config,
            "navigate-blocked-domain",
            f"BLOCKED: {action_label} targeting '{invocation.url}' denied (domain not in allowlist)",
            f"{action_label} targeting '{invocation.url}' is outside the allowed domain list. Allow?",
        )

    if invocation.action == "browser_navigate":
        return "allow", ""

    category = CATEGORY_BY_ACTION.get(invocation.action)
    if category is not None:
        return _decide_from_category(
            config,
            category,
            f"BLOCKED: {action_label} denied by Playwright policy",
            f"{action_label} detected -- confirm to proceed?",
        )

    return _decide_from_category(
        config,
        "unknown-mcp-action",
        f"BLOCKED: Unknown Playwright action '{action_label}' denied by default",
        f"Unknown Playwright action '{action_label}' -- confirm to proceed?",
    )


@fail_close
def main() -> None:
    """Evaluate the incoming tool call against Playwright policy."""
    input_data = json.load(sys.stdin)
    tool_name = str(input_data.get("tool_name", ""))
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    invocations = _resolve_playwright_invocations(tool_name, tool_input)
    if not invocations:
        allow()
        return

    config = load_config()
    for invocation in invocations:
        decision, message = _evaluate_invocation(invocation, config)
        if decision == "allow":
            continue
        if decision == "deny":
            deny(message)
            return
        ask(message)
        return

    allow()


if __name__ == "__main__":
    main()
