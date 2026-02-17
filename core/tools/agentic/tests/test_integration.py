"""Integration tests for observability gaps compliance."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
AGENTIC_DIR = PROJECT_ROOT / "core" / "tools" / "agentic"

# Files that MUST NOT contain capture_output=True (L2-L4)
NO_CAPTURE_OUTPUT_FILES = [
    AGENTIC_DIR / "ospec.py",
    AGENTIC_DIR / "oresearch.py",
    AGENTIC_DIR / "coordinator.py",
    AGENTIC_DIR / "campaign.py",
]

# Files that must import EXIT_TIMEOUT from lib
EXIT_TIMEOUT_FILES = [
    AGENTIC_DIR / "ospec.py",
    AGENTIC_DIR / "oresearch.py",
    AGENTIC_DIR / "coordinator.py",
    AGENTIC_DIR / "campaign.py",
]


class TestNoCaptureOutput:
    """O-04: Zero capture_output=True remaining in L2-L4 scripts."""

    @pytest.mark.parametrize("filepath", NO_CAPTURE_OUTPUT_FILES, ids=lambda p: p.name)
    def test_no_capture_output(self, filepath: Path) -> None:
        content = filepath.read_text(encoding="utf-8")
        assert "capture_output=True" not in content, (
            f"{filepath.name} still contains capture_output=True"
        )


class TestExitTimeout:
    """A-04: EXIT_TIMEOUT exists and is imported."""

    def test_exit_timeout_in_lib(self) -> None:
        sys.path.insert(0, str(AGENTIC_DIR))
        from lib import EXIT_TIMEOUT, EXIT_CODE_NAMES, NON_ABSORBABLE_EXIT_CODES
        assert EXIT_TIMEOUT == 21
        assert EXIT_TIMEOUT in NON_ABSORBABLE_EXIT_CODES
        assert EXIT_CODE_NAMES[EXIT_TIMEOUT] == "TIMEOUT"

    @pytest.mark.parametrize("filepath", EXIT_TIMEOUT_FILES, ids=lambda p: p.name)
    def test_exit_timeout_imported(self, filepath: Path) -> None:
        content = filepath.read_text(encoding="utf-8")
        assert "EXIT_TIMEOUT" in content, (
            f"{filepath.name} does not reference EXIT_TIMEOUT"
        )


class TestExitInterrupted:
    """R-09, R-10, R-11: KeyboardInterrupt returns EXIT_INTERRUPTED."""

    @pytest.mark.parametrize(
        "filepath",
        [AGENTIC_DIR / "spawn.py", AGENTIC_DIR / "spec.py", AGENTIC_DIR / "researcher.py"],
        ids=lambda p: p.name,
    )
    def test_exit_interrupted_on_keyboard(self, filepath: Path) -> None:
        content = filepath.read_text(encoding="utf-8")
        assert "EXIT_INTERRUPTED" in content, (
            f"{filepath.name} does not reference EXIT_INTERRUPTED"
        )


class TestCoordinatorNoLocalConstants:
    """A-01: coordinator.py has zero locally-defined exit-code constants."""

    def test_no_local_exit_constants(self) -> None:
        content = (AGENTIC_DIR / "coordinator.py").read_text(encoding="utf-8")
        assert "EXIT_SUCCESS = 0" not in content
        assert "EXIT_FAILURE = 1" not in content
        assert "EXIT_DEPTH_EXCEEDED = 2" not in content
        assert "EXIT_INTERRUPTED = 20" not in content
