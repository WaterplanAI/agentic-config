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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
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
        raise
    return r


def test_redact_inline_authorization_header() -> TestResult:
    r = TestResult("_redact_secrets: redacts inline Authorization bearer header")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets(
            {'command': 'curl -H "Authorization: Bearer abc123" https://example.com'}
        )
        rendered = str(result)
        assert "abc123" not in rendered, f"Bearer token not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_compact_authorization_header() -> TestResult:
    r = TestResult("_redact_secrets: redacts compact Authorization:\"Bearer ...\" header form")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets(
            {'command': 'curl -H Authorization:"Bearer abc123" https://example.com'}
        )
        rendered = str(result)
        assert "abc123" not in rendered, f"Compact bearer token not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_quoted_secret_assignment_values() -> TestResult:
    r = TestResult("_redact_secrets: redacts quoted secret assignment values")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets({'command': 'export OPENAI_API_KEY="abc 123"'})
        rendered = str(result)
        assert "abc 123" not in rendered, f"Quoted env secret not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        result = _redact_secrets({'command': 'password: "abc 123"'})
        rendered = str(result)
        assert "abc 123" not in rendered, f"Quoted password not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_json_secret_payload() -> TestResult:
    r = TestResult("_redact_secrets: redacts JSON-like secret payloads inside strings")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets({'command': 'curl -d {"api_key":"abc123"} https://example.com'})
        rendered = str(result)
        assert "abc123" not in rendered, f"JSON api_key not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        result = _redact_secrets({'command': 'curl -d {"Authorization":"Bearer abc123"} https://example.com'})
        rendered = str(result)
        assert "abc123" not in rendered, f"JSON Authorization not redacted: {result}"
        assert "REDACTED" in rendered, f"Expected REDACTED marker: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
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
        raise
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
        raise
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
        raise
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
        raise
    return r


def test_redact_secrets_sensitive_keys() -> TestResult:
    r = TestResult("_redact_secrets: redacts values for sensitive dict keys (Issue 3)")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        # Direct sensitive keys
        result = _redact_secrets({"token": "abc123", "api_key": "secret_value"})
        assert result["token"] == "***REDACTED***", f"token not redacted: {result}"
        assert result["api_key"] == "***REDACTED***", f"api_key not redacted: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_secrets_nested_sensitive_keys() -> TestResult:
    r = TestResult("_redact_secrets: redacts nested sensitive keys like Authorization header (Issue 3)")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        # Nested: headers.Authorization
        result = _redact_secrets({"headers": {"Authorization": "Bearer abc123"}})
        assert result["headers"]["Authorization"] == "***REDACTED***", (
            f"Authorization not redacted: {result}"
        )

        # Nested: credentials.password
        result = _redact_secrets({"credentials": {"password": "s3cret"}})
        assert result["credentials"]["password"] == "***REDACTED***", (
            f"password not redacted: {result}"
        )

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_secrets_preserves_nonsensitive_keys() -> TestResult:
    r = TestResult("_redact_secrets: preserves non-sensitive keys (Issue 3)")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets({"command": "ls -la", "file_path": "/tmp/test.txt"})
        assert result["command"] == "ls -la", f"command modified: {result}"
        assert result["file_path"] == "/tmp/test.txt", f"file_path modified: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_redact_secrets_mixed_keys() -> TestResult:
    r = TestResult("_redact_secrets: redacts sensitive keys while preserving others in same dict")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        result = _redact_secrets({
            "url": "https://example.com",
            "access_token": "mytoken123",
            "method": "POST",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----",
        })
        assert result["url"] == "https://example.com", f"url modified: {result}"
        assert result["method"] == "POST", f"method modified: {result}"
        assert result["access_token"] == "***REDACTED***", f"access_token not redacted: {result}"
        assert result["private_key"] == "***REDACTED***", f"private_key not redacted: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_system_message_redacts_secrets() -> TestResult:
    r = TestResult("systemMessage display redacts secrets (MEDIUM-2)")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f'log_dir: "{tmpdir}/logs"\nmax_words: 50\ndisplay_tools:\n  - "Bash"\n'
            )

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook(
                "Bash",
                {"command": "echo hi", "token": "secret123", "api_key": "mykey"},
                env_override=env,
            )

            msg = output.get("systemMessage", "")
            assert "secret123" not in msg, f"Raw token leaked in systemMessage: {msg}"
            assert "mykey" not in msg, f"Raw api_key leaked in systemMessage: {msg}"
            assert "REDACTED" in msg, f"Expected REDACTED marker in systemMessage: {msg}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_audit_log_redacts_inline_authorization_header() -> TestResult:
    r = TestResult("audit log and systemMessage redact inline Authorization bearer header")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f'log_dir: "{tmpdir}/logs"\nmax_words: 50\ndisplay_tools:\n  - "Bash"\n'
            )

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook(
                "Bash",
                {"command": 'curl -H "Authorization: Bearer abc123" https://example.com'},
                env_override=env,
            )

            msg = output.get("systemMessage", "")
            assert "abc123" not in msg, f"Bearer token leaked in systemMessage: {msg}"
            assert "REDACTED" in msg, f"Expected REDACTED marker in systemMessage: {msg}"

            log_file = next((Path(tmpdir) / "logs").glob("*.jsonl"))
            content = log_file.read_text()
            assert "abc123" not in content, f"Bearer token leaked in audit log: {content}"
            assert "REDACTED" in content, f"Expected REDACTED marker in audit log: {content}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_audit_log_redacts_compact_authorization_header() -> TestResult:
    r = TestResult("audit log and systemMessage redact compact Authorization:\"Bearer ...\" header")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f'log_dir: "{tmpdir}/logs"\nmax_words: 50\ndisplay_tools:\n  - "Bash"\n'
            )

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook(
                "Bash",
                {"command": 'curl -H Authorization:"Bearer abc123" https://example.com'},
                env_override=env,
            )

            msg = output.get("systemMessage", "")
            assert "abc123" not in msg, f"Compact bearer token leaked in systemMessage: {msg}"
            assert "REDACTED" in msg, f"Expected REDACTED marker in systemMessage: {msg}"

            log_file = next((Path(tmpdir) / "logs").glob("*.jsonl"))
            content = log_file.read_text()
            assert "abc123" not in content, f"Compact bearer token leaked in audit log: {content}"
            assert "REDACTED" in content, f"Expected REDACTED marker in audit log: {content}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_audit_log_redacts_json_secret_payload() -> TestResult:
    r = TestResult("audit log and systemMessage redact JSON-like secret payloads")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f'log_dir: "{tmpdir}/logs"\nmax_words: 50\ndisplay_tools:\n  - "Bash"\n'
            )

            env = {"CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin")}
            output = run_hook(
                "Bash",
                {"command": 'curl -d {"api_key":"abc123","Authorization":"Bearer abc123"} https://example.com'},
                env_override=env,
            )

            msg = output.get("systemMessage", "")
            assert "abc123" not in msg, f"JSON secret leaked in systemMessage: {msg}"
            assert "REDACTED" in msg, f"Expected REDACTED marker in systemMessage: {msg}"

            log_file = next((Path(tmpdir) / "logs").glob("*.jsonl"))
            content = log_file.read_text()
            assert "abc123" not in content, f"JSON secret leaked in audit log: {content}"
            assert "REDACTED" in content, f"Expected REDACTED marker in audit log: {content}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_sensitive_keys_no_false_positives() -> TestResult:
    r = TestResult("_SENSITIVE_KEYS: no false-positive on monkey/keyboard/author/token_count (MEDIUM-3)")
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tool_audit", str(HOOK_PATH))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _redact_secrets = mod._redact_secrets

        # These keys should NOT be redacted (false positives in old regex)
        result = _redact_secrets({
            "monkey": "banana",
            "keyboard": "qwerty",
            "author": "Jane Doe",
            "token_count": "42",
            "authority": "admin",
            "turkey": "gobble",
        })
        assert result["monkey"] == "banana", f"monkey falsely redacted: {result}"
        assert result["keyboard"] == "qwerty", f"keyboard falsely redacted: {result}"
        assert result["author"] == "Jane Doe", f"author falsely redacted: {result}"
        assert result["token_count"] == "42", f"token_count falsely redacted: {result}"
        assert result["authority"] == "admin", f"authority falsely redacted: {result}"
        assert result["turkey"] == "gobble", f"turkey falsely redacted: {result}"

        # These keys SHOULD be redacted (true positives)
        result = _redact_secrets({
            "api_key": "secret_val",
            "token": "abc123",
            "password": "s3cret",
            "Authorization": "Bearer tok",
            "access_token": "tok123",
            "client_secret": "cs_val",
        })
        assert result["api_key"] == "***REDACTED***", f"api_key not redacted: {result}"
        assert result["token"] == "***REDACTED***", f"token not redacted: {result}"
        assert result["password"] == "***REDACTED***", f"password not redacted: {result}"
        assert result["Authorization"] == "***REDACTED***", f"Authorization not redacted: {result}"
        assert result["access_token"] == "***REDACTED***", f"access_token not redacted: {result}"
        assert result["client_secret"] == "***REDACTED***", f"client_secret not redacted: {result}"

        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
    return r


def test_deep_merge_skips_yaml_null() -> TestResult:
    r = TestResult("_deep_merge: skips None overlay values (YAML null)")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Plugin defaults with display_tools list
            config_dir = Path(tmpdir) / "plugin" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "audit.default.yaml").write_text(
                f'log_dir: "{tmpdir}/logs"\nmax_words: 50\ndisplay_tools:\n  - "Bash"\n'
            )

            # Project override with display_tools: null (YAML null -> Python None)
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "audit.yaml").write_text("display_tools: null\n")

            env = {
                "CLAUDE_PLUGIN_ROOT": str(Path(tmpdir) / "plugin"),
                "CLAUDE_PROJECT_DIR": str(project_dir),
            }
            # Should NOT crash; display_tools: null should be ignored
            output = run_hook("Bash", {"command": "echo hello"}, env_override=env)

            # Hook should succeed (systemMessage or empty -- not a deny)
            decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
            assert decision != "deny", f"Hook denied due to null display_tools: {output}"
        r.mark_pass()
    except Exception as e:
        r.mark_fail(str(e))
        raise
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
        test_redact_inline_authorization_header,
        test_redact_compact_authorization_header,
        test_redact_quoted_secret_assignment_values,
        test_redact_json_secret_payload,
        test_validate_log_permissions_valid,
        test_validate_log_permissions_clamps,
        test_redact_secrets_list,
        test_redact_secrets_sensitive_keys,
        test_redact_secrets_nested_sensitive_keys,
        test_redact_secrets_preserves_nonsensitive_keys,
        test_redact_secrets_mixed_keys,
        test_system_message_redacts_secrets,
        test_audit_log_redacts_inline_authorization_header,
        test_audit_log_redacts_compact_authorization_header,
        test_audit_log_redacts_json_secret_payload,
        test_sensitive_keys_no_false_positives,
        test_deep_merge_skips_yaml_null,
    ])


if __name__ == "__main__":
    main()
