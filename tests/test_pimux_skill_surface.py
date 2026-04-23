#!/usr/bin/env python3
"""Surface checks for local pimux skills and references."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_SKILL = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "SKILL.md"
PIMUX_COMMANDS = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "references" / "commands.md"
PIMUX_PROTOCOL = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "references" / "protocol.md"
PIMUX_PATTERNS = PROJECT_ROOT / ".pi" / "skills" / "pimux" / "references" / "patterns.md"
PACKAGE_PIMUX_DOCS = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "docs"
PACKAGE_PIMUX_COMMANDS = PACKAGE_PIMUX_DOCS / "commands.md"
PACKAGE_PIMUX_PROTOCOL = PACKAGE_PIMUX_DOCS / "protocol.md"
PACKAGE_PIMUX_PATTERNS = PACKAGE_PIMUX_DOCS / "patterns.md"
PACKAGE_WORKFLOW_SKILLS = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills"
MUX_ALIAS = PROJECT_ROOT / ".pi" / "skills" / "mux" / "SKILL.md"
MUX_OSPEC_ALIAS = PROJECT_ROOT / ".pi" / "skills" / "mux-ospec" / "SKILL.md"
MUX_ROADMAP_ALIAS = PROJECT_ROOT / ".pi" / "skills" / "mux-roadmap" / "SKILL.md"
LEGACY_PIMUX_MUX = PROJECT_ROOT / ".pi" / "skills" / ("pimux" + "-mux") / "SKILL.md"
LEGACY_PIMUX_OSPEC = PROJECT_ROOT / ".pi" / "skills" / ("pimux" + "-ospec") / "SKILL.md"
LEGACY_PIMUX_ROADMAP = PROJECT_ROOT / ".pi" / "skills" / ("pimux" + "-roadmap") / "SKILL.md"


def test_core_skill_requires_explicit_messaging_settlement_and_trigger_commitment() -> None:
    """The base skill should document explicit messaging, authority, settlement, and trigger discipline."""
    text = PIMUX_SKILL.read_text()
    protocol = PIMUX_PROTOCOL.read_text()
    assert "FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity." in text
    assert "Parent -> child messaging uses `pimux send_message`." in text
    assert "Child -> parent reporting uses `pimux report_parent`." in text
    assert "Parent-side interface delivery should also show bridge message traffic concisely; parent -> child messages stay visible without forcing an extra turn." in text
    assert "`list`, `tree`, and `navigate` should keep agent IDs visible while adding role/goal labels, clearer hierarchy connectors, and best-effort safe styling when the host interface supports it." in text
    assert "Success settles only after `report_parent(closeout)` plus child exit." in text
    assert "live-session actions such as `open`, `capture`, `send`, and `kill` should prefer currently running agents in interactive selectors" in text
    assert "If the user explicitly invokes `pimux`, `mux`, `mux-ospec`, or `mux-roadmap`, treat that as a commitment to the pimux runtime." in text
    assert "fail-closed parent control-plane lock" in text
    assert "Only the authoritative direct child session for a bridge may call `report_parent`." in protocol
    assert "the parent is fail-closed to `pimux`, `AskUserQuestion`, and `say`" in protocol
    assert "that trigger is a runtime commitment, not a suggestion." in protocol
    assert "Default supervision is scoped to the current session hierarchy." in protocol
    assert "Do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity." in protocol
    assert "the supervising wrapper should propagate the matching terminal kind and exit cleanly instead of forcing `closeout` or relying on manual kill" in protocol
    assert "For cascade-kill testing, keep the wrapper alive and kill a disposable child parent/descendant pair under it rather than making the wrapper itself the killed parent." in protocol


def test_commands_reference_exposes_minimal_surface() -> None:
    """The commands reference should document the reduced pimux surface."""
    text = PIMUX_COMMANDS.read_text()
    assert "- `spawn`" in text
    assert "- `open`" in text
    assert "- `tree`" in text
    assert "- `send_message`" in text
    assert "- `report_parent`" in text
    assert "Parent-side interface delivery should also show parent -> child bridge messages as concise pimux events without triggering an extra turn." in text
    assert "list/tree/navigation labels keep the agent ID visible while adding role/goal context for easier selection" in text
    assert "interactive `open`, `capture`, `send`, and `kill` pickers should prefer live agents when no target is provided" in text
    assert "- `kill`" in text
    assert "- `unlock`" in text
    assert "/pimux unlock" in text


def test_package_pimux_runtime_docs_are_canonical() -> None:
    """Package-owned runtime docs should exist before local pimux references are retired."""
    commands = PACKAGE_PIMUX_COMMANDS.read_text()
    protocol = PACKAGE_PIMUX_PROTOCOL.read_text()
    patterns = PACKAGE_PIMUX_PATTERNS.read_text()
    assert "Package-owned runtime docs" in commands
    assert "Package-owned runtime protocol docs" in protocol
    assert "Package-owned runtime patterns" in patterns
    assert "FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity." in protocol
    assert "Workflow wrappers should reference these docs instead of project-local `.pi` copies." in patterns


def test_package_workflow_skills_do_not_reference_local_pimux_docs() -> None:
    """Package skills should not depend on project-local pimux reference docs."""
    for skill_path in sorted(PACKAGE_WORKFLOW_SKILLS.glob("ac-workflow-mux*/SKILL.md")):
        assert ".pi/skills/pimux" not in skill_path.read_text()


def test_wrapper_skills_point_back_to_core_pimux_contract() -> None:
    """The mux/ospec/roadmap aliases should stay thin and runtime-bound to pimux."""
    patterns = PIMUX_PATTERNS.read_text()
    assert "Use pimux as the control-plane runtime for:" in patterns
    assert "If `pimux`, `mux`, `mux-ospec`, or `mux-roadmap` is explicitly invoked" in patterns
    assert "fail-closed to `pimux`, `AskUserQuestion`, and `say`" in patterns

    mux_text = MUX_ALIAS.read_text()
    assert "If the user explicitly triggers `mux`, the parent must actually run through `pimux`." in mux_text

    ospec_text = MUX_OSPEC_ALIAS.read_text()
    assert "If the user explicitly triggers `mux-ospec`, keep work in the tmux-backed stage lane." in ospec_text
    assert "inline prompt without a spec path" in ospec_text
    assert "create it instead of blocking" in ospec_text

    roadmap_text = MUX_ROADMAP_ALIAS.read_text()
    assert "If the user explicitly triggers `mux-roadmap`, keep work in the tmux-backed roadmap lane." in roadmap_text
    assert "inline prompt without a path" in roadmap_text
    assert "create it instead of blocking" in roadmap_text

    for text in (mux_text, ospec_text, roadmap_text):
        assert "pimux" in text
        assert "do not poll pimux or use Bash sleep/wait loops" in text

    assert not LEGACY_PIMUX_MUX.exists()
    assert not LEGACY_PIMUX_OSPEC.exists()
    assert not LEGACY_PIMUX_ROADMAP.exists()
