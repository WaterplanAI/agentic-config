#!/usr/bin/env python3
"""Unit tests for credential-guardian hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "credential-guardian.py"


def run_hook(tool_name: str, tool_input: dict) -> dict:
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    hook_out = output.get("hookSpecificOutput", {})
    return {"decision": hook_out.get("permissionDecision", "allow"), "reason": hook_out.get("permissionDecisionReason", "")}


def test_blocks_ssh_read() -> TestResult:
    r = TestResult("Blocks Read of ~/.ssh/")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/.ssh/id_rsa")})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_aws_grep() -> TestResult:
    r = TestResult("Blocks Grep in ~/.aws/")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~/.aws/credentials"), "pattern": "secret"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_project_read() -> TestResult:
    r = TestResult("Allows Read in ~/projects/")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/projects/test/file.py")})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_claude_settings() -> TestResult:
    r = TestResult("Allows Read of ~/.claude/settings.json")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/.claude/settings.json")})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_non_read_tools() -> TestResult:
    r = TestResult("Allows non-Read tools (Bash)")
    try:
        out = run_hook("Bash", {"command": "ls"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_relative_glob_from_home() -> TestResult:
    r = TestResult("Blocks Glob(path=~, pattern=.ssh/*)")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": ".ssh/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_relative_grep_glob_from_home() -> TestResult:
    r = TestResult("Blocks Grep(path=~, glob=.aws/*)")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~"), "glob": ".aws/*", "pattern": "secret"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_fail_close_on_bad_input() -> TestResult:
    r = TestResult("Fail-close on invalid JSON input")
    try:
        result = subprocess.run(
            [str(HOOK_PATH)], input="not valid json",
            capture_output=True, text=True,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", f"Expected deny on error, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("credential-guardian unit tests", [
        test_blocks_ssh_read,
        test_blocks_aws_grep,
        test_allows_project_read,
        test_allows_claude_settings,
        test_allows_non_read_tools,
        test_blocks_relative_glob_from_home,
        test_blocks_relative_grep_glob_from_home,
        test_fail_close_on_bad_input,
    ])


if __name__ == "__main__":
    main()
