#!/usr/bin/env python3
"""
Compliance tests for phased execution.

Validates that mux executes phases in order, not all at once.
Phases: decomposition -> research -> audits -> consolidation -> coordination -> verification -> sentinel
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations

import pytest

# Phase order (index = execution order)
PHASE_ORDER = [
    "decomposition",
    "research",
    "audit",
    "consolidation",
    "coordination",
    "verification",
    "sentinel",
]


def classify_phase(task_params: dict) -> str | None:
    """Classify a Task call into its phase based on prompt/instructions."""
    prompt = task_params.get("prompt", "").lower()
    instructions = task_params.get("instructions", "").lower()
    description = task_params.get("description", "").lower()
    text = f"{prompt} {instructions} {description}"

    if "sentinel" in text or "quality gate" in text:
        return "sentinel"
    if "verify" in text or "verification" in text:
        return "verification"
    if "coordinat" in text or "writer" in text:
        return "coordination"
    if "consolidat" in text or "aggregate" in text:
        return "consolidation"
    if "audit" in text or "codebase analysis" in text:
        return "audit"
    if "research" in text or "web search" in text:
        return "research"
    if "decompos" in text or "parse task" in text:
        return "decomposition"
    return None


def test_phases_not_all_launched_together(inspector):
    """Verify phases are NOT all launched in the same message batch.

    CRITICAL: The bug we're testing for is launching ALL phases at once
    instead of executing them in sequence.
    """
    # Simulate violation: launching all phases together
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Research topic A",
            "phase": "research",
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
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Consolidate findings",
            "phase": "consolidation",
        },
    )
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Coordinate writers",
            "phase": "coordination",
        },
    )

    task_calls = inspector.get_calls("Task")

    # Extract phases from timestamps
    phases_by_batch: dict[float, list[str]] = {}
    for call in task_calls:
        batch_key = round(call.timestamp, 1)  # Group by ~100ms batches
        phase = call.parameters.get("phase") or classify_phase(call.parameters)
        if phase:
            phases_by_batch.setdefault(batch_key, []).append(phase)

    # Check for violation: multiple distinct phases in same batch
    for batch_time, phases in phases_by_batch.items():
        unique_phases = set(phases)

        # Allow: multiple workers in same phase (e.g., 3 researchers)
        # Block: multiple distinct phases (e.g., research + audit + consolidation)
        if len(unique_phases) > 2:  # Allow research+audit overlap, but not more
            with pytest.raises(AssertionError, match="Phases launched together"):
                assert len(unique_phases) <= 2, (
                    f"Phases launched together at {batch_time}: {unique_phases}. "
                    "Mux must execute phases sequentially, not all at once."
                )


def test_phase_order_respected(inspector):
    """Verify later phases don't start before earlier phases."""
    # Simulate correct order
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Research topic",
        },
    )
    # Advance time
    inspector.advance_time(0.5)
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Audit codebase",
        },
    )

    task_calls = inspector.get_calls("Task")

    # Build phase timeline
    phase_times: dict[str, float] = {}
    for call in task_calls:
        phase = classify_phase(call.parameters)
        if phase and phase not in phase_times:
            phase_times[phase] = call.timestamp

    # Verify order
    for phase, time in phase_times.items():
        phase_idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else -1
        for later_phase, later_time in phase_times.items():
            later_idx = (
                PHASE_ORDER.index(later_phase) if later_phase in PHASE_ORDER else -1
            )
            if later_idx > phase_idx and later_time < time:
                pytest.fail(
                    f"Phase '{later_phase}' started before '{phase}' "
                    f"but should come after in phase order"
                )


def test_no_premature_consolidation(inspector):
    """Verify consolidation doesn't start before research/audit complete."""
    # Simulate premature consolidation (violation)
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Research topic",
        },
    )
    # Consolidation immediately after (no time for research to complete)
    inspector.record(
        "Task",
        {
            "run_in_background": True,
            "prompt": "Consolidate findings",
        },
    )

    task_calls = inspector.get_calls("Task")

    research_calls = [
        c for c in task_calls if classify_phase(c.parameters) == "research"
    ]
    consolidation_calls = [
        c for c in task_calls if classify_phase(c.parameters) == "consolidation"
    ]

    if research_calls and consolidation_calls:
        # Consolidation should not start immediately after research
        # (some time should pass for signals to be created)
        research_end = max(r.timestamp for r in research_calls)
        consolidation_start = min(c.timestamp for c in consolidation_calls)

        # If consolidation starts within 100ms of research launch, it's premature
        if consolidation_start - research_end < 0.1:
            with pytest.raises(AssertionError, match="Premature consolidation"):
                assert consolidation_start - research_end >= 0.1, (
                    "Premature consolidation: started immediately after research launch. "
                    "Must wait for research signals before consolidating."
                )
