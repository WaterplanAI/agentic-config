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

# Import the hook module directly for unit-testing internal functions
HOOKS_DIR = Path(__file__).parent.parent.parent / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))


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


def test_redact_secrets_api_key() -> TestResult:
    r = TestResult("_redact_secrets: redacts API key patterns")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        # sk- key
        result = _redact_secrets({"command": "export TOKEN=sk-abc123defghijklmnopqrst"})
        assert "sk-abc123" not in str(result), f"sk- key not redacted: {result}"

        # ghp_ token
        result = _redact_secrets({"msg": "ghp_" + "A" * 36})
        assert ("ghp_" + "A" * 36) not in str(result), f"ghp_ token not redacted: {result}"

        # AKIA AWS key
        result = _redact_secrets({"data": "AKIAIOSFODNN7EXAMPLE"})
        assert "AKIAIOSFODNN7EXAMPLE" not in str(result), f"AKIA key not redacted: {result}"

        # api_key=value pattern
        result = _redact_secrets("api_key=mysecretvalue123")
        assert "mysecretvalue123" not in str(result), f"api_key not redacted: {result}"

        # Nested structure
        result = _redact_secrets({"outer": {"inner": "token=sk-abcdefghijklmnopqrstuv"}})
        assert "sk-abcdef" not in str(result), f"Nested secret not redacted: {result}"

        # Safe content untouched
        result = _redact_secrets({"command": "echo hello"})
        assert result == {"command": "echo hello"}, f"Safe content modified: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_validate_log_permissions_valid() -> TestResult:
    r = TestResult("_validate_log_permissions: accepts valid permissions")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _validate = mod._validate_log_permissions

        # 0o600 is valid and should pass through
        assert _validate(0o600) == 0o600, "0o600 should be accepted"
        # 0o400 has no group/other bits, should pass
        assert _validate(0o400) == 0o400, "0o400 should be accepted"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_validate_log_permissions_clamps() -> TestResult:
    r = TestResult("_validate_log_permissions: clamps overly permissive values")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _validate = mod._validate_log_permissions

        # 0o644 has group/other bits -> clamped to 0o600
        assert _validate(0o644) == 0o600, "0o644 should be clamped to 0o600"
        # 0o777 has group/other bits -> clamped
        assert _validate(0o777) == 0o600, "0o777 should be clamped to 0o600"
        # Non-int -> default 0o600
        assert _validate("bad") == 0o600, "Non-int should default to 0o600"  # type: ignore[arg-type]
        # Negative -> default 0o600
        assert _validate(-1) == 0o600, "Negative should default to 0o600"
        # > 0o777 -> default 0o600
        assert _validate(0o1000) == 0o600, ">0o777 should default to 0o600"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
    return r


def test_redact_secrets_list() -> TestResult:
    r = TestResult("_redact_secrets: handles list inputs")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets(["normal", "secret=sk-abcdefghijklmnopqrstuv", 42])
        assert "sk-abcdef" not in str(result), f"List secret not redacted: {result}"
        assert result[0] == "normal"
        assert result[2] == 42

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
        test_redact_secrets_api_key,
        test_validate_log_permissions_valid,
        test_validate_log_permissions_clamps,
        test_redact_secrets_list,
    ])


if __name__ == "__main__":
    main()
