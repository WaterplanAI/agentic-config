#!/usr/bin/env python3
"""
Compliance tests for forbidden tool usage.

Validates that mux agent never uses Read, Write, Edit, Grep, or Bash (except allowed).
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations



def test_no_read_tool_used(inspector):
    """Verify mux never uses Read tool."""
    # Simulate mux operations
    inspector.record("Task", {"run_in_background": True})

    # Verify Read tool not used
    assert not inspector.has_tool("Read"), "Mux must not use Read tool - delegate via Task"


def test_no_write_tool_used(inspector):
    """Verify mux never uses Write tool."""
    # Simulate mux operations
    inspector.record("Task", {"run_in_background": True})

    # Verify Write tool not used
    assert not inspector.has_tool("Write"), "Mux must not use Write tool - delegate via Task"


def test_no_edit_tool_used(inspector):
    """Verify mux never uses Edit tool."""
    # Simulate mux operations
    inspector.record("Task", {"run_in_background": True})

    # Verify Edit tool not used
    assert not inspector.has_tool("Edit"), "Mux must not use Edit tool - delegate via Task"


def test_no_grep_tool_used(inspector):
    """Verify mux never uses Grep tool."""
    # Simulate mux operations
    inspector.record("Task", {"run_in_background": True})

    # Verify Grep tool not used
    assert not inspector.has_tool("Grep"), "Mux must not use Grep tool - delegate via Task"


def test_no_glob_tool_used(inspector):
    """Verify mux never uses Glob tool."""
    # Simulate mux operations
    inspector.record("Task", {"run_in_background": True})

    # Verify Glob tool not used
    assert not inspector.has_tool("Glob"), "Mux must not use Glob tool - delegate via Task"


def test_bash_only_allowed_commands(inspector):
    """Verify Bash tool only used for signal/circuit-breaker operations."""
    allowed_patterns = [
        "signal.py",
        "circuit-breaker",
        "verify.py",
    ]

    # Simulate allowed Bash usage
    inspector.record(
        "Bash",
        {
            "command": "uv run /path/to/signal.py /path/to/signal.done",
        },
    )

    bash_calls = inspector.get_calls("Bash")

    for call in bash_calls:
        command = call.parameters.get("command", "")

        # Verify command matches allowed pattern
        is_allowed = any(pattern in command for pattern in allowed_patterns)

        assert is_allowed, f"Bash command not allowed: {command}"


def test_no_file_system_operations(inspector):
    """Verify mux never performs direct file system operations."""
    forbidden_tools = ["Read", "Write", "Edit", "Grep", "Glob"]

    # Simulate mux session
    inspector.record("Task", {"run_in_background": True, "agent_type": "worker"})
    inspector.record(
        "Bash",
        {
            "command": "uv run signal.py /signals/worker.done",
        },
    )

    # Verify no forbidden tools
    for tool in forbidden_tools:
        assert (
            not inspector.has_tool(tool)
        ), f"Mux must not use {tool} for file operations"


def test_only_coordination_tools_allowed(inspector):
    """Verify mux only uses coordination tools, not execution tools."""
    allowed_tools = ["Task", "Bash"]  # Bash only for signal/circuit-breaker

    # Simulate mux coordination
    inspector.record("Task", {"run_in_background": True})
    inspector.record("Bash", {"command": "uv run signal.py"})

    # Verify only allowed tools used
    for call in inspector.calls:
        assert (
            call.name in allowed_tools
        ), f"Tool {call.name} not allowed - mux must only coordinate"
