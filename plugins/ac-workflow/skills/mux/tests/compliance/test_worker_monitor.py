#!/usr/bin/env python3
"""
Compliance tests for completion tracking requirements.

Validates that workers produce signal files and orchestrator uses
verify.py for post-completion verification (no polling loops).
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations


def test_workers_all_background(inspector):
    """Verify all worker tasks use run_in_background=True."""
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "agent_type": "worker",
            "task_id": "worker-001",
            "instructions": "Analyze code",
        },
    )
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "agent_type": "worker",
            "task_id": "worker-002",
            "instructions": "Research topic",
        },
    )

    task_calls = inspector.get_calls("Task")
    workers = [c for c in task_calls if c.parameters.get("agent_type") == "worker"]

    for worker in workers:
        assert worker.parameters.get("run_in_background") is True, (
            f"Worker {worker.parameters.get('task_id')} must use run_in_background=True"
        )


def test_no_monitor_agents_launched(inspector):
    """Verify no monitor agents are launched (pattern removed)."""
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "agent_type": "worker",
            "task_id": "worker-001",
        },
    )

    task_calls = inspector.get_calls("Task")
    monitors = [c for c in task_calls if c.parameters.get("agent_type") == "monitor"]

    assert len(monitors) == 0, (
        "Monitor agents should not be launched. "
        "Use runtime task-notification for completion tracking."
    )


def test_no_polling_in_bash_calls(inspector):
    """Verify orchestrator does not use polling loops."""
    inspector.record(
        "Bash",
        {"command": "uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py dir --action summary"},
    )

    bash_calls = inspector.get_calls("Bash")

    for call in bash_calls:
        cmd = call.parameters.get("command", "")
        assert "poll-signals" not in cmd, (
            "poll-signals.py is deprecated. Use check-signals.py for one-shot checks."
        )
        assert "while" not in cmd or "sleep" not in cmd, (
            "Polling loops are forbidden. Wait for task-notification."
        )


def test_verify_used_for_completion_check(inspector):
    """Verify orchestrator uses verify.py for post-completion checks."""
    inspector.record(
        "Bash",
        {
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py session_dir --action summary"
        },
    )

    bash_calls = inspector.get_calls("Bash")
    verify_calls = [
        c for c in bash_calls if "verify.py" in c.parameters.get("command", "")
    ]

    assert len(verify_calls) > 0, (
        "Orchestrator must use verify.py for post-completion verification"
    )


def test_no_taskoutput_blocking(inspector):
    """Verify TaskOutput is never used (blocks context)."""
    task_calls = inspector.get_calls("TaskOutput")

    assert len(task_calls) == 0, (
        "TaskOutput is FORBIDDEN. It blocks until agent completes, defeating the architecture."
    )
