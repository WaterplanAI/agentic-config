#!/usr/bin/env python3
"""Unit tests for signal file creation."""
import subprocess
import tempfile
from pathlib import Path


def run_signal_tool(signal_path: Path, output_path: Path, status: str, **kwargs) -> subprocess.CompletedProcess:
    """Helper to run signal.py tool."""
    cmd = [
        "uv", "run",
        "${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py",
        str(signal_path),
        "--path", str(output_path),
        "--status", status,
    ]

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

    return subprocess.run(cmd, capture_output=True, text=True)


def test_signal_basic_success():
    """Test basic signal creation with success status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        signals_dir = tmpdir / ".signals"
        output_file = tmpdir / "output.md"
        signal_file = signals_dir / "001-test.done"

        # Create output file
        output_file.write_text("test content\n")

        # Run signal tool
        proc = run_signal_tool(signal_file, output_file, "success")

        # Verify success
        assert proc.returncode == 0, f"Signal tool failed: {proc.stderr}"

        # Verify signal file exists with .done extension
        assert signal_file.exists(), "Signal file should exist with .done extension"

        # Verify signal content
        content = signal_file.read_text()
        assert f"path: {output_file}" in content, "Signal should contain output path"
        assert "status: success" in content, "Signal should have success status"
        test_size = len("test content\n")
        assert f"size: {test_size}" in content, "Signal should have correct size"
        assert "created_at:" in content, "Signal should have timestamp"


def test_signal_basic_fail():
    """Test basic signal creation with fail status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        signals_dir = tmpdir / ".signals"
        output_file = tmpdir / "output.md"
        signal_file = signals_dir / "002-test.fail"

        # Run signal tool with error message
        proc = run_signal_tool(signal_file, output_file, "fail", error="timeout error")

        # Verify success
        assert proc.returncode == 0, f"Signal tool failed: {proc.stderr}"

        # Verify signal file exists with .fail extension
        assert signal_file.exists(), "Signal file should exist with .fail extension"

        # Verify signal content
        content = signal_file.read_text()
        assert "status: fail" in content, "Signal should have fail status"
        assert "error: timeout error" in content, "Signal should contain error message"


def test_signal_auto_size():
    """Test auto-calculation of size from output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        signals_dir = tmpdir / ".signals"
        output_file = tmpdir / "output.md"
        signal_file = signals_dir / "003-test.done"

        # Create output file with known content
        content = "A" * 1000
        output_file.write_text(content)

        # Run signal tool without --size
        run_signal_tool(signal_file, output_file, "success")

        # Verify size was auto-calculated
        signal_content = signal_file.read_text()
        assert f"size: {len(content)}" in signal_content, "Size should be auto-calculated from file"


def test_signal_trace_id_auto():
    """Test auto-detection of trace ID from .trace file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        signals_dir = tmpdir / ".signals"
        output_file = tmpdir / "output.md"
        signal_file = signals_dir / "004-test.done"
        trace_file = tmpdir / ".trace"

        # Create .trace file
        trace_file.write_text("trace-12345\n")

        # Run signal tool without --trace-id
        run_signal_tool(signal_file, output_file, "success")

        # Verify trace ID was auto-detected
        signal_content = signal_file.read_text()
        assert "trace_id: trace-12345" in signal_content, "Trace ID should be auto-detected from .trace file"


def test_signal_version_tracking():
    """Test version and previous path tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        signals_dir = tmpdir / ".signals"
        output_file = tmpdir / "output-v2.md"
        signal_file = signals_dir / "005-test.done"
        previous_file = tmpdir / "output-v1.md"

        # Run signal tool with version info
        run_signal_tool(
            signal_file, output_file, "success",
            version=2, previous=str(previous_file)
        )

        # Verify version fields in signal
        signal_content = signal_file.read_text()
        assert "version: 2" in signal_content, "Signal should contain version number"
        assert f"previous: {previous_file}" in signal_content, "Signal should contain previous path"
