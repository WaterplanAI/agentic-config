#!/usr/bin/env python3
"""Unit tests for A2A server module.

NOTE: These tests were written for Flask implementation.
Current server uses FastAPI. Skipped until rewritten.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Skip entire module - tests written for Flask, server is now FastAPI
pytestmark = pytest.mark.skip(reason="Server API changed - needs rewrite for FastAPI")

# Import from parent
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "a2a"))

# These imports will fail but module is skipped
try:
    from server import create_app, TaskRequest
except ImportError:
    create_app = None
    TaskRequest = None


def test_create_app():
    """Test Flask app creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)

        assert app is not None
        assert hasattr(app, 'route')


def test_task_request_validation():
    """Test TaskRequest model validation."""
    # Valid request
    req = TaskRequest(
        session_id="test-session",
        prompt="Test prompt",
        agent_type="test-agent"
    )
    assert req.session_id == "test-session"
    assert req.prompt == "Test prompt"
    assert req.agent_type == "test-agent"

    # With optional model config
    req_with_config = TaskRequest(
        session_id="test-session",
        prompt="Test prompt",
        agent_type="test-agent",
        model_config={"temperature": 0.7}
    )
    assert req_with_config.model_config == {"temperature": 0.7}


def test_submit_endpoint_with_auth():
    """Test /a2a/tasks/submit endpoint with authentication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)
        client = app.test_client()

        # Setup dev mode for testing
        os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

        try:
            # Valid request
            response = client.post(
                "/a2a/tasks/submit",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "session_id": "test-session",
                    "prompt": "Test task",
                    "agent_type": "test-agent"
                }
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert "task_id" in data
            assert data["status"] == "submitted"
        finally:
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_submit_endpoint_no_auth():
    """Test /a2a/tasks/submit endpoint rejects without auth."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)
        client = app.test_client()

        # Production mode (no auth configured)
        os.environ.pop("AGENTIC_MUX_DEV_MODE", None)
        os.environ.pop("A2A_BEARER_TOKENS", None)

        # Request without Authorization header
        response = client.post(
            "/a2a/tasks/submit",
            json={
                "session_id": "test-session",
                "prompt": "Test task",
                "agent_type": "test-agent"
            }
        )

        assert response.status_code == 401


def test_get_task_endpoint():
    """Test /a2a/tasks/<task_id> endpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)
        client = app.test_client()

        os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

        try:
            # Create a task first
            submit_response = client.post(
                "/a2a/tasks/submit",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "session_id": "test-session",
                    "prompt": "Test task",
                    "agent_type": "test-agent"
                }
            )
            task_id = json.loads(submit_response.data)["task_id"]

            # Get the task
            get_response = client.get(
                f"/a2a/tasks/{task_id}",
                headers={"Authorization": "Bearer test-token"}
            )

            assert get_response.status_code == 200
            data = json.loads(get_response.data)
            assert data["id"] == task_id
            assert data["sessionId"] == "test-session"
        finally:
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_get_task_not_found():
    """Test /a2a/tasks/<task_id> with non-existent task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)
        client = app.test_client()

        os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

        try:
            response = client.get(
                "/a2a/tasks/nonexistent-task-id",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 404
        finally:
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_cancel_task_endpoint():
    """Test /a2a/tasks/<task_id>/cancel endpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        app = create_app(storage_dir)
        client = app.test_client()

        os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

        try:
            # Create a task
            submit_response = client.post(
                "/a2a/tasks/submit",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "session_id": "test-session",
                    "prompt": "Test task",
                    "agent_type": "test-agent"
                }
            )
            task_id = json.loads(submit_response.data)["task_id"]

            # Cancel the task
            cancel_response = client.post(
                f"/a2a/tasks/{task_id}/cancel",
                headers={"Authorization": "Bearer test-token"}
            )

            assert cancel_response.status_code == 200
            data = json.loads(cancel_response.data)
            assert data["status"]["state"] == "canceled"
        finally:
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)
