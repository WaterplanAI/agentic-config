#!/usr/bin/env python3
"""Smoke tests for the generated mux foundation assets."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUX_TOOLS_ROOT = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "tools"
PI_MUX_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md"
PI_MUX_OSPEC_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md"
PI_MUX_ROADMAP_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md"
PI_MUX_SUBAGENT_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md"
CLAUDE_MUX_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux" / "SKILL.md"
CLAUDE_MUX_OSPEC_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-ospec" / "SKILL.md"
CLAUDE_MUX_ROADMAP_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-roadmap" / "SKILL.md"
CLAUDE_MUX_SUBAGENT_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-subagent" / "SKILL.md"


def run_python_script(script_path: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a generated Python helper and capture its output."""
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_session_dir(stdout: str) -> str:
    """Extract the relative session directory from session.py output."""
    for line in stdout.splitlines():
        if line.startswith("SESSION_DIR="):
            return line.removeprefix("SESSION_DIR=").strip()
    raise AssertionError(f"Missing SESSION_DIR in output: {stdout}")


def test_generated_mux_claude_frontmatter_survives_generation() -> None:
    """The canonical generator should preserve mux-specific Claude frontmatter extras."""
    mux_text = CLAUDE_MUX_SKILL.read_text()
    assert "hooks:" in mux_text
    assert "matcher: Read|Write|Edit|NotebookEdit|Grep|Glob|WebSearch|WebFetch|TaskOutput|Skill|Bash|Task" in mux_text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/mux/hooks/mux-orchestrator-guard.py" in mux_text

    mux_ospec_text = CLAUDE_MUX_OSPEC_SKILL.read_text()
    assert "argument-hint:" in mux_ospec_text
    assert "requires-skills:" in mux_ospec_text
    assert "- spec" in mux_ospec_text

    mux_roadmap_text = CLAUDE_MUX_ROADMAP_SKILL.read_text()
    assert "**Modes:**" in mux_roadmap_text
    assert "`start` - New session." in mux_roadmap_text
    assert "`continue` - Resume session." in mux_roadmap_text

    subagent_text = CLAUDE_MUX_SUBAGENT_SKILL.read_text()
    assert "hooks:" in subagent_text
    assert "matcher: TaskOutput" in subagent_text
    assert "${CLAUDE_PLUGIN_ROOT}/mux/subagent-hooks/mux-subagent-guard.py" in subagent_text


def test_generated_pi_mux_foundation_assets_exist() -> None:
    """The pi workflow package should ship the mux foundation assets and mux skill family."""
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "README.md").exists()
    assert (MUX_TOOLS_ROOT / "session.py").exists()
    assert (MUX_TOOLS_ROOT / "signal.py").exists()
    assert (MUX_TOOLS_ROOT / "verify.py").exists()
    assert PI_MUX_SKILL.exists()
    assert PI_MUX_OSPEC_SKILL.exists()
    assert PI_MUX_ROADMAP_SKILL.exists()
    assert PI_MUX_SUBAGENT_SKILL.exists()

    subagent_text = PI_MUX_SUBAGENT_SKILL.read_text()
    assert "../../assets/mux/tools/signal.py" in subagent_text
    assert "../../assets/mux/protocol/subagent.md" in subagent_text
    assert "Do not launch nested subagents" in subagent_text


def test_generated_pi_mux_orchestrators_reference_shared_foundation() -> None:
    """The generated pi mux orchestrators should consume the shared foundation honestly."""
    mux_text = PI_MUX_SKILL.read_text()
    assert "../../assets/mux/protocol/foundation.md" in mux_text
    assert "Use a single `subagent` call" in mux_text
    assert "coordinator -> subagent" in mux_text

    mux_ospec_text = PI_MUX_OSPEC_SKILL.read_text()
    assert "argument-hint: '[modifier] [spec_path]'" in mux_ospec_text
    assert "../../assets/agents/spec/" in mux_ospec_text
    assert "sibling `-stages/` directory" in mux_ospec_text
    assert "does not recreate the original inline CREATE/bootstrap flow" in mux_ospec_text
    assert "no nested `Skill(...)`" in mux_ospec_text

    mux_roadmap_text = PI_MUX_ROADMAP_SKILL.read_text()
    assert "Roadmap `## Implementation Progress` section = cross-phase mirror." in mux_roadmap_text
    assert "Do not invent a separate `CONTINUE.md` by default" in mux_roadmap_text
    assert "one worker layer only: coordinator -> subagent" in mux_roadmap_text
    assert "does not recreate the original Claude-only `start` / `continue` / `--wait-after-plan` bootstrap surface" in mux_roadmap_text


def test_generated_mux_tools_support_session_signal_and_summary_flow(tmp_path: Path) -> None:
    """The generated mux helper scripts should work together from the package asset root."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".git").mkdir()

    session_result = run_python_script(MUX_TOOLS_ROOT / "session.py", "phase-007-smoke", "--base", "tmp/mux-smoke", cwd=workspace)
    assert session_result.returncode == 0, session_result.stdout + session_result.stderr
    session_dir_rel = parse_session_dir(session_result.stdout)
    session_dir = workspace / session_dir_rel
    assert session_dir.exists()
    assert (session_dir / ".signals").exists()

    report_rel = "reports/worker.md"
    report_path = workspace / report_rel
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Worker Report\n\n"
        "## Table of Contents\n"
        "- Item\n\n"
        "## Executive Summary\n"
        "- **Status**: pass\n"
        "- **Files**: reports/worker.md\n\n"
        "### Next Steps\n"
        "- **Recommended action**: continue\n"
        "- **Dependencies**: none\n"
        "- **Routing hint**: writer\n"
    )

    signal_rel = f"{session_dir_rel}/.signals/worker.done"
    signal_result = run_python_script(
        MUX_TOOLS_ROOT / "signal.py",
        signal_rel,
        "--path",
        report_rel,
        "--status",
        "success",
        cwd=workspace,
    )
    assert signal_result.returncode == 0, signal_result.stdout + signal_result.stderr
    assert (workspace / signal_rel).exists()

    verify_result = run_python_script(MUX_TOOLS_ROOT / "verify.py", session_dir_rel, "--action", "summary", cwd=workspace)
    assert verify_result.returncode == 0, verify_result.stdout + verify_result.stderr
    assert "completed: 1" in verify_result.stdout
    assert "failed: 0" in verify_result.stdout

    check_result = run_python_script(MUX_TOOLS_ROOT / "check-signals.py", session_dir_rel, "--expected", "1", cwd=workspace)
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert '"status": "complete"' in check_result.stdout

    summary_result = run_python_script(MUX_TOOLS_ROOT / "extract-summary.py", report_rel, cwd=workspace)
    assert summary_result.returncode == 0, summary_result.stdout + summary_result.stderr
    assert "## Executive Summary" in summary_result.stdout
    assert "**Status**: pass" in summary_result.stdout
