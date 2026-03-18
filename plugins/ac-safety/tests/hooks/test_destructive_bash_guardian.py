#!/usr/bin/env python3
"""Unit tests for destructive-bash-guardian hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "destructive-bash-guardian.py"


def run_hook(command: str) -> dict:
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    hook_out = output.get("hookSpecificOutput", {})
    return {"decision": hook_out.get("permissionDecision", "allow"), "reason": hook_out.get("permissionDecisionReason", "")}


def test_blocks_rm_rf_home() -> TestResult:
    r = TestResult("Blocks rm -rf ~/")
    try:
        out = run_hook("rm -rf ~/important_stuff")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_git_force_push() -> TestResult:
    r = TestResult("Blocks git push --force")
    try:
        out = run_hook("git push origin main --force")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_terraform_destroy() -> TestResult:
    r = TestResult("Blocks terraform destroy")
    try:
        out = run_hook("terraform destroy -auto-approve")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_safe_commands() -> TestResult:
    r = TestResult("Allows safe commands (ls, git status)")
    try:
        for cmd in ["ls -la", "git status", "echo hello", "cat README.md"]:
            out = run_hook(cmd)
            assert out["decision"] == "allow", f"Expected allow for '{cmd}', got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_non_bash_tools() -> TestResult:
    r = TestResult("Allows non-Bash tools")
    try:
        result = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/test"}}),
            capture_output=True, text=True,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "allow", f"Expected allow for Read, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_home_no_slash() -> TestResult:
    r = TestResult("Blocks rm -rf ~ (no trailing slash)")
    try:
        out = run_hook("rm -rf ~")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_parent_dir() -> TestResult:
    r = TestResult("Blocks rm -rf .. (parent directory)")
    try:
        out = run_hook("rm -rf ..")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_parent_relative() -> TestResult:
    r = TestResult("Blocks rm -rf ../foo (parent-relative path)")
    try:
        out = run_hook("rm -rf ../foo")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_git_push_origin_f() -> TestResult:
    r = TestResult("Blocks git push origin -f (flag after remote)")
    try:
        out = run_hook("git push origin -f")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_git_push_origin_main_f() -> TestResult:
    r = TestResult("Blocks git push origin main -f (flag after branch)")
    try:
        out = run_hook("git push origin main -f")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_double_dash_home() -> TestResult:
    """NEW-01: rm -rf -- ~ (POSIX end-of-options bypass)"""
    r = TestResult("Blocks rm -rf -- ~ (POSIX -- separator)")
    try:
        out = run_hook("rm -rf -- ~")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_r_f_double_dash_home() -> TestResult:
    """NEW-01+07: rm -r -f -- ~ (split flags + -- separator)"""
    r = TestResult("Blocks rm -r -f -- ~ (split flags + --)")
    try:
        out = run_hook("rm -r -f -- ~")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_subshell() -> TestResult:
    """NEW-02: (rm -rf ~) subshell bypass"""
    r = TestResult("Blocks (rm -rf ~) subshell")
    try:
        out = run_hook("(rm -rf ~)")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_backtick() -> TestResult:
    """NEW-02: `rm -rf ~` backtick bypass"""
    r = TestResult("Blocks `rm -rf ~` backtick")
    try:
        out = run_hook("`rm -rf ~`")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_dollar_subshell() -> TestResult:
    """NEW-02: $(rm -rf ~) dollar-subshell bypass"""
    r = TestResult("Blocks $(rm -rf ~) dollar-subshell")
    try:
        out = run_hook("$(rm -rf ~)")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_split_flags() -> TestResult:
    """NEW-07: rm -r -f ~ (split flags, not combined -rf)"""
    r = TestResult("Blocks rm -r -f ~ (split flags)")
    try:
        out = run_hook("rm -r -f ~")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_split_flags_reversed() -> TestResult:
    """NEW-07: rm -f -r ~ (split flags reversed)"""
    r = TestResult("Blocks rm -f -r ~ (split flags reversed)")
    try:
        out = run_hook("rm -f -r ~")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_find_delete() -> TestResult:
    """NEW-07: find ~ -delete"""
    r = TestResult("Blocks find ~ -delete")
    try:
        out = run_hook("find ~ -delete")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_find_exec_rm() -> TestResult:
    """NEW-07: find ~ -exec rm -rf {} +"""
    r = TestResult("Blocks find ~ -exec rm")
    try:
        out = run_hook("find ~ -exec rm -rf {} +")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_xargs_rm() -> TestResult:
    """NEW-07: echo ~ | xargs rm -rf"""
    r = TestResult("Blocks xargs rm")
    try:
        out = run_hook("echo ~ | xargs rm -rf")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_dollar_home() -> TestResult:
    """H-01: rm -rf $HOME (shell variable bypass)"""
    r = TestResult("Blocks rm -rf $HOME")
    try:
        out = run_hook("rm -rf $HOME")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_dollar_brace_home() -> TestResult:
    """H-01: rm -rf ${HOME} (braced shell variable bypass)"""
    r = TestResult("Blocks rm -rf ${HOME}")
    try:
        out = run_hook("rm -rf ${HOME}")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_dollar_home_subdir() -> TestResult:
    """H-01: rm -rf $HOME/Documents (variable + subdirectory)"""
    r = TestResult("Blocks rm -rf $HOME/Documents")
    try:
        out = run_hook("rm -rf $HOME/Documents")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_git_push_combined_uf() -> TestResult:
    """H-03: git push -uf origin main (combined-flag bypass)"""
    r = TestResult("Blocks git push -uf origin main")
    try:
        out = run_hook("git push -uf origin main")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_git_push_force_with_lease() -> TestResult:
    """Regression: git push --force-with-lease should still be allowed"""
    r = TestResult("Allows git push --force-with-lease")
    try:
        out = run_hook("git push --force-with-lease origin feat")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_quoted_dollar_home() -> TestResult:
    """H-NEW-02: rm -rf "$HOME" (quoted variable bypass)"""
    r = TestResult('Blocks rm -rf "$HOME"')
    try:
        out = run_hook('rm -rf "$HOME"')
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_single_quoted_dollar_home() -> TestResult:
    """H-NEW-02: rm -rf '$HOME' (single-quoted variable bypass)"""
    r = TestResult("Blocks rm -rf '$HOME'")
    try:
        out = run_hook("rm -rf '$HOME'")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_quoted_brace_home() -> TestResult:
    """H-NEW-02: rm -rf "${HOME}" (quoted braced variable bypass)"""
    r = TestResult('Blocks rm -rf "${HOME}"')
    try:
        out = run_hook('rm -rf "${HOME}"')
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_quoted_tilde() -> TestResult:
    """H-NEW-02: rm -rf "~" (quoted tilde bypass)"""
    r = TestResult('Blocks rm -rf "~"')
    try:
        out = run_hook('rm -rf "~"')
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_quoted_dollar_home_subdir() -> TestResult:
    """H-005-01: rm -rf "$HOME"/Documents (quoted variable + subdirectory bypass)"""
    r = TestResult('Blocks rm -rf "$HOME"/Documents')
    try:
        out = run_hook('rm -rf "$HOME"/Documents')
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_rm_rf_quoted_brace_home_subdir() -> TestResult:
    """H-005-01: rm -rf "${HOME}"/Documents (quoted braced variable + subdirectory bypass)"""
    r = TestResult('Blocks rm -rf "${HOME}"/Documents')
    try:
        out = run_hook('rm -rf "${HOME}"/Documents')
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_eval_rm_rf_tilde() -> TestResult:
    """M-NEW-01: eval 'rm -rf ~' (indirect execution bypass)"""
    r = TestResult("Blocks eval 'rm -rf ~'")
    try:
        out = run_hook("eval 'rm -rf ~'")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_blocks_bash_c_rm_rf_tilde() -> TestResult:
    """M-NEW-01: bash -c 'rm -rf ~' (indirect execution bypass)"""
    r = TestResult("Blocks bash -c 'rm -rf ~'")
    try:
        out = run_hook("bash -c 'rm -rf ~'")
        assert out["decision"] == "deny", f"Expected deny, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("destructive-bash-guardian unit tests", [
        test_blocks_rm_rf_home, test_blocks_git_force_push,
        test_blocks_terraform_destroy, test_allows_safe_commands,
        test_allows_non_bash_tools,
        test_blocks_rm_rf_home_no_slash,
        test_blocks_rm_rf_parent_dir,
        test_blocks_rm_rf_parent_relative,
        test_blocks_git_push_origin_f,
        test_blocks_git_push_origin_main_f,
        # NEW-01: POSIX -- separator bypass
        test_blocks_rm_rf_double_dash_home,
        test_blocks_rm_r_f_double_dash_home,
        # NEW-02: subshell/backtick/dollar-subshell bypass
        test_blocks_rm_rf_subshell,
        test_blocks_rm_rf_backtick,
        test_blocks_rm_rf_dollar_subshell,
        # NEW-07: find -delete, xargs rm, split flags
        test_blocks_rm_split_flags,
        test_blocks_rm_split_flags_reversed,
        test_blocks_find_delete,
        test_blocks_find_exec_rm,
        test_blocks_xargs_rm,
        # H-01: $HOME / ${HOME} variable expansion bypass
        test_blocks_rm_rf_dollar_home,
        test_blocks_rm_rf_dollar_brace_home,
        test_blocks_rm_rf_dollar_home_subdir,
        # H-03: git push combined-flag bypass
        test_blocks_git_push_combined_uf,
        test_allows_git_push_force_with_lease,
        # H-NEW-02: quoted variable bypass
        test_blocks_rm_rf_quoted_dollar_home,
        test_blocks_rm_rf_single_quoted_dollar_home,
        test_blocks_rm_rf_quoted_brace_home,
        test_blocks_rm_rf_quoted_tilde,
        # H-005-01: quoted $HOME with subdirectory
        test_blocks_rm_rf_quoted_dollar_home_subdir,
        test_blocks_rm_rf_quoted_brace_home_subdir,
        # M-NEW-01: eval / bash -c indirect execution bypass
        test_blocks_eval_rm_rf_tilde,
        test_blocks_bash_c_rm_rf_tilde,
    ])


if __name__ == "__main__":
    main()
