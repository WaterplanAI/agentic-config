#!/usr/bin/env python3
"""E2E tests: validate ac-safety plugin structure and loadability."""

import ast
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_safety_test_support import TestResult, run_tests  # noqa: E402  # pyright: ignore[reportMissingImports]

REPO_ROOT = Path(__file__).parent.parent.parent.parent


def test_ac_safety_structure() -> TestResult:
    r = TestResult("ac-safety: all required files exist")
    try:
        base = REPO_ROOT / "ac-safety"
        required = [
            ".claude-plugin/plugin.json", "hooks/hooks.json", "config/safety.default.yaml",
            "scripts/hooks/_lib.py", "scripts/hooks/credential-guardian.py",
            "scripts/hooks/destructive-bash-guardian.py", "scripts/hooks/write-scope-guardian.py",
            "scripts/hooks/supply-chain-guardian.py", "scripts/hooks/playwright-guardian.py",
            "skills/configure-safety/SKILL.md", "CLAUDE.md", "README.md",
        ]
        for f in required:
            assert (base / f).exists(), f"Missing: {f}"
        # Validate JSON files
        json.loads((base / ".claude-plugin/plugin.json").read_text())
        json.loads((base / "hooks/hooks.json").read_text())
        # Validate YAML
        yaml.safe_load((base / "config/safety.default.yaml").read_text())
        # Validate Python syntax
        for py in base.glob("scripts/hooks/*.py"):
            ast.parse(py.read_text())
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def main() -> None:
    run_tests("ac-safety E2E plugin structure tests", [test_ac_safety_structure])


if __name__ == "__main__":
    main()
