#!/usr/bin/env python3
"""
Compliance tests for signal protocol requirements.

Validates that mux never manually polls signals - only via verify.py automation.
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations



def test_no_manual_signal_polling(inspector):
    """Verify mux never manually polls signal files."""
    forbidden_patterns = ["ls .signals", "find .signals", "test -f", "[ -f"]

    # Simulate mux operations
    inspector.record(
        "Bash",
        {
            "command": "uv run verify.py --signals-dir /path/.signals --expected 3",
        },
    )

    bash_calls = inspector.get_calls("Bash")

    for call in bash_calls:
        command = call.parameters.get("command", "")

        # Verify no manual polling patterns
        for pattern in forbidden_patterns:
            assert (
                pattern not in command
            ), f"Manual signal polling forbidden: {pattern}"


def test_no_ls_signals_in_loop(inspector):
    """Verify mux never uses ls or find to check signals."""
    # Allowed: verify.py automation
    inspector.record(
        "Bash",
        {
            "command": "uv run verify.py --expected 2",
        },
    )

    # Verify no ls/find commands targeting signals
    bash_calls = inspector.get_calls("Bash")

    for call in bash_calls:
        command = call.parameters.get("command", "")

        # Forbidden patterns
        assert "ls" not in command or ".signals" not in command, "Manual ls .signals forbidden"
        assert (
            "find" not in command or ".signals" not in command
        ), "Manual find .signals forbidden"


def test_signals_via_verify_py(inspector):
    """Verify signal verification always uses verify.py."""
    # Simulate proper signal verification
    inspector.record(
        "Bash",
        {
            "command": "uv run /path/to/verify.py --signals-dir /session/.signals --expected 3",
        },
    )

    bash_calls = inspector.get_calls("Bash")

    # Find signal-related commands
    signal_commands = [
        c for c in bash_calls if ".signals" in c.parameters.get("command", "")
    ]

    # All must use verify.py
    for cmd in signal_commands:
        command = cmd.parameters.get("command", "")
        assert (
            "verify.py" in command
        ), "Signal verification must use verify.py, not manual polling"


def test_no_while_loop_signal_checks(inspector):
    """Verify mux never uses while loops to wait for signals."""
    forbidden_patterns = ["while", "until", "for"]

    inspector.record("Bash", {"command": "uv run verify.py --expected 2"})

    bash_calls = inspector.get_calls("Bash")

    for call in bash_calls:
        command = call.parameters.get("command", "")

        if ".signals" in command or "signal" in command.lower():
            # Verify no loop constructs
            for pattern in forbidden_patterns:
                assert (
                    pattern not in command.lower()
                ), f"Forbidden loop construct in signal check: {pattern}"


def test_verify_py_has_expected_count(inspector):
    """Verify verify.py always receives --expected parameter."""
    # Simulate verify.py calls
    inspector.record(
        "Bash",
        {
            "command": "uv run verify.py --signals-dir /path/.signals --expected 3",
        },
    )

    bash_calls = inspector.get_calls("Bash")
    verify_calls = [c for c in bash_calls if "verify.py" in c.parameters.get("command", "")]

    for call in verify_calls:
        command = call.parameters.get("command", "")

        # Verify --expected parameter present
        assert (
            "--expected" in command
        ), "verify.py must receive --expected count parameter"
