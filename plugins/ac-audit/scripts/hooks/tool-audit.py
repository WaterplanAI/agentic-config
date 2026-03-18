#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Claude Code Tool Audit Hook.

Displays real-time tool usage via systemMessage and writes
append-only JSONL audit log. Config-driven via audit.default.yaml.
Fail-close on errors.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", str(os.getpid()))


def _find_plugin_root() -> Path:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent.parent


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Deep-merge overlay into base. Simpler than ac-safety (no union-merge or most-restrictive-wins)."""
    result = dict(base)
    for key, overlay_val in overlay.items():
        if overlay_val is None:
            continue
        if key not in result:
            result[key] = overlay_val
        elif isinstance(result[key], dict) and isinstance(overlay_val, dict):
            result[key] = _deep_merge(result[key], overlay_val)
        else:
            result[key] = overlay_val
    return result


MAX_CONFIG_SIZE = 1_048_576  # 1 MB


def _safe_read_yaml(path: Path) -> dict:
    """Read YAML file with size guard. Returns empty dict on skip/error."""
    try:
        content = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return {}
    if len(content) > MAX_CONFIG_SIZE:
        print(f"Warning: config file {path} exceeds {MAX_CONFIG_SIZE} bytes, skipping", file=sys.stderr)
        return {}
    result = yaml.safe_load(content)
    if not isinstance(result, dict):
        if result is not None:
            print(f"Warning: config file {path} is not a YAML mapping, skipping", file=sys.stderr)
        return {}
    return result


def _load_audit_config() -> dict:
    plugin_root = _find_plugin_root()
    defaults_path = plugin_root / "config" / "audit.default.yaml"
    config: dict = _safe_read_yaml(defaults_path)

    # User override (deep-merge)
    user_path = Path.home() / ".claude" / "audit.yaml"
    user_cfg = _safe_read_yaml(user_path)
    if user_cfg:
        config = _deep_merge(config, user_cfg)

    # Project override (deep-merge)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    project_path = Path(project_dir) / "audit.yaml"
    proj_cfg = _safe_read_yaml(project_path)
    if proj_cfg:
        config = _deep_merge(config, proj_cfg)

    return config


def _truncate_field_values(obj: object, max_words: int = 50) -> object:
    if isinstance(obj, dict):
        return {k: _truncate_field_values(v, max_words) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_truncate_field_values(item, max_words) for item in obj]
    elif isinstance(obj, str):
        words = obj.split()
        if len(words) > max_words:
            return " ".join(words[:max_words]) + "..."
        return obj
    return obj


def _format_simple(data: dict, indent: int = 0) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{'  ' * indent}{key}:")
            lines.append(_format_simple(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{'  ' * indent}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(_format_simple(item, indent + 1))
                else:
                    lines.append(f"{'  ' * (indent + 1)}- {item}")
        else:
            lines.append(f"{'  ' * indent}{key}: {value}")
    return "\n".join(lines)


# Patterns for redacting secrets from audit log entries
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer)\s*[=:]\s*\S+"), r"\1=***REDACTED***"),
    (re.compile(r"\b(sk-[A-Za-z0-9]{20,})\b"), "***REDACTED_KEY***"),
    (re.compile(r"\b(ghp_[A-Za-z0-9]{36,})\b"), "***REDACTED_KEY***"),
    (re.compile(r"\b(gho_[A-Za-z0-9]{36,})\b"), "***REDACTED_KEY***"),
    (re.compile(r"\b(AKIA[A-Z0-9]{16})\b"), "***REDACTED_KEY***"),
    (re.compile(r"\b(xox[bpras]-[A-Za-z0-9\-]+)\b"), "***REDACTED_KEY***"),
]

# Key names that indicate sensitive values -- matched case-insensitively against dict keys.
# Three tiers to avoid false positives (e.g. "monkey", "author", "token_count"):
#   1. Exact-match standalone words: token, secret, password, etc.
#   2. Known compound key patterns: api_key, access_token, private_key, etc.
#   3. Short ambiguous words only when exact: key, auth
_SENSITIVE_KEYS: re.Pattern[str] = re.compile(
    r"^(?:token|secret|password|passwd|credentials?|authorization|bearer)$"
    r"|(?:api[_\-]?key|access[_\-]?token|refresh[_\-]?token|private[_\-]?key"
    r"|client[_\-]?secret|auth[_\-]?token)"
    r"|^(?:key|auth)$",
    re.IGNORECASE,
)

# Maximum acceptable log permissions (0o600). More permissive values are clamped.
_MAX_LOG_PERMISSIONS = 0o600


def _redact_secrets(obj: object) -> object:
    """Redact common secret patterns from strings and sensitive dict keys in a nested structure."""
    if isinstance(obj, dict):
        result: dict[str, object] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SENSITIVE_KEYS.search(k):
                # For container values (dict/list), recurse so nested keys
                # are individually redacted rather than replacing the whole structure.
                if isinstance(v, (dict, list)):
                    result[k] = _redact_secrets(v)
                else:
                    result[k] = "***REDACTED***"
            else:
                result[k] = _redact_secrets(v)
        return result
    elif isinstance(obj, list):
        return [_redact_secrets(item) for item in obj]
    elif isinstance(obj, str):
        text = obj
        for pattern, replacement in _SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        return text
    return obj


def _validate_log_permissions(value: object) -> int:
    """Validate and clamp log_permissions to no more permissive than 0o600."""
    if not isinstance(value, int):
        return _MAX_LOG_PERMISSIONS
    # Reject clearly bogus values (negative or > 0o777)
    if value < 0 or value > 0o777:
        return _MAX_LOG_PERMISSIONS
    # Clamp: strip any bits more permissive than _MAX_LOG_PERMISSIONS
    # Ensure group/other have no permissions beyond what _MAX_LOG_PERMISSIONS allows
    if value & 0o177:  # any group/other bits set
        print(
            f"Warning: log_permissions {oct(value)} is more permissive than {oct(_MAX_LOG_PERMISSIONS)}, clamping",
            file=sys.stderr,
        )
        return _MAX_LOG_PERMISSIONS
    return value


def _write_audit_log(tool_name: str, tool_input: dict, log_dir: str, log_permissions: int) -> None:
    log_path = Path(os.path.expanduser(log_dir))
    log_path.mkdir(parents=True, exist_ok=True)
    if not log_path.is_dir():
        raise NotADirectoryError(f"Audit log path is not a directory: {log_path}")

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    log_file = log_path / f"{today}.jsonl"
    redacted_input = _redact_secrets(tool_input)
    entry = {"ts": now.isoformat(), "tool": tool_name, "input": redacted_input, "session": SESSION_ID}
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    log_file.chmod(log_permissions)


def main() -> None:
    try:
        json_input = sys.stdin.read().strip()
        if not json_input:
            raise ValueError("No input received from Claude Code")

        data = json.loads(json_input)
        tool_name = data.get("tool_name", "Unknown")
        tool_input = data.get("tool_input", {})

        config = _load_audit_config()
        log_dir = config.get("log_dir", "~/.claude/audit-logs")
        log_permissions = _validate_log_permissions(config.get("log_permissions", 0o600))
        display_tools = set(config.get("display_tools", ["Bash"]))
        max_words = config.get("max_words", 50)

        _write_audit_log(tool_name, tool_input, log_dir, log_permissions)

        if tool_name in display_tools:
            redacted = _redact_secrets(tool_input)
            truncated = _truncate_field_values(redacted, max_words)
            message = f"{tool_name}:\n{_format_simple(truncated) if isinstance(truncated, dict) else str(truncated)}"
            print(json.dumps({"systemMessage": message}))

    except Exception as e:
        # Fail-close: deny on audit errors
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Audit hook error (fail-close): {e}",
            }
        }))
        print(f"Audit hook error (fail-close): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
