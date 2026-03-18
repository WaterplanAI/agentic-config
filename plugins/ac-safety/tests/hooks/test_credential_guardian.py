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
        raise
    return r


def test_blocks_aws_grep() -> TestResult:
    r = TestResult("Blocks Grep in ~/.aws/")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~/.aws/credentials"), "pattern": "secret"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_project_read() -> TestResult:
    r = TestResult("Allows Read in ~/projects/")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/projects/test/file.py")})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_claude_settings() -> TestResult:
    r = TestResult("Allows Read of ~/.claude/settings.json")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/.claude/settings.json")})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_non_read_tools() -> TestResult:
    r = TestResult("Allows non-Read tools (Bash)")
    try:
        out = run_hook("Bash", {"command": "ls"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_relative_glob_from_home() -> TestResult:
    r = TestResult("Blocks Glob(path=~, pattern=.ssh/*)")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": ".ssh/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_relative_grep_glob_from_home() -> TestResult:
    r = TestResult("Blocks Grep(path=~, glob=.aws/*)")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~"), "glob": ".aws/*", "pattern": "secret"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
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
        raise
    return r


def test_blocks_npmrc_outside_project_roots() -> TestResult:
    r = TestResult("Blocks .npmrc outside project roots")
    try:
        out = run_hook("Read", {"file_path": "/var/data/.npmrc"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        assert "credential" in out["reason"].lower() or "blocked" in out["reason"].lower()
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_npmrc_in_project() -> TestResult:
    r = TestResult("Allows .npmrc inside project roots")
    try:
        out = run_hook("Read", {"file_path": os.path.expanduser("~/projects/myapp/.npmrc")})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_netrc_outside_project_roots() -> TestResult:
    r = TestResult("Blocks .netrc outside project roots and /tmp/")
    try:
        out = run_hook("Read", {"file_path": "/opt/config/.netrc"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_glob_wildcard_stripping() -> TestResult:
    r = TestResult("Blocks Glob with wildcard pattern targeting blocked dir")
    try:
        # Pattern: ~/.ssh/**/*.pub -- the concrete prefix ~/.ssh/ should be blocked
        out = run_hook("Glob", {"path": os.path.expanduser("~/.ssh"), "pattern": "**/*.pub"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_grep_glob_wildcard_stripping() -> TestResult:
    r = TestResult("Blocks Grep with glob wildcard targeting blocked dir")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~/.aws"), "glob": "**/*.json", "pattern": "key"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_recursive_glob_ssh_from_home() -> TestResult:
    """NEW-06: Glob(pattern='**/.ssh/*', path='~') bypasses credential-guardian"""
    r = TestResult("Blocks Glob(pattern='**/.ssh/*', path='~')")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": "**/.ssh/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_recursive_glob_aws_from_home() -> TestResult:
    """NEW-06: Glob(pattern='**/.aws/*', path='~') should also be blocked"""
    r = TestResult("Blocks Glob(pattern='**/.aws/*', path='~')")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": "**/.aws/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_recursive_grep_ssh_from_home() -> TestResult:
    """NEW-06: Grep(path='~', glob='**/.ssh/*') should also be blocked"""
    r = TestResult("Blocks Grep(path='~', glob='**/.ssh/*')")
    try:
        out = run_hook("Grep", {"path": os.path.expanduser("~"), "glob": "**/.ssh/*", "pattern": "key"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_grep_root_glob_aws() -> TestResult:
    """H-02: Grep(path='/', glob='**/.aws/*') must be blocked"""
    r = TestResult("Blocks Grep(path='/', glob='**/.aws/*')")
    try:
        out = run_hook("Grep", {"path": "/", "glob": "**/.aws/*", "pattern": "secret"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_grep_root_glob_ssh() -> TestResult:
    """H-02: Grep(path='/', glob='**/.ssh/*') must be blocked"""
    r = TestResult("Blocks Grep(path='/', glob='**/.ssh/*')")
    try:
        out = run_hook("Grep", {"path": "/", "glob": "**/.ssh/*", "pattern": "key"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_glob_root_docker() -> TestResult:
    """H-NEW-01: Glob(path='/', pattern='**/.docker/*') must be blocked"""
    r = TestResult("Blocks Glob(path='/', pattern='**/.docker/*')")
    try:
        out = run_hook("Glob", {"path": "/", "pattern": "**/.docker/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_glob_root_gnupg() -> TestResult:
    """H-NEW-01: Glob(path='/', pattern='**/.gnupg/*') must be blocked"""
    r = TestResult("Blocks Glob(path='/', pattern='**/.gnupg/*')")
    try:
        out = run_hook("Glob", {"path": "/", "pattern": "**/.gnupg/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_tmp_traversal_ssh() -> TestResult:
    """H-005-02: /tmp/../Users/xxx/.ssh traversal on macOS"""
    r = TestResult("Blocks /tmp/../~/.ssh traversal")
    try:
        home = os.path.expanduser("~")
        crafted = f"/tmp/../{home.lstrip('/')}/.ssh/id_rsa"
        out = run_hook("Read", {"file_path": crafted})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_var_traversal_aws() -> TestResult:
    """H-005-02: /var/../Users/xxx/.aws traversal on macOS"""
    r = TestResult("Blocks /var/../~/.aws traversal")
    try:
        home = os.path.expanduser("~")
        crafted = f"/var/../{home.lstrip('/')}/.aws/credentials"
        out = run_hook("Read", {"file_path": crafted})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_broad_glob_from_home() -> TestResult:
    """Issue 1: Glob(path='~', pattern='**/*') broad recursive scan from HOME -> DENY."""
    r = TestResult("Denies Glob(path='~', pattern='**/*') broad scan")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": "**/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_broad_grep_from_root() -> TestResult:
    """Issue 1: Grep(path='/', glob='**/*', pattern='PRIVATE KEY') broad scan -> DENY."""
    r = TestResult("Denies Grep(path='/', pattern='PRIVATE KEY') broad scan")
    try:
        out = run_hook("Grep", {"path": "/", "glob": "**/*", "pattern": "PRIVATE KEY"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_broad_glob_tilde_str() -> TestResult:
    """Issue 1: Glob(path='~/', pattern='**/*.pem') from HOME -> DENY."""
    r = TestResult("Denies Glob(path='~/', pattern='**/*.pem') broad scan")
    try:
        out = run_hook("Glob", {"path": "~/", "pattern": "**/*.pem"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_denies_broad_glob_from_root() -> TestResult:
    """Issue 3: Glob(path='/', pattern='**/*') broad scan -> DENY (not ask)."""
    r = TestResult("Denies Glob(path='/', pattern='**/*') with broad-scan: deny")
    try:
        out = run_hook("Glob", {"path": "/", "pattern": "**/*"})
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_broad_glob_in_project() -> TestResult:
    """Issue 1: Glob(path='~/projects/myapp', pattern='**/*') in project root is OK."""
    r = TestResult("Allows Glob in project root with **/*")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~/projects/myapp"), "pattern": "**/*"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_non_recursive_glob_from_home() -> TestResult:
    """Issue 1: Glob(path='~', pattern='*.txt') non-recursive from HOME is OK."""
    r = TestResult("Allows non-recursive Glob from HOME")
    try:
        out = run_hook("Glob", {"path": os.path.expanduser("~"), "pattern": "*.txt"})
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_empty_path_glob_ssh() -> TestResult:
    """MEDIUM-002: Glob(path='', pattern='**/.ssh/*') from HOME should DENY."""
    r = TestResult("Blocks Glob(path='', pattern='**/.ssh/*') empty base_path")
    try:
        # Run with CWD=HOME to simulate the bypass scenario
        home = os.path.expanduser("~")
        result = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps({"tool_name": "Glob", "tool_input": {"path": "", "pattern": "**/.ssh/*"}}),
            capture_output=True, text=True, cwd=home,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
        assert decision != "allow", f"Expected deny/ask, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_blocks_empty_path_grep_aws() -> TestResult:
    """MEDIUM-002: Grep(path='', glob='**/.aws/*') from HOME should DENY."""
    r = TestResult("Blocks Grep(path='', glob='**/.aws/*') empty base_path")
    try:
        home = os.path.expanduser("~")
        result = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps({"tool_name": "Grep", "tool_input": {"path": "", "glob": "**/.aws/*", "pattern": "secret"}}),
            capture_output=True, text=True, cwd=home,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
        assert decision != "allow", f"Expected deny/ask, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_allows_empty_path_safe_pattern() -> TestResult:
    """MEDIUM-002 regression: Glob(path='', pattern='*.py') from project dir should ALLOW."""
    r = TestResult("Allows Glob(path='', pattern='*.py') from project dir")
    try:
        import tempfile
        project_dir = os.path.expanduser("~/projects/myapp")
        # Use a temp dir under ~/projects/ as CWD if the target doesn't exist
        if not os.path.isdir(project_dir):
            tmpdir = tempfile.mkdtemp(prefix="myapp_", dir=os.path.expanduser("~/projects"))
        else:
            tmpdir = project_dir
        try:
            result = subprocess.run(
                [str(HOOK_PATH)],
                input=json.dumps({"tool_name": "Glob", "tool_input": {"path": "", "pattern": "*.py"}}),
                capture_output=True, text=True, cwd=tmpdir,
            )
            output = json.loads(result.stdout)
            decision = output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
            assert decision == "allow", f"Expected allow, got {decision}"
        finally:
            if tmpdir != project_dir:
                os.rmdir(tmpdir)
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
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
        test_blocks_npmrc_outside_project_roots,
        test_allows_npmrc_in_project,
        test_blocks_netrc_outside_project_roots,
        test_glob_wildcard_stripping,
        test_grep_glob_wildcard_stripping,
        # NEW-06: recursive glob pattern bypass
        test_blocks_recursive_glob_ssh_from_home,
        test_blocks_recursive_glob_aws_from_home,
        test_blocks_recursive_grep_ssh_from_home,
        # H-02: Grep with root base_path + blocked glob segment
        test_blocks_grep_root_glob_aws,
        test_blocks_grep_root_glob_ssh,
        # H-NEW-01: root path bypass regression (path="/")
        test_blocks_glob_root_docker,
        test_blocks_glob_root_gnupg,
        # H-005-02: macOS /private symlink traversal
        test_blocks_tmp_traversal_ssh,
        test_blocks_var_traversal_aws,
        # Issue 1: broad recursive scan bypass
        test_blocks_broad_glob_from_home,
        test_blocks_broad_grep_from_root,
        test_blocks_broad_glob_tilde_str,
        test_allows_broad_glob_in_project,
        test_allows_non_recursive_glob_from_home,
        # MEDIUM-002: empty base_path bypass
        test_blocks_empty_path_glob_ssh,
        test_blocks_empty_path_grep_aws,
        test_allows_empty_path_safe_pattern,
        # Issue 3: broad-scan category now defaults to deny
        test_denies_broad_glob_from_root,
    ])


if __name__ == "__main__":
    main()
