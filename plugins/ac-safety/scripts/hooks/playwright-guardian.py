#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: restricts Playwright/MCP tool usage.

Config-driven via safety.yaml (playwright section).
Default category decisions: ASK. Fail-close on errors.
"""

import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, load_config

MCP_PREFIXES = ["mcp__playwright__", "mcp__plugin_playwright_playwright__"]

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


def _get_mcp_action(tool_name: str) -> str | None:
    for prefix in MCP_PREFIXES:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):]
    return None


def _is_domain_allowed(url: str, allowed_domains: set[str]) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        bare_host = hostname.removeprefix("www.")
        return hostname in allowed_domains or bare_host in allowed_domains or f"www.{bare_host}" in allowed_domains
    except Exception:
        return False


@fail_close
def main() -> None:
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    action = _get_mcp_action(tool_name)
    if action is None:
        allow()
        return

    config = load_config()
    pw = config.get("playwright", {})
    if not isinstance(pw, dict):
        pw = {}

    always_blocked = set(pw.get("always_blocked_tools", list(DEFAULT_ALWAYS_BLOCKED)))
    always_allowed = set(pw.get("always_allowed_tools", list(DEFAULT_ALWAYS_ALLOWED)))
    allowed_domains = set(pw.get("allowed_domains", list(DEFAULT_ALLOWED_DOMAINS)))

    # Always blocked
    if action in always_blocked:
        deny(f"BLOCKED: {action} is always blocked (arbitrary code execution / credential risk)")
        return

    # Always allowed
    if action in always_allowed:
        allow()
        return

    # Navigation: check domain
    if action == "browser_navigate":
        url = tool_input.get("url", "")
        if not _is_domain_allowed(url, allowed_domains):
            decision = get_category_decision(config, "playwright", "navigate-blocked-domain")
            if decision == "deny":
                deny(f"BLOCKED: Navigation to '{url}' denied (domain not in allowlist)")
            elif decision == "ask":
                ask(f"Navigation to '{url}' -- domain not in allowlist. Allow?")
            else:
                allow()
            return
        allow()
        return

    # File upload
    if action == "browser_file_upload":
        decision = get_category_decision(config, "playwright", "browser-file-upload")
        if decision == "deny":
            deny("BLOCKED: browser_file_upload is blocked (data exfiltration risk)")
        elif decision == "ask":
            ask("browser_file_upload detected -- confirm to proceed?")
        else:
            allow()
        return

    # Unknown MCP action
    decision = get_category_decision(config, "playwright", "unknown-mcp-action")
    if decision == "deny":
        deny(f"BLOCKED: Unknown MCP action '{action}' denied by default")
    elif decision == "ask":
        ask(f"Unknown MCP action '{action}' -- confirm to proceed?")
    else:
        allow()


if __name__ == "__main__":
    main()
