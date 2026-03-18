#!/usr/bin/env python3
"""Unit tests for tool-audit hook."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ac_audit_test_support import TestResult, run_tests  # noqa: E402  # pyright: ignore[reportMissingImports]


HOOK_PATH = Path(__file__).parent.parent.parent / "scripts" / "hooks" / "tool-audit.py"


def run_hook(tool_name: str, tool_input: dict, env_override: dict | None = None) -> dict:
    env = dict(os.environ)
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        [str(HOOK_PATH)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True, env=env,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def test_jsonl_log_writing() -> TestResult:
    r = TestResult("Writes JSONL audit log to log_dir")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a config that points log_dir to tmpdir
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "audit.default.yaml"
            config_file.write_text(f"log_dir: \"{tmpdir}/logs\"\nmax_words: 50\ndisplay_tools:\n  - \"Bash\"\n")

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            run_hook("Bash", {"command": "echo hello"}, env_override=env)

            # Check that a log file was created
            log_dir = Path(tmpdir) / "logs"
            assert log_dir.exists(), "Log directory was not auto-created"
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) == 1, f"Expected 1 log file, got {len(log_files)}"

            # Validate JSONL content
            content = log_files[0].read_text().strip()
            entry = json.loads(content)
            assert entry["tool"] == "Bash"
            assert entry["input"]["command"] == "echo hello"
            assert "ts" in entry
            assert "session" in entry
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_truncation_behavior() -> TestResult:
    r = TestResult("Truncates long field values in display")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "audit.default.yaml"
            config_file.write_text(f"log_dir: \"{tmpdir}/logs\"\nmax_words: 5\ndisplay_tools:\n  - \"Bash\"\n")

            long_cmd = " ".join(["word"] * 20)
            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook("Bash", {"command": long_cmd}, env_override=env)

            # systemMessage should contain truncated content
            msg = output.get("systemMessage", "")
            assert "..." in msg, f"Expected truncation in display, got: {msg}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_fail_close_on_error() -> TestResult:
    r = TestResult("Fail-close: denies on invalid JSON input")
    try:
        result = subprocess.run(
            [str(HOOK_PATH)], input="not valid json",
            capture_output=True, text=True,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", f"Expected deny on error, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_missing_log_directory_autocreates() -> TestResult:
    r = TestResult("Auto-creates missing log directory")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "new-audit-logs"
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "audit.default.yaml"
            config_file.write_text(f"log_dir: \"{log_dir}\"\nmax_words: 50\ndisplay_tools:\n  - \"Bash\"\n")

            assert not log_dir.exists(), "Log dir should not exist before test"
            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            run_hook("Bash", {"command": "test"}, env_override=env)
            assert log_dir.exists(), "Log dir should be auto-created"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_config_override_precedence() -> TestResult:
    r = TestResult("Project config overrides plugin defaults")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Plugin defaults with max_words=50
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f"log_dir: \"{tmpdir}/logs\"\nmax_words: 50\ndisplay_tools:\n  - \"Bash\"\n"
            )

            # Project override with max_words=3
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "audit.yaml").write_text("max_words: 3\n")

            long_cmd = " ".join(["word"] * 20)
            env = {
                "CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin"),
                "CLAUDE_PROJECT_DIR": str(project_dir),
            }
            output = run_hook("Bash", {"command": long_cmd}, env_override=env)

            # With max_words=3, truncation should be aggressive
            msg = output.get("systemMessage", "")
            assert "..." in msg, f"Expected truncation with override, got: {msg}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_fail_close_when_log_path_is_unusable() -> TestResult:
    r = TestResult("Fail-close when audit log path cannot be created")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            unusable_log_path = Path(tmpdir) / "not-a-directory"
            unusable_log_path.write_text("occupied")
            (config_dir / "audit.default.yaml").write_text(
                f"log_dir: \"{unusable_log_path}\"\nmax_words: 50\ndisplay_tools:\n  - \"Bash\"\n"
            )

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook("Bash", {"command": "echo hello"}, env_override=env)
            decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
            assert decision == "deny", f"Expected deny, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_fail_close_on_empty_input() -> TestResult:
    r = TestResult("Fail-close: denies on empty stdin")
    try:
        result = subprocess.run(
            [str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", f"Expected deny on empty input, got {decision}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def main() -> None:
    run_tests("tool-audit unit tests", [
        test_jsonl_log_writing,
        test_truncation_behavior,
        test_fail_close_on_error,
        test_missing_log_directory_autocreates,
        test_config_override_precedence,
        test_fail_close_when_log_path_is_unusable,
        test_fail_close_on_empty_input,
    ])


if __name__ == "__main__":
    main()
