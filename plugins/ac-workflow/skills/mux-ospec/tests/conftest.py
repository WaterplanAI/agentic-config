#!/usr/bin/env python3
"""
Shared pytest fixtures for mux-ospec testing.

Provides fixtures for:
1. Spec file parsing/validation
2. Session directory structure
3. Tool call inspection (inherited from mux patterns)
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks test as slow")
    config.addinivalue_line("markers", "integration: marks test as integration test")


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

    def record(self, name: str, parameters: dict[str, Any]) -> None:
        """Record a tool call."""
        self.calls.append(ToolCall(name=name, parameters=parameters))

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


@pytest.fixture
def inspector() -> ToolCallInspector:
    """Provide tool call inspector for test."""
    return ToolCallInspector()


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Provide temporary session directory structure for mux-ospec."""
    session = tmp_path / "session"
    session.mkdir()

    # Create mux-ospec standard directories
    (session / ".signals").mkdir()
    (session / "research").mkdir()
    (session / "phases").mkdir()
    (session / "phases" / "phase-1").mkdir()
    (session / "phases" / "phase-2").mkdir()
    (session / "reviews").mkdir()
    (session / "tests").mkdir()

    return session


@pytest.fixture
def sample_spec(tmp_path: Path) -> Path:
    """Provide sample spec file for testing."""
    spec_content = """# Sample Spec

## Human Section

### Requirements
- Build feature X
- Integrate with Y

### Success Criteria
| SC-ID | Observable Behavior | Phase |
|-------|---------------------|-------|
| SC-001 | Feature X renders correctly | 1 |
| SC-002 | Integration with Y works | 2 |

## AI Section

### Plan
(AI fills this)

### Implementation
(AI fills this)
"""
    spec_file = tmp_path / "specs" / "2026" / "02" / "feature-branch" / "001-sample.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(spec_content)
    return spec_file


@pytest.fixture
def sample_spec_no_sc(tmp_path: Path) -> Path:
    """Provide spec file without success criteria table."""
    spec_content = """# Minimal Spec

## Human Section

### Requirements
- Do something

## AI Section
(empty)
"""
    spec_file = tmp_path / "specs" / "minimal.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(spec_content)
    return spec_file


@pytest.fixture
def workflow_state_template() -> dict[str, Any]:
    """Provide workflow state template for testing."""
    return {
        "session_id": "150000-abcd1234",
        "command": "mux-ospec",
        "started_at": "2026-02-04T15:00:00Z",
        "updated_at": "2026-02-04T15:00:00Z",
        "status": "in_progress",
        "arguments": {
            "modifier": "full",
            "spec_path": "/path/to/spec.md",
            "cycles": 3,
            "phased": False,
        },
        "current_phase": 1,
        "current_stage": "GATHER",
        "total_phases": 2,
        "phases": [],
        "error_context": None,
        "resume_instruction": "Resume with: /mux-ospec resume",
    }
