#!/usr/bin/env python3
"""Smoke tests for the canonical generator after shipped-surface migration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = PROJECT_ROOT / "tools" / "generate_canonical_wrappers.py"


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
    """Plugin filtering should cover the canonical workflow scope without touching manual siblings."""
    result = run_generator("--check", "--plugin", "ac-workflow")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "product-manager" not in result.stdout
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-product-manager" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-tmux-agent" / "SKILL.md").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "tmux-agent" / "index.ts").exists()


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
    assert qa_package["dependencies"] == {"@agentic-config/pi-compat": "0.2.6"}
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
    """The package and canonical status surfaces should stay aligned with the generated-first plus direct tmux-agent boundary."""
    canonical_readme = (PROJECT_ROOT / "canonical" / "README.md").read_text()
    assert "`42` canonical skill definitions" in canonical_readme
    assert "`42` shipped Claude/pi skill pairs in the current generated package surface" in canonical_readme
    assert "package-owned direct `tmux-agent` migration" in canonical_readme
    assert "no explicit deferred pi pressure case remains inside the current canonical skill tree" in canonical_readme
    assert "The shipped pi `mux-ospec` wrapper assumes an existing spec path" in canonical_readme
    assert "authoritative maintenance path" in canonical_readme
    assert "`playwright-guardian.py`" not in canonical_readme

    packages_readme = (PROJECT_ROOT / "packages" / "README.md").read_text()
    assert "`43` shipped namespaced skills" in packages_readme
    assert "Still explicitly deferred in the current shipped surface" in packages_readme
    assert "The roadmap evidence artifact is" in packages_readme
    assert "direct package-owned `tmux-agent` migration" in packages_readme
    assert "ac-workflow-tmux-agent" in packages_readme
    assert "`playwright-guardian.py`" not in packages_readme

    pi_all_readme = (PROJECT_ROOT / "packages" / "pi-all" / "README.md").read_text()
    assert "`43` namespaced skills across the plugin packages" in pi_all_readme
    assert "ac-workflow-mux-roadmap" in pi_all_readme
    assert "ac-workflow-tmux-agent" in pi_all_readme
    assert "The shipped pi mux family is an honest adaptation" in pi_all_readme
    assert "Still explicitly deferred in the current shipped surface" in pi_all_readme
    assert "generated-first plus one direct package-owned `tmux-agent` surface" in pi_all_readme
    assert "`playwright-guardian.py`" not in pi_all_readme

    git_readme = (PROJECT_ROOT / "packages" / "pi-ac-git" / "README.md").read_text()
    assert "Shipped generated skill surface" in git_readme
    assert "thin-wrapper" not in git_readme
    assert "`ac-git-worktree`" in git_readme
    assert "### Deferred surface\n- None." in git_readme

    qa_readme = (PROJECT_ROOT / "packages" / "pi-ac-qa" / "README.md").read_text()
    assert "Shipped generated skill surface" in qa_readme
    assert "thin-wrapper" not in qa_readme
    assert "`ac-qa-gh-pr-review`" in qa_readme
    assert "worker-wave helpers" in qa_readme
    assert "### Deferred surface\n- None." in qa_readme

    meta_readme = (PROJECT_ROOT / "packages" / "pi-ac-meta" / "README.md").read_text()
    assert "Shipped generated skill surface" in meta_readme
    assert "thin-wrapper" not in meta_readme
    assert "generated `ac-meta` skill surface" in meta_readme

    audit_readme = (PROJECT_ROOT / "packages" / "pi-ac-audit" / "README.md").read_text()
    assert "generated pi-facing audit configuration skill" in audit_readme
    assert "IT001 matrix" not in audit_readme
    assert "non-IT001" not in audit_readme

    compat_readme = (PROJECT_ROOT / "packages" / "pi-compat" / "README.md").read_text()
    assert "Package topology status" in compat_readme
    assert "Compatibility boundary" in compat_readme
    assert "IT001 topology status" not in compat_readme

    git_assets_readme = (PROJECT_ROOT / "packages" / "pi-ac-git" / "assets" / "scripts" / "README.md").read_text()
    assert "current generated `ac-git` skill surface" in git_assets_readme
    assert "thin-wrapper" not in git_assets_readme

    safety_readme = (PROJECT_ROOT / "packages" / "pi-ac-safety" / "README.md").read_text()
    assert "Package surface status: `active`" in safety_readme
    assert "playwright guardian parity" in safety_readme
    assert "### Deferred surface\n- None." in safety_readme

    safety_skill = (PROJECT_ROOT / "packages" / "pi-ac-safety" / "skills" / "ac-safety-configure-safety" / "SKILL.md").read_text()
    assert "currently shipped guardian" in safety_skill
    assert "deferred config data" not in safety_skill
    assert "(credential/destructive_bash/write_scope/supply_chain/playwright/all)" in safety_skill
    assert "not shipped in IT001" not in safety_skill

    release_skill = (PROJECT_ROOT / "packages" / "pi-ac-git" / "skills" / "ac-git-release" / "SKILL.md").read_text()
    assert "does not ship as a separate pi wrapper in the current package surface" in release_skill
    assert "Phase 004" not in release_skill

    meta_extensions_readme = (PROJECT_ROOT / "packages" / "pi-ac-meta" / "extensions" / "README.md").read_text()
    qa_extensions_readme = (PROJECT_ROOT / "packages" / "pi-ac-qa" / "extensions" / "README.md").read_text()
    for text in (meta_extensions_readme, qa_extensions_readme):
        assert "currently documentation-only" in text
        assert "Phase 003" not in text

    workflow_extensions_readme = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "README.md").read_text()
    assert "tmux-agent/" in workflow_extensions_readme
    assert "exact repo-owned migration of the proven global `tmux-agent` extension" in workflow_extensions_readme
    assert "currently documentation-only" not in workflow_extensions_readme

    workflow_readme = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "README.md").read_text()
    assert "ac-workflow-tmux-agent" in workflow_readme
    assert "package-local `tmux-agent` extension" in workflow_readme
    assert "project-agnostic surface instead of relying on a user-global-only install" in workflow_readme

    hook_compat_readme = (PROJECT_ROOT / "packages" / "pi-compat" / "extensions" / "hook-compat" / "README.md").read_text()
    assert "Shared hook-adapter foundation" in hook_compat_readme
    assert "Shared Phase 005" not in hook_compat_readme
