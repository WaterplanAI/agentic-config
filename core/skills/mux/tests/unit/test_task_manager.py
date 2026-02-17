#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.0"]
# ///
"""Unit tests for TaskManager state machine validation."""
# ruff: noqa: F821

import json
import tempfile
from pathlib import Path
from typing import Any

# Import by loading task-manager.py and executing it
a2a_path = Path(__file__).parent.parent.parent / "a2a"
task_manager_file = a2a_path / "task-manager.py"

# Read and exec the module
with open(task_manager_file) as f:
    code = f.read()
    # Remove shebang and script metadata if present
    lines = code.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('# ///') and 'script' in line:
            # Skip until closing # ///
            for j in range(i+1, len(lines)):
                if lines[j].startswith('# ///'):
                    start_idx = j + 1
                    break
        elif not line.startswith('#'):
            break
    code = '\n'.join(lines[start_idx:])

    # Execute in current namespace
    exec(code, globals())

# Type hints for exec'd symbols (suppress linter warnings)
TaskManager: Any
TaskState: Any
Task: Any
sync_from_signals: Any


def test_valid_transitions():
    """Test all valid state transitions are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TaskManager(Path(tmpdir))
        task = manager.create_task("session-001", "Test task")

        # submitted -> working
        result = manager.update_status(task.id, TaskState.WORKING, "Started")
        assert result is not None
        assert result.status.state == TaskState.WORKING

        # working -> input-required
        result = manager.update_status(task.id, TaskState.INPUT_REQUIRED, "Need input")
        assert result is not None
        assert result.status.state == TaskState.INPUT_REQUIRED

        # input-required -> working
        result = manager.update_status(task.id, TaskState.WORKING, "Resumed")
        assert result is not None
        assert result.status.state == TaskState.WORKING

        # working -> completed
        result = manager.update_status(task.id, TaskState.COMPLETED, "Done")
        assert result is not None
        assert result.status.state == TaskState.COMPLETED

        print("✓ Valid transitions test passed")


def test_invalid_transitions():
    """Test invalid state transitions are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TaskManager(Path(tmpdir))
        task = manager.create_task("session-001", "Test task")

        # Move to completed state
        manager.update_status(task.id, TaskState.WORKING, "Started")
        manager.update_status(task.id, TaskState.COMPLETED, "Done")

        # Try invalid transition: completed -> working (should fail)
        result = manager.update_status(task.id, TaskState.WORKING, "Trying to restart")
        assert result is None, "Should reject transition from terminal state"

        # Verify state unchanged
        task = manager.get_task(task.id)
        assert task.status.state == TaskState.COMPLETED

        print("✓ Invalid transitions test passed")


def test_terminal_state_enforcement():
    """Test that terminal states (completed, failed, canceled) cannot be changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TaskManager(Path(tmpdir))

        # Test completed terminal state
        task1 = manager.create_task("session-001", "Test 1")
        manager.update_status(task1.id, TaskState.WORKING, "Started")
        manager.update_status(task1.id, TaskState.COMPLETED, "Done")
        assert manager.update_status(task1.id, TaskState.WORKING, "Try restart") is None

        # Test failed terminal state
        task2 = manager.create_task("session-002", "Test 2")
        manager.update_status(task2.id, TaskState.WORKING, "Started")
        manager.update_status(task2.id, TaskState.FAILED, "Error")
        assert manager.update_status(task2.id, TaskState.WORKING, "Try restart") is None

        # Test canceled terminal state
        task3 = manager.create_task("session-003", "Test 3")
        manager.update_status(task3.id, TaskState.WORKING, "Started")
        manager.update_status(task3.id, TaskState.CANCELED, "Stopped")
        assert manager.update_status(task3.id, TaskState.WORKING, "Try restart") is None

        print("✓ Terminal state enforcement test passed")


def test_cancel_task_validation():
    """Test that cancel_task respects state machine rules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TaskManager(Path(tmpdir))

        # Can cancel active task
        task1 = manager.create_task("session-001", "Test 1")
        manager.update_status(task1.id, TaskState.WORKING, "Started")
        result = manager.cancel_task(task1.id)
        assert result is not None
        assert result.status.state == TaskState.CANCELED

        # Cannot cancel completed task
        task2 = manager.create_task("session-002", "Test 2")
        manager.update_status(task2.id, TaskState.WORKING, "Started")
        manager.update_status(task2.id, TaskState.COMPLETED, "Done")
        result = manager.cancel_task(task2.id)
        assert result is None

        print("✓ Cancel task validation test passed")


def test_sync_from_signals_malformed():
    """Test error handling for malformed signal files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "storage"
        signals = Path(tmpdir) / "signals"
        signals.mkdir()

        manager = TaskManager(storage)
        task = manager.create_task("session-001", "Test task")

        # Create malformed signal file
        fail_signal = signals / "phase-001.fail"
        fail_signal.write_text("not valid json")

        # Should not crash, should handle gracefully
        try:
            sync_from_signals(manager, task.id, signals)
            # If no exception, check task state unchanged or set to failed
            updated_task = manager.get_task(task.id)
            # Should either remain SUBMITTED or be FAILED with error message
            assert updated_task.status.state in [TaskState.SUBMITTED, TaskState.FAILED]
            print("✓ Malformed signal handling test passed")
        except json.JSONDecodeError:
            print("✗ Malformed signal crashed (should handle gracefully)")
            raise


if __name__ == "__main__":
    test_valid_transitions()
    test_invalid_transitions()
    test_terminal_state_enforcement()
    test_cancel_task_validation()
    test_sync_from_signals_malformed()
    print("\n✓ All tests passed")
