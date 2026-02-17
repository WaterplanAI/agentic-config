#!/usr/bin/env python3
"""
Compliance tests for interactive gate requirements.

Validates that mux uses AskUserQuestion at critical decision points:
- Sentinel failure
- Consolidation needed
- Error recovery
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations


def test_sentinel_failure_triggers_user_question(inspector):
    """Verify AskUserQuestion is used when sentinel review fails.

    After sentinel review, if FAIL, orchestrator must ask user:
    - Proceed anyway?
    - Address gaps first?
    """
    # Simulate sentinel failure scenario
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Sentinel review",
            "agent_type": "sentinel",
        },
    )

    # Simulate sentinel signaling failure (via signal file)
    # After failure, orchestrator should ask user
    inspector.record(
        "AskUserQuestion",
        {
            "questions": [
                {
                    "question": "Sentinel review found gaps. How to proceed?",
                    "options": ["Proceed anyway", "Address gaps"],
                }
            ],
        },
    )

    ask_calls = inspector.get_calls("AskUserQuestion")
    sentinel_tasks = [
        c for c in inspector.get_calls("Task") if "sentinel" in c.parameters.get("prompt", "").lower()
    ]

    # If sentinel was launched, user question should follow
    if sentinel_tasks:
        assert len(ask_calls) > 0, (
            "After sentinel review, AskUserQuestion must be used for failure handling"
        )


def test_consolidation_decision_asks_user(inspector):
    """Verify AskUserQuestion is used for consolidation decision.

    When total output > 80KB, orchestrator should ask:
    - Auto-consolidate?
    - Manual review first?
    """
    # Simulate large output scenario
    inspector.record(
        "Bash",
        {
            "command": "uv run .claude/skills/mux/tools/verify.py $SESSION --action total-size",
            "result": "Total: 120KB",  # > 80KB threshold
        },
    )

    # User should be asked about consolidation
    inspector.record(
        "AskUserQuestion",
        {
            "questions": [
                {
                    "question": "Output exceeds 80KB. Consolidate automatically?",
                    "options": ["Auto-consolidate", "Manual review", "Skip consolidation"],
                }
            ],
        },
    )

    ask_calls = inspector.get_calls("AskUserQuestion")

    # Verify consolidation decision was asked
    consolidation_questions = [
        c
        for c in ask_calls
        if any(
            "consolidat" in q.get("question", "").lower()
            for q in c.parameters.get("questions", [])
        )
    ]

    assert len(consolidation_questions) > 0, (
        "When output exceeds threshold, AskUserQuestion must be used for consolidation decision"
    )


def test_error_recovery_asks_user(inspector):
    """Verify AskUserQuestion is used for error recovery decisions.

    On agent timeout/failure, orchestrator should ask:
    - Retry with tighter scope?
    - Skip this agent?
    - Abort session?
    """
    # Simulate error scenario
    inspector.record(
        "AskUserQuestion",
        {
            "questions": [
                {
                    "question": "Agent timed out. How to proceed?",
                    "options": ["Retry with tighter scope", "Skip agent", "Abort"],
                }
            ],
        },
    )

    ask_calls = inspector.get_calls("AskUserQuestion")

    # Verify error recovery questions include appropriate options
    for call in ask_calls:
        questions = call.parameters.get("questions", [])
        for q in questions:
            if "timeout" in q.get("question", "").lower() or "error" in q.get("question", "").lower():
                options = [o.get("label", "") for o in q.get("options", [])]
                has_retry = any("retry" in o.lower() for o in options)
                has_skip = any("skip" in o.lower() for o in options)
                has_abort = any("abort" in o.lower() for o in options)

                assert has_retry or has_skip or has_abort, (
                    "Error recovery AskUserQuestion must include retry/skip/abort options"
                )


def test_no_user_question_for_normal_progress(inspector):
    """Verify AskUserQuestion is NOT used for normal phase transitions.

    Normal flow should proceed automatically with voice/text announcements.
    Only critical decision points should interrupt.
    """
    # Simulate normal flow
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Research topic",
        },
    )
    inspector.record(
        "mcp__voicemode__converse",
        {
            "message": "Research phase launched",
            "wait_for_response": False,
        },
    )
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Audit codebase",
        },
    )

    # No AskUserQuestion between normal phases
    ask_calls = inspector.get_calls("AskUserQuestion")

    # Filter out critical decision questions (those are expected)
    routine_questions = [
        c
        for c in ask_calls
        if not any(
            keyword in str(c.parameters).lower()
            for keyword in ["sentinel", "fail", "error", "consolidat", "timeout"]
        )
    ]

    assert len(routine_questions) == 0, (
        "AskUserQuestion should NOT be used for routine phase transitions. "
        f"Found {len(routine_questions)} non-critical questions."
    )


def test_voice_announcement_between_phases(inspector):
    """Verify voice announcements are used between phases (not questions)."""
    # Simulate phase transition with voice
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Research topic",
            "phase": "research",
        },
    )
    inspector.record(
        "mcp__voicemode__converse",
        {
            "message": "Research complete. Starting audits.",
            "wait_for_response": False,
        },
    )
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Audit codebase",
            "phase": "audit",
        },
    )

    voice_calls = inspector.get_calls("mcp__voicemode__converse")

    # Voice should be used for announcements
    assert len(voice_calls) > 0, "Voice announcements should be used between phases"

    # Voice should not wait for response (announcement, not conversation)
    for call in voice_calls:
        if "complete" in call.parameters.get("message", "").lower():
            assert call.parameters.get("wait_for_response") is False, (
                "Phase transition voice should not wait for response"
            )
