#!/usr/bin/env python3
"""Unit tests for circuit breaker race condition fixes."""
import subprocess
import sys
import tempfile
import time
from importlib.util import spec_from_file_location, module_from_spec
from multiprocessing import Process, Queue
from pathlib import Path

# Import circuit_breaker module directly from script
script_path = Path(__file__).parent.parent.parent / "tools" / "circuit-breaker.py"
spec = spec_from_file_location("circuit_breaker", script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load circuit_breaker from {script_path}")
circuit_breaker = module_from_spec(spec)
sys.modules["circuit_breaker"] = circuit_breaker
spec.loader.exec_module(circuit_breaker)

# Import needed symbols
CircuitState = circuit_breaker.CircuitState
CircuitStatus = circuit_breaker.CircuitStatus
check_circuit = circuit_breaker.check_circuit
record_success = circuit_breaker.record_success
record_failure = circuit_breaker.record_failure
load_circuit = circuit_breaker.load_circuit
save_circuit = circuit_breaker.save_circuit
FAILURE_THRESHOLD = circuit_breaker.FAILURE_THRESHOLD
RESET_TIMEOUT = circuit_breaker.RESET_TIMEOUT


def _check_and_report_helper(session_path: Path, agent: str, q: Queue):
    """Helper for multiprocessing - must be at module level."""
    try:
        allowed = check_circuit(session_path, agent)
        final_status = load_circuit(session_path, agent)
        q.put(("ok", allowed, final_status.state.value))
    except Exception as e:
        q.put(("error", str(e)))


def test_check_circuit_concurrent_half_open_transition():
    """Test that concurrent check_circuit calls handle OPEN->HALF_OPEN transition atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        agent_type = "test_agent"

        # Setup: Create OPEN circuit with expired timeout
        status = CircuitStatus(
            state=CircuitState.OPEN,
            failure_count=FAILURE_THRESHOLD,
            last_failure_time=time.time() - RESET_TIMEOUT - 1,
            half_open_successes=0,
        )
        save_circuit(session_dir, agent_type, status)

        queue = Queue()

        # Start 5 concurrent processes checking circuit
        processes = []
        for _ in range(5):
            p = Process(target=_check_and_report_helper, args=(session_dir, agent_type, queue))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=2)

        # Collect results
        results = []
        while not queue.empty():
            results.append(queue.get())

        # All should succeed (allowed=True)
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        for r in results:
            assert r[0] == "ok", f"Process failed: {r}"
            assert r[1] is True, f"Circuit should allow execution: {r}"

        # Final state should be HALF_OPEN (exactly one transition)
        final_status = load_circuit(session_dir, agent_type)
        assert final_status.state == CircuitState.HALF_OPEN, f"Expected HALF_OPEN, got {final_status.state}"


def test_record_success_concurrent_increment():
    """Test that concurrent record_success calls increment counter atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        agent_type = "test_agent"

        # Setup: HALF_OPEN state (successes will increment)
        status = CircuitStatus(
            state=CircuitState.HALF_OPEN,
            failure_count=0,
            last_failure_time=None,
            half_open_successes=0,
        )
        save_circuit(session_dir, agent_type, status)

        # Use subprocess instead of multiprocessing to avoid module import issues
        # Record 3 concurrent successes
        processes = []
        for _ in range(3):
            p = subprocess.Popen(
                [sys.executable, str(script_path), "success", str(session_dir), agent_type],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(p)

        for p in processes:
            p.wait(timeout=5)

        # Should transition to CLOSED after threshold met
        final_status = load_circuit(session_dir, agent_type)
        assert final_status.state == CircuitState.CLOSED, f"Expected CLOSED, got {final_status.state}"
        assert final_status.failure_count == 0, f"Expected 0 failures, got {final_status.failure_count}"


def test_record_failure_concurrent_increment():
    """Test that concurrent record_failure calls increment counter atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        agent_type = "test_agent"

        # Setup: CLOSED state with 0 failures
        status = CircuitStatus.default()
        save_circuit(session_dir, agent_type, status)

        # Use subprocess instead of multiprocessing to avoid module import issues
        # Record FAILURE_THRESHOLD concurrent failures
        processes = []
        for _ in range(FAILURE_THRESHOLD):
            p = subprocess.Popen(
                [sys.executable, str(script_path), "failure", str(session_dir), agent_type],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(p)

        for p in processes:
            p.wait(timeout=5)

        # Should transition to OPEN after threshold
        final_status = load_circuit(session_dir, agent_type)
        assert final_status.state == CircuitState.OPEN, f"Expected OPEN, got {final_status.state}"
        assert final_status.failure_count >= FAILURE_THRESHOLD, f"Expected >={FAILURE_THRESHOLD} failures, got {final_status.failure_count}"
