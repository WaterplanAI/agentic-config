"""A2A (Agent-to-Agent) Protocol Support for Swarm Orchestration."""

from .auth import generate_token, verify_token
from .client import A2AClient, A2AError
from .task_manager import Task, TaskManager, TaskState

__all__ = [
    "A2AClient",
    "A2AError",
    "Task",
    "TaskManager",
    "TaskState",
    "generate_token",
    "verify_token",
]
