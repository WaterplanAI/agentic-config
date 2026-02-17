#!/usr/bin/env python3
"""
Compliance tests for the NO SELF-EXECUTION rule.

CRITICAL: Mux orchestrator must NEVER execute tasks itself.
All work must be delegated via Task().

Forbidden direct execution tools:
- Read, Write, Edit, Grep, Glob (file operations)
- WebFetch, WebSearch (web operations)
- Any Bash command that does actual work

Allowed orchestrator tools:
- Task (delegation)
- Bash (only: mkdir, uv run .claude/skills/mux/tools/*.py)
- AskUserQuestion (user interaction)
- mcp__voicemode__converse (voice updates)
- TaskCreate, TaskUpdate, TaskList (task management)
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations

import re

import pytest


# Tools the orchestrator must NEVER use
FORBIDDEN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
]

# Allowed tools for orchestrator
ALLOWED_TOOLS = [
    "Task",
    "Bash",  # Only for mkdir-p and uv run .claude/skills/mux/tools/*.py
    "AskUserQuestion",
    "mcp__voicemode__converse",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
]

# Allowed bash patterns
ALLOWED_BASH_PATTERNS = [
    r"^mkdir\s+-p\s+",  # Directory creation
    r"^uv\s+run\s+.*tools/",  # MUX tools only
    r"^uv\s+run\s+.*\.py",  # PEP 723 scripts
]


def test_no_read_tool_usage(inspector):
    """Verify orchestrator never uses Read tool.

    Reading files = executing work that should be delegated to workers.
    """
    # Record violation
    inspector.record("Read", {"file_path": "/some/file.md"})

    read_calls = inspector.get_calls("Read")

    with pytest.raises(AssertionError, match="Read is FORBIDDEN"):
        assert len(read_calls) == 0, (
            f"Read is FORBIDDEN for orchestrator - found {len(read_calls)} calls. "
            "Delegate file reading to workers via Task()."
        )


def test_no_write_tool_usage(inspector):
    """Verify orchestrator never uses Write tool.

    Writing files = executing work that should be delegated to workers.
    """
    inspector.record("Write", {"file_path": "/some/output.md", "content": "..."})

    write_calls = inspector.get_calls("Write")

    with pytest.raises(AssertionError, match="Write is FORBIDDEN"):
        assert len(write_calls) == 0, (
            f"Write is FORBIDDEN for orchestrator - found {len(write_calls)} calls. "
            "Delegate file writing to workers via Task()."
        )


def test_no_edit_tool_usage(inspector):
    """Verify orchestrator never uses Edit tool."""
    inspector.record(
        "Edit",
        {
            "file_path": "/some/file.md",
            "old_string": "old",
            "new_string": "new",
        },
    )

    edit_calls = inspector.get_calls("Edit")

    with pytest.raises(AssertionError, match="Edit is FORBIDDEN"):
        assert len(edit_calls) == 0, (
            f"Edit is FORBIDDEN for orchestrator - found {len(edit_calls)} calls. "
            "Delegate file editing to workers via Task()."
        )


def test_no_grep_tool_usage(inspector):
    """Verify orchestrator never uses Grep tool."""
    inspector.record("Grep", {"pattern": "TODO", "path": "/project"})

    grep_calls = inspector.get_calls("Grep")

    with pytest.raises(AssertionError, match="Grep is FORBIDDEN"):
        assert len(grep_calls) == 0, (
            f"Grep is FORBIDDEN for orchestrator - found {len(grep_calls)} calls. "
            "Delegate searching to workers via Task()."
        )


def test_no_glob_tool_usage(inspector):
    """Verify orchestrator never uses Glob tool."""
    inspector.record("Glob", {"pattern": "**/*.md"})

    glob_calls = inspector.get_calls("Glob")

    with pytest.raises(AssertionError, match="Glob is FORBIDDEN"):
        assert len(glob_calls) == 0, (
            f"Glob is FORBIDDEN for orchestrator - found {len(glob_calls)} calls. "
            "Delegate file discovery to workers via Task()."
        )


def test_no_webfetch_tool_usage(inspector):
    """Verify orchestrator never uses WebFetch tool."""
    inspector.record(
        "WebFetch",
        {
            "url": "https://example.com",
            "prompt": "summarize",
        },
    )

    webfetch_calls = inspector.get_calls("WebFetch")

    with pytest.raises(AssertionError, match="WebFetch is FORBIDDEN"):
        assert len(webfetch_calls) == 0, (
            f"WebFetch is FORBIDDEN for orchestrator - found {len(webfetch_calls)} calls. "
            "Delegate web fetching to researchers via Task()."
        )


def test_no_websearch_tool_usage(inspector):
    """Verify orchestrator never uses WebSearch tool."""
    inspector.record("WebSearch", {"query": "python async"})

    websearch_calls = inspector.get_calls("WebSearch")

    with pytest.raises(AssertionError, match="WebSearch is FORBIDDEN"):
        assert len(websearch_calls) == 0, (
            f"WebSearch is FORBIDDEN for orchestrator - found {len(websearch_calls)} calls. "
            "Delegate web searching to researchers via Task()."
        )


def test_bash_only_allowed_patterns(inspector):
    """Verify Bash is only used for allowed patterns."""
    # Allowed: mkdir -p
    inspector.record("Bash", {"command": "mkdir -p /tmp/session"})

    # Allowed: uv run .claude/skills/mux/tools/*.py
    inspector.record("Bash", {"command": "uv run .claude/skills/mux/tools/verify.py /session --action summary"})

    # Forbidden: cat, grep, etc.
    inspector.record("Bash", {"command": "cat /some/file.md"})
    inspector.record("Bash", {"command": "grep TODO /project"})
    inspector.record("Bash", {"command": "ls -la /project/src"})

    bash_calls = inspector.get_calls("Bash")

    forbidden_bash = []
    for call in bash_calls:
        command = call.parameters.get("command", "")
        is_allowed = any(re.match(pattern, command) for pattern in ALLOWED_BASH_PATTERNS)
        if not is_allowed:
            forbidden_bash.append(command)

    with pytest.raises(AssertionError, match="Forbidden Bash"):
        assert len(forbidden_bash) == 0, (
            f"Forbidden Bash commands: {forbidden_bash}. "
            "Orchestrator Bash is only for: mkdir -p, uv run .claude/skills/mux/tools/*.py"
        )


def test_all_work_delegated_via_task(inspector):
    """Verify ALL actual work goes through Task delegation."""
    # Simulate proper delegation
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Read and analyze project structure",
            "subagent_type": "general-purpose",
        },
    )
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Search web for best practices",
            "subagent_type": "general-purpose",
        },
    )

    task_calls = inspector.get_calls("Task")

    # Verify tasks exist for work that would otherwise need forbidden tools
    has_file_work = any(
        any(kw in c.parameters.get("prompt", "").lower() for kw in ["read", "analyze", "audit"])
        for c in task_calls
    )
    has_web_work = any(
        any(kw in c.parameters.get("prompt", "").lower() for kw in ["search", "fetch", "research"])
        for c in task_calls
    )

    assert has_file_work or has_web_work, (
        "Work must be delegated via Task. "
        "Found no tasks with file/web work delegation."
    )


def test_only_allowed_tools_used(inspector):
    """Comprehensive check: only allowed tools are used."""
    # Simulate mux session with only allowed tools
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Audit codebase",
        },
    )
    inspector.record(
        "Bash",
        {
            "command": "mkdir -p /tmp/session/.signals",
        },
    )
    inspector.record(
        "mcp__voicemode__converse",
        {
            "message": "Starting mux",
            "wait_for_response": False,
        },
    )

    # Verify no forbidden tools
    all_tools = {c.name for c in inspector.calls}
    forbidden_used = all_tools & set(FORBIDDEN_TOOLS)

    assert len(forbidden_used) == 0, (
        f"Forbidden tools used: {forbidden_used}. "
        f"Allowed tools: {ALLOWED_TOOLS}"
    )


def test_no_context_gathering_by_orchestrator(inspector):
    """Verify orchestrator never gathers context itself.

    Context gathering (reading files, searching) must be delegated.
    """
    # Simulate delegation (correct)
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Gather context: read project files and understand structure",
            "subagent_type": "general-purpose",
        },
    )

    # Verify no direct context gathering
    context_tools = ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]
    for tool in context_tools:
        calls = inspector.get_calls(tool)
        assert len(calls) == 0, (
            f"Orchestrator used {tool} for context gathering. "
            "Must delegate to workers via Task()."
        )


def test_no_inline_content_in_task_prompts(inspector):
    """Verify Task prompts pass paths, not file content.

    WRONG: Task(prompt="Analyze this: <file content here>")
    RIGHT: Task(prompt="Analyze file at /path/to/file.md")
    """
    # Simulate correct usage
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Analyze file at /session/research/topic.md",
        },
    )

    # Simulate violation
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Analyze this content: # Full file content here\n## Section 1\nLots of text...",
        },
    )

    task_calls = inspector.get_calls("Task")

    for call in task_calls:
        prompt = call.parameters.get("prompt", "")

        # Heuristic: if prompt > 500 chars and has markdown-like content
        if len(prompt) > 500:
            has_file_content = any(
                marker in prompt for marker in ["```", "## ", "### ", "def ", "class ", "import "]
            )
            if has_file_content:
                with pytest.raises(AssertionError, match="Inline content"):
                    assert len(prompt) <= 500, (
                        "Inline content in Task prompt detected. "
                        f"Prompt length: {len(prompt)} chars. "
                        "Pass file PATHS, not content."
                    )
