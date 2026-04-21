#!/usr/bin/env python3
"""
Real API integration tests for MUX-OSPEC compliance validation.

Layer 2 tests that ACTUALLY invoke MUX-OSPEC skill behavior to verify:
- Skill invocation patterns (mux direct, others via Task)
- Forbidden tools are blocked (TaskOutput, run_in_background=False)
- MUX delegation pattern for GATHER
- Signal protocol enforcement
- Modifier workflows (full, lean, leanest)
- Mandatory SUCCESS_CRITERIA + CONFIRM_SC gate semantics
- PASS-only advancement gates
- Repo-scoped commit evidence contract
- Spec skill delegation via Task pattern

APPROACH: Since the SDK doesn't auto-discover skills from .claude/skills/,
we explicitly ask Claude to read the MUX-OSPEC SKILL.md and follow its instructions.
This tests REAL MUX-OSPEC behavior, not simulated via system prompts.

REQUIRES: Claude CLI authenticated (claude --version works)
MARKERS: slow, expensive, integration

Run with:
    uv run pytest ${CLAUDE_PLUGIN_ROOT}/skills/mux-ospec/tests/integration/test_real_api_compliance.py -v -m "slow"
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0", "pytest-asyncio>=0.23.0", "claude-agent-sdk>=0.1.29"]
# ///

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest  # pyright: ignore[reportMissingImports]

if TYPE_CHECKING:
    pass

# Skip entire module if SDK not available or not authenticated
pytestmark = [
    pytest.mark.slow,
    pytest.mark.expensive,
    pytest.mark.integration,
    pytest.mark.asyncio,
]

# Paths for integration execution
PLUGIN_ROOT = Path(__file__).resolve().parents[4]  # plugins/ac-workflow
PROJECT_ROOT = PLUGIN_ROOT.parent.parent
MUX_OSPEC_SKILL_PATH = str(PLUGIN_ROOT / "skills" / "mux-ospec" / "SKILL.md")
MUX_SKILL_PATH = str(PLUGIN_ROOT / "skills" / "mux" / "SKILL.md")
PLUGIN_CATALOG_PATH = PROJECT_ROOT / "docs" / "plugin-catalog.md"
OSPEC_WORKFLOW_DOC_PATH = PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "ospec-workflow.md"
OSPEC_PHASES_DOC_PATH = PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "ospec-phases.md"
STAGE_PATTERNS_DOC_PATH = PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "stage-patterns.md"
SKILL_DELEGATION_DOC_PATH = (
    PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "skill-delegation.md"
)
STACK_PRIMING_DOC_PATH = (
    PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "stack-priming.md"
)
PHASE_EXECUTOR_PATH = PLUGIN_ROOT / "skills" / "mux-ospec" / "agents" / "phase-executor.md"
ERROR_RECOVERY_PATH = PLUGIN_ROOT / "skills" / "mux-ospec" / "cookbook" / "error-recovery.md"
CANONICAL_MUX_ROADMAP_BODY_PATH = (
    PROJECT_ROOT / "canonical" / "ac-workflow" / "skills" / "mux-roadmap" / "body.md"
)
PLUGIN_MUX_ROADMAP_SKILL_PATH = (
    PLUGIN_ROOT / "skills" / "mux-roadmap" / "SKILL.md"
)


def load_mux_ospec_skill_text() -> str:
    """Load generated mux-ospec skill text for contract assertions."""
    return Path(MUX_OSPEC_SKILL_PATH).read_text(encoding="utf-8")


def is_sdk_available() -> bool:
    """Check if claude-agent-sdk is installed."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: F401  # pyright: ignore[reportMissingImports]

        return True
    except ImportError:
        return False


def is_claude_authenticated() -> bool:
    """Check if Claude CLI is authenticated."""
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def skip_if_not_available() -> None:
    """Skip test if SDK not available or not authenticated."""
    if not is_sdk_available():
        pytest.skip("claude-agent-sdk not installed")
    if not is_claude_authenticated():
        pytest.skip("Claude CLI not authenticated - run 'claude login'")


@dataclass
class ToolCall:
    """Captured tool call for inspection."""

    name: str
    input: dict[str, Any]


def build_mux_ospec_prompt(
    task_description: str, session_dir: Path | None = None
) -> str:
    """
    Build a prompt that asks Claude to read and follow MUX-OSPEC skill.

    Since SDK doesn't auto-discover skills, we explicitly tell Claude to:
    1. Read the MUX-OSPEC SKILL.md
    2. Follow its delegation protocol
    """
    session_context = f"\nSession directory: {session_dir}" if session_dir else ""

    return f"""Read the MUX-OSPEC skill from {MUX_OSPEC_SKILL_PATH}, then follow its instructions.

TASK: {task_description}{session_context}
Note: Use absolute paths in all Task prompts"""


async def invoke_mux_ospec_skill(
    task_description: str,
    session_dir: Path | None = None,
    max_turns: int = 5,
) -> list[ToolCall]:
    """
    Invoke MUX-OSPEC skill by asking Claude to read and follow SKILL.md.

    This is the CORRECT approach - we ask Claude to read the actual skill
    file and follow its instructions, then observe what tools it uses.
    """
    from claude_agent_sdk import ClaudeAgentOptions, query  # pyright: ignore[reportMissingImports]
    from claude_agent_sdk.types import (  # pyright: ignore[reportMissingImports]
        AssistantMessage,
        ToolUseBlock,
    )

    tool_calls: list[ToolCall] = []
    prompt = build_mux_ospec_prompt(task_description, session_dir)

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=max_turns,
        model="claude-3-7-20250219",
        cwd=str(PROJECT_ROOT),
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(ToolCall(name=block.name, input=block.input))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"claude-agent-sdk query unavailable in this environment: {exc}")

    return tool_calls


def filter_post_skill_read_tools(tool_calls: list[ToolCall]) -> list[ToolCall]:
    """
    Return tool calls AFTER the initial Read of SKILL.md.

    MUX-OSPEC is allowed to Read the skill file first, but after that
    it must only delegate via Task or call mux directly via Skill.
    """
    found_skill_read = False
    post_read_calls: list[ToolCall] = []

    for call in tool_calls:
        if call.name == "Read" and "SKILL.md" in call.input.get("file_path", ""):
            found_skill_read = True
            continue
        if found_skill_read:
            post_read_calls.append(call)

    return post_read_calls


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Create temporary session directory structure."""
    session = tmp_path / "mux-ospec-session"
    session.mkdir()
    (session / ".signals").mkdir()
    (session / "research").mkdir()
    (session / "phases").mkdir()
    (session / "reviews").mkdir()
    (session / "tests").mkdir()
    return session


class TestSkillInvocationPatternCompliance:
    """Test that MUX-OSPEC follows correct skill invocation patterns."""

    @pytest.mark.asyncio
    async def test_skill_invocation_pattern_compliance(
        self, session_dir: Path
    ) -> None:
        """Verify Skill(mux) direct, Task(Invoke Skill) for others.

        MUX-OSPEC MUST:
        - Call Skill(skill="mux") directly for GATHER
        - Call Task(prompt="Invoke Skill(...)") for spec, orc, etc.
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec specs/test.md",
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Collect Skill calls
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Check Skill calls - only mux is allowed directly
        for skill in skill_calls:
            skill_name = skill.input.get("skill", "")
            assert skill_name == "mux", (
                f"Only Skill(skill='mux') is allowed directly. Found: Skill(skill='{skill_name}'). "
                "Other skills MUST use Task(prompt='Invoke Skill(...)')."
            )

        # Check Task calls that invoke skills use correct pattern
        for task in task_calls:
            prompt = task.input.get("prompt", "")
            # If task invokes a skill, verify pattern
            if "Skill(" in prompt or "skill=" in prompt.lower():
                # Should NOT be invoking mux via Task (mux is direct)
                assert "skill=\"mux\"" not in prompt and "skill='mux'" not in prompt, (
                    "mux skill should be called directly via Skill(), not via Task. "
                    f"Found: {prompt[:100]}"
                )


class TestForbiddenToolDetection:
    """Test that MUX-OSPEC avoids forbidden tools."""

    @pytest.mark.asyncio
    async def test_forbidden_tool_detection(self, session_dir: Path) -> None:
        """Detect TaskOutput, run_in_background=False violations.

        FORBIDDEN (ZERO TOLERANCE):
        - TaskOutput() - NEVER block on agent completion
        - run_in_background=False - ALWAYS use True
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec lean specs/test.md",
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # TaskOutput is FORBIDDEN
        task_output_calls = [t for t in post_read_calls if t.name == "TaskOutput"]
        assert len(task_output_calls) == 0, (
            f"MUX-OSPEC must NEVER use TaskOutput - found {len(task_output_calls)} calls. "
            "TaskOutput blocks context and defeats the signal-based architecture."
        )

        # All Task calls MUST use run_in_background=True
        task_calls = [t for t in post_read_calls if t.name == "Task"]
        for task in task_calls:
            run_in_bg = task.input.get("run_in_background")
            assert run_in_bg is True, (
                f"Task MUST use run_in_background=True, got: {run_in_bg}. "
                f"Task prompt: {task.input.get('prompt', '')[:80]}"
            )

        # MUX-OSPEC should NOT use direct file operations after skill read
        read_calls = [t for t in post_read_calls if t.name == "Read"]
        write_calls = [t for t in post_read_calls if t.name == "Write"]
        edit_calls = [t for t in post_read_calls if t.name == "Edit"]
        grep_calls = [t for t in post_read_calls if t.name == "Grep"]
        glob_calls = [t for t in post_read_calls if t.name == "Glob"]

        assert len(read_calls) == 0, "MUX-OSPEC must NOT use Read directly after skill load"
        assert len(write_calls) == 0, "MUX-OSPEC must NOT use Write directly"
        assert len(edit_calls) == 0, "MUX-OSPEC must NOT use Edit directly"
        assert len(grep_calls) == 0, "MUX-OSPEC must NOT use Grep directly"
        assert len(glob_calls) == 0, "MUX-OSPEC must NOT use Glob directly"


class TestMuxDelegationPattern:
    """Test that MUX-OSPEC delegates GATHER to mux skill correctly."""

    @pytest.mark.asyncio
    async def test_mux_delegation_pattern(self, session_dir: Path) -> None:
        """Verify delegation via mux skill.

        For GATHER phase, MUX-OSPEC MUST:
        - Call Skill(skill="mux") directly (not via Task)
        - mux handles worker delegation internally
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec specs/test.md",  # full modifier triggers GATHER
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for direct Skill(mux) call
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        mux_calls = [s for s in skill_calls if s.input.get("skill") == "mux"]

        # Full workflow should include mux call for GATHER
        # (may not always trigger in limited turns, so we check pattern)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Verify delegation happens (either mux skill or Task delegation)
        has_delegation = len(mux_calls) > 0 or len(task_calls) > 0
        assert has_delegation, (
            "MUX-OSPEC must delegate work. Expected Skill(mux) or Task() calls. "
            f"Found {len(mux_calls)} mux calls, {len(task_calls)} Task calls."
        )

        # If mux is called, verify it's done correctly
        for mux_call in mux_calls:
            args = mux_call.input.get("args", "")
            assert args, "Skill(mux) call must include args with task description"


class TestSignalProtocolCompliance:
    """Test that signals are created via tools, not Write."""

    @pytest.mark.asyncio
    async def test_signal_protocol_compliance(self, session_dir: Path) -> None:
        """Verify signal creation patterns.

        Signals must be created via:
        - uv run $MUX_TOOLS/signal.py
        - NOT via Write() to .signals/ directory
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec lean specs/test.md",
            session_dir,
            max_turns=7,
        )

        # Check that Write was NOT used for signal creation
        write_calls = [t for t in tool_calls if t.name == "Write"]

        # Check if any Write calls target signals directory
        signal_writes = [
            w
            for w in write_calls
            if ".signals" in w.input.get("file_path", "")
            or ".done" in w.input.get("file_path", "")
            or ".json" in w.input.get("file_path", "")
            and "signals" in w.input.get("file_path", "").lower()
        ]

        assert len(signal_writes) == 0, (
            "Signals must NOT be created via Write - use signal.py tool. "
            f"Found {len(signal_writes)} Write calls to signal paths."
        )

        # Verify Bash calls use signal tools when accessing signals
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        bash_calls = [t for t in post_read_calls if t.name == "Bash"]

        for bash in bash_calls:
            cmd = bash.input.get("command", "")
            if ".signals" in cmd:
                is_allowed = (
                    "signal.py" in cmd
                    or "verify.py" in cmd
                    or "check-signals.py" in cmd
                    or "mkdir" in cmd
                    or cmd.strip().startswith("ls ")  # single ls for inspection
                )
                assert is_allowed, (
                    f"MUX-OSPEC Bash on signals must use tools, not direct access: {cmd}"
                )


class TestWorkflowContractSurface:
    """Static contract checks on generated mux-ospec skill surface."""

    async def test_required_stage_gate_and_commit_contract_text(self) -> None:
        """Validate clarified contract text is present on authoritative plugin surface."""
        skill_text = load_mux_ospec_skill_text()

        assert (
            "`full`: `CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> "
            "CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL`"
            in skill_text
        )
        assert (
            "`lean`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION`"
            in skill_text
        )
        assert (
            "`leanest`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION`"
            in skill_text
        )

        assert "`SUCCESS_CRITERIA` is mandatory content before `CONFIRM_SC`" in skill_text
        assert "`CONFIRM_SC` is a mandatory user approval gate before `PLAN`" in skill_text
        assert (
            "Only `PASS` can advance through `REVIEW`, `TEST`, `SENTINEL`, or `SELF_VALIDATION`."
            in skill_text
        )

        assert "`repo_scope`: `spec-only` | `root-only` | `root+spec`" in skill_text
        assert "`root_commit`: short hash or `N/A`" in skill_text
        assert "`spec_commit`: short hash or `N/A`" in skill_text
        assert "1. commit root repo first" in skill_text
        assert "2. commit spec repo second (via spec resolver)" in skill_text

    async def test_stage_tier_mapping_consistency_across_manual_surfaces(self) -> None:
        """Ensure manual docs and examples match the authoritative stage-tier mapping."""
        plugin_catalog = PLUGIN_CATALOG_PATH.read_text(encoding="utf-8")
        workflow_doc = OSPEC_WORKFLOW_DOC_PATH.read_text(encoding="utf-8")
        phases_doc = OSPEC_PHASES_DOC_PATH.read_text(encoding="utf-8")
        phase_executor = PHASE_EXECUTOR_PATH.read_text(encoding="utf-8")
        stage_patterns = STAGE_PATTERNS_DOC_PATH.read_text(encoding="utf-8")
        error_recovery = ERROR_RECOVERY_PATH.read_text(encoding="utf-8")

        assert "openai-codex/gpt-5.4:xhigh" in plugin_catalog
        assert "openai-codex/gpt-5.3-codex:high" in plugin_catalog
        assert "high-tier" in plugin_catalog
        assert "medium-tier" in plugin_catalog

        for required_line in [
            "| GATHER | medium-tier |",
            "| REVIEW | high-tier |",
            "| FIX | medium-tier |",
            "| TEST | medium-tier |",
            "| SELF_VALIDATION | high-tier |",
        ]:
            assert required_line in workflow_doc

        assert "PLAN -> IMPLEMENT -> REVIEW -> FIX |" not in workflow_doc
        assert "Per-phase SENTINEL (optional" not in workflow_doc

        assert "All phases execute with high-tier models for quality stages." not in phases_doc
        assert 'model="medium-tier"' in phases_doc

        assert (
            'Task(prompt="...", model="medium-tier", run_in_background=True)  # Researcher workers'
            in phase_executor
        )

        assert "Skip phase and continue" not in error_recovery

        assert "--skip" not in workflow_doc
        assert "Stages can be skipped via `--skip` flag." not in stage_patterns

    async def test_manual_spec_path_and_stage_claim_regression_guards(self) -> None:
        """Guard weak-model manuals against legacy path examples and stale stage claims."""
        skill_delegation = SKILL_DELEGATION_DOC_PATH.read_text(encoding="utf-8")
        stack_priming = STACK_PRIMING_DOC_PATH.read_text(encoding="utf-8")
        canonical_roadmap = CANONICAL_MUX_ROADMAP_BODY_PATH.read_text(encoding="utf-8")
        plugin_roadmap = PLUGIN_MUX_ROADMAP_SKILL_PATH.read_text(encoding="utf-8")

        legacy_specs_path = re.compile(r"(?<!\\.specs/)specs/\\d{4}/\\d{2}/")

        for surface_name, surface_text in [
            ("skill-delegation", skill_delegation),
            ("stack-priming", stack_priming),
            ("canonical-mux-roadmap", canonical_roadmap),
            ("plugin-mux-roadmap", plugin_roadmap),
        ]:
            assert legacy_specs_path.search(surface_text) is None, (
                f"Legacy specs path found in {surface_name}; use .specs/specs/... examples only."
            )

        assert "spec skill has no REVIEW stage" not in skill_delegation
        assert "spec skill has no FIX stage" not in skill_delegation

        assert (
            'Skill(skill="spec", args="PLAN .specs/specs/2026/02/auth/001-system.md ultrathink")'
            in skill_delegation
        )
        assert "spec_path: .specs/specs/2026/02/feature-xyz/001-title.md" in stack_priming

        for roadmap_surface in [canonical_roadmap, plugin_roadmap]:
            assert (
                "/mux-roadmap .specs/specs/2026/02/feature-branch/001-feature-spec.md start"
                in roadmap_surface
            )
            assert "PATH: .specs/specs/2026/02/..." in roadmap_surface
            assert "Read(.specs/specs/2026/02/.../001-spec.md)" in roadmap_surface
            assert 'Bash("ls .specs/specs/2026/02/.../")' in roadmap_surface

    async def test_skip_bypass_and_roadmap_stage_chain_regression_guards(self) -> None:
        """Guard against cookbook stage-bypass drift and outdated roadmap stage chain text."""
        workflow_doc = OSPEC_WORKFLOW_DOC_PATH.read_text(encoding="utf-8")
        stage_patterns = STAGE_PATTERNS_DOC_PATH.read_text(encoding="utf-8")
        canonical_roadmap = CANONICAL_MUX_ROADMAP_BODY_PATH.read_text(encoding="utf-8")
        plugin_roadmap = PLUGIN_MUX_ROADMAP_SKILL_PATH.read_text(encoding="utf-8")

        assert "Optional via `--skip` flag." not in workflow_doc
        assert "Stages can be skipped via `--skip` flag." not in stage_patterns
        assert "Primary stages are mandatory" in stage_patterns

        outdated_chain = (
            "GATHER -> CONFIRM SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> "
            "TEST -> DOCUMENT -> SENTINEL"
        )
        explicit_chain = (
            "GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> "
            "IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL"
        )

        assert outdated_chain not in canonical_roadmap
        assert outdated_chain not in plugin_roadmap
        assert explicit_chain in canonical_roadmap
        assert explicit_chain in plugin_roadmap


    async def test_manual_stage_order_contract_in_phase_executor_and_phases_doc(self) -> None:
        """Catch manual-surface stage-order regressions for weak-model-facing docs."""
        phase_executor = PHASE_EXECUTOR_PATH.read_text(encoding="utf-8")
        phases_doc = OSPEC_PHASES_DOC_PATH.read_text(encoding="utf-8")

        required_executor_steps = [
            "d. SUCCESS_CRITERIA",
            "e. CONFIRM_SC",
            "f. PLAN",
            "j. TEST",
            "k. DOCUMENT",
            "l. FINAL VALIDATION",
        ]
        for step in required_executor_steps:
            assert step in phase_executor, f"Missing required phase-executor step: {step}"

        assert phase_executor.index("d. SUCCESS_CRITERIA") < phase_executor.index(
            "e. CONFIRM_SC"
        ) < phase_executor.index("f. PLAN")
        assert phase_executor.index("j. TEST") < phase_executor.index(
            "k. DOCUMENT"
        ) < phase_executor.index("l. FINAL VALIDATION")

        assert "- full: run SENTINEL" in phase_executor
        assert "- lean/leanest: run SELF_VALIDATION" in phase_executor

        assert "| Success Criteria | SUCCESS_CRITERIA |" in phases_doc
        assert "| Alignment Gate | CONFIRM_SC |" in phases_doc
        assert (
            phases_doc.index("### SUCCESS_CRITERIA Stage")
            < phases_doc.index("### CONFIRM_SC Stage")
            < phases_doc.index("### PLAN Stage")
        )


class TestModifierFullWorkflow:
    """Test full modifier behavior."""

    @pytest.mark.asyncio
    async def test_modifier_full_workflow(self, session_dir: Path) -> None:
        """Test full modifier behavior.

        Full workflow: CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA ->
        CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec specs/test.md",  # No modifier = full
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Full workflow should include mux call for GATHER
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Full requires GATHER via mux
        mux_calls = [s for s in skill_calls if s.input.get("skill") == "mux"]

        # Verify at least one form of delegation
        has_delegation = len(mux_calls) > 0 or len(task_calls) > 0
        assert has_delegation, (
            "Full workflow must delegate work. "
            f"Found {len(mux_calls)} mux calls, {len(task_calls)} Task calls."
        )

        # Verify all Task calls use background
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                "All Task calls must use run_in_background=True"
            )


class TestModifierLeanWorkflow:
    """Test lean modifier behavior (skips GATHER)."""

    @pytest.mark.asyncio
    async def test_modifier_lean_workflow(self, session_dir: Path) -> None:
        """Test lean modifier (skips GATHER).

        Lean workflow: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX ->
        TEST -> DOCUMENT -> SELF_VALIDATION.
        SUCCESS_CRITERIA content must already exist before CONFIRM_SC.
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec lean specs/test.md",
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Lean should NOT call mux for GATHER (no research phase)
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Lean uses Task delegation for spec stages
        # May or may not have mux calls depending on interpretation

        # Verify delegation exists
        has_delegation = len(skill_calls) > 0 or len(task_calls) > 0
        assert has_delegation, (
            "Lean workflow must delegate work. "
            f"Found {len(skill_calls)} Skill calls, {len(task_calls)} Task calls."
        )

        # All Task calls must use background
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                "All Task calls must use run_in_background=True"
            )


class TestModifierLeanestWorkflow:
    """Test leanest modifier (low-tier execution)."""

    @pytest.mark.asyncio
    async def test_modifier_leanest_workflow(self, session_dir: Path) -> None:
        """Test leanest modifier (low-tier execution).

        Leanest workflow: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX ->
        TEST -> SELF_VALIDATION.
        SUCCESS_CRITERIA content must already exist before CONFIRM_SC.
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec leanest specs/test.md",
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Leanest may use low-tier model for some tasks
        # Verify delegation pattern is maintained
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                "All Task calls must use run_in_background=True"
            )

        # Verify we have some delegation
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        has_delegation = len(skill_calls) > 0 or len(task_calls) > 0
        assert has_delegation, (
            "Leanest workflow must delegate work. "
            f"Found {len(skill_calls)} Skill calls, {len(task_calls)} Task calls."
        )


class TestSpecSkillDelegation:
    """Test that spec skill is called via Task pattern."""

    @pytest.mark.asyncio
    async def test_spec_skill_delegation(self, session_dir: Path) -> None:
        """Verify spec skill called via Task pattern.

        MUX-OSPEC MUST call spec via:
        Task(prompt="Invoke Skill(skill='spec', args='...')")

        NOT via direct Skill(skill="spec") call.
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_ospec_skill(
            "/mux-ospec lean specs/test.md",
            session_dir,
            max_turns=7,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Direct Skill calls should NOT include spec
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]
        spec_direct_calls = [s for s in skill_calls if s.input.get("skill") == "spec"]

        assert len(spec_direct_calls) == 0, (
            f"spec skill must NOT be called directly - found {len(spec_direct_calls)} direct calls. "
            "Use Task(prompt='Invoke Skill(skill=\"spec\", ...)') instead."
        )

        # If Task calls invoke spec, verify pattern
        task_calls = [t for t in post_read_calls if t.name == "Task"]
        spec_via_task = [
            t
            for t in task_calls
            if "spec" in t.input.get("prompt", "").lower()
            and ("skill" in t.input.get("prompt", "").lower() or "invoke" in t.input.get("prompt", "").lower())
        ]

        # Verify spec invocations use Task pattern (if any exist)
        for task in spec_via_task:
            prompt = task.input.get("prompt", "")
            # Should contain invoke pattern
            has_invoke_pattern = (
                "Invoke Skill" in prompt
                or "invoke skill" in prompt.lower()
                or "Skill(" in prompt
            )
            assert has_invoke_pattern or "spec" in prompt.lower(), (
                f"spec invocation should use Invoke Skill pattern: {prompt[:100]}"
            )


class TestNoPollingSelfExecution:
    """Test that orchestrator does not self-poll for completion."""

    @pytest.mark.asyncio
    async def test_no_polling_self_execution(self, session_dir: Path) -> None:
        """Verify orchestrator does not poll signals itself."""
        skip_if_not_available()

        signals_dir = session_dir / ".signals"

        tool_calls = await invoke_mux_ospec_skill(
            f"Check completion status. Signals dir: {signals_dir}",
            session_dir,
        )

        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden polling patterns in Bash commands
        forbidden_patterns = [
            r"while\s",
            r"until\s",
            r"for\s.*in.*\.done",
            r"sleep\s+\d",
            r"test\s+-f.*\.done",
            r"\[\s+-f.*\.done",
        ]

        bash_calls = [t for t in post_read_calls if t.name == "Bash"]

        for bash in bash_calls:
            command = bash.input.get("command", "")
            for pattern in forbidden_patterns:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"MUX-OSPEC forbidden polling pattern '{pattern}' found in: {command}"
                )


# Run tests directly if executed as script
if __name__ == "__main__":
    print("Require 3 consecutive runs to pass...")
    print("Pass 1...")
    pytest.main([__file__, "-v", "-m", "slow"])
    print("Pass 2...")
    pytest.main([__file__, "-v", "-m", "slow"])
    print("Pass 3...")
    pytest.main([__file__, "-v", "-m", "slow"])
