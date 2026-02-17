# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.100", "uvicorn>=0.23", "pydantic>=2.0"]
# ///
"""
A2A JSON-RPC 2.0 Server for Swarm Orchestration.

Endpoints:
  GET  /.well-known/agent.json  - Agent Card discovery
  POST /a2a                     - JSON-RPC 2.0 methods
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import verify_token
from task_manager import TaskManager, TaskState, sync_from_signals

app = FastAPI(title="Swarm A2A Server", version="1.0.0")

# CORS for external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize task manager
STORAGE_DIR = Path(".a2a/tasks")
task_manager = TaskManager(STORAGE_DIR)

# Load agent card
AGENT_CARD_PATH = Path(__file__).parent / "agent-card.json"


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] | None = None
    id: str | int | None = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    result: Any = None
    error: dict[str, Any] | None = None
    id: str | int | None = None


@app.get("/.well-known/agent.json")
async def get_agent_card() -> Response:
    """Return Agent Card for discovery."""
    if not AGENT_CARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Agent card not found")
    return Response(
        content=AGENT_CARD_PATH.read_text(),
        media_type="application/json",
    )


@app.post("/a2a")
async def handle_jsonrpc(request: Request) -> JsonRpcResponse:
    """Handle JSON-RPC 2.0 requests."""
    # Verify auth
    auth_header = request.headers.get("Authorization", "")
    if not verify_token(auth_header):
        return JsonRpcResponse(
            error={"code": -32001, "message": "Unauthorized"},
            id=None,
        )

    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)
    except Exception:
        return JsonRpcResponse(
            error={"code": -32700, "message": "Parse error"},
            id=None,
        )

    # Route methods
    method_handlers = {
        "tasks/send": handle_tasks_send,
        "tasks/get": handle_tasks_get,
        "tasks/cancel": handle_tasks_cancel,
        "tasks/sendSubscribe": handle_tasks_subscribe,
    }

    handler = method_handlers.get(rpc_request.method)
    if not handler:
        return JsonRpcResponse(
            error={"code": -32601, "message": f"Method not found: {rpc_request.method}"},
            id=rpc_request.id,
        )

    try:
        result = await handler(rpc_request.params or {})
        return JsonRpcResponse(result=result, id=rpc_request.id)
    except Exception as e:
        return JsonRpcResponse(
            error={"code": -32000, "message": str(e)},
            id=rpc_request.id,
        )


async def handle_tasks_send(params: dict[str, Any]) -> dict[str, Any]:
    """Create and start a new task (tasks/send).

    Params:
        message: str - Task description
        skill: str - Skill ID (e.g., "swarm:research")
    """
    message = params.get("message", "")
    skill = params.get("skill", "swarm:research")

    if not message:
        raise ValueError("message is required")

    # Create swarm session
    session_result = subprocess.run(
        ["uv", "run", "tools/session.py", skill.replace(":", "-")],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    if session_result.returncode != 0:
        raise RuntimeError(f"Session creation failed: {session_result.stderr}")

    session_dir = session_result.stdout.strip()
    session_id = Path(session_dir).name

    # Create A2A task
    task = task_manager.create_task(session_id, message)

    # Start swarm workflow (non-blocking)
    # Note: In production, this would invoke the swarm skill
    task_manager.update_status(task.id, TaskState.WORKING, "Workflow started")

    return task.to_dict()


async def handle_tasks_get(params: dict[str, Any]) -> dict[str, Any]:
    """Get task status (tasks/get).

    Params:
        id: str - Task ID
    """
    task_id = params.get("id", "")
    if not task_id:
        raise ValueError("id is required")

    task = task_manager.get_task(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")

    # Sync from signals if working
    if task.status.state == TaskState.WORKING:
        session_dir = Path("tmp/swarm") / task.session_id
        signals_dir = session_dir / ".signals"
        sync_from_signals(task_manager, task_id, signals_dir)
        task = task_manager.get_task(task_id)

    return task.to_dict() if task else {}


async def handle_tasks_cancel(params: dict[str, Any]) -> dict[str, Any]:
    """Cancel a task (tasks/cancel).

    Params:
        id: str - Task ID
    """
    task_id = params.get("id", "")
    if not task_id:
        raise ValueError("id is required")

    task = task_manager.cancel_task(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")

    return task.to_dict()


async def handle_tasks_subscribe(params: dict[str, Any]) -> dict[str, Any]:
    """Subscribe to task updates (tasks/sendSubscribe).

    Note: SSE streaming not implemented in MVP. Returns current state.

    Params:
        id: str - Task ID
    """
    return await handle_tasks_get(params)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the A2A server."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
