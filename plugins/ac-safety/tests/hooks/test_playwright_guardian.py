#!/usr/bin/env python3
"""Unit tests for playwright-guardian hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "playwright-guardian.py"


def run_hook(tool_name: str, tool_input: dict) -> dict:
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    hook_out = output.get("hookSpecificOutput", {})
    return {"decision": hook_out.get("permissionDecision", "allow"), "reason": hook_out.get("permissionDecisionReason", "")}


def test_blocks_browser_evaluate() -> TestResult:
    r = TestResult("Blocks browser_evaluate (always blocked)")
    try:
        out = run_hook("mcp__playwright__browser_evaluate", {"script": "document.cookie"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_browser_snapshot() -> TestResult:
    r = TestResult("Allows browser_snapshot (always allowed)")
    try:
        out = run_hook("mcp__playwright__browser_snapshot", {})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_navigate_allowed_domain() -> TestResult:
    r = TestResult("Allows navigate to github.com")
    try:
        out = run_hook("mcp__playwright__browser_navigate", {"url": "https://github.com/test"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_asks_navigate_blocked_domain() -> TestResult:
    r = TestResult("Asks for navigate to unknown domain (default: ask)")
    try:
        out = run_hook("mcp__playwright__browser_navigate", {"url": "https://evil.com/phishing"})
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_asks_action_with_url_on_blocked_domain() -> TestResult:
    """Any action with a url param on blocked domain triggers domain check."""
    r = TestResult("Asks for action with url param on blocked domain")
    try:
        # Use a non-always-blocked, non-always-allowed action that has a url
        # param. browser_navigate is the canonical example, but also test an
        # unknown action carrying a url field.
        out = run_hook("mcp__playwright__browser_navigate_custom", {"url": "https://evil.com/exploit"})
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_action_with_url_on_allowed_domain() -> TestResult:
    """Action with url param on allowed domain proceeds normally."""
    r = TestResult("Allows action with url param on allowed domain")
    try:
        # Unknown action with allowed domain url -- falls through to unknown-mcp-action
        out = run_hook("mcp__playwright__browser_navigate_custom", {"url": "https://github.com/test"})
        # Domain is allowed, so it falls to the unknown-mcp-action handler (ask by default)
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_denies_playwright_cli_run_code() -> TestResult:
    """Bash-based playwright-cli run-code maps to a blocked Playwright action."""
    r = TestResult("Denies playwright-cli run-code via Bash")
    try:
        out = run_hook("Bash", {"command": "playwright-cli run-code \"document.title\""})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_playwright_cli_snapshot_with_env_prefix() -> TestResult:
    """Bash-based playwright-cli snapshot remains allowed with env prefixes."""
    r = TestResult("Allows playwright-cli snapshot with env prefix")
    try:
        out = run_hook("Bash", {"command": "PLAYWRIGHT_CLI_SESSION=review playwright-cli snapshot"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_asks_playwright_cli_open_blocked_domain() -> TestResult:
    """Bash-based playwright-cli navigation inherits the domain allowlist policy."""
    r = TestResult("Asks for playwright-cli open on blocked domain")
    try:
        out = run_hook("Bash", {"command": "playwright-cli open https://evil.com/phishing"})
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_denies_playwright_cli_fill() -> TestResult:
    """Bash-based playwright-cli fill maps to a blocked Playwright action."""
    r = TestResult("Denies playwright-cli fill via Bash")
    try:
        out = run_hook("Bash", {"command": "playwright-cli fill '#email' 'user@example.com'"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_denies_blocked_action_in_playwright_cli_chain() -> TestResult:
    """Later blocked playwright-cli segments still block the overall Bash command."""
    r = TestResult("Denies blocked action in chained playwright-cli Bash command")
    try:
        out = run_hook(
            "Bash",
            {"command": "playwright-cli snapshot && playwright-cli run-code \"document.title\""},
        )
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("playwright-guardian unit tests", [
        test_blocks_browser_evaluate,
        test_allows_browser_snapshot,
        test_allows_navigate_allowed_domain,
        test_asks_navigate_blocked_domain,
        test_asks_action_with_url_on_blocked_domain,
        test_allows_action_with_url_on_allowed_domain,
        test_denies_playwright_cli_run_code,
        test_allows_playwright_cli_snapshot_with_env_prefix,
        test_asks_playwright_cli_open_blocked_domain,
        test_denies_playwright_cli_fill,
        test_denies_blocked_action_in_playwright_cli_chain,
    ])


if __name__ == "__main__":
    main()
