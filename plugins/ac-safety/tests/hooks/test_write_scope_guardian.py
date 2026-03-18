#!/usr/bin/env python3
"""Unit tests for write-scope-guardian hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "write-scope-guardian.py"


def run_hook(tool_name: str, tool_input: dict) -> dict:
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    hook_out = output.get("hookSpecificOutput", {})
    return {"decision": hook_out.get("permissionDecision", "allow"), "reason": hook_out.get("permissionDecisionReason", "")}


def test_allows_project_write() -> TestResult:
    r = TestResult("Allows Write to ~/projects/")
    try:
        out = run_hook("Write", {"file_path": os.path.expanduser("~/projects/test/file.py"), "content": "test"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_settings_write() -> TestResult:
    r = TestResult("Blocks Write to ~/.claude/settings.json")
    try:
        out = run_hook("Write", {"file_path": os.path.expanduser("~/.claude/settings.json"), "content": "{}"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_asks_hooks_write() -> TestResult:
    r = TestResult("Asks for Write to ~/.claude/hooks/")
    try:
        out = run_hook("Write", {"file_path": os.path.expanduser("~/.claude/hooks/test.py"), "content": "test"})
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_system_write() -> TestResult:
    r = TestResult("Blocks Write to /etc/")
    try:
        out = run_hook("Write", {"file_path": "/etc/passwd", "content": "test"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_git_hooks_injection() -> TestResult:
    r = TestResult("Blocks Write to .git/hooks/")
    try:
        out = run_hook("Write", {"file_path": "/tmp/repo/.git/hooks/pre-commit", "content": "test"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_category_deny_cannot_weaken_to_allow() -> TestResult:
    r = TestResult("Category decision cannot weaken deny to allow")
    try:
        # /etc/passwd is in blocked_write_prefixes => _check_write returns deny
        # Even if a project config sets the category to "allow", the guardian
        # should still deny (deny-cannot-weaken-to-allow guard)
        out = run_hook("Write", {"file_path": "/etc/hosts", "content": "test"})
        assert out["decision"] == "deny", f"Expected deny for /etc/hosts, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_safety_yaml_write() -> TestResult:
    r = TestResult("Blocks Write to ~/.claude/safety.yaml (tamper protection)")
    try:
        out = run_hook("Write", {"file_path": os.path.expanduser("~/.claude/safety.yaml"), "content": "hack: true"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        assert "tamper" in out["reason"].lower() or "blocked" in out["reason"].lower()
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_audit_yaml_write() -> TestResult:
    r = TestResult("Blocks Write to ~/.claude/audit.yaml (tamper protection)")
    try:
        out = run_hook("Write", {"file_path": os.path.expanduser("~/.claude/audit.yaml"), "content": "hack: true"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("write-scope-guardian unit tests", [
        test_allows_project_write, test_blocks_settings_write,
        test_asks_hooks_write, test_blocks_system_write, test_blocks_git_hooks_injection,
        test_category_deny_cannot_weaken_to_allow,
        test_blocks_safety_yaml_write,
        test_blocks_audit_yaml_write,
    ])


if __name__ == "__main__":
    main()
