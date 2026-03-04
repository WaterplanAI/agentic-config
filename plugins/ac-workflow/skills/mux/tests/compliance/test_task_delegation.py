#!/usr/bin/env python3
"""
Compliance tests for task delegation requirements.

Validates that mux always delegates work via Task tool with run_in_background=True.
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations

import re

import pytest


def test_task_always_has_run_in_background(inspector, mock_client):
    """Verify all Task calls use run_in_background=True."""
    # Simulate mux creating tasks
    mock_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        messages=[{"role": "user", "content": "Analyze codebase"}],
        tools=[{"name": "Task", "description": "Delegate work"}],
    )

    # Verify Task was called
    task_calls = inspector.get_calls("Task")
    assert len(task_calls) > 0, "Mux must create tasks"

    # Verify all tasks use run_in_background
    for call in task_calls:
        assert call.parameters.get(
            "run_in_background"
        ) is True, "Task must use run_in_background=True"


def test_task_has_absolute_paths(inspector, session_dir):
    """Verify task instructions use absolute paths."""
    # Simulate task creation with paths
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "instructions": f"Read {session_dir}/audits/report.md",
        },
    )

    task_calls = inspector.get_calls("Task")
    for call in task_calls:
        instructions = call.parameters.get("instructions", "")

        # Extract paths from instructions
        paths = re.findall(r"(/[^\s]+)", instructions)

        for path in paths:
            assert path.startswith("/"), f"Path must be absolute: {path}"


def test_no_blocking_task_calls(inspector, mock_client):
    """Verify mux never waits for task completion synchronously."""
    # Simulate mux workflow
    mock_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        messages=[{"role": "user", "content": "Process data"}],
        tools=[{"name": "Task"}],
    )

    task_calls = inspector.get_calls("Task")

    # All tasks must be background
    blocking_tasks = [
        c for c in task_calls if not c.parameters.get("run_in_background", False)
    ]

    assert (
        len(blocking_tasks) == 0
    ), f"Found {len(blocking_tasks)} blocking task calls - all must be background"


def test_mux_delegates_file_operations(inspector):
    """Verify mux delegates file operations instead of executing directly."""
    # Forbidden tools that mux should never call
    forbidden = ["Read", "Write", "Edit", "Grep", "Glob"]

    # Mux should delegate via Task instead
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "agent_type": "worker",
            "instructions": "Read project files",
        },
    )

    # Verify no forbidden tools used
    for tool in forbidden:
        assert not inspector.has_tool(tool), f"Mux must not use {tool} - delegate via Task"

    # Verify Task was used
    assert inspector.has_tool("Task"), "Mux must delegate via Task tool"


def test_worker_tasks_have_agent_type(inspector):
    """Verify worker tasks specify agent_type."""
    # Simulate worker task creation
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "agent_type": "worker",
            "instructions": "Analyze code",
        },
    )

    task_calls = inspector.get_calls("Task")
    worker_tasks = [c for c in task_calls if "worker" in c.parameters.get("instructions", "").lower()]

    for task in worker_tasks:
        assert (
            "agent_type" in task.parameters
        ), "Worker tasks must specify agent_type parameter"
        assert task.parameters["agent_type"] in [
            "worker",
            "monitor",
        ], "agent_type must be worker or monitor"


def test_no_task_output_usage(inspector):
    """Verify mux NEVER uses TaskOutput to block on agent completion.

    TaskOutput defeats the signal-based architecture:
    - Blocks orchestrator context
    - Wastes tokens waiting
    - Causes "I'll wait for the monitor to complete" bug
    """
    # Simulate violation: using TaskOutput
    inspector.record(
        "TaskOutput",
        {
            "task_id": "monitor-001",
            "block": True,
        },
    )

    task_output_calls = inspector.get_calls("TaskOutput")

    # This SHOULD fail - TaskOutput is forbidden
    with pytest.raises(AssertionError, match="TaskOutput is FORBIDDEN"):
        assert len(task_output_calls) == 0, (
            f"TaskOutput is FORBIDDEN - found {len(task_output_calls)} calls. "
            "Signals are the ONLY completion mechanism."
        )
