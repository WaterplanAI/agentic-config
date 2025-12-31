#!/usr/bin/env python3
"""
Comprehensive tests for dry-run-guard.py pretooluse hook.

Tests all scenarios:
- Allow operations when dry-run disabled
- Block Write/Edit/NotebookEdit when dry-run enabled
- Allow session status file exception
- Block/allow Bash commands based on pattern analysis
- Exception handling and fail-open behavior
"""

import json
import subprocess
from pathlib import Path
from typing import Any


class TestResult:
    """Test result with pass/fail status."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: str | None = None

    def mark_pass(self) -> None:
        self.passed = True

    def mark_fail(self, error: str) -> None:
        self.passed = False
        self.error = error

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        msg = f"  {status}: {self.name}"
        if self.error:
            msg += f"\n    Error: {self.error}"
        return msg


def get_repo_root() -> Path:
    """Get repository root directory."""
    return Path(__file__).parent.parent


def find_claude_pid() -> int | None:
    """Find Claude process PID from process tree (matches hook implementation)."""
    import subprocess
    import os

    try:
        pid = os.getpid()
        for _ in range(10):
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                capture_output=True, text=True
            )
            line = result.stdout.strip()
            if not line:
                break
            parts = line.split()
            if len(parts) >= 3:
                current_pid, ppid, comm = int(parts[0]), int(parts[1]), parts[2]
                if "claude" in comm.lower():
                    return current_pid
                pid = ppid
            else:
                break
    except Exception:
        pass
    return None


def get_status_file_path() -> Path:
    """Get session status file path (matches hook behavior)."""
    repo_root = get_repo_root()
    claude_pid = find_claude_pid()
    if claude_pid:
        return repo_root / f"outputs/session/{claude_pid}/status.yml"
    return repo_root / "outputs/session/status.yml"


def run_hook(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the dry-run-guard hook with given input.

    Returns:
        Hook output as dictionary
    """
    repo_root = get_repo_root()
    hook_path = repo_root / "core/hooks/pretooluse/dry-run-guard.py"

    input_data = {
        "tool_name": tool_name,
        "tool_input": tool_input
    }

    result = subprocess.run(
        [str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        cwd=str(repo_root)  # Run from repo root
    )

    if result.returncode != 0:
        raise RuntimeError(f"Hook exited with code {result.returncode}: {result.stderr}")

    output = json.loads(result.stdout)
    # Convert hook output format to test-friendly format
    hook_output = output.get("hookSpecificOutput", {})
    return {
        "decision": hook_output.get("permissionDecision", "allow"),
        "message": hook_output.get("permissionDecisionReason", "")
    }


def test_allow_when_no_dry_run() -> TestResult:
    """Test that operations are allowed when dry-run is disabled."""
    result = TestResult("Allow operations when dry-run disabled")

    try:
        # Ensure no dry-run status file exists
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

        # Test Write tool
        output = run_hook("Write", {"file_path": "/tmp/test.txt", "content": "test"})
        assert output["decision"] == "allow", f"Expected allow, got {output['decision']}"

        # Test Edit tool
        output = run_hook("Edit", {"file_path": "/tmp/test.txt", "old_string": "a", "new_string": "b"})
        assert output["decision"] == "allow", f"Expected allow, got {output['decision']}"

        # Test NotebookEdit tool
        output = run_hook("NotebookEdit", {"notebook_path": "/tmp/test.ipynb", "new_source": "test"})
        assert output["decision"] == "allow", f"Expected allow, got {output['decision']}"

        # Test Bash with write command
        output = run_hook("Bash", {"command": "echo test > /tmp/test.txt"})
        assert output["decision"] == "allow", f"Expected allow, got {output['decision']}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))

    return result


def test_block_write_when_dry_run() -> TestResult:
    """Test that Write tool is blocked when dry-run enabled."""
    result = TestResult("Block Write tool when dry-run enabled")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test Write tool
        output = run_hook("Write", {"file_path": "/tmp/test.txt", "content": "test"})
        assert output["decision"] == "deny", f"Expected deny, got {output['decision']}"
        assert "Blocked by dry-run mode" in output["message"], "Missing block message"
        assert "/tmp/test.txt" in output["message"], "Missing file path in message"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_block_edit_when_dry_run() -> TestResult:
    """Test that Edit tool is blocked when dry-run enabled."""
    result = TestResult("Block Edit tool when dry-run enabled")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test Edit tool
        output = run_hook("Edit", {"file_path": "/tmp/test.txt", "old_string": "a", "new_string": "b"})
        assert output["decision"] == "deny", f"Expected deny, got {output['decision']}"
        assert "Blocked by dry-run mode" in output["message"], "Missing block message"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_block_notebook_edit_when_dry_run() -> TestResult:
    """Test that NotebookEdit tool is blocked when dry-run enabled."""
    result = TestResult("Block NotebookEdit tool when dry-run enabled")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test NotebookEdit tool
        output = run_hook("NotebookEdit", {"notebook_path": "/tmp/test.ipynb", "new_source": "test"})
        assert output["decision"] == "deny", f"Expected deny, got {output['decision']}"
        assert "Blocked by dry-run mode" in output["message"], "Missing block message"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_allow_session_status_exception() -> TestResult:
    """Test that session status file can be modified even when dry-run enabled."""
    result = TestResult("Allow session status file exception during dry-run")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test Write to status file (should be allowed as exception)
        # Use absolute path to match hook's resolution logic
        abs_path = status_file.resolve()
        output = run_hook("Write", {"file_path": str(abs_path), "content": "dry_run: false"})
        assert output["decision"] == "allow", f"Expected allow for status file exception, got {output['decision']}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_block_bash_write_commands() -> TestResult:
    """Test that Bash commands with write patterns are blocked."""
    result = TestResult("Block Bash commands with write patterns")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test various write patterns
        write_commands = [
            "echo test > /tmp/test.txt",
            "cat file.txt >> output.txt",
            "cp source.txt dest.txt",
            "mv old.txt new.txt",
            "rm file.txt",
            "touch newfile.txt",
            "mkdir newdir",
            "tee output.txt",
            "git add .",
            "git commit -m 'test'",
            "git push",
        ]

        for command in write_commands:
            output = run_hook("Bash", {"command": command})
            assert output["decision"] == "deny", f"Expected deny for '{command}', got {output['decision']}"
            assert "Blocked by dry-run mode" in output["message"], f"Missing block message for '{command}'"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_allow_bash_safe_commands() -> TestResult:
    """Test that safe Bash commands are allowed during dry-run."""
    result = TestResult("Allow safe Bash commands during dry-run")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test various safe patterns
        safe_commands = [
            "ls -la",
            "cat file.txt",
            "grep pattern file.txt",
            "find . -name '*.py'",
            "git status",
            "git diff",
            "git log",
            "git branch",
            "pwd",
            "env",
            "echo 'test'",  # echo without redirect
            "head -n 10 file.txt",
            "tail -f log.txt",
        ]

        for command in safe_commands:
            output = run_hook("Bash", {"command": command})
            assert output["decision"] == "allow", f"Expected allow for '{command}', got {output['decision']}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_allow_read_only_tools() -> TestResult:
    """Test that read-only tools are always allowed."""
    result = TestResult("Allow read-only tools (Read, Grep, Glob)")

    try:
        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test Read tool
        output = run_hook("Read", {"file_path": "/tmp/test.txt"})
        assert output["decision"] == "allow", f"Expected allow for Read, got {output['decision']}"

        # Test Grep tool
        output = run_hook("Grep", {"pattern": "test", "path": "/tmp"})
        assert output["decision"] == "allow", f"Expected allow for Grep, got {output['decision']}"

        # Test Glob tool
        output = run_hook("Glob", {"pattern": "*.py"})
        assert output["decision"] == "allow", f"Expected allow for Glob, got {output['decision']}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_fail_open_on_invalid_json() -> TestResult:
    """Test that hook fails open (allows) when receiving invalid JSON."""
    result = TestResult("Fail-open on invalid JSON input")

    try:
        repo_root = get_repo_root()
        hook_path = repo_root / "core/hooks/pretooluse/dry-run-guard.py"

        # Send invalid JSON
        proc_result = subprocess.run(
            [str(hook_path)],
            input="invalid json",
            capture_output=True,
            text=True,
            cwd=str(repo_root)
        )

        assert proc_result.returncode == 0, "Hook should exit 0 on error (fail-open)"
        output = json.loads(proc_result.stdout)
        hook_output = output.get("hookSpecificOutput", {})
        decision = hook_output.get("permissionDecision", "allow")
        assert decision == "allow", f"Expected allow on error, got {decision}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))

    return result


def test_fail_open_on_malformed_status_file() -> TestResult:
    """Test that hook fails open when status file is malformed."""
    result = TestResult("Fail-open on malformed status.yml")

    try:
        # Create malformed status file
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("invalid: yaml: content: [[[")

        # Test Write tool (should allow because status file is malformed)
        output = run_hook("Write", {"file_path": "/tmp/test.txt", "content": "test"})
        assert output["decision"] == "allow", f"Expected allow on malformed status, got {output['decision']}"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def test_performance() -> TestResult:
    """Test that hook completes within performance requirement (<100ms)."""
    result = TestResult("Performance: hook completes <100ms")

    try:
        import time

        # Enable dry-run
        status_file = get_status_file_path()
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text("dry_run: true\n")

        # Test multiple operations and measure time
        iterations = 10
        start = time.time()

        for _ in range(iterations):
            run_hook("Write", {"file_path": "/tmp/test.txt", "content": "test"})

        elapsed_ms = (time.time() - start) * 1000 / iterations

        # Average should be well under 100ms
        assert elapsed_ms < 100, f"Average execution time {elapsed_ms:.2f}ms exceeds 100ms requirement"

        result.mark_pass()
    except Exception as e:
        result.mark_fail(str(e))
    finally:
        # Cleanup
        status_file = get_status_file_path()
        if status_file.exists():
            status_file.unlink()

    return result


def main() -> None:
    """Run all tests and report results."""
    print("Running dry-run-guard.py hook tests...\n")

    tests = [
        test_allow_when_no_dry_run,
        test_block_write_when_dry_run,
        test_block_edit_when_dry_run,
        test_block_notebook_edit_when_dry_run,
        test_allow_session_status_exception,
        test_block_bash_write_commands,
        test_allow_bash_safe_commands,
        test_allow_read_only_tools,
        test_fail_open_on_invalid_json,
        test_fail_open_on_malformed_status_file,
        test_performance,
    ]

    results = []
    passed = 0
    failed = 0

    for test_func in tests:
        test_result = test_func()
        results.append(test_result)

        if test_result.passed:
            passed += 1
        else:
            failed += 1

        print(test_result)

    print(f"\n{'='*60}")
    print(f"Test Results: {passed} passed, {failed} failed out of {len(results)} total")
    print(f"{'='*60}")

    if failed > 0:
        print("\nFAILED TESTS:")
        for test_result in results:
            if not test_result.passed:
                print(f"  - {test_result.name}")
                if test_result.error:
                    print(f"    {test_result.error}")
        exit(1)
    else:
        print("\nAll tests passed!")
        exit(0)


if __name__ == "__main__":
    main()
