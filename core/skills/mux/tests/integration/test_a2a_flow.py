#!/usr/bin/env python3
"""Integration tests for full A2A client-server task submission flow."""
import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

# Import A2A modules
a2a_dir = Path(__file__).parent.parent.parent / "a2a"
client_path = a2a_dir / "client.py"
server_path = a2a_dir / "server.py"
task_manager_path = a2a_dir / "task-manager.py"

# Load client module
spec_client = spec_from_file_location("a2a_client", client_path)
if spec_client is None or spec_client.loader is None:
    raise ImportError(f"Cannot load client from {client_path}")
a2a_client = module_from_spec(spec_client)
sys.modules["a2a_client"] = a2a_client
spec_client.loader.exec_module(a2a_client)

# Load task_manager module
spec_tm = spec_from_file_location("task_manager", task_manager_path)
if spec_tm is None or spec_tm.loader is None:
    raise ImportError(f"Cannot load task_manager from {task_manager_path}")
task_manager = module_from_spec(spec_tm)
sys.modules["task_manager"] = task_manager
spec_tm.loader.exec_module(task_manager)

# Import symbols
TaskManager = task_manager.TaskManager
TaskState = task_manager.TaskState
sync_from_signals = task_manager.sync_from_signals


def test_task_lifecycle_with_signals():
    """Test full task lifecycle: create -> working -> completed via signals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / "storage"
        signals_dir = Path(tmpdir) / "signals"
        signals_dir.mkdir(parents=True)

        # Create task
        manager = TaskManager(storage_dir)
        task = manager.create_task("session-001", "Test task")
        assert task.status.state == TaskState.SUBMITTED

        # Simulate worker starting (signal: working)
        working_signal = signals_dir / "worker.done"
        working_signal.write_text(json.dumps({"status": "working", "message": "Started processing"}))

        # Sync signals
        sync_from_signals(manager, task.id, signals_dir)
        task = manager.get_task(task.id)
        assert task.status.state == TaskState.WORKING, f"Expected WORKING, got {task.status.state}"

        # Simulate worker completion (signal: sentinel.done)
        deliverable_path = Path(tmpdir) / "output.md"
        deliverable_path.write_text("# Test Output\n\nTask completed successfully")
        sentinel_signal = signals_dir / "sentinel.done"
        sentinel_signal.write_text(json.dumps({"path": str(deliverable_path), "status": "completed"}))

        # Sync final signals
        sync_from_signals(manager, task.id, signals_dir)
        task = manager.get_task(task.id)
        assert task.status.state == TaskState.COMPLETED, f"Expected COMPLETED, got {task.status.state}"
        assert len(task.artifacts) > 0, "Expected artifact from deliverable"


def test_task_failure_via_signal():
    """Test task failure handling via fail signal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / "storage"
        signals_dir = Path(tmpdir) / "signals"
        signals_dir.mkdir(parents=True)

        # Create task
        manager = TaskManager(storage_dir)
        task = manager.create_task("session-002", "Test task")

        # Move to working state
        manager.update_status(task.id, TaskState.WORKING, "Started")

        # Simulate worker failure (signal: phase-001.fail)
        fail_signal = signals_dir / "phase-001.fail"
        fail_signal.write_text(json.dumps({"error": "Worker crashed", "phase": "001"}))

        # Sync signals
        sync_from_signals(manager, task.id, signals_dir)
        task = manager.get_task(task.id)
        assert task.status.state == TaskState.FAILED, f"Expected FAILED, got {task.status.state}"
        assert "Worker crashed" in task.status.message


def test_concurrent_task_submissions():
    """Test multiple concurrent task submissions in same session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / "storage"

        # Create multiple tasks for same session
        manager = TaskManager(storage_dir)
        tasks = []
        for i in range(5):
            task = manager.create_task("session-multi", f"Task {i}")
            tasks.append(task)

        # Verify all tasks created
        assert len(tasks) == 5
        assert all(t.status.state == TaskState.SUBMITTED for t in tasks)

        # Verify each task has unique ID
        task_ids = {t.id for t in tasks}
        assert len(task_ids) == 5, "Task IDs must be unique"

        # Update tasks independently (respect state machine: SUBMITTED -> WORKING -> COMPLETED)
        for i, task in enumerate(tasks):
            if i % 2 == 0:
                manager.update_status(task.id, TaskState.WORKING, f"Processing {i}")
            else:
                # Valid transition: SUBMITTED -> WORKING -> COMPLETED
                manager.update_status(task.id, TaskState.WORKING, f"Starting {i}")
                manager.update_status(task.id, TaskState.COMPLETED, f"Done {i}")

        # Verify states
        for i, task in enumerate(tasks):
            updated = manager.get_task(task.id)
            expected_state = TaskState.WORKING if i % 2 == 0 else TaskState.COMPLETED
            assert updated.status.state == expected_state
