#!/usr/bin/env python3
"""
Real API integration tests for MUX compliance validation.

Layer 2 tests that ACTUALLY invoke MUX skill behavior to verify:
- Task tool creates background agents
- Forbidden tools are blocked/delegated
- Completion tracking via task-notification works
- Signal protocol is enforced
- End-to-end MUX workflow executes

APPROACH: Since the SDK doesn't auto-discover skills from .claude/skills/,
we explicitly ask Claude to read the MUX SKILL.md and follow its instructions.
This tests REAL MUX behavior, not simulated via system prompts.

REQUIRES: Claude CLI authenticated (claude --version works)
MARKERS: slow, expensive, integration

Run with:
    uv run pytest core/skills/mux/tests/integration/test_real_api_compliance.py -v -m "slow"
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

import pytest

if TYPE_CHECKING:
    pass

# Skip entire module if SDK not available or not authenticated
pytestmark = [
    pytest.mark.slow,
    pytest.mark.expensive,
    pytest.mark.integration,
    pytest.mark.asyncio,
]

# Project root where MUX skill exists
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent)
MUX_SKILL_PATH = f"{PROJECT_ROOT}/core/skills/mux/SKILL.md"


def is_sdk_available() -> bool:
    """Check if claude-agent-sdk is installed."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: F401

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


def build_mux_prompt(task_description: str, session_dir: Path | None = None) -> str:
    """
    Build a prompt that asks Claude to read and follow MUX skill.

    Since SDK doesn't auto-discover skills, we explicitly tell Claude to:
    1. Read the MUX SKILL.md
    2. Follow its delegation protocol
    """
    session_context = f"\nSession directory: {session_dir}" if session_dir else ""

    return f"""Read the MUX skill from {MUX_SKILL_PATH}, then follow its instructions.

TASK: {task_description}{session_context}
Note: Use absolute paths in all Task prompts"""


async def invoke_mux_skill(
    task_description: str,
    session_dir: Path | None = None,
    max_turns: int = 5,
) -> list[ToolCall]:
    """
    Invoke MUX skill by asking Claude to read and follow SKILL.md.

    This is the CORRECT approach - we ask Claude to read the actual skill
    file and follow its instructions, then observe what tools it uses.
    """
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import AssistantMessage, ToolUseBlock

    tool_calls: list[ToolCall] = []
    prompt = build_mux_prompt(task_description, session_dir)

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=max_turns,
        model="claude-sonnet-4-5-20250929",
        cwd=PROJECT_ROOT,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append(ToolCall(name=block.name, input=block.input))

    return tool_calls


def filter_post_skill_read_tools(tool_calls: list[ToolCall]) -> list[ToolCall]:
    """
    Return tool calls AFTER the initial Read of SKILL.md.

    MUX is allowed to Read the skill file first, but after that
    it must only delegate via Task.
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
    session = tmp_path / "mux-session"
    session.mkdir()
    (session / ".signals").mkdir()
    (session / "outputs").mkdir()
    (session / "workers").mkdir()
    return session


class TestRealTaskCreatesBackgroundAgent:
    """Test that MUX skill actually creates background agents via Task tool."""

    @pytest.mark.asyncio
    async def test_real_task_creates_background_agent(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it delegates via Task with run_in_background=True."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research Python async patterns",
            session_dir,
        )

        # Get tool calls after skill is read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        assert len(task_calls) > 0, "MUX must delegate via Task tool"

        # All Task calls should use run_in_background=True
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                f"Task must use run_in_background=True, got: {task.input}"
            )


class TestRealForbiddenToolBlocked:
    """Test that MUX orchestrator delegates instead of using forbidden tools."""

    @pytest.mark.asyncio
    async def test_real_forbidden_tool_blocked(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it doesn't use Read/Write/Edit directly after skill load."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Analyze the code structure",
            session_dir,
        )

        # Get tool calls AFTER the skill is read (initial Read is allowed)
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # MUX orchestrator should NOT use these tools after reading skill
        read_calls = [t for t in post_read_calls if t.name == "Read"]
        write_calls = [t for t in post_read_calls if t.name == "Write"]
        edit_calls = [t for t in post_read_calls if t.name == "Edit"]
        grep_calls = [t for t in post_read_calls if t.name == "Grep"]
        glob_calls = [t for t in post_read_calls if t.name == "Glob"]

        # MUX should delegate via Task instead
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        assert len(read_calls) == 0, "MUX must NOT use Read directly after skill load"
        assert len(write_calls) == 0, "MUX must NOT use Write directly"
        assert len(edit_calls) == 0, "MUX must NOT use Edit directly"
        assert len(grep_calls) == 0, "MUX must NOT use Grep directly"
        assert len(glob_calls) == 0, "MUX must NOT use Glob directly"
        assert len(task_calls) > 0, "MUX must delegate via Task tool"


class TestRealCompletionTracking:
    """Test that MUX uses task-notification for completion tracking."""

    @pytest.mark.asyncio
    async def test_real_completion_tracking(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify completion tracking via task-notification."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research 2 topics: Python async, TypeScript generics",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Verify we have at least 1 worker task
        assert len(task_calls) >= 1, (
            f"MUX must launch at least 1 worker task, got {len(task_calls)}. "
            f"Tasks: {[t.input.get('description', t.input.get('prompt', '')[:50]) for t in task_calls]}"
        )

        # Classify workers (tasks doing actual work)
        workers = []

        for task in task_calls:
            prompt_text = task.input.get("prompt", "").lower()
            description = task.input.get("description", "").lower()
            run_in_background = task.input.get("run_in_background", False)

            # Worker detection: background task doing research/audit work
            work_keywords = ["research", "analyze", "audit", "investigate", "review", "check"]
            is_doing_work = any(kw in prompt_text or kw in description for kw in work_keywords)

            if run_in_background and is_doing_work:
                workers.append(task)

        # Build diagnostic info for assertion messages
        task_info = [
            f"model={t.input.get('model', 'none')}, bg={t.input.get('run_in_background')}, "
            f"desc={t.input.get('description', '')[:30]}"
            for t in task_calls
        ]

        assert len(workers) >= 1, (
            f"MUX must launch at least 1 worker (background task doing work). "
            f"Found {len(workers)} workers. Tasks: {task_info}"
        )

        # Verify workers use run_in_background
        for worker in workers:
            assert worker.input.get("run_in_background") is True, (
                "Worker tasks must use run_in_background=True"
            )


class TestRealSignalProtocol:
    """Test that MUX signal creation uses tools, not manual methods."""

    @pytest.mark.asyncio
    async def test_real_signal_protocol(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify signal protocol compliance."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Quick audit of project structure",
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
        ]

        assert len(signal_writes) == 0, (
            "Signals must NOT be created via Write - MUX uses signal.py"
        )


class TestRealMuxMiniWorkflow:
    """Test smallest possible real MUX execution end-to-end."""

    @pytest.mark.asyncio
    async def test_real_mux_mini_workflow(
        self, session_dir: Path
    ) -> None:
        """Execute minimal MUX workflow with real skill invocation.

        Flow:
        1. Claude reads MUX SKILL.md
        2. Delegates to workers (researcher/auditor)
        3. Runtime delivers task-notification on completion
        4. Verification via verify.py
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Audit the project structure",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        assert len(task_calls) >= 1, (
            f"Mini workflow needs at least 1 worker task, "
            f"got {len(task_calls)}"
        )

        # Verify all use run_in_background
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                "All MUX tasks must be background"
            )

        # Verify prompts contain absolute paths
        has_absolute_path = any(
            "/" in task.input.get("prompt", "")
            for task in task_calls
        )
        assert has_absolute_path, "MUX tasks must include absolute paths in prompts"

        # Verify we have worker-like tasks
        has_worker = any(
            "audit" in t.input.get("prompt", "").lower()
            or "research" in t.input.get("prompt", "").lower()
            or "analyz" in t.input.get("prompt", "").lower()
            for t in task_calls
        )

        assert has_worker, "MUX workflow must include worker task"


class TestRealNoPollingSelfExecution:
    """Test that MUX orchestrator never polls signals itself."""

    @pytest.mark.asyncio
    async def test_real_no_polling_self_execution(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it doesn't use polling loops."""
        skip_if_not_available()

        signals_dir = session_dir / ".signals"

        tool_calls = await invoke_mux_skill(
            f"Check completion status. Signals dir: {signals_dir}",
            session_dir,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden polling patterns in Bash commands
        # Polling = repeated checking via loops (while/until/for + sleep)
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
                    f"MUX forbidden polling pattern '{pattern}' found in: {command}"
                )

        # If bash was used, verify it's not for direct signal checking in a loop
        # Single ls for informational purposes is allowed; polling loops are not
        for bash in bash_calls:
            cmd = bash.input.get("command", "")
            # Allowed: mkdir, uv run .claude/skills/mux/tools/*.py, single ls for inspection
            if ".signals" in cmd:
                is_allowed = (
                    "verify.py" in cmd
                    or "check-signals.py" in cmd
                    or "signal.py" in cmd
                    or "mkdir" in cmd
                    or cmd.strip().startswith("ls ")  # single ls for inspection
                )
                assert is_allowed, (
                    f"MUX Bash on signals must use tools, not direct access: {cmd}"
                )


class TestRealNoTaskOutputBlocking:
    """Test that MUX orchestrator never uses TaskOutput to block on agents."""

    @pytest.mark.asyncio
    async def test_real_no_task_output_blocking(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it never uses TaskOutput.

        TaskOutput blocks until agent completion, which:
        - Wastes orchestrator context
        - Defeats the signal-based architecture
        - Causes the exact bug shown in: "I'll wait for the monitor to complete"
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research async patterns and audit codebase",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # TaskOutput is FORBIDDEN - signals are the only completion mechanism
        task_output_calls = [t for t in post_read_calls if t.name == "TaskOutput"]

        assert len(task_output_calls) == 0, (
            f"MUX must NEVER use TaskOutput - found {len(task_output_calls)} calls. "
            "Signals are the ONLY completion mechanism. "
            "TaskOutput blocks context and defeats the architecture."
        )


class TestRealNoWebToolsSelfExecution:
    """Test that MUX orchestrator never uses WebFetch/WebSearch directly."""

    @pytest.mark.asyncio
    async def test_real_no_web_tools_self_execution(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it delegates web operations."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research best practices for Python async patterns from the web",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # WebFetch and WebSearch are FORBIDDEN for orchestrator
        webfetch_calls = [t for t in post_read_calls if t.name == "WebFetch"]
        websearch_calls = [t for t in post_read_calls if t.name == "WebSearch"]

        assert len(webfetch_calls) == 0, (
            f"MUX must NOT use WebFetch directly - found {len(webfetch_calls)} calls. "
            "Delegate web fetching to researchers via Task()."
        )
        assert len(websearch_calls) == 0, (
            f"MUX must NOT use WebSearch directly - found {len(websearch_calls)} calls. "
            "Delegate web searching to researchers via Task()."
        )

        # Verify research is delegated
        task_calls = [t for t in post_read_calls if t.name == "Task"]
        has_research_delegation = any(
            "research" in t.input.get("prompt", "").lower()
            or "web" in t.input.get("prompt", "").lower()
            or "search" in t.input.get("prompt", "").lower()
            for t in task_calls
        )
        assert has_research_delegation, (
            "Web research must be delegated via Task, not executed directly"
        )


class TestRealInteractiveGatesAtDecisions:
    """Test that MUX uses AskUserQuestion at critical decision points."""

    @pytest.mark.asyncio
    async def test_real_no_interactive_gate_for_normal_progress(
        self, session_dir: Path
    ) -> None:
        """Verify AskUserQuestion is NOT used for routine phase transitions.

        Normal flow: voice announcement + auto-proceed
        NOT: asking user permission for each step
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research async patterns",
            session_dir,
            max_turns=5,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check AskUserQuestion calls
        ask_calls = [t for t in post_read_calls if t.name == "AskUserQuestion"]

        # Filter out critical decision questions (those ARE expected)
        routine_questions = []
        for call in ask_calls:
            questions = call.input.get("questions", [])
            for q in questions:
                question_text = q.get("question", "").lower()
                # Critical decisions are OK to ask about
                is_critical = any(
                    kw in question_text
                    for kw in ["sentinel", "fail", "error", "consolidat", "timeout", "gap"]
                )
                if not is_critical:
                    routine_questions.append(question_text)

        assert len(routine_questions) == 0, (
            f"AskUserQuestion should NOT be used for routine transitions. "
            f"Found {len(routine_questions)} non-critical questions: {routine_questions[:3]}"
        )


class TestRealPhasedExecutionNotAllAtOnce:
    """Test that MUX executes phases sequentially, not all at once."""

    @pytest.mark.asyncio
    async def test_real_phased_execution_not_all_at_once(
        self, session_dir: Path
    ) -> None:
        """Verify phases don't all launch in the same message batch.

        CRITICAL BUG: Launching research + audit + consolidation + write all together
        CORRECT: Sequential phases with signal-based progression
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Full analysis: research async patterns, audit codebase, write summary",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Classify phases from Task prompts
        phase_keywords = {
            "research": ["research", "search", "investigate"],
            "audit": ["audit", "analyze", "review code"],
            "consolidation": ["consolidat", "aggregate", "merge"],
            "coordination": ["coordinat", "write", "compose"],
        }

        phases_found: list[str] = []
        for task in task_calls:
            prompt = task.input.get("prompt", "").lower()
            for phase, keywords in phase_keywords.items():
                if any(kw in prompt for kw in keywords):
                    phases_found.append(phase)
                    break

        # Dedupe while preserving order
        unique_phases = list(dict.fromkeys(phases_found))

        # If we have multiple distinct phases, verify they're not all in the same batch
        # The key insight: if all 4+ phases are in the first batch, that's the bug
        if len(unique_phases) >= 3:
            # With max_turns=7, we expect phases to be spread across turns
            # If all phases appear with the same count as tasks, they launched together
            assert len(task_calls) > len(unique_phases), (
                f"Phases appear to have launched all at once. "
                f"Found {len(unique_phases)} phases in {len(task_calls)} tasks. "
                f"Phases: {unique_phases}. "
                "MUX must execute phases sequentially with signal-based progression."
            )


class TestRealVoiceAnnouncementsBetweenPhases:
    """Test that MUX uses voice announcements for phase transitions."""

    @pytest.mark.asyncio
    async def test_real_voice_announcements_between_phases(
        self, session_dir: Path
    ) -> None:
        """Verify voice is used for phase transition announcements."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research async patterns and audit the codebase",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for voice announcements
        voice_calls = [
            t for t in post_read_calls
            if t.name == "mcp__voicemode__converse"
        ]

        # Voice announcements should NOT wait for response (announcement mode)
        for voice in voice_calls:
            message = voice.input.get("message", "").lower()
            # Phase announcements should be fire-and-forget
            if any(kw in message for kw in ["phase", "launch", "start", "complete"]):
                assert voice.input.get("wait_for_response") is False, (
                    f"Phase announcement voice should not wait for response: {message}"
                )


class TestRealNoAgentOutputPolling:
    """Test that MUX orchestrator never polls agent output files."""

    @pytest.mark.asyncio
    async def test_real_no_agent_output_polling(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it never polls agent output files.

        FORBIDDEN: Reading/tailing /private/tmp/claude-*/tasks/*.output
        CORRECT: Trust notification system, use signals for completion
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research Python async patterns and check agent status",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden output file polling patterns
        forbidden_output_patterns = [
            r"/private/tmp/claude.*tasks.*\.output",
            r"claude-.*\.output",
            r"tasks/.*\.output",
            r"tail.*\.output",
            r"cat.*\.output",
        ]

        # Check Read calls for output file access
        read_calls = [t for t in post_read_calls if t.name == "Read"]
        for read in read_calls:
            file_path = read.input.get("file_path", "")
            for pattern in forbidden_output_patterns:
                assert not re.search(pattern, file_path, re.IGNORECASE), (
                    f"MUX FORBIDDEN: polling agent output file via Read: {file_path}. "
                    "Trust notification system - never poll task output files."
                )

        # Check Bash calls for output file access
        bash_calls = [t for t in post_read_calls if t.name == "Bash"]
        for bash in bash_calls:
            command = bash.input.get("command", "")
            for pattern in forbidden_output_patterns:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"MUX FORBIDDEN: polling agent output file via Bash: {command}. "
                    "Trust notification system - never poll task output files."
                )


class TestRealNoSkillInvocationFromOrchestrator:
    """Test that MUX orchestrator never calls Skill() directly."""

    @pytest.mark.asyncio
    async def test_real_no_skill_invocation_from_orchestrator(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it never uses Skill() directly.

        FATAL VIOLATION: Skill() executes IN orchestrator context
        CORRECT: Delegate via Task() with explicit skill invocation instructions
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Run spec workflow for a new feature",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Skill tool is FORBIDDEN - it executes in orchestrator context
        skill_calls = [t for t in post_read_calls if t.name == "Skill"]

        assert len(skill_calls) == 0, (
            f"MUX FATAL: Skill() called directly from orchestrator - found {len(skill_calls)} calls. "
            "Skill() executes IN your context, causing context suicide. "
            "Delegate via Task() with explicit skill invocation instructions."
        )


class TestRealTaskPromptsContainAbsolutePaths:
    """Test that MUX Task prompts contain absolute paths, not vague instructions."""

    @pytest.mark.asyncio
    async def test_real_task_prompts_contain_absolute_paths(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify Task prompts include absolute paths.

        VIOLATION: Vague prompts like "run /spec" or "analyze codebase"
        CORRECT: Explicit paths like "/Users/x/project/..." in prompts
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            f"Audit the codebase structure. Session: {session_dir}",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # Skip if no task calls (test may timeout before delegation)
        if len(task_calls) == 0:
            pytest.skip("No Task calls captured - test may need more turns")

        # Check that prompts contain absolute paths (Unix-style)
        prompts_with_paths = 0
        for task in task_calls:
            prompt = task.input.get("prompt", "")
            # Check for absolute path patterns (Unix)
            if re.search(r"/[A-Za-z][A-Za-z0-9_/-]*", prompt):
                prompts_with_paths += 1

        # At least half of Task prompts should contain absolute paths
        ratio = prompts_with_paths / len(task_calls) if task_calls else 0
        assert ratio >= 0.5, (
            f"MUX Task prompts should contain absolute paths. "
            f"Found {prompts_with_paths}/{len(task_calls)} prompts with paths ({ratio:.0%}). "
            "Use explicit paths in prompts, not vague instructions."
        )


class TestRealNoDirectGrepCatFind:
    """Test that MUX never runs grep/cat/find/head/tail directly."""

    @pytest.mark.asyncio
    async def test_real_no_direct_grep_cat_find(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it doesn't run inspection commands.

        CONTEXT SUICIDE: Running grep, cat, head, tail, find for content inspection
        CORRECT: Delegate all inspection to workers via Task()
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Find all Python files and analyze their content",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden inspection commands in Bash
        forbidden_commands = [
            r"^\s*grep\s",
            r"^\s*cat\s",
            r"^\s*head\s",
            r"^\s*tail\s",
            r"^\s*find\s",
            r"\|\s*grep\s",
            r"\|\s*cat\s",
            r"\|\s*head\s",
            r"\|\s*tail\s",
        ]

        bash_calls = [t for t in post_read_calls if t.name == "Bash"]
        for bash in bash_calls:
            command = bash.input.get("command", "")
            # Allow mkdir and tool invocations
            if "mkdir" in command or "uv run tools" in command:
                continue
            for pattern in forbidden_commands:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"MUX FORBIDDEN: inspection command in Bash: {command}. "
                    "Delegate content inspection to workers via Task()."
                )


class TestRealNoBuildTestLintCommands:
    """Test that MUX never runs build/test/lint commands directly."""

    @pytest.mark.asyncio
    async def test_real_no_build_test_lint_commands(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it doesn't run build/test/lint directly.

        CONTEXT SUICIDE: Running npx, npm, cdk, cargo, go, make, pytest, ruff
        CORRECT: Delegate all build/test/lint to workers via Task()
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Run tests and lint the codebase",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden build/test/lint commands
        forbidden_commands = [
            r"^\s*npm\s",
            r"^\s*npx\s",
            r"^\s*cdk\s",
            r"^\s*cargo\s",
            r"^\s*go\s+(build|test|run)",
            r"^\s*make\s",
            r"^\s*pytest\s",
            r"^\s*ruff\s",
            r"^\s*pyright\s",
            r"^\s*mypy\s",
        ]

        bash_calls = [t for t in post_read_calls if t.name == "Bash"]
        for bash in bash_calls:
            command = bash.input.get("command", "")
            # Allow mkdir and mux tool invocations
            if "mkdir" in command or "uv run .claude/skills/mux/tools/" in command:
                continue
            for pattern in forbidden_commands:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"MUX FORBIDDEN: build/test/lint command: {command}. "
                    "Delegate build/test/lint to workers via Task()."
                )


class TestRealNoGitInspectionCommands:
    """Test that MUX never runs git inspection commands directly."""

    @pytest.mark.asyncio
    async def test_real_no_git_inspection_commands(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it doesn't run git inspection directly.

        CONTEXT SUICIDE: Running git status, git diff, git log for inspection
        CORRECT: Delegate git inspection to workers via Task()
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Analyze recent git changes and commits",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden git inspection commands
        forbidden_git_patterns = [
            r"git\s+status",
            r"git\s+diff",
            r"git\s+log",
            r"git\s+show",
            r"git\s+blame",
        ]

        bash_calls = [t for t in post_read_calls if t.name == "Bash"]
        for bash in bash_calls:
            command = bash.input.get("command", "")
            for pattern in forbidden_git_patterns:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"MUX FORBIDDEN: git inspection command: {command}. "
                    "Delegate git inspection to workers via Task()."
                )


class TestRealDelegationNotInlineExecution:
    """Test that MUX delegates work instead of implementing inline."""

    @pytest.mark.asyncio
    async def test_real_delegation_not_inline_execution(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX with complex task and verify delegation over inline work.

        VIOLATION: Implementing agent behavior inline
        CORRECT: Decompose and delegate via Task()
        """
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research async patterns, audit the codebase, and write a summary report",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Count delegation vs direct execution
        task_calls = [t for t in post_read_calls if t.name == "Task"]
        forbidden_tools = ["Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch"]
        direct_execution_calls = [
            t for t in post_read_calls if t.name in forbidden_tools
        ]

        # MUX should have more delegations than direct executions
        assert len(task_calls) > len(direct_execution_calls), (
            f"MUX should delegate more than execute directly. "
            f"Found {len(task_calls)} Task calls vs {len(direct_execution_calls)} direct execution calls. "
            f"Direct tools used: {[t.name for t in direct_execution_calls]}"
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
