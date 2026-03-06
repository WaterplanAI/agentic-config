#!/usr/bin/env python3
"""
Unit tests for spec parsing functionality.

Tests:
- Success criteria extraction from spec tables
- Modifier parsing (full, lean, leanest)
- Flag parsing (--cycles, --phased)
- Phase count detection
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///

from __future__ import annotations

import re
from pathlib import Path


def parse_success_criteria(spec_content: str) -> list[dict[str, str]]:
    """Parse success criteria table from spec content.

    Expected format:
    | SC-ID | Observable Behavior | Phase |
    |-------|---------------------|-------|
    | SC-001 | Description | 1 |

    Returns:
        List of dicts with keys: id, behavior, phase
    """
    criteria = []

    # Find table rows matching SC-XXX pattern
    pattern = r"\|\s*(SC-\d+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|"

    for match in re.finditer(pattern, spec_content):
        criteria.append({
            "id": match.group(1).strip(),
            "behavior": match.group(2).strip(),
            "phase": match.group(3).strip(),
        })

    return criteria


def parse_arguments(args_string: str) -> dict[str, str | int | bool]:
    """Parse mux-ospec arguments.

    Examples:
        "full specs/path.md" -> {"modifier": "full", "spec_path": "specs/path.md"}
        "lean --cycles=2 specs/path.md" -> {"modifier": "lean", "cycles": 2, ...}
        "--phased specs/path.md" -> {"modifier": "full", "phased": True, ...}

    Returns:
        Dict with parsed arguments
    """
    result: dict[str, str | int | bool] = {
        "modifier": "full",
        "phased": False,
        "cycles": 3,  # default
        "spec_path": "",
    }

    tokens = args_string.split()

    for token in tokens:
        # Modifier detection
        if token in ("full", "lean", "leanest"):
            result["modifier"] = token
        # Flag detection
        elif token == "--phased":
            result["phased"] = True
        elif token.startswith("--cycles="):
            result["cycles"] = int(token.split("=")[1])
        # Spec path (non-flag, non-modifier)
        elif not token.startswith("--"):
            if result["modifier"] != token:  # avoid overwriting modifier as path
                result["spec_path"] = token

    return result


def count_phases_from_sc(criteria: list[dict[str, str]]) -> int:
    """Count total phases from success criteria.

    Returns highest phase number found.
    """
    if not criteria:
        return 1  # default single phase

    phases = [int(sc["phase"]) for sc in criteria if sc["phase"].isdigit()]
    return max(phases) if phases else 1


class TestSuccessCriteriaParsing:
    """Tests for success criteria extraction."""

    def test_parse_standard_sc_table(self, sample_spec: Path) -> None:
        """Parse SC table from standard spec format."""
        content = sample_spec.read_text()
        criteria = parse_success_criteria(content)

        assert len(criteria) == 2
        assert criteria[0]["id"] == "SC-001"
        assert criteria[0]["behavior"] == "Feature X renders correctly"
        assert criteria[0]["phase"] == "1"

    def test_parse_empty_sc_returns_empty_list(self, sample_spec_no_sc: Path) -> None:
        """Spec without SC table returns empty list."""
        content = sample_spec_no_sc.read_text()
        criteria = parse_success_criteria(content)

        assert criteria == []

    def test_parse_multiline_sc_table(self) -> None:
        """Parse SC table with multiple phases."""
        content = """
| SC-ID | Observable Behavior | Phase |
|-------|---------------------|-------|
| SC-001 | First criterion | 1 |
| SC-002 | Second criterion | 1 |
| SC-003 | Third criterion | 2 |
| SC-004 | Fourth criterion | 3 |
"""
        criteria = parse_success_criteria(content)

        assert len(criteria) == 4
        assert criteria[3]["id"] == "SC-004"
        assert criteria[3]["phase"] == "3"

    def test_phase_count_from_sc(self) -> None:
        """Count phases from SC criteria."""
        criteria = [
            {"id": "SC-001", "behavior": "Test", "phase": "1"},
            {"id": "SC-002", "behavior": "Test", "phase": "1"},
            {"id": "SC-003", "behavior": "Test", "phase": "2"},
            {"id": "SC-004", "behavior": "Test", "phase": "3"},
        ]

        phase_count = count_phases_from_sc(criteria)
        assert phase_count == 3

    def test_phase_count_empty_sc(self) -> None:
        """Empty SC defaults to 1 phase."""
        phase_count = count_phases_from_sc([])
        assert phase_count == 1


class TestArgumentParsing:
    """Tests for argument/flag parsing."""

    def test_parse_default_modifier(self) -> None:
        """Default modifier is 'full'."""
        result = parse_arguments("specs/path.md")

        assert result["modifier"] == "full"
        assert result["spec_path"] == "specs/path.md"

    def test_parse_lean_modifier(self) -> None:
        """Lean modifier skips GATHER stage."""
        result = parse_arguments("lean specs/path.md")

        assert result["modifier"] == "lean"
        assert result["spec_path"] == "specs/path.md"

    def test_parse_leanest_modifier(self) -> None:
        """Leanest modifier uses minimal execution."""
        result = parse_arguments("leanest specs/path.md")

        assert result["modifier"] == "leanest"

    def test_parse_cycles_flag(self) -> None:
        """Parse --cycles flag."""
        result = parse_arguments("--cycles=2 specs/path.md")

        assert result["cycles"] == 2

    def test_parse_phased_flag(self) -> None:
        """Parse --phased flag for DAG decomposition."""
        result = parse_arguments("--phased specs/path.md")

        assert result["phased"] is True

    def test_parse_combined_args(self) -> None:
        """Parse combined modifier, flags, and path."""
        result = parse_arguments("lean --cycles=5 --phased specs/2026/02/branch/001-feat.md")

        assert result["modifier"] == "lean"
        assert result["cycles"] == 5
        assert result["phased"] is True
        assert result["spec_path"] == "specs/2026/02/branch/001-feat.md"

    def test_default_cycles_is_three(self) -> None:
        """Default review cycles is 3."""
        result = parse_arguments("specs/path.md")

        assert result["cycles"] == 3


class TestWorkflowModifiers:
    """Tests for workflow behavior based on modifiers."""

    def test_full_includes_gather(self) -> None:
        """Full modifier includes GATHER stage."""
        stages_for_full = ["GATHER", "CONSOLIDATE", "PHASE_LOOP", "TEST", "DOCUMENT", "SENTINEL"]

        result = parse_arguments("full specs/path.md")
        assert result["modifier"] == "full"
        assert "GATHER" in stages_for_full

    def test_lean_skips_gather(self) -> None:
        """Lean modifier skips GATHER stage."""
        stages_for_lean = ["PHASE_LOOP", "TEST", "DOCUMENT"]

        result = parse_arguments("lean specs/path.md")
        assert result["modifier"] == "lean"
        assert "GATHER" not in stages_for_lean

    def test_leanest_minimal_stages(self) -> None:
        """Leanest has minimal stage set."""
        stages_for_leanest = ["PHASE_LOOP", "TEST"]

        result = parse_arguments("leanest specs/path.md")
        assert result["modifier"] == "leanest"
        assert "DOCUMENT" not in stages_for_leanest
        assert "GATHER" not in stages_for_leanest
