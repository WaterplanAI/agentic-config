# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.25"]
# ///
"""
A2A Client SDK for Swarm Orchestration.

Example usage:
    client = A2AClient("http://localhost:8000", token="your-token")
    task = client.send_task("Research AI orchestration patterns")
    while task["status"]["state"] == "working":
        time.sleep(5)
        task = client.get_task(task["id"])
    print(task["artifacts"])
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class A2AError(Exception):
    """A2A client error."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"A2A Error {code}: {message}")


class A2AClient:
    """Client for interacting with Swarm A2A server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize A2A client.

        Args:
            base_url: Server base URL
            token: Bearer token for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._request_id = 0

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Make JSON-RPC call.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Result from server

        Raises:
            A2AError: If server returns error
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._next_id(),
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/a2a",
                json=payload,
                headers=self._get_headers(),
            )

        response.raise_for_status()
        data = response.json()

        if "error" in data and data["error"]:
            raise A2AError(data["error"]["code"], data["error"]["message"])

        return data.get("result")

    def get_agent_card(self) -> dict[str, Any]:
        """Fetch agent card.

        Returns:
            Agent card JSON
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.json()

    def send_task(
        self,
        message: str,
        skill: str = "swarm:research",
    ) -> dict[str, Any]:
        """Create and start a new task.

        Args:
            message: Task description
            skill: Skill ID to invoke

        Returns:
            Task object
        """
        return self._call("tasks/send", {"message": message, "skill": skill})

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Get task status and artifacts.

        Args:
            task_id: Task ID

        Returns:
            Task object
        """
        return self._call("tasks/get", {"id": task_id})

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a running task.

        Args:
            task_id: Task ID

        Returns:
            Canceled task object
        """
        return self._call("tasks/cancel", {"id": task_id})

    def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Wait for task to complete.

        Args:
            task_id: Task ID
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds

        Returns:
            Completed task object

        Raises:
            TimeoutError: If task doesn't complete within timeout
            A2AError: If task fails
        """
        start = time.time()
        while time.time() - start < timeout:
            task = self.get_task(task_id)
            state = task["status"]["state"]

            if state == "completed":
                return task
            if state in ("failed", "canceled"):
                raise A2AError(-1, f"Task {state}: {task['status']['message']}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


def main() -> None:
    """CLI interface for testing."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="A2A Client CLI")
    parser.add_argument("--url", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--token", help="Bearer token")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # agent-card command
    subparsers.add_parser("agent-card", help="Get agent card")

    # send command
    send_parser = subparsers.add_parser("send", help="Send a task")
    send_parser.add_argument("message", help="Task message")
    send_parser.add_argument("--skill", default="swarm:research", help="Skill ID")
    send_parser.add_argument("--wait", action="store_true", help="Wait for completion")

    # get command
    get_parser = subparsers.add_parser("get", help="Get task status")
    get_parser.add_argument("task_id", help="Task ID")

    # cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel task")
    cancel_parser.add_argument("task_id", help="Task ID")

    args = parser.parse_args()
    client = A2AClient(args.url, args.token)

    try:
        if args.command == "agent-card":
            result = client.get_agent_card()
        elif args.command == "send":
            result = client.send_task(args.message, args.skill)
            if args.wait:
                result = client.wait_for_completion(result["id"])
        elif args.command == "get":
            result = client.get_task(args.task_id)
        elif args.command == "cancel":
            result = client.cancel_task(args.task_id)
        else:
            parser.print_help()
            return

        print(json.dumps(result, indent=2))
    except A2AError as e:
        print(f"Error: {e}")
        raise SystemExit(1)
    except httpx.HTTPError as e:
        print(f"HTTP Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
