#!/usr/bin/env python3
"""Regression tests for harden-supply-chain-sec safety guidance."""

import re
from pathlib import Path

SKILL_PATH = (
    Path(__file__).parent.parent / "skills" / "harden-supply-chain-sec" / "SKILL.md"
)


def _read_skill() -> str:
    return SKILL_PATH.read_text()


def test_detection_stays_read_only() -> None:
    content = _read_skill()
    assert "Do not install, enable, or update tooling during preflight." in content
    assert "do NOT run `corepack enable` during detection" in content
    assert "then `corepack enable` if available" not in content


def test_remote_shell_installers_are_not_recommended() -> None:
    content = _read_skill()
    assert 'curl -fsSL https://bun.sh/install | bash -s "bun-v<version>"' not in content
    assert 'curl -LsSf https://astral.sh/uv/<version>/install.sh | sh' not in content

    dangerous_lines: list[str] = []
    for line in content.splitlines():
        if re.search(r"curl\s+[^\n`]*\|\s*(?:bash|sh)\b", line):
            if not any(
                marker in line
                for marker in (
                    "Never recommend or run",
                    "Do NOT use or display",
                    "without `curl | sh`",
                )
            ):
                dangerous_lines.append(line)
    assert dangerous_lines == []


def test_manager_update_commands_require_confirmation() -> None:
    content = _read_skill()
    assert "header: `Prerequisite`" in content
    assert "Run the age-verified install/update command for <manager> now?" in content
    assert 'label: "Run now"' in content


def test_missing_audit_tools_require_confirmation() -> None:
    content = _read_skill()
    assert "header: `Audit tool`" in content
    assert "`<tool_name>` is not installed. Run the install command now?" in content
    assert "Recommend installation of the tool" not in content


def test_lockfile_regeneration_requires_confirmation() -> None:
    content = _read_skill()
    assert 'label: "Auto-fix declarations"' in content
    assert 'label: "Auto-fix and re-generate"' not in content
    assert "Run the lockfile re-generation command for <manager> now?" in content


def test_uv_duration_guidance_is_preserved() -> None:
    content = _read_skill()
    assert 'If installed >= 0.9.17: use duration string format (e.g., `"7 days"`)' in content
