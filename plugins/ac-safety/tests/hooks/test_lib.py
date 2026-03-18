#!/usr/bin/env python3
"""Unit tests for _lib.py shared safety library."""

import json
import os
import sys
from pathlib import Path

# Add tests dir for conftest, hooks dir for _lib
sys.path.insert(0, str(Path(__file__).parent.parent))
HOOKS_DIR = Path(__file__).parent.parent.parent / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]
from _lib import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    _deep_merge,
    _most_restrictive,
    allow,
    ask,
    deny,
    fail_close,
    get_category_decision,
    is_in_prefixes,
    resolve_path,
)


def test_most_restrictive() -> TestResult:
    r = TestResult("most_restrictive: deny > ask > allow")
    try:
        assert _most_restrictive("deny", "allow") == "deny"
        assert _most_restrictive("allow", "deny") == "deny"
        assert _most_restrictive("ask", "allow") == "ask"
        assert _most_restrictive("allow", "ask") == "ask"
        assert _most_restrictive("deny", "ask") == "deny"
        assert _most_restrictive("allow", "allow") == "allow"
        assert _most_restrictive("deny", "deny") == "deny"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_deep_merge_basic() -> TestResult:
    r = TestResult("deep_merge: basic dict merge")
    try:
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        overlay = {"b": {"c": 99, "e": 4}, "f": 5}
        result = _deep_merge(base, overlay)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3
        assert result["b"]["e"] == 4
        assert result["f"] == 5
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_deep_merge_categories_most_restrictive() -> TestResult:
    r = TestResult("deep_merge: categories use most-restrictive-wins")
    try:
        base = {"categories": {"git-destructive": "deny", "file-destruction": "allow"}}
        overlay = {"categories": {"git-destructive": "allow", "file-destruction": "deny"}}
        result = _deep_merge(base, overlay)
        # Most restrictive wins: deny beats allow
        assert result["categories"]["git-destructive"] == "deny"
        assert result["categories"]["file-destruction"] == "deny"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_deep_merge_list_replacement() -> TestResult:
    r = TestResult("deep_merge: non-security lists are replaced, security lists are union-merged")
    try:
        # Non-security list: overlay replaces
        base = {"allowed": ["/a/", "/b/"]}
        overlay = {"allowed": ["/c/"]}
        result = _deep_merge(base, overlay)
        assert result["allowed"] == ["/c/"]

        # Security list (ending in _prefixes): union-merged
        base = {"blocked_prefixes": ["/a/", "/b/"]}
        overlay = {"blocked_prefixes": ["/b/", "/c/"]}
        result = _deep_merge(base, overlay)
        assert set(result["blocked_prefixes"]) == {"/a/", "/b/", "/c/"}

        # Security list (ending in _allowlist): union-merged
        base = {"npx_allowlist": ["pkg-a", "pkg-b"]}
        overlay = {"npx_allowlist": ["pkg-b", "pkg-c"]}
        result = _deep_merge(base, overlay)
        assert set(result["npx_allowlist"]) == {"pkg-a", "pkg-b", "pkg-c"}

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_get_category_decision_defaults() -> TestResult:
    r = TestResult("get_category_decision: returns ask by default")
    try:
        config: dict = {}
        assert get_category_decision(config, "destructive_bash", "git-destructive") == "ask"

        config = {"destructive_bash": {"categories": {"git-destructive": "deny"}}}
        assert get_category_decision(config, "destructive_bash", "git-destructive") == "deny"
        assert get_category_decision(config, "destructive_bash", "unknown-cat") == "ask"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_resolve_path() -> TestResult:
    r = TestResult("resolve_path: expands ~ and resolves symlinks")
    try:
        home = os.path.expanduser("~")
        result = resolve_path("~/test/file.txt")
        assert result.startswith(home)
        assert "~" not in result
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_is_in_prefixes() -> TestResult:
    r = TestResult("is_in_prefixes: matches resolved prefixes")
    try:
        assert is_in_prefixes("/tmp/foo/bar.txt", ["/tmp/foo/"])
        assert not is_in_prefixes("/var/log/test.txt", ["/tmp/foo/"])
        assert is_in_prefixes("~/projects/test/a.py", ["~/projects/"])
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_fail_close_decorator() -> TestResult:
    r = TestResult("fail_close: catches exceptions and denies")
    try:
        import io
        from contextlib import redirect_stdout

        @fail_close
        def bad_main() -> None:
            raise ValueError("test error")

        buf = io.StringIO()
        with redirect_stdout(buf):
            bad_main()

        output = json.loads(buf.getvalue().strip())
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", f"Expected deny on error, got {decision}"
        assert "test error" in output["hookSpecificOutput"]["permissionDecisionReason"]
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_decision_helpers_output() -> TestResult:
    r = TestResult("deny/allow/ask: produce correct JSON output")
    try:
        import io
        from contextlib import redirect_stdout

        # Test deny
        buf = io.StringIO()
        with redirect_stdout(buf):
            deny("test reason")
        out = json.loads(buf.getvalue())
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == "test reason"

        # Test allow
        buf = io.StringIO()
        with redirect_stdout(buf):
            allow()
        out = json.loads(buf.getvalue())
        assert out["hookSpecificOutput"]["permissionDecision"] == "allow"

        # Test ask
        buf = io.StringIO()
        with redirect_stdout(buf):
            ask("confirm?")
        out = json.loads(buf.getvalue())
        assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == "confirm?"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("_lib.py unit tests", [
        test_most_restrictive, test_deep_merge_basic,
        test_deep_merge_categories_most_restrictive,
        test_deep_merge_list_replacement, test_get_category_decision_defaults,
        test_resolve_path, test_is_in_prefixes,
        test_fail_close_decorator, test_decision_helpers_output,
    ])


if __name__ == "__main__":
    main()
