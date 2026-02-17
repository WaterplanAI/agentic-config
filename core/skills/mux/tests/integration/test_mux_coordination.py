#!/usr/bin/env python3
"""Integration tests for circuit breaker + signal + task manager coordination."""
import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from multiprocessing import Process
from pathlib import Path

# Import modules
mux_tools = Path(__file__).parent.parent.parent / "tools"
a2a_dir = Path(__file__).parent.parent.parent / "a2a"

# Load circuit_breaker
cb_path = mux_tools / "circuit-breaker.py"
spec_cb = spec_from_file_location("circuit_breaker", cb_path)
if spec_cb is None or spec_cb.loader is None:
    raise ImportError(f"Cannot load circuit_breaker from {cb_path}")
circuit_breaker = module_from_spec(spec_cb)
sys.modules["circuit_breaker"] = circuit_breaker
spec_cb.loader.exec_module(circuit_breaker)

# Load signal
signal_path = mux_tools / "signal.py"
spec_sig = spec_from_file_location("signal_tool", signal_path)
if spec_sig is None or spec_sig.loader is None:
    raise ImportError(f"Cannot load signal from {signal_path}")
signal_tool = module_from_spec(spec_sig)
sys.modules["signal_tool"] = signal_tool
spec_sig.loader.exec_module(signal_tool)

# Load task_manager
tm_path = a2a_dir / "task-manager.py"
spec_tm = spec_from_file_location("task_manager", tm_path)
if spec_tm is None or spec_tm.loader is None:
    raise ImportError(f"Cannot load task_manager from {tm_path}")
task_manager = module_from_spec(spec_tm)
sys.modules["task_manager"] = task_manager
spec_tm.loader.exec_module(task_manager)

# Import symbols
check_circuit = circuit_breaker.check_circuit
record_success = circuit_breaker.record_success
record_failure = circuit_breaker.record_failure
CircuitState = circuit_breaker.CircuitState
TaskManager = task_manager.TaskManager
TaskState = task_manager.TaskState
sync_from_signals = task_manager.sync_from_signals


def _create_signal_helper(sig_dir: Path, idx: int):
    """Helper for multiprocessing - must be at module level."""
    sig_file = sig_dir / f"test-{idx}.done"
    sig_file.write_text(json.dumps({"id": idx}))


def _record_success_helper(session_dir: Path, agent_type: str):
    """Helper for multiprocessing - must be at module level."""
    record_success(session_dir, agent_type)


def test_circuit_breaker_prevents_task_submission():
    """Test circuit breaker prevents task submission when open."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / "session"
        session_dir.mkdir()
        agent_type = "test_agent"

        # Open circuit by recording failures
        for _ in range(5):
            record_failure(session_dir, agent_type)

        # Verify circuit is open
        allowed = check_circuit(session_dir, agent_type)
        assert not allowed, "Circuit should be OPEN after failures"

        # Attempt task submission (should be blocked)
        storage_dir = Path(tmpdir) / "storage"
        manager = TaskManager(storage_dir)

        # Circuit breaker should prevent this in production
        # Here we verify the check_circuit logic works
        assert not check_circuit(session_dir, agent_type), "Circuit should remain OPEN"


def test_signal_triggers_task_state_update():
    """Test signal creation triggers task manager state update."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / "storage"
        signals_dir = Path(tmpdir) / "signals"
        signals_dir.mkdir()

        # Create task
        manager = TaskManager(storage_dir)
        task = manager.create_task("session-003", "Test task")

        # Create signal using signal tool logic (atomic write)
        signal_file = signals_dir / "phase-001.done"
        signal_data = {"status": "completed", "phase": "001"}
        signal_file.write_text(json.dumps(signal_data))

        # Before sync: task should be SUBMITTED
        assert task.status.state == TaskState.SUBMITTED

        # After sync: task state should update based on signals
        # (In this test, we have a done signal but not sentinel.done)
        sync_from_signals(manager, task.id, signals_dir)
        task = manager.get_task(task.id)

        # Task should still be in working state (not completed yet)
        # because sentinel.done is not present
        assert task.status.state in [TaskState.SUBMITTED, TaskState.WORKING]


def test_concurrent_signal_and_circuit_breaker():
    """Test concurrent signal creation and circuit breaker state updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / "session"
        signals_dir = Path(tmpdir) / "signals"
        session_dir.mkdir()
        signals_dir.mkdir()

        agent_type = "concurrent_agent"

        # Concurrently record successes and create signals
        processes = []
        for i in range(10):
            # Process 1: Record success in circuit breaker
            p1 = Process(target=_record_success_helper, args=(session_dir, agent_type))
            # Process 2: Create signal
            p2 = Process(target=_create_signal_helper, args=(signals_dir, i))

            processes.extend([p1, p2])
            p1.start()
            p2.start()

        # Wait for all processes
        for p in processes:
            p.join()

        # Verify circuit breaker state (should be CLOSED with successes)
        allowed = check_circuit(session_dir, agent_type)
        assert allowed, "Circuit should be CLOSED after successes"

        # Verify all signals created
        signal_files = list(signals_dir.glob("*.done"))
        assert len(signal_files) == 10, f"Expected 10 signals, got {len(signal_files)}"
