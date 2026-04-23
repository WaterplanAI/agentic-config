#!/usr/bin/env python3
"""Smoke tests for the canonical generator after shipped-surface migration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = PROJECT_ROOT / "tools" / "generate_canonical_wrappers.py"
RELEASE_VERSION = (PROJECT_ROOT / "VERSION").read_text().strip()


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the canonical generator CLI."""
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_generator_check_mode_is_clean() -> None:
    """The committed canonical scope should already be in sync."""
    result = run_generator("--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Canonical outputs are up to date." in result.stdout


def test_generator_covers_current_canonical_scope() -> None:
    """The canonical tree should cover shipped skills plus explicit deferred pressure cases."""
    canonical_skills = sorted(PROJECT_ROOT.glob("canonical/*/skills/*/skill.yaml"))
    assert len(canonical_skills) == 42
    assert (PROJECT_ROOT / "canonical" / "ac-audit" / "skills" / "configure-audit" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-safety" / "skills" / "harden-supply-chain-sec" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-tools" / "skills" / "gcp-setup" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-tools" / "skills" / "gsuite" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-tools" / "skills" / "setup-voice-mode" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-git" / "skills" / "worktree" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-qa" / "skills" / "gh-pr-review" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "product-manager" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-ospec" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-roadmap" / "skill.yaml").exists()
    assert (PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-subagent" / "skill.yaml").exists()


def test_generator_plugin_filter_stays_within_seeded_scope() -> None:
    """Plugin filtering should cover the canonical workflow scope without reintroducing removed manual siblings."""
    result = run_generator("--check", "--plugin", "ac-workflow")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "product-manager" not in result.stdout
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-product-manager" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md").exists()
    assert not (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "index.ts").exists()
    assert not (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "tmux-agent" / "index.ts").exists()

    protocol_files = [
        "subagent.md",
        "foundation.md",
        "guardrail-policy.md",
        "strict-happy-path-transcript.md",
        "strict-blocker-path-transcript.md",
        "strict-regression-checklist.md",
    ]
    for protocol_file in protocol_files:
        assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "protocol" / protocol_file).exists()
        assert (PROJECT_ROOT / "plugins" / "ac-workflow" / "mux" / "protocol" / protocol_file).exists()


def test_generator_keeps_mux_ospec_pimux_markers_in_sync() -> None:
    """Canonical and generated mux-ospec surfaces should share pimux runtime markers."""
    canonical_pi_body = (
        PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-ospec" / "body.pi.md"
    ).read_text()
    generated_pi_skill = (
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md"
    ).read_text()

    markers = [
        "pimux",
        "binding runtime contract",
        "pimux`-only cross-stage orchestrator",
        "The first real move is to spawn the authoritative stage-owning `pimux` child.",
        "The first observable parent tool call must be `pimux spawn`.",
        "FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.",
        "no-spec invocation starts at Stage `000 CREATE`",
        "route to `BLOCK`",
    ]
    for marker in markers:
        assert marker in canonical_pi_body
        assert marker in generated_pi_skill


def test_generator_keeps_mux_sibling_pimux_markers_in_sync() -> None:
    """Canonical and generated mux sibling surfaces should share pimux authority markers."""
    canonical_mux_body = (
        PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux" / "body.pi.md"
    ).read_text()
    generated_mux_skill = (
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md"
    ).read_text()
    canonical_roadmap_body = (
        PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-roadmap" / "body.pi.md"
    ).read_text()
    generated_roadmap_skill = (
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md"
    ).read_text()

    mux_markers = [
        "pimux",
        "binding runtime contract",
        "pimux`-only control plane",
        "The first real move is to spawn the authoritative `pimux` child coordinator.",
        "The first observable parent tool call must be `pimux spawn`.",
        "FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.",
        "../../assets/mux/protocol/foundation.md",
        "coordinator -> subagent",
        "--strict-runtime --session-key <key>",
    ]
    for marker in mux_markers:
        assert marker in canonical_mux_body
        assert marker in generated_mux_skill

    roadmap_markers = [
        "pimux",
        "binding runtime contract",
        "pimux`-only roadmap orchestrator",
        "Do not inspect roadmap files, phase docs, or repo targets in the parent before spawn.",
        "The first observable parent tool call must be `pimux spawn`.",
        "FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.",
        "phase-owning `/mux-ospec` child",
        "stage-owning `pimux` child",
        "No silent fallback to non-`pimux` runtime",
    ]
    for marker in roadmap_markers:
        assert marker in canonical_roadmap_body
        assert marker in generated_roadmap_skill


def test_generator_keeps_mux_subagent_data_plane_markers_in_sync() -> None:
    """Canonical and generated mux-subagent surfaces should share data-plane contract markers."""
    canonical_pi_body = (
        PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-subagent" / "body.pi.md"
    ).read_text()
    generated_pi_skill = (
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md"
    ).read_text()
    canonical_claude_body = (
        PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-subagent" / "body.md"
    ).read_text()
    generated_claude_skill = (
        PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-subagent" / "SKILL.md"
    ).read_text()

    markers = [
        "binding runtime contract",
        "data-plane only",
        "exactly `0` on success",
        "Do not launch nested `subagent` calls",
        "control-plane bridge tools or `report_parent`",
    ]
    for marker in markers:
        assert marker in canonical_pi_body
        assert marker in generated_pi_skill
        assert marker in canonical_claude_body
        assert marker in generated_claude_skill


def test_generator_ships_worktree_and_gh_pr_review_on_shared_runtime() -> None:
    """`worktree` and `gh-pr-review` should now ship on the bounded shared runtime."""
    result = run_generator("--check", "--plugin", "ac-git", "--plugin", "ac-qa")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (PROJECT_ROOT / "plugins" / "ac-git" / "skills" / "worktree" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "plugins" / "ac-qa" / "skills" / "gh-pr-review" / "SKILL.md").exists()

    worktree_canonical = (PROJECT_ROOT / "canonical" / "ac-git" / "skills" / "worktree" / "skill.yaml").read_text()
    assert "status: supported" in worktree_canonical
    assert "body_file: body.pi.md" in worktree_canonical
    assert "pi: cookbook" in worktree_canonical

    worktree_skill_path = PROJECT_ROOT / "packages" / "pi-ac-git" / "skills" / "ac-git-worktree" / "SKILL.md"
    assert worktree_skill_path.exists()
    worktree_skill = worktree_skill_path.read_text()
    assert "../../assets/scripts/spec-resolver.sh" in worktree_skill
    assert "subagent.parallel" in worktree_skill
    assert "node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js" in worktree_skill
    assert worktree_skill.count("-path '*/templates/*'") >= 2
    assert worktree_skill.count("-path '*/tests/*'") >= 2
    assert "subagent.chain" not in worktree_skill
    assert "mux session" not in worktree_skill
    assert "still depends on skill-to-skill" not in worktree_skill
    assert (PROJECT_ROOT / "packages" / "pi-ac-git" / "skills" / "ac-git-worktree" / "cookbook" / "setup.md").exists()

    review_canonical = (PROJECT_ROOT / "canonical" / "ac-qa" / "skills" / "gh-pr-review" / "skill.yaml").read_text()
    assert "status: supported" in review_canonical
    assert "body_file: body.pi.md" in review_canonical

    review_skill_path = PROJECT_ROOT / "packages" / "pi-ac-qa" / "skills" / "ac-qa-gh-pr-review" / "SKILL.md"
    assert review_skill_path.exists()
    review_skill = review_skill_path.read_text()
    assert "AskUserQuestion" in review_skill
    assert "subagent.parallel" in review_skill
    assert "node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js" in review_skill
    assert "local checkout does not match the PR head" in review_skill
    assert "generic parallel subagent review orchestration beyond the current shared runtime foundation" not in review_skill
    assert "report aggregation still assumes task-worker fan-out" not in review_skill

    qa_package = json.loads((PROJECT_ROOT / "packages" / "pi-ac-qa" / "package.json").read_text())
    assert qa_package["dependencies"] == {"@agentic-config/pi-compat": RELEASE_VERSION}
    assert qa_package["bundledDependencies"] == ["@agentic-config/pi-compat"]
    assert "node_modules/@agentic-config/pi-compat/extensions" in qa_package["pi"]["extensions"]


def test_generator_package_runtime_output_exists() -> None:
    """Package runtime outputs should remain wired for hook-backed packages."""
    result = run_generator("--check", "--plugin", "ac-git", "--plugin", "ac-safety", "--plugin", "ac-tools")
    assert result.returncode == 0, result.stdout + result.stderr
    git_hook_extension = PROJECT_ROOT / "packages" / "pi-ac-git" / "extensions" / "hook-compat.js"
    assert git_hook_extension.exists()
    assert 'registerHookCompatPackage' in git_hook_extension.read_text()

    safety_hook_extension = PROJECT_ROOT / "packages" / "pi-ac-safety" / "extensions" / "hook-compat.js"
    assert safety_hook_extension.exists()
    safety_hook_text = safety_hook_extension.read_text()
    assert 'registerHookCompatPackage' in safety_hook_text
    assert 'playwright-guardian.py' in safety_hook_text

    safety_hook_asset = PROJECT_ROOT / "packages" / "pi-ac-safety" / "assets" / "scripts" / "hooks" / "playwright-guardian.py"
    assert safety_hook_asset.exists()

    tools_hook_extension = PROJECT_ROOT / "packages" / "pi-ac-tools" / "extensions" / "hook-compat.js"
    assert tools_hook_extension.exists()
    tools_hook_text = tools_hook_extension.read_text()
    assert 'registerHookCompatPackage' in tools_hook_text
    assert 'gsuite-public-asset-guard' in tools_hook_text


def test_mux_documentation_surfaces_match_current_generated_boundary() -> None:
    """Workflow docs should reflect canonical IDs, mux aliases, and runtime-only pimux boundary."""
    packages_readme = (PROJECT_ROOT / "packages" / "README.md").read_text()
    assert "ac-workflow-mux" in packages_readme
    assert "mux-ospec" in packages_readme
    assert "runtime/tooling only" in packages_readme
    for legacy_name in ("pimux" + "-mux", "pimux" + "-ospec", "pimux" + "-roadmap"):
        assert legacy_name not in packages_readme

    workflow_extensions_readme = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "README.md").read_text()
    assert "pimux/" in workflow_extensions_readme
    assert "strict-mux-runtime/" in workflow_extensions_readme
    assert "tmux-agent/" not in workflow_extensions_readme

    workflow_readme = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "README.md").read_text()
    assert "ac-workflow-mux" in workflow_readme
    assert "ac-workflow-mux-ospec" in workflow_readme
    assert "ac-workflow-mux-roadmap" in workflow_readme
    assert "pimux" in workflow_readme
    assert "runtime/tooling only" in workflow_readme
    for legacy_name in ("pimux" + "-mux", "pimux" + "-ospec", "pimux" + "-roadmap"):
        assert legacy_name not in workflow_readme


def test_pi_user_facing_assets_use_pi_first_wording() -> None:
    """Pi-facing generated/manual assets should avoid unnecessary Claude branding."""
    forbidden_phrases = {
        PROJECT_ROOT / "packages" / "pi-ac-meta" / "skills" / "ac-meta-hook-writer" / "SKILL.md": [
            "Claude Code Hook Writer",
            "Creates Python hooks for Claude Code",
            "original Claude Code hook authoring target",
            "Tool parameters from Claude Code.",
            "Pretooluse hook for Claude Code",
            "Claude Code hook format",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-meta" / "skills" / "ac-meta-skill-writer" / "SKILL.md": [
            "authoring Claude Code skills",
            "code.claude.com/docs/en/skills",
            "original Claude Code skill authoring target",
            "Claude Code skill specification",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-setup-voice-mode" / "SKILL.md": [
            "Setup VoiceMode for Claude Code",
            "voice interactions with Claude Code",
            "Add MCP server to Claude Code",
            "Restart Claude Code",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-human-agentic-design" / "SKILL.md": [
            "/tmp/claude-prototypes/<session-id>",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-gsuite" / "SKILL.md": [
            "for Claude Code with multi-account support",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-agentic-export" / "SKILL.md": [
            "Claude-only delegation primitive",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-agentic-import" / "SKILL.md": [
            "Claude-only delegation primitive",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-agentic-share" / "SKILL.md": [
            "Claude-only delegation primitives",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-ac-issue" / "SKILL.md": [
            "Claude-plugin-root version lookup",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-video-query" / "SKILL.md": [
            "Claude plugin root",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-had" / "SKILL.md": [
            "Claude-only delegation primitive",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-dry-run" / "SKILL.md": [
            "Claude-compatible PID tracing",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-dr" / "SKILL.md": [
            "<claude_pid>",
            "raw Claude skill-delegation syntax",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-git" / "skills" / "ac-git-pull-request" / "SKILL.md": [
            "Claude Code Attribution",
            "Links to Claude Code for transparency",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md": [
            "mechanical Claude MUX clone",
            "Claude-only hooks or task notifications",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md": [
            "original Claude workflow",
            "Claude-only nested skill execution",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md": [
            "Claude-only nested skill loading",
            "original Claude-only `start` / `continue` / `--wait-after-plan` bootstrap surface",
            "original Claude skill had one",
            "Claude-only orchestration machinery",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md": [
            "Runtime Differences From Claude",
            "Claude-style `TaskOutput`",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "README.md": [
            "pi and Claude mux surfaces",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "protocol" / "subagent.md": [
            "Claude-style `TaskOutput`",
        ],
        PROJECT_ROOT / "packages" / "pi-compat" / "README.md": [
            "Claude-style pre-tool hook runtime",
            "pi-to-Claude payload mapping",
        ],
        PROJECT_ROOT / "packages" / "pi-compat" / "extensions" / "README.md": [
            "pi-to-Claude payload mapping",
        ],
        PROJECT_ROOT / "packages" / "pi-compat" / "extensions" / "hook-compat" / "README.md": [
            "Claude-style pre-tool hook scripts",
            "pi-to-Claude payload mapping",
        ],
        PROJECT_ROOT / "packages" / "pi-compat" / "extensions" / "notebook-edit" / "README.md": [
            "Claude `NotebookEdit` events",
        ],
        PROJECT_ROOT / "packages" / "pi-ac-safety" / "README.md": [
            "pi/Claude runtime",
            "Claude-package scope",
            "Claude-parity completion claim",
        ],
        PROJECT_ROOT / "packages" / "pi-all" / "README.md": [
            "Claude orchestration prompts",
            "every Claude marketplace surface",
        ],
    }

    for path, phrases in forbidden_phrases.items():
        text = path.read_text()
        for phrase in phrases:
            assert phrase not in text, f"Unexpected Claude branding in {path}: {phrase}"

    assert "/tmp/pi-prototypes/<session-id>" in (
        PROJECT_ROOT / "packages" / "pi-ac-tools" / "skills" / "ac-tools-human-agentic-design" / "SKILL.md"
    ).read_text()
    assert "compat payload mapping" in (PROJECT_ROOT / "packages" / "pi-compat" / "README.md").read_text()
    assert "No silent fallback to non-`pimux` runtime for explicit mux-roadmap execution." in (
        PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md"
    ).read_text()
