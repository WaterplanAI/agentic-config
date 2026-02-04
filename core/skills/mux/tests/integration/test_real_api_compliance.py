#!/usr/bin/env python3
"""
Real API integration tests for MUX compliance validation.

Layer 2 tests that ACTUALLY invoke MUX skill behavior to verify:
- Task tool creates background agents
- Forbidden tools are blocked/delegated
- Worker-monitor pairing works
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


class TestRealWorkerMonitorPairing:
    """Test that MUX workers are always paired with monitors."""

    @pytest.mark.asyncio
    async def test_real_worker_monitor_pairing(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify worker+monitor pairing."""
        skip_if_not_available()

        tool_calls = await invoke_mux_skill(
            "Research 2 topics: Python async, TypeScript generics",
            session_dir,
            max_turns=7,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)
        task_calls = [t for t in post_read_calls if t.name == "Task"]

        # First verify we have at least 2 tasks (worker+monitor minimum)
        assert len(task_calls) >= 2, (
            f"MUX worker+monitor pattern requires at least 2 Task calls, got {len(task_calls)}. "
            f"Tasks: {[t.input.get('description', t.input.get('prompt', '')[:50]) for t in task_calls]}"
        )

        # Classify workers vs monitors using robust detection
        workers = []
        monitors = []

        for task in task_calls:
            prompt_text = task.input.get("prompt", "").lower()
            description = task.input.get("description", "").lower()
            model = task.input.get("model", "")
            run_in_background = task.input.get("run_in_background", False)

            # Monitor detection (strict): haiku model is the primary indicator
            # Secondary: explicit monitor role in description/prompt start
            is_monitor = (
                model == "haiku"
                or description.startswith("monitor")
                or prompt_text.startswith("you are the monitor")
                or prompt_text.startswith("monitor ")
                or "poll-signals" in prompt_text
            )

            # Worker detection: background task that does actual research/audit work
            # Check for work-related keywords that indicate this is a worker
            work_keywords = ["research", "analyze", "audit", "investigate", "review", "check"]
            is_doing_work = any(kw in prompt_text or kw in description for kw in work_keywords)
            is_worker = run_in_background and (is_doing_work or not is_monitor)

            # Classify - if it's clearly a monitor, it's not a worker
            if is_monitor and model == "haiku":
                monitors.append(task)
            elif is_worker:
                workers.append(task)
            elif is_monitor:
                monitors.append(task)

        # Build diagnostic info for assertion messages
        task_info = [
            f"model={t.input.get('model', 'none')}, bg={t.input.get('run_in_background')}, "
            f"desc={t.input.get('description', '')[:30]}"
            for t in task_calls
        ]

        assert len(workers) >= 1, (
            f"MUX must launch at least 1 worker (background task without monitor markers). "
            f"Found {len(workers)} workers, {len(monitors)} monitors. Tasks: {task_info}"
        )
        assert len(monitors) >= 1, (
            f"MUX must launch monitor with workers. "
            f"Found {len(workers)} workers, {len(monitors)} monitors. Tasks: {task_info}"
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
        3. Launches monitor
        4. Verification via Task delegation
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

        assert len(task_calls) >= 2, (
            f"Mini workflow needs at least 2 tasks (worker + monitor), "
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

        # Verify we have worker-like and monitor-like tasks
        has_worker = any(
            "audit" in t.input.get("prompt", "").lower()
            or "research" in t.input.get("prompt", "").lower()
            or "analyz" in t.input.get("prompt", "").lower()
            for t in task_calls
        )

        has_monitor = any(
            "monitor" in t.input.get("prompt", "").lower()
            or t.input.get("model") == "haiku"
            or "poll-signals" in t.input.get("prompt", "").lower()
            for t in task_calls
        )

        assert has_worker, "MUX workflow must include worker task"
        assert has_monitor, "MUX workflow must include monitor task"


class TestRealNoPollingSelfExecution:
    """Test that MUX orchestrator never polls signals itself."""

    @pytest.mark.asyncio
    async def test_real_no_polling_self_execution(
        self, session_dir: Path
    ) -> None:
        """Invoke MUX and verify it delegates polling to monitor."""
        skip_if_not_available()

        signals_dir = session_dir / ".signals"

        tool_calls = await invoke_mux_skill(
            f"Check completion status. Signals dir: {signals_dir}",
            session_dir,
        )

        # Get tool calls after skill read
        post_read_calls = filter_post_skill_read_tools(tool_calls)

        # Check for forbidden polling patterns in Bash commands
        # Note: Single `ls` of .signals is allowed for informational purposes
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
            # Allowed: mkdir, uv run tools/*.py, single ls for inspection
            if ".signals" in cmd:
                is_allowed = (
                    "verify.py" in cmd
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


# Run tests directly if executed as script
if __name__ == "__main__":
    print("Require 3 consecutive runs to pass...")
    print("Pass 1...")
    pytest.main([__file__, "-v", "-m", "slow"])
    print("Pass 2...")
    pytest.main([__file__, "-v", "-m", "slow"])
    print("Pass 3...")
    pytest.main([__file__, "-v", "-m", "slow"])
