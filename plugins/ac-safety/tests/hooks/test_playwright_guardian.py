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
    return r


def test_allows_browser_snapshot() -> TestResult:
    r = TestResult("Allows browser_snapshot (always allowed)")
    try:
        out = run_hook("mcp__playwright__browser_snapshot", {})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_navigate_allowed_domain() -> TestResult:
    r = TestResult("Allows navigate to github.com")
    try:
        out = run_hook("mcp__playwright__browser_navigate", {"url": "https://github.com/test"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_navigate_blocked_domain() -> TestResult:
    r = TestResult("Asks for navigate to unknown domain (default: ask)")
    try:
        out = run_hook("mcp__playwright__browser_navigate", {"url": "https://evil.com/phishing"})
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("playwright-guardian unit tests", [
        test_blocks_browser_evaluate, test_allows_browser_snapshot,
        test_allows_navigate_allowed_domain, test_asks_navigate_blocked_domain,
    ])


if __name__ == "__main__":
    main()
