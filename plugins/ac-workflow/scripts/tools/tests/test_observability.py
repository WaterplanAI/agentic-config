"""Unit tests for lib/observability.py patterns P1-P7."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.observability import (
    Timer,
    build_child_env_with_trace,
    emit_event,
    get_trace_id,
    propagate_trace_id,
    run_streaming,
    signal_completion,
    write_consolidated_report,
    write_live_report,
)


# -- P4: Timer ---------------------------------------------------------------


class TestTimer:
    def test_elapsed_ms_after_exit(self) -> None:
        with Timer() as t:
            time.sleep(0.05)
        assert t.elapsed_ms >= 40  # Allow some margin
        assert t.elapsed_ms < 500

    def test_elapsed_seconds(self) -> None:
        with Timer() as t:
            time.sleep(0.05)
        assert t.elapsed_seconds >= 0.04
        assert t.elapsed_seconds < 0.5

    def test_running_elapsed_ms(self) -> None:
        with Timer() as t:
            mid = t.running_elapsed_ms
            time.sleep(0.02)
        after = t.running_elapsed_ms
        assert after >= mid


# -- P1: run_streaming -------------------------------------------------------


class TestRunStreaming:
    def test_captures_stdout(self) -> None:
        exit_code, stdout = run_streaming(
            ["python3", "-c", "print('hello')"],
            timeout=10,
            label="test",
        )
        assert exit_code == 0
        assert "hello" in stdout

    def test_forwards_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code, stdout = run_streaming(
            ["python3", "-c", "import sys; print('err', file=sys.stderr); print('out')"],
            timeout=10,
            label="test",
        )
        assert exit_code == 0
        assert "out" in stdout
        # stderr is forwarded to parent stderr
        captured = capsys.readouterr()
        assert "err" in captured.err

    def test_timeout_raises(self) -> None:
        import subprocess
        with pytest.raises(subprocess.TimeoutExpired):
            run_streaming(
                ["python3", "-c", "import time; time.sleep(10)"],
                timeout=1,
                label="test",
            )

    def test_nonzero_exit_code(self) -> None:
        exit_code, _ = run_streaming(
            ["python3", "-c", "import sys; sys.exit(42)"],
            timeout=10,
            label="test",
        )
        assert exit_code == 42


# -- P3: Trace ID Propagation ------------------------------------------------


class TestTraceId:
    def test_get_trace_id_from_env(self) -> None:
        with patch.dict(os.environ, {"AGENTIC_TRACE_ID": "abc123"}):
            assert get_trace_id() == "abc123"

    def test_get_trace_id_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AGENTIC_TRACE_ID", None)
            assert get_trace_id() is None

    def test_propagate_trace_id_generates(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AGENTIC_TRACE_ID", None)
            trace_id = propagate_trace_id()
            assert len(trace_id) == 16  # hex of 8 bytes
            assert os.environ["AGENTIC_TRACE_ID"] == trace_id

    def test_propagate_trace_id_from_session(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AGENTIC_TRACE_ID", None)
            (tmp_path / ".trace").write_text("session-trace-123\n")
            trace_id = propagate_trace_id(tmp_path)
            assert trace_id == "session-trace-123"

    def test_build_child_env_with_trace(self) -> None:
        env = build_child_env_with_trace(2, "trace-abc")
        assert env["AGENTIC_SPAWN_DEPTH"] == "3"
        assert env["AGENTIC_TRACE_ID"] == "trace-abc"
        # Should not mutate os.environ
        assert os.environ.get("AGENTIC_SPAWN_DEPTH") != "3"


# -- P2: Signal Completion ---------------------------------------------------


class TestSignalCompletion:
    def test_writes_signal_file(self, tmp_path: Path) -> None:
        (tmp_path / ".signals").mkdir()
        path = signal_completion(tmp_path, "L2", "test-stage", "done", elapsed_seconds=1.5)
        assert path is not None
        assert path.exists()
        content = path.read_text()
        assert "status: done" in content
        assert "layer: L2" in content

    def test_noop_when_session_dir_none(self) -> None:
        result = signal_completion(None, "L2", "test", "done")
        assert result is None


# -- P5: Structured Progress Events ------------------------------------------


class TestEmitEvent:
    def test_emits_json_and_human(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.dict(os.environ, {"AGENTIC_TRACE_ID": "t1"}):
            emit_event("L2", "test-stage", "COMPLETE", elapsed_ms=1500, detail="ok")
        captured = capsys.readouterr()
        assert "@{" in captured.err  # JSON line
        assert "[test-stage] COMPLETE (1.5s) - ok" in captured.err


# -- P6: Live Report ---------------------------------------------------------


class TestWriteLiveReport:
    def test_appends_to_file(self, tmp_path: Path) -> None:
        write_live_report(tmp_path, "L2", "stage1", "STARTING")
        write_live_report(tmp_path, "L2", "stage1", "COMPLETE", elapsed_seconds=2.5)
        content = (tmp_path / ".live-report").read_text()
        assert "STARTING" in content
        assert "COMPLETE" in content
        assert "(2.5s)" in content
        assert content.count("\n") == 2

    def test_noop_when_none(self) -> None:
        write_live_report(None, "L2", "stage1", "STARTING")  # Should not raise


# -- P7: Consolidated Report -------------------------------------------------


class TestWriteConsolidatedReport:
    def test_generates_report(self, tmp_path: Path) -> None:
        (tmp_path / ".trace").write_text("test-trace-id\n")
        (tmp_path / ".signals").mkdir()
        (tmp_path / ".signals" / "L2-stage1.done").write_text(
            "layer: L2\nname: stage1\nstatus: done\ncreated_at: 2026-02-08T00:00:00Z\n"
        )
        write_live_report(tmp_path, "L2", "stage1", "COMPLETE", elapsed_seconds=1.0)
        report_path = write_consolidated_report(tmp_path)
        assert report_path.exists()
        content = report_path.read_text()
        assert "test-trace-id" in content
        assert "L2" in content
        assert "stage1" in content
        assert "Timeline" in content
