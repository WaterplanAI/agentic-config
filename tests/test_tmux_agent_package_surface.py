#!/usr/bin/env python3
"""Package-owned tmux-agent migration parity checks."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GLOBAL_EXTENSION = Path.home() / ".pi" / "agent" / "extensions" / "tmux-agent" / "index.ts"
GLOBAL_SKILL = Path.home() / ".pi" / "agent" / "skills" / "tmux-agent" / "SKILL.md"
GLOBAL_SKILL_REFS = Path.home() / ".pi" / "agent" / "skills" / "tmux-agent" / "references"
PACKAGE_EXTENSION = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "tmux-agent" / "index.ts"
PACKAGE_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "SKILL.md"
PACKAGE_SKILL_REFS = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "references"


def strip_frontmatter(markdown_text: str) -> str:
    """Return the markdown body without YAML frontmatter."""
    if not markdown_text.startswith("---\n"):
        return markdown_text
    _frontmatter, body = markdown_text.split("\n---\n", 1)
    return body


def test_package_extension_matches_global_source_exactly() -> None:
    """The repo-owned extension should be a byte-for-byte copy of the proven global logic."""
    assert PACKAGE_EXTENSION.read_text() == GLOBAL_EXTENSION.read_text()


def test_package_skill_body_only_changes_surface_ownership_wording() -> None:
    """The repo-owned skill should preserve the proven body with only package-surface adjustments."""
    package_body = strip_frontmatter(PACKAGE_SKILL.read_text())
    global_body = strip_frontmatter(GLOBAL_SKILL.read_text())
    expected_body = global_body.replace(
        "Use the global `tmux_agent` tool and `/tmux-agent` command for long-lived tmux-backed Pi sessions.",
        "Use the shipped `tmux_agent` tool and `/tmux-agent` command for long-lived tmux-backed Pi sessions.",
        1,
    )
    assert package_body == expected_body


def test_package_skill_references_match_global_source_exactly() -> None:
    """All migrated reference files should match the proven global skill references exactly."""
    global_paths = sorted(path.name for path in GLOBAL_SKILL_REFS.glob("*.md"))
    package_paths = sorted(path.name for path in PACKAGE_SKILL_REFS.glob("*.md"))
    assert package_paths == global_paths
    for filename in global_paths:
        assert (PACKAGE_SKILL_REFS / filename).read_text() == (GLOBAL_SKILL_REFS / filename).read_text()
