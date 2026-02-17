# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.0"]
# ///
r"""
A2A Task Manager: Maps swarm sessions to A2A Task objects.

State transitions:
  submitted -> working -> [input-required] -> completed
                     \                        /
                      -> failed -> canceled
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TaskState(Enum):
    """A2A task states per specification."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# Valid state transitions per A2A task lifecycle
VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.SUBMITTED: {
        TaskState.WORKING,
        TaskState.FAILED,
        TaskState.CANCELED,
    },
    TaskState.WORKING: {
        TaskState.INPUT_REQUIRED,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELED,
    },
    TaskState.INPUT_REQUIRED: {TaskState.WORKING, TaskState.CANCELED},
    # Terminal states: no transitions allowed
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELED: set(),
}


@dataclass
class TaskStatus:
    """Current task status."""

    state: TaskState
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Artifact:
    """Task output artifact."""

    name: str
    type: str  # MIME type
    parts: list[dict[str, Any]]


@dataclass
class Message:
    """History message."""

    role: str  # "user" | "agent"
    parts: list[dict[str, Any]]


@dataclass
class Task:
    """A2A Task object."""

    id: str
    session_id: str
    status: TaskStatus
    artifacts: list[Artifact] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to A2A JSON format."""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "status": {
                "state": self.status.state.value,
                "message": self.status.message,
                "timestamp": self.status.timestamp,
            },
            "artifacts": [
                {"name": a.name, "type": a.type, "parts": a.parts} for a in self.artifacts
            ],
            "history": [{"role": m.role, "parts": m.parts} for m in self.history],
        }


class TaskManager:
    """Manages A2A tasks and swarm session mapping."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        """Initialize task manager.

        Args:
            storage_dir: Directory for task persistence (default: .a2a/tasks/)
        """
        self.storage_dir = storage_dir or Path(".a2a/tasks")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, Task] = {}
        self._session_to_task: dict[str, str] = {}  # session_id -> task_id

    def create_task(self, session_id: str, input_text: str) -> Task:
        """Create a new A2A task for a swarm session.

        Args:
            session_id: Swarm session ID
            input_text: User's task request

        Returns:
            Created Task object
        """
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        task = Task(
            id=task_id,
            session_id=session_id,
            status=TaskStatus(state=TaskState.SUBMITTED, message="Task submitted"),
            history=[Message(role="user", parts=[{"type": "text", "text": input_text}])],
        )
        self._tasks[task_id] = task
        self._session_to_task[session_id] = task_id
        self._persist(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        if task_id in self._tasks:
            return self._tasks[task_id]
        # Try loading from storage
        return self._load(task_id)

    def get_task_by_session(self, session_id: str) -> Task | None:
        """Get task by swarm session ID."""
        task_id = self._session_to_task.get(session_id)
        return self.get_task(task_id) if task_id else None

    def update_status(
        self, task_id: str, state: TaskState, message: str
    ) -> Task | None:
        """Update task status with state transition validation.

        Args:
            task_id: Task ID
            state: New state
            message: Status message

        Returns:
            Updated task or None if not found or invalid transition
        """
        task = self.get_task(task_id)
        if not task:
            return None

        # Validate state transition
        current_state = task.status.state
        valid_next_states = VALID_TRANSITIONS.get(current_state, set())

        if state not in valid_next_states:
            # Invalid transition - return None to signal error
            return None

        task.status = TaskStatus(state=state, message=message)
        self._persist(task)
        return task

    def add_artifact(
        self, task_id: str, name: str, mime_type: str, content: str
    ) -> Task | None:
        """Add artifact to task.

        Args:
            task_id: Task ID
            name: Artifact filename
            mime_type: MIME type
            content: Artifact content

        Returns:
            Updated task or None if not found
        """
        task = self.get_task(task_id)
        if not task:
            return None
        artifact = Artifact(
            name=name,
            type=mime_type,
            parts=[{"type": "text", "text": content}],
        )
        task.artifacts.append(artifact)
        self._persist(task)
        return task

    def add_agent_message(self, task_id: str, message: str) -> Task | None:
        """Add agent message to history.

        Args:
            task_id: Task ID
            message: Agent message

        Returns:
            Updated task or None if not found
        """
        task = self.get_task(task_id)
        if not task:
            return None
        task.history.append(Message(role="agent", parts=[{"type": "text", "text": message}]))
        self._persist(task)
        return task

    def cancel_task(self, task_id: str) -> Task | None:
        """Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            Updated task or None if task not found or in terminal state
        """
        # update_status will validate transition to CANCELED
        return self.update_status(task_id, TaskState.CANCELED, "Task canceled by user")

    def _persist(self, task: Task) -> None:
        """Persist task to storage."""
        path = self.storage_dir / f"{task.id}.json"
        path.write_text(json.dumps(task.to_dict(), indent=2))

    def _load(self, task_id: str) -> Task | None:
        """Load task from storage."""
        path = self.storage_dir / f"{task_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        task = Task(
            id=data["id"],
            session_id=data["sessionId"],
            status=TaskStatus(
                state=TaskState(data["status"]["state"]),
                message=data["status"]["message"],
                timestamp=data["status"]["timestamp"],
            ),
            artifacts=[
                Artifact(name=a["name"], type=a["type"], parts=a["parts"])
                for a in data.get("artifacts", [])
            ],
            history=[
                Message(role=m["role"], parts=m["parts"])
                for m in data.get("history", [])
            ],
        )
        self._tasks[task_id] = task
        self._session_to_task[task.session_id] = task_id
        return task


# Swarm integration helpers
def sync_from_signals(manager: TaskManager, task_id: str, signals_dir: Path) -> None:
    """Sync task state from swarm signal files.

    Args:
        manager: Task manager
        task_id: Task ID to update
        signals_dir: Path to .signals/ directory
    """
    if not signals_dir.exists():
        return

    done_signals = list(signals_dir.glob("*.done"))
    fail_signals = list(signals_dir.glob("*.fail"))

    if fail_signals:
        # Read first failure with error handling
        try:
            fail_data = json.loads(fail_signals[0].read_text())
            error_msg = fail_data.get('error', 'unknown')
        except (json.JSONDecodeError, OSError) as e:
            error_msg = f"malformed signal file: {e}"

        manager.update_status(task_id, TaskState.FAILED, f"Worker failed: {error_msg}")
        return

    if done_signals:
        # Check if all expected signals present (heuristic: sentinel.done = final)
        sentinel_done = signals_dir / "sentinel.done"
        if sentinel_done.exists():
            # Read deliverable path from sentinel signal with error handling
            try:
                sentinel_data = json.loads(sentinel_done.read_text())
                deliverable_path = Path(sentinel_data.get("path", ""))
                if deliverable_path.exists():
                    manager.add_artifact(
                        task_id,
                        deliverable_path.name,
                        "text/markdown",
                        deliverable_path.read_text(),
                    )
            except (json.JSONDecodeError, OSError, KeyError) as e:
                # Log error but continue with completion
                # (signal exists but malformed - task did complete)
                manager.add_agent_message(
                    task_id,
                    f"Warning: could not read deliverable from sentinel signal: {e}",
                )

            manager.update_status(task_id, TaskState.COMPLETED, "Workflow completed")
        else:
            # Still working
            manager.update_status(
                task_id,
                TaskState.WORKING,
                f"In progress: {len(done_signals)} phases complete",
            )


if __name__ == "__main__":
    # Quick test
    manager = TaskManager(Path("/tmp/a2a-test"))
    task = manager.create_task("session-001", "Research AI orchestration patterns")
    print(f"Created: {task.id}")
    manager.update_status(task.id, TaskState.WORKING, "Starting research phase")
    print(f"Updated: {json.dumps(task.to_dict(), indent=2)}")
