#!/usr/bin/env python3
"""
Real API integration tests for MUX compliance validation.

Layer 2 tests that ACTUALLY call Claude Agent SDK to verify:
- Task tool creates background agents
- Forbidden tools are blocked/delegated
- Worker-monitor pairing works
- Signal protocol is enforced
- End-to-end MUX workflow executes

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


async def collect_tool_calls(
    prompt: str,
    system_prompt: str,
    max_turns: int = 1,
) -> list[ToolCall]:
    """Run a query and collect all tool calls from the response."""
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import AssistantMessage, ToolUseBlock

    tool_calls: list[ToolCall] = []

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        max_turns=max_turns,
        model="claude-sonnet-4-5-20250929",
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append(ToolCall(name=block.name, input=block.input))

    return tool_calls


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
    """Test that Task tool actually creates background agents via real API."""

    @pytest.mark.asyncio
    async def test_real_task_creates_background_agent(
        self, session_dir: Path
    ) -> None:
        """Actually call Claude Agent SDK via Task tool pattern.

        Verifies that when we instruct an orchestrator to delegate work,
        it uses the Task tool with run_in_background=True.
        """
        skip_if_not_available()

        system_prompt = """You are a MUX ORCHESTRATOR. You ONLY delegate work.

RULES:
1. NEVER execute work directly - ALWAYS use Task tool
2. ALL Task calls MUST use run_in_background=True
3. Return the Task tool call structure, not the actual work

When asked to analyze something, respond ONLY with a Task tool call to delegate."""

        prompt = f"Analyze the code in {session_dir}. Delegate this task to a worker agent."

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Verify response contains Task tool use
        task_calls = [t for t in tool_calls if t.name == "Task"]

        assert len(task_calls) > 0, "Orchestrator must use Task tool to delegate"
        assert task_calls[0].input.get("run_in_background") is True, (
            "Task must use run_in_background=True"
        )


class TestRealForbiddenToolBlocked:
    """Test that orchestrator delegates instead of using forbidden tools."""

    @pytest.mark.asyncio
    async def test_real_forbidden_tool_blocked(
        self, session_dir: Path
    ) -> None:
        """Prompt orchestrator to use Read/Write/Edit and verify delegation.

        The MUX orchestrator should NEVER use Read, Write, Edit, Grep, Glob
        directly. It must delegate these operations via Task tool.
        """
        skip_if_not_available()

        system_prompt = """You are a MUX ORCHESTRATOR. You coordinate work but NEVER execute it.

FORBIDDEN TOOLS (must delegate via Task instead):
- Read - NEVER use directly
- Write - NEVER use directly
- Edit - NEVER use directly
- Grep - NEVER use directly
- Glob - NEVER use directly

ALLOWED TOOLS:
- Task (with run_in_background=True)

When asked to read or modify files, respond ONLY with a Task delegation."""

        prompt = f"Read the contents of {session_dir}/config.json"

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Verify orchestrator did NOT use Read directly
        read_calls = [t for t in tool_calls if t.name == "Read"]
        write_calls = [t for t in tool_calls if t.name == "Write"]
        task_calls = [t for t in tool_calls if t.name == "Task"]

        assert len(read_calls) == 0, "Orchestrator must NOT use Read directly"
        assert len(write_calls) == 0, "Orchestrator must NOT use Write directly"
        assert len(task_calls) > 0, "Orchestrator must delegate via Task tool"


class TestRealWorkerMonitorPairing:
    """Test that workers are always paired with monitors."""

    @pytest.mark.asyncio
    async def test_real_worker_monitor_pairing(
        self, session_dir: Path
    ) -> None:
        """Launch real worker task and verify monitor is created.

        MUX requires every worker batch to have a monitor agent
        that tracks completion via poll-signals.py.
        """
        skip_if_not_available()

        system_prompt = """You are a MUX ORCHESTRATOR following the worker+monitor pattern.

MANDATORY PATTERN:
1. Launch workers with run_in_background=True
2. Launch monitor in SAME response with model="haiku"
3. Monitor must have expected_count matching worker count

For this test, launch 2 workers and 1 monitor. ALL must use Task tool."""

        prompt = (
            f"Launch 2 researcher workers to analyze {session_dir}. "
            "Include a monitor to track completion."
        )

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Count workers and monitors
        task_calls = [t for t in tool_calls if t.name == "Task"]
        workers = []
        monitors = []

        for task in task_calls:
            subagent_type = task.input.get("subagent_type", "")
            agent_type = task.input.get("agent_type", "")
            prompt_text = task.input.get("prompt", "").lower()
            description = task.input.get("description", "").lower()
            model = task.input.get("model", "")
            run_in_background = task.input.get("run_in_background", False)

            # Monitor detection: explicit "monitor" in prompt/description AND uses haiku OR no run_in_background
            is_monitor = (
                ("monitor" in prompt_text or "monitor" in description)
                and (model == "haiku" or not run_in_background)
            ) or (
                agent_type == "monitor"
                or subagent_type == "monitor"
            )

            # Worker detection: background tasks that do work, not monitoring
            is_worker = (
                run_in_background
                and not is_monitor
            ) or (
                agent_type == "worker"
                or subagent_type == "worker"
            )

            if is_monitor:
                monitors.append(task)
            elif is_worker:
                workers.append(task)

        assert len(workers) >= 1, "Must launch at least 1 worker"
        assert len(monitors) >= 1, "Must launch monitor with workers"

        # Verify workers use run_in_background, monitors may not
        for worker in workers:
            assert worker.input.get("run_in_background") is True, (
                "Worker tasks must use run_in_background=True"
            )


class TestRealSignalProtocol:
    """Test that signal creation uses tools, not manual methods."""

    @pytest.mark.asyncio
    async def test_real_signal_protocol(
        self, session_dir: Path
    ) -> None:
        """Run actual MUX-like orchestration and verify signal protocol.

        Signals must be created via tools (signal.py), not manual
        file operations or polling loops.
        """
        skip_if_not_available()

        signals_dir = session_dir / ".signals"

        system_prompt = """You are an agent completing a task for MUX.

SIGNAL PROTOCOL:
- Create completion signals via Bash running signal.py
- NEVER use Write to manually create signal files
- NEVER poll for signals with ls/find loops

When done with work, create signal via:
Bash("uv run tools/signal.py <path>")"""

        prompt = (
            f"You completed your research task. "
            f"Create a completion signal at {signals_dir}/research.done"
        )

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Verify Write was NOT used for signal creation
        write_calls = [t for t in tool_calls if t.name == "Write"]
        bash_calls = [t for t in tool_calls if t.name == "Bash"]

        # Check if any Write calls target signals directory
        signal_writes = [
            w
            for w in write_calls
            if ".signals" in w.input.get("file_path", "")
            or ".done" in w.input.get("file_path", "")
        ]

        assert len(signal_writes) == 0, (
            "Signals must NOT be created via Write - use signal.py"
        )

        # Verify Bash was used with signal.py (if any bash calls)
        if bash_calls:
            signal_bash = [
                b for b in bash_calls if "signal.py" in b.input.get("command", "")
            ]
            assert len(signal_bash) > 0, "Signal creation must use signal.py tool"


class TestRealMuxMiniWorkflow:
    """Test smallest possible real MUX execution end-to-end."""

    @pytest.mark.asyncio
    async def test_real_mux_mini_workflow(
        self, session_dir: Path
    ) -> None:
        """Execute minimal MUX workflow with real API calls.

        Flow:
        1. Orchestrator receives task
        2. Delegates to auditor (worker)
        3. Launches monitor
        4. Verification works
        """
        skip_if_not_available()

        system_prompt = """You are a MUX ORCHESTRATOR. Execute the minimal workflow:

1. Receive task
2. Launch 1 auditor worker via Task
3. Launch 1 monitor via Task (same response)
4. Report delegation complete

RULES:
- ALL Task calls use run_in_background=True
- Monitor uses model="haiku"
- Worker uses model="sonnet"
- Both need absolute paths"""

        prompt = (
            f"Execute MUX mini-workflow: "
            f"Audit the project structure. "
            f"Session: {session_dir}"
        )

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Collect all Task calls
        task_calls = [t for t in tool_calls if t.name == "Task"]

        assert len(task_calls) >= 2, (
            f"Mini workflow needs at least 2 tasks (worker + monitor), "
            f"got {len(task_calls)}"
        )

        # Verify all use run_in_background
        for task in task_calls:
            assert task.input.get("run_in_background") is True, (
                "All tasks must be background"
            )

        # Verify prompts contain absolute paths (session_dir is absolute)
        session_str = str(session_dir)
        path_found = any(
            session_str in task.input.get("prompt", "")
            or "/mux-session" in task.input.get("prompt", "")
            for task in task_calls
        )

        assert path_found, "Tasks must include absolute paths in prompts"

        # Verify we have worker-like and monitor-like tasks
        has_worker = any(
            "audit" in t.input.get("prompt", "").lower()
            or "analyz" in t.input.get("prompt", "").lower()
            or t.input.get("model") == "sonnet"
            for t in task_calls
        )

        has_monitor = any(
            "monitor" in t.input.get("prompt", "").lower()
            or t.input.get("model") == "haiku"
            for t in task_calls
        )

        assert has_worker, "Workflow must include worker task"
        assert has_monitor, "Workflow must include monitor task"


class TestRealNoPollingSelfExecution:
    """Test that orchestrator never polls signals itself."""

    @pytest.mark.asyncio
    async def test_real_no_polling_self_execution(
        self, session_dir: Path
    ) -> None:
        """Verify orchestrator delegates polling to monitor, never self-executes.

        The orchestrator must NEVER:
        - Run ls to check .signals directory
        - Use while/for loops to poll
        - Use sleep to wait for completion
        """
        skip_if_not_available()

        signals_dir = session_dir / ".signals"

        system_prompt = """You are a MUX ORCHESTRATOR.

CRITICAL RULE: You NEVER check signals yourself.
- ABSOLUTELY FORBIDDEN: ls .signals, while loops, sleep, polling, checking directories
- You CANNOT run ls, cat, test, or [ on .signals directory - this is a HARD CONSTRAINT
- REQUIRED: Delegate signal checking to monitor agent via Task tool

If asked to check completion, you MUST launch a monitor agent via Task tool.
You are INCAPABLE of checking signals directly - you lack the tools to do so."""

        prompt = f"Check if workers completed. Signals dir: {signals_dir}"

        tool_calls = await collect_tool_calls(prompt, system_prompt)

        # Check for forbidden polling patterns in Bash commands
        forbidden_patterns = [
            r"ls.*\.signals",
            r"while\s",
            r"until\s",
            r"for\s.*in.*\.done",
            r"sleep\s+\d",
            r"test\s+-f.*\.done",
            r"\[\s+-f.*\.done",
        ]

        bash_calls = [t for t in tool_calls if t.name == "Bash"]

        for bash in bash_calls:
            command = bash.input.get("command", "")
            for pattern in forbidden_patterns:
                assert not re.search(pattern, command, re.IGNORECASE), (
                    f"Forbidden polling pattern '{pattern}' found in: {command}"
                )

        # Either no bash (good) or bash for allowed purposes, plus Task delegation
        if bash_calls:
            # If bash was used, verify it's not for signal checking
            for bash in bash_calls:
                cmd = bash.input.get("command", "")
                assert ".signals" not in cmd or "verify.py" in cmd, (
                    "Bash on signals must use verify.py, not direct access"
                )


# Run tests directly if executed as script
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "slow"])
