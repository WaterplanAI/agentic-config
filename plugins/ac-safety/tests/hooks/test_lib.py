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
    _UNION_MERGE_SUFFIXES,
    _deep_merge,
    _is_broad_path,
    _most_restrictive,
    _strip_broad_entries,
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
    return r


def test_strip_broad_entries_removes_root() -> TestResult:
    r = TestResult("_strip_broad_entries: strips / from security lists")
    try:
        config = {"allowed_project_roots": ["/", "~/projects/"]}
        result = _strip_broad_entries(config)
        resolved_roots = [os.path.realpath(os.path.expanduser(p)) for p in result["allowed_project_roots"]]
        assert os.path.realpath("/") not in resolved_roots, "/ should be stripped"
        assert any("projects" in p for p in resolved_roots), "~/projects/ should remain"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_removes_home() -> TestResult:
    r = TestResult("_strip_broad_entries: strips ~/ from security allowlist lists")
    try:
        home = os.path.expanduser("~")
        config = {"allowed_write_prefixes": ["~/", "~/.ssh/", home]}
        result = _strip_broad_entries(config)
        resolved = [os.path.realpath(os.path.expanduser(p)) for p in result["allowed_write_prefixes"]]
        assert os.path.realpath(home) not in resolved, "~/ should be stripped"
        assert any(".ssh" in p for p in resolved), "~/.ssh/ should remain"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_ignores_non_security_lists() -> TestResult:
    r = TestResult("_strip_broad_entries: ignores non-security-suffix lists")
    try:
        config = {"random_list": ["/", "~/"], "allowed_project_roots": ["~/projects/"]}
        result = _strip_broad_entries(config)
        # Non-security list should be untouched
        assert "/" in result["random_list"]
        assert "~/" in result["random_list"]
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_nested() -> TestResult:
    r = TestResult("_strip_broad_entries: recurses into nested dicts")
    try:
        config = {"credential_guardian": {"allowed_write_prefixes": ["/", "~/.ssh/"]}}
        result = _strip_broad_entries(config)
        resolved = [os.path.realpath(os.path.expanduser(p)) for p in result["credential_guardian"]["allowed_write_prefixes"]]
        assert os.path.realpath("/") not in resolved, "/ should be stripped from nested list"
        assert any(".ssh" in p for p in resolved), "~/.ssh/ should remain"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_resolve_path_private_normalization() -> TestResult:
    r = TestResult("resolve_path: normalizes /private/Users/... to /Users/... on macOS")
    try:
        import platform
        if platform.system() != "Darwin":
            # Only relevant on macOS; skip on other platforms
            r.mark_pass()
            return r
        home = os.path.expanduser("~")
        # Simulate: /tmp/../Users/foo -> realpath -> /private/Users/foo
        # resolve_path should strip /private prefix since /private/Users doesn't
        # really exist on macOS (the real dirs are /private/tmp, /private/var, /private/etc)
        crafted = f"/tmp/../{home.lstrip('/')}"
        resolved = resolve_path(crafted)
        assert not resolved.startswith("/private/Users"), (
            f"Expected /private prefix stripped, got {resolved}"
        )
        assert resolved.startswith(home), f"Expected prefix {home}, got {resolved}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_resolve_path_private_preserves_real_dirs() -> TestResult:
    r = TestResult("resolve_path: preserves /private/tmp and /private/var on macOS")
    try:
        import platform
        if platform.system() != "Darwin":
            r.mark_pass()
            return r
        # /tmp resolves to /private/tmp on macOS -- should stay as-is
        resolved_tmp = resolve_path("/tmp")
        assert resolved_tmp == "/private/tmp", f"Expected /private/tmp, got {resolved_tmp}"
        resolved_var = resolve_path("/var")
        assert resolved_var == "/private/var", f"Expected /private/var, got {resolved_var}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_union_merge_roots_suffix() -> TestResult:
    r = TestResult("_deep_merge: _roots suffix is union-merged (not replaced)")
    try:
        assert "_roots" in _UNION_MERGE_SUFFIXES, "_roots not in _UNION_MERGE_SUFFIXES"
        base = {"allowed_project_roots": ["~/projects/", "~/work/"]}
        overlay = {"allowed_project_roots": ["~/projects/", "~/extra/"]}
        result = _deep_merge(base, overlay)
        roots = set(result["allowed_project_roots"])
        assert roots == {"~/projects/", "~/work/", "~/extra/"}, f"Expected union-merge, got {roots}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_deep_merge_null_does_not_overwrite_dict() -> TestResult:
    r = TestResult("deep_merge: null overlay does not overwrite existing dict (Issue 1)")
    try:
        base = {"credential_guardian": {"categories": {"ssh-keys": "deny"}}}
        overlay = {"credential_guardian": None}
        result = _deep_merge(base, overlay)
        # null must NOT replace the dict
        assert isinstance(result["credential_guardian"], dict), (
            f"Expected dict, got {type(result['credential_guardian'])}"
        )
        assert result["credential_guardian"]["categories"]["ssh-keys"] == "deny"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_deep_merge_null_does_not_overwrite_scalar() -> TestResult:
    r = TestResult("deep_merge: null overlay does not overwrite existing scalar")
    try:
        base = {"max_retries": 3}
        overlay = {"max_retries": None}
        result = _deep_merge(base, overlay)
        assert result["max_retries"] == 3, f"Expected 3, got {result['max_retries']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_deep_merge_null_does_not_overwrite_list() -> TestResult:
    r = TestResult("deep_merge: null overlay does not overwrite existing list")
    try:
        base = {"blocked_prefixes": ["~/.ssh/", "~/.aws/"]}
        overlay = {"blocked_prefixes": None}
        result = _deep_merge(base, overlay)
        assert result["blocked_prefixes"] == ["~/.ssh/", "~/.aws/"], (
            f"Expected original list, got {result['blocked_prefixes']}"
        )
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_deep_merge_null_adds_new_key() -> TestResult:
    r = TestResult("deep_merge: null for new key is skipped (never introduces None)")
    try:
        base = {"a": 1}
        overlay = {"b": None}
        result = _deep_merge(base, overlay)
        # New key with None value should be skipped entirely
        assert "b" not in result, f"Expected 'b' absent, got {result}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_rejects_users_dir() -> TestResult:
    r = TestResult("_strip_broad_entries: strips /Users and /home (Issue 2)")
    try:
        config = {"allowed_project_roots": ["/Users", "/home", "~/projects/"]}
        result = _strip_broad_entries(config)
        resolved_roots = [os.path.realpath(os.path.expanduser(p)) for p in result["allowed_project_roots"]]
        home = os.path.realpath(os.path.expanduser("~"))
        # /Users and /home should be stripped (they are ancestors of HOME or top-level)
        for root in resolved_roots:
            assert not home.startswith(root.rstrip("/") + "/"), (
                f"HOME ancestor {root} should have been stripped"
            )
        assert any("projects" in p for p in resolved_roots), "~/projects/ should remain"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_rejects_home_ancestors() -> TestResult:
    r = TestResult("_strip_broad_entries: strips any ancestor of HOME")
    try:
        home = os.path.realpath(os.path.expanduser("~"))
        # Build ancestor: e.g. if HOME is /Users/john, ancestor is /Users
        parent = os.path.dirname(home)
        if parent and parent != home:  # Ensure we have a real parent
            config = {"allowed_project_roots": [parent, "~/projects/"]}
            result = _strip_broad_entries(config)
            resolved_roots = [os.path.realpath(os.path.expanduser(p)) for p in result["allowed_project_roots"]]
            assert os.path.realpath(parent) not in resolved_roots, (
                f"HOME ancestor {parent} should be stripped"
            )
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_rejects_top_level_dirs() -> TestResult:
    r = TestResult("_strip_broad_entries: strips top-level dirs like /Applications, /System")
    try:
        # Use dirs that resolve to true top-level paths (len(parts) <= 2).
        # On macOS, /tmp -> /private/tmp (3 parts), so use /Applications, /System instead.
        config = {"allowed_project_roots": ["/Applications", "/System", "~/projects/"]}
        result = _strip_broad_entries(config)
        resolved_roots = [os.path.realpath(os.path.expanduser(p)) for p in result["allowed_project_roots"]]
        # Single-component top-level paths should be stripped
        for raw in ["/Applications", "/System"]:
            resolved = os.path.realpath(raw)
            assert resolved not in resolved_roots, f"Top-level dir {raw} ({resolved}) should be stripped"
        assert any("projects" in p for p in resolved_roots), "~/projects/ should remain"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_strip_broad_entries_preserves_blocked_prefixes() -> TestResult:
    r = TestResult("_strip_broad_entries: preserves broad entries in blocked_* deny-lists (MEDIUM-1)")
    try:
        config = {
            "blocked_write_prefixes": ["/usr/", "/bin/", "/sbin/", "~/.ssh/"],
            "allowed_project_roots": ["/usr/", "~/projects/"],
        }
        result = _strip_broad_entries(config)
        # Deny-list entries must survive -- stripping them weakens security
        blocked = result["blocked_write_prefixes"]
        assert "/usr/" in blocked, f"/usr/ missing from blocked_write_prefixes: {blocked}"
        assert "/bin/" in blocked, f"/bin/ missing from blocked_write_prefixes: {blocked}"
        assert "/sbin/" in blocked, f"/sbin/ missing from blocked_write_prefixes: {blocked}"
        assert "~/.ssh/" in blocked, f"~/.ssh/ missing from blocked_write_prefixes: {blocked}"
        # Allowlist entries with broad paths should still be stripped
        allowed = result["allowed_project_roots"]
        assert "/usr/" not in allowed, "/usr/ should be stripped from allowed_project_roots"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_is_broad_path_detects_ancestors() -> TestResult:
    r = TestResult("_is_broad_path: correctly identifies HOME ancestors")
    try:
        home = os.path.realpath(os.path.expanduser("~"))
        parent = os.path.dirname(home)
        assert _is_broad_path(os.path.realpath("/")), "/ should be broad"
        assert _is_broad_path(os.path.realpath(home)), "HOME should be broad"
        if parent and parent != "/":
            assert _is_broad_path(os.path.realpath(parent)), f"HOME parent {parent} should be broad"
        # A project dir deep inside home should NOT be broad
        assert not _is_broad_path(os.path.realpath(os.path.expanduser("~/projects/myapp"))), (
            "~/projects/myapp should NOT be broad"
        )
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("_lib.py unit tests", [
        test_most_restrictive, test_deep_merge_basic,
        test_deep_merge_categories_most_restrictive,
        test_deep_merge_list_replacement, test_get_category_decision_defaults,
        test_resolve_path, test_is_in_prefixes,
        test_fail_close_decorator, test_decision_helpers_output,
        test_strip_broad_entries_removes_root,
        test_strip_broad_entries_removes_home,
        test_strip_broad_entries_ignores_non_security_lists,
        test_strip_broad_entries_nested,
        test_resolve_path_private_normalization,
        test_resolve_path_private_preserves_real_dirs,
        test_union_merge_roots_suffix,
        test_deep_merge_null_does_not_overwrite_dict,
        test_deep_merge_null_does_not_overwrite_scalar,
        test_deep_merge_null_does_not_overwrite_list,
        test_deep_merge_null_adds_new_key,
        test_strip_broad_entries_rejects_users_dir,
        test_strip_broad_entries_rejects_home_ancestors,
        test_strip_broad_entries_rejects_top_level_dirs,
        test_strip_broad_entries_preserves_blocked_prefixes,
        test_is_broad_path_detects_ancestors,
    ])


if __name__ == "__main__":
    main()
