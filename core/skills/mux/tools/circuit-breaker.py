#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Circuit Breaker for Swarm Agent Failure Recovery.

Tracks agent failures and prevents cascading failures by opening circuit
after threshold reached. Auto-resets after timeout.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests fail fast
- HALF_OPEN: Testing if circuit can close

Usage:
    # Check if circuit allows execution
    uv run circuit-breaker.py check <session_dir> <agent_type>

    # Record success
    uv run circuit-breaker.py success <session_dir> <agent_type>

    # Record failure
    uv run circuit-breaker.py failure <session_dir> <agent_type>

    # Get circuit status
    uv run circuit-breaker.py status <session_dir> [--agent <agent_type>]

    # Reset circuit
    uv run circuit-breaker.py reset <session_dir> <agent_type>
"""

import argparse
import json
import sys
import time
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Any

# Import file locking utility from Phase 1
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.file_lock import FileLock

# Configuration
FAILURE_THRESHOLD = 3  # Opens after 3 consecutive failures
RESET_TIMEOUT = 300  # 300 seconds (5 minutes) before auto-reset attempt
HALF_OPEN_SUCCESS_THRESHOLD = 1  # Successes needed to close from half-open


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStatus:
    state: CircuitState
    failure_count: int
    last_failure_time: float | None
    half_open_successes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "half_open_successes": self.half_open_successes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircuitStatus":
        return cls(
            state=CircuitState(data.get("state", "closed")),
            failure_count=data.get("failure_count", 0),
            last_failure_time=data.get("last_failure_time"),
            half_open_successes=data.get("half_open_successes", 0),
        )

    @classmethod
    def default(cls) -> "CircuitStatus":
        return cls(
            state=CircuitState.CLOSED,
            failure_count=0,
            last_failure_time=None,
            half_open_successes=0,
        )


def get_circuit_file(session_dir: Path, agent_type: str) -> Path:
    """Get path to circuit state file for agent type."""
    circuit_dir = session_dir / ".circuits"
    circuit_dir.mkdir(parents=True, exist_ok=True)
    return circuit_dir / f"{agent_type}.json"


def load_circuit(session_dir: Path, agent_type: str) -> CircuitStatus:
    """Load circuit status from file."""
    circuit_file = get_circuit_file(session_dir, agent_type)
    if circuit_file.exists():
        data = json.loads(circuit_file.read_text())
        return CircuitStatus.from_dict(data)
    return CircuitStatus.default()


def save_circuit(session_dir: Path, agent_type: str, status: CircuitStatus) -> None:
    """Save circuit status to file."""
    circuit_file = get_circuit_file(session_dir, agent_type)
    circuit_file.write_text(json.dumps(status.to_dict(), indent=2))


def check_circuit(session_dir: Path, agent_type: str) -> bool:
    """Check if circuit allows execution. Returns True if allowed."""
    circuit_file = get_circuit_file(session_dir, agent_type)
    lock_file = circuit_file.parent / f".{circuit_file.name}.lock"

    with FileLock(lock_file):
        status = load_circuit(session_dir, agent_type)
        now = time.time()

        if status.state == CircuitState.CLOSED:
            return True

        if status.state == CircuitState.OPEN:
            # Check if timeout has passed for auto-reset attempt
            if status.last_failure_time and (now - status.last_failure_time) >= RESET_TIMEOUT:
                # Transition to half-open
                status.state = CircuitState.HALF_OPEN
                status.half_open_successes = 0
                save_circuit(session_dir, agent_type, status)
                return True
            return False

        if status.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            return True

        return False


def record_success(session_dir: Path, agent_type: str) -> CircuitStatus:
    """Record successful execution."""
    circuit_file = get_circuit_file(session_dir, agent_type)
    lock_file = circuit_file.parent / f".{circuit_file.name}.lock"

    with FileLock(lock_file):
        status = load_circuit(session_dir, agent_type)

        if status.state == CircuitState.HALF_OPEN:
            status.half_open_successes += 1
            if status.half_open_successes >= HALF_OPEN_SUCCESS_THRESHOLD:
                # Close the circuit
                status.state = CircuitState.CLOSED
                status.failure_count = 0
                status.half_open_successes = 0
        elif status.state == CircuitState.CLOSED:
            # Reset failure count on success
            status.failure_count = 0

        save_circuit(session_dir, agent_type, status)
        return status


def record_failure(session_dir: Path, agent_type: str) -> CircuitStatus:
    """Record failed execution."""
    circuit_file = get_circuit_file(session_dir, agent_type)
    lock_file = circuit_file.parent / f".{circuit_file.name}.lock"

    with FileLock(lock_file):
        status = load_circuit(session_dir, agent_type)
        status.failure_count += 1
        status.last_failure_time = time.time()

        if status.state == CircuitState.HALF_OPEN:
            # Immediately open on failure in half-open state
            status.state = CircuitState.OPEN
        elif status.failure_count >= FAILURE_THRESHOLD:
            status.state = CircuitState.OPEN

        save_circuit(session_dir, agent_type, status)
        return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Circuit breaker for swarm agents")
    parser.add_argument("action", choices=["check", "success", "failure", "status", "reset"])
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("agent_type", nargs="?", default=None)
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    session_dir = args.session_dir.resolve()

    if args.action == "check":
        allowed = check_circuit(session_dir, args.agent_type)
        print(json.dumps({"allowed": allowed}) if args.json else ("allowed" if allowed else "blocked"))
        sys.exit(0 if allowed else 1)

    elif args.action == "success":
        status = record_success(session_dir, args.agent_type)
        print(json.dumps(status.to_dict()) if args.json else f"state: {status.state.value}")

    elif args.action == "failure":
        status = record_failure(session_dir, args.agent_type)
        print(json.dumps(status.to_dict()) if args.json else f"state: {status.state.value}")

    elif args.action == "status":
        if args.agent_type:
            status = load_circuit(session_dir, args.agent_type)
            print(json.dumps(status.to_dict()) if args.json else f"{args.agent_type}: {status.state.value} (failures: {status.failure_count})")
        else:
            # List all circuits
            circuit_dir = session_dir / ".circuits"
            if circuit_dir.exists():
                circuits = {}
                for f in circuit_dir.glob("*.json"):
                    agent_type = f.stem
                    status = load_circuit(session_dir, agent_type)
                    circuits[agent_type] = status.to_dict()
                print(json.dumps(circuits, indent=2) if args.json else "\n".join(f"{k}: {v['state']}" for k, v in circuits.items()))
            else:
                print(json.dumps({}) if args.json else "No circuits found")

    elif args.action == "reset":
        status = CircuitStatus.default()
        save_circuit(session_dir, args.agent_type, status)
        print(json.dumps(status.to_dict()) if args.json else "reset")


if __name__ == "__main__":
    main()
