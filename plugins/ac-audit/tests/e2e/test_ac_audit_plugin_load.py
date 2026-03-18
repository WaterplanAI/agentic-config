#!/usr/bin/env python3
"""E2E tests: validate ac-audit plugin structure and loadability."""

import ast
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_audit_test_support import TestResult, run_tests  # noqa: E402  # pyright: ignore[reportMissingImports]

REPO_ROOT = Path(__file__).parent.parent.parent.parent


def test_ac_audit_structure() -> TestResult:
    r = TestResult("ac-audit: all required files exist")
    try:
        base = REPO_ROOT / "ac-audit"
        required = [
            ".claude-plugin/plugin.json", "hooks/hooks.json", "config/audit.default.yaml",
            "scripts/hooks/tool-audit.py", "CLAUDE.md", "README.md",
        ]
        for f in required:
            assert (base / f).exists(), f"Missing: {f}"
        json.loads((base / ".claude-plugin/plugin.json").read_text())
        json.loads((base / "hooks/hooks.json").read_text())
        yaml.safe_load((base / "config/audit.default.yaml").read_text())
        ast.parse((base / "scripts/hooks/tool-audit.py").read_text())
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def main() -> None:
    run_tests("ac-audit E2E plugin structure tests", [test_ac_audit_structure])


if __name__ == "__main__":
    main()
