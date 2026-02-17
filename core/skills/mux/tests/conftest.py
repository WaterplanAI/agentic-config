#!/usr/bin/env python3
"""
Shared pytest fixtures and utilities for mux compliance testing.

Provides two-layer architecture:
1. MockClient for fast unit tests
2. Claude Agent SDK for integration tests (marked slow/expensive)
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0", "pytest-asyncio>=0.23.0", "claude-agent-sdk>=0.1.29"]
# ///

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

# Configure pytest-asyncio mode
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks test as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "expensive: marks test as expensive (API costs)")
    config.addinivalue_line("markers", "integration: marks test as integration test")
    config.addinivalue_line("markers", "asyncio: marks test as async")


@dataclass
class ToolCall:
    """Captured tool call for inspection."""

    name: str
    parameters: dict[str, Any]
    timestamp: float = field(default_factory=lambda: __import__("time").time())


class ToolCallInspector:
    """Captures and inspects tool calls for compliance validation."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []
        self._time_offset: float = 0.0

    def record(self, name: str, parameters: dict[str, Any]) -> None:
        """Record a tool call."""
        import time

        self.calls.append(
            ToolCall(name=name, parameters=parameters, timestamp=time.time() + self._time_offset)
        )

    def has_tool(self, name: str) -> bool:
        """Check if tool was called."""
        return any(c.name == name for c in self.calls)

    def get_calls(self, name: str) -> list[ToolCall]:
        """Get all calls for specific tool."""
        return [c for c in self.calls if c.name == name]

    def count(self, name: str) -> int:
        """Count calls for specific tool."""
        return len(self.get_calls(name))

    def clear(self) -> None:
        """Clear all recorded calls."""
        self.calls.clear()
        self._time_offset = 0.0

    def advance_time(self, seconds: float) -> None:
        """Advance simulated time for phase separation testing."""
        self._time_offset += seconds


class MockClient:
    """Mock Anthropic client for unit tests."""

    def __init__(self, inspector: ToolCallInspector) -> None:
        self.inspector = inspector
        self.messages = MagicMock()
        self.messages.create = self._mock_create

    def _mock_create(self, **kwargs: Any) -> MagicMock:
        """Mock message creation and capture tool use."""
        tools = kwargs.get("tools", [])

        # Simulate tool use in response
        response = MagicMock()
        response.content = []

        # Check for Task tool usage (mux should always use this)
        if any(t.get("name") == "Task" for t in tools):
            self.inspector.record("Task", {"run_in_background": True})

        return response


@pytest.fixture
def inspector() -> ToolCallInspector:
    """Provide tool call inspector for test."""
    return ToolCallInspector()


@pytest.fixture
def mock_client(inspector: ToolCallInspector) -> MockClient:
    """Provide mock client for unit tests."""
    return MockClient(inspector)


def is_sdk_available() -> bool:
    """Check if claude-agent-sdk is installed."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: F401

        return True
    except ImportError:
        return False


def is_claude_authenticated() -> bool:
    """Check if Claude CLI is authenticated."""
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


@pytest.fixture
def sdk_options() -> "ClaudeAgentOptions":
    """Provide Claude Agent SDK options for integration tests.

    Requires Claude CLI to be authenticated (claude login).
    Marked as slow and expensive - skip by default.
    """
    if not is_sdk_available():
        pytest.skip("claude-agent-sdk not installed")
    if not is_claude_authenticated():
        pytest.skip("Claude CLI not authenticated - run 'claude login'")

    from claude_agent_sdk import ClaudeAgentOptions

    return ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=1,
        model="claude-sonnet-4-5-20250929",
    )


# DEPRECATED: Use sdk_options instead
@pytest.fixture
def real_client() -> Any:
    """Provide real Anthropic client for integration tests.

    DEPRECATED: Use sdk_options fixture with claude-agent-sdk instead.

    Requires ANTHROPIC_API_KEY environment variable.
    Marked as slow and expensive - skip by default.
    """
    import os

    try:
        from anthropic import Anthropic
    except ImportError:
        pytest.skip("anthropic package not installed - use sdk_options instead")
        return None  # unreachable but helps type checker

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set - skipping real API test")

    return Anthropic(api_key=api_key)


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Provide temporary session directory structure."""
    session = tmp_path / "session"
    session.mkdir()

    # Create standard directories
    (session / "audits").mkdir()
    (session / "deliverables").mkdir()
    (session / ".signals").mkdir()
    (session / "workers").mkdir()

    return session


@pytest.fixture
def mux_config(session_dir: Path) -> dict[str, Any]:
    """Provide mux configuration for testing."""
    return {
        "session_dir": str(session_dir),
        "signals_dir": str(session_dir / ".signals"),
        "workers_dir": str(session_dir / "workers"),
        "audits_dir": str(session_dir / "audits"),
        "deliverables_dir": str(session_dir / "deliverables"),
    }
