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
    ])


if __name__ == "__main__":
    main()
