#!/usr/bin/env python3
"""Package-owned tmux-agent migration parity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_HASHES = json.loads((PROJECT_ROOT / "tests" / "fixtures" / "tmux_agent_global_source_hashes.json").read_text())
PACKAGE_EXTENSION = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "tmux-agent" / "index.ts"
PACKAGE_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "SKILL.md"
PACKAGE_SKILL_REFS = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "references"


def strip_frontmatter(markdown_text: str) -> str:
    """Return the markdown body without YAML frontmatter."""
    if not markdown_text.startswith("---\n"):
        return markdown_text
    _frontmatter, body = markdown_text.split("\n---\n", 1)
    return body


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest for UTF-8 text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 digest for raw bytes."""
    return hashlib.sha256(content).hexdigest()


def test_package_extension_matches_repo_owned_global_source_hash() -> None:
    """The repo-owned extension should match the committed global-source fingerprint exactly."""
    assert sha256_bytes(PACKAGE_EXTENSION.read_bytes()) == FIXTURE_HASHES["extension_sha256"]


def test_package_skill_body_only_changes_surface_ownership_wording() -> None:
    """The repo-owned skill should preserve the proven body with only package-surface wording adjustments."""
    package_body = strip_frontmatter(PACKAGE_SKILL.read_text())
    normalized_to_global_wording = package_body.replace(
        "Use the shipped `tmux_agent` tool and `/tmux-agent` command for long-lived tmux-backed Pi sessions.",
        "Use the global `tmux_agent` tool and `/tmux-agent` command for long-lived tmux-backed Pi sessions.",
        1,
    )
    assert sha256_text(normalized_to_global_wording) == FIXTURE_HASHES["skill_body_sha256"]


def test_package_skill_references_match_repo_owned_global_source_hashes() -> None:
    """All migrated reference files should match the committed global-source fingerprints exactly."""
    expected_hashes = FIXTURE_HASHES["reference_sha256"]
    expected_paths = sorted(expected_hashes)
    package_paths = sorted(path.name for path in PACKAGE_SKILL_REFS.glob("*.md"))
    assert package_paths == expected_paths
    for filename in expected_paths:
        assert sha256_bytes((PACKAGE_SKILL_REFS / filename).read_bytes()) == expected_hashes[filename]
