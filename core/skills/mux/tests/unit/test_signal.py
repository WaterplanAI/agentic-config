#!/usr/bin/env python3
"""Unit tests for signal file creation."""
import subprocess
import tempfile
from pathlib import Path


class TestResult:
    """Test result tracking."""
    def __init__(self):
        self.passed = []
        self.failed = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"✓ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"✗ {test_name}: {error}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{len(self.passed)}/{total} tests passed")
        if self.failed:
            print("\nFailed tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")
        return len(self.failed) == 0


def run_signal_tool(signal_path: Path, output_path: Path, status: str, **kwargs) -> subprocess.CompletedProcess:
    """Helper to run signal.py tool."""
    cmd = [
        "uv", "run",
        "core/skills/mux/tools/signal.py",
        str(signal_path),
        "--path", str(output_path),
        "--status", status,
    ]

    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                cmd.append(f"--{key.replace('_', '-')}")
            continue
        cmd.extend([f"--{key.replace('_', '-')}", str(value)])

    return subprocess.run(cmd, capture_output=True, text=True)


def test_signal_basic_success(result: TestResult):
    """Test basic signal creation with success status."""
    test_name = "test_signal_basic_success"
    try:
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

            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_basic_fail(result: TestResult):
    """Test basic signal creation with fail status."""
    test_name = "test_signal_basic_fail"
    try:
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

            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_auto_size(result: TestResult):
    """Test auto-calculation of size from output file."""
    test_name = "test_signal_auto_size"
    try:
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

            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_trace_id_auto(result: TestResult):
    """Test auto-detection of trace ID from .trace file."""
    test_name = "test_signal_trace_id_auto"
    try:
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

            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_version_tracking(result: TestResult):
    """Test version and previous path tracking."""
    test_name = "test_signal_version_tracking"
    try:
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

            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_require_bus_fails_when_missing(result: TestResult):
    """Test --require-bus fails when no hub metadata is available."""
    test_name = "test_signal_require_bus_fails_when_missing"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            signals_dir = tmpdir / ".signals"
            output_file = tmpdir / "output.md"
            signal_file = signals_dir / "006-test.done"

            output_file.write_text("test content\n")
            proc = run_signal_tool(signal_file, output_file, "success", require_bus=True)

            assert proc.returncode != 0, "Signal tool should fail when --require-bus is set and no bus exists"
            assert signal_file.exists(), "Signal file should still be created even when publish fails"
            assert "require-bus" in proc.stderr, "stderr should mention require-bus publish failure"
            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_signal_soft_publish_fallback(result: TestResult):
    """Test publish fallback keeps success when bus metadata is missing."""
    test_name = "test_signal_soft_publish_fallback"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            signals_dir = tmpdir / ".signals"
            output_file = tmpdir / "output.md"
            signal_file = signals_dir / "007-test.done"

            output_file.write_text("test content\n")
            proc = run_signal_tool(signal_file, output_file, "success")

            assert proc.returncode == 0, f"Signal tool should succeed without bus metadata: {proc.stderr}"
            assert signal_file.exists(), "Signal file should exist"
            result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))


if __name__ == "__main__":
    import sys

    result = TestResult()

    test_signal_basic_success(result)
    test_signal_basic_fail(result)
    test_signal_auto_size(result)
    test_signal_trace_id_auto(result)
    test_signal_version_tracking(result)
    test_signal_require_bus_fails_when_missing(result)
    test_signal_soft_publish_fallback(result)

    success = result.summary()
    sys.exit(0 if success else 1)
