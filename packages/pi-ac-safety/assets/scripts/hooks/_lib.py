"""
Shared library for ac-safety guardian hooks.

Provides config loading (3-tier deep-merge), decision helpers,
path utilities, and fail-close error handling.

This module is imported by guardian scripts (credential-guardian.py, etc.)
which declare ``dependencies = ["pyyaml"]`` in their PEP 723 headers.
PyYAML is therefore available at runtime via ``uv run --script``.
Do NOT run this file directly -- it is a library, not an entry point.
"""

import json
import os
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import yaml

# Maximum config file size (1 MB). Files exceeding this are skipped.
MAX_CONFIG_SIZE = 1_048_576

# Decision priority for most-restrictive-wins resolution
_DECISION_PRIORITY: dict[str, int] = {"deny": 0, "ask": 1, "allow": 2}


def _most_restrictive(a: str, b: str) -> str:
    """Return the more restrictive of two decisions (deny > ask > allow)."""
    pa = _DECISION_PRIORITY.get(a, 1)  # unknown defaults to ask
    pb = _DECISION_PRIORITY.get(b, 1)
    return a if pa <= pb else b


# Keys whose list values are security-critical and must be union-merged
# (overlay adds to base, never replaces). Matched by suffix.
_UNION_MERGE_SUFFIXES = ("_prefixes", "_allowlist", "_files", "_filenames", "_extensions", "_tools", "_roots")

# Specific list keys that also require union-merge semantics even though they do
# not use one of the generic suffixes above.
_UNION_MERGE_KEYS = frozenset({"allowed_domains", "allowed_cli_actions", "allowed_mcp_actions"})


def _deep_merge(base: dict, overlay: dict) -> dict:
    """
    Deep-merge overlay into base. Returns new dict.

    For category decision dicts, applies most-restrictive-wins.
    For security-critical lists (keys ending in _prefixes, _allowlist,
    _files, _filenames, _extensions) plus selected explicit allow-list keys,
    merges by union (combine + deduplicate).
    For other lists, overlay replaces base entirely.
    For dicts, recursively merge.
    """
    result = dict(base)
    for key, overlay_val in overlay.items():
        # Never let YAML null overwrite an existing value -- most-defensive approach
        # consistent with "most-restrictive-wins" philosophy.
        if overlay_val is None:
            continue
        if key not in result:
            result[key] = overlay_val
        elif isinstance(result[key], dict) and isinstance(overlay_val, dict):
            # Check if this is a "categories" dict (values are decision strings)
            if key == "categories":
                merged_cats: dict[str, str] = dict(result[key])
                for cat_key, cat_val in overlay_val.items():
                    if cat_key in merged_cats:
                        merged_cats[cat_key] = _most_restrictive(merged_cats[cat_key], str(cat_val))
                    else:
                        merged_cats[cat_key] = str(cat_val)
                result[key] = merged_cats
            else:
                result[key] = _deep_merge(result[key], overlay_val)
        elif isinstance(result[key], list) and isinstance(overlay_val, list):
            # Security-critical lists: union-merge to prevent accidental loss of defaults
            if key in _UNION_MERGE_KEYS or any(key.endswith(suffix) for suffix in _UNION_MERGE_SUFFIXES):
                seen: set[str] = set()
                merged_list: list[Any] = []
                for item in result[key] + overlay_val:
                    item_key = str(item)
                    if item_key not in seen:
                        seen.add(item_key)
                        merged_list.append(item)
                result[key] = merged_list
            else:
                # Non-security lists: overlay replaces
                result[key] = overlay_val
        else:
            # Scalars: overlay replaces
            result[key] = overlay_val
    return result


# Paths that are too broad to be allowed in security-critical lists.
# Resolved at runtime so expanduser works correctly.
_OVERLY_BROAD_PATHS: frozenset[str] = frozenset()


def _resolve_broad_paths() -> frozenset[str]:
    """Compute the set of overly broad resolved paths (cached after first call)."""
    global _OVERLY_BROAD_PATHS  # noqa: PLW0603
    if _OVERLY_BROAD_PATHS:
        return _OVERLY_BROAD_PATHS
    home = os.path.expanduser("~")
    _OVERLY_BROAD_PATHS = frozenset({
        os.path.realpath("/"),
        os.path.realpath(home),
        os.path.realpath(home + "/"),
    })
    return _OVERLY_BROAD_PATHS


def _is_broad_path(resolved: str) -> bool:
    """Return True if resolved path is too broad for security-critical lists.

    Rejects:
    - Exact / and $HOME
    - Any ancestor of $HOME (e.g. /Users, /home)
    - Top-level system directories (single-component absolute paths like /tmp, /var, /etc)
    """
    broad = _resolve_broad_paths()
    if resolved in broad:
        return True
    home = os.path.realpath(os.path.expanduser("~"))
    # Reject any path that is an ancestor of HOME
    if home.startswith(resolved.rstrip("/") + "/"):
        return True
    # Reject single-component absolute paths (top-level dirs: /tmp, /var, /etc, /Users, etc.)
    # A resolved absolute path like "/Users" has parts ('/', 'Users') -- 2 parts = top-level dir.
    from pathlib import PurePosixPath
    parts = PurePosixPath(resolved).parts
    if len(parts) <= 2 and resolved != "/":
        return True
    return False


def _strip_broad_entries(config: dict[str, Any]) -> dict[str, Any]:
    """Remove overly broad entries from union-merged allowlist security lists.

    Strips: /, ~/, HOME ancestors (/Users, /home), and top-level system dirs.
    Only applies to allowlist-type keys. Keys starting with ``blocked`` are
    deny-lists and intentionally contain broad paths -- stripping them would
    weaken security.
    """
    for key, val in config.items():
        if isinstance(val, dict):
            config[key] = _strip_broad_entries(val)
        elif (
            isinstance(val, list)
            and any(key.endswith(s) for s in _UNION_MERGE_SUFFIXES)
            and not key.startswith("blocked")
        ):
            original_len = len(val)
            cleaned = [
                item for item in val
                if not _is_broad_path(os.path.realpath(os.path.expanduser(str(item).rstrip("/") or "/")))
            ]
            if len(cleaned) < original_len:
                print(
                    f"Warning: removed overly broad entries from '{key}' "
                    f"(rejected {original_len - len(cleaned)} entry/entries)",
                    file=sys.stderr,
                )
            config[key] = cleaned
    return config


def _find_plugin_root() -> Path:
    """Find plugin root from CLAUDE_PLUGIN_ROOT env or relative to this file."""
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    # Fallback: scripts/hooks/_lib.py -> plugin root is ../..
    return Path(__file__).resolve().parent.parent.parent


def load_config() -> dict[str, Any]:
    """
    Load safety config with 3-tier deep-merge resolution.

    Priority (most-restrictive-wins at category level):
      1. Project-level: $CWD/safety.yaml or $CLAUDE_PROJECT_DIR/safety.yaml
      2. User-level: ~/.claude/safety.yaml
      3. Plugin defaults: <plugin_root>/config/safety.default.yaml

    Returns:
        Merged config dict.
    """
    plugin_root = _find_plugin_root()

    def _safe_read_yaml(path: Path) -> dict[str, Any]:
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

    # Layer 1: Plugin defaults (base)
    defaults_path = plugin_root / "config" / "safety.default.yaml"
    config: dict[str, Any] = _safe_read_yaml(defaults_path)

    # Layer 2: User-level
    user_path = Path.home() / ".claude" / "safety.yaml"
    user_cfg = _safe_read_yaml(user_path)
    if user_cfg:
        config = _deep_merge(config, user_cfg)

    # Layer 3: Project-level
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    project_path = Path(project_dir) / "safety.yaml"
    proj_cfg = _safe_read_yaml(project_path)
    if proj_cfg:
        config = _deep_merge(config, proj_cfg)

    # Reject overly broad entries (/, ~/) that could weaken security
    config = _strip_broad_entries(config)

    return config


def get_category_decision(config: dict[str, Any], guardian: str, category: str) -> str:
    """
    Get the resolved decision for a guardian category.

    Returns "deny", "ask", or "allow". Defaults to "ask" if not configured.
    """
    guardian_cfg = config.get(guardian, {})
    if not isinstance(guardian_cfg, dict):
        return "ask"
    categories = guardian_cfg.get("categories", {})
    if not isinstance(categories, dict):
        return "ask"
    decision = str(categories.get(category, "ask")).lower()
    if decision not in _DECISION_PRIORITY:
        return "ask"
    return decision


def resolve_path(path: str) -> str:
    """Resolve path: expanduser + realpath, with /private normalization for macOS."""
    resolved = os.path.realpath(os.path.expanduser(path))
    # macOS: /tmp -> /private/tmp, /var -> /private/var, /etc -> /private/etc
    # Traversal like /tmp/../Users/foo resolves to /private/Users/foo which
    # doesn't match /Users/foo in prefix checks. Normalize: if resolved starts
    # with /private/ but is NOT under the three real /private/* dirs, strip it.
    if sys.platform == "darwin" and resolved.startswith("/private/"):
        _REAL_PRIVATE = ("/private/tmp", "/private/var", "/private/etc")
        if not any(resolved.startswith(p + "/") or resolved == p for p in _REAL_PRIVATE):
            candidate = resolved[len("/private"):]
            if os.path.exists(os.path.dirname(candidate) or "/"):
                resolved = candidate
    return resolved


def is_in_prefixes(path: str, prefixes: list[str]) -> bool:
    """Check if resolved path starts with any resolved prefix."""
    resolved = resolve_path(path)
    for prefix in prefixes:
        real_prefix = os.path.realpath(os.path.expanduser(prefix.rstrip("/")))
        if resolved.startswith(real_prefix + "/") or resolved == real_prefix:
            return True
    return False


def deny(reason: str) -> None:
    """Print JSON deny decision to stdout."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def allow() -> None:
    """Print JSON allow decision to stdout."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }))


def build_permission_decision_metadata(
    allow_key: str | None = None,
    project_patch: dict[str, Any] | None = None,
    user_patch: dict[str, Any] | None = None,
    script_path: str = "scripts/hooks/persist-allow.py",
) -> dict[str, Any]:
    """Build optional metadata consumed by hook-compat's richer ask UI."""
    metadata: dict[str, Any] = {}
    if allow_key:
        metadata["allowKey"] = allow_key
    if project_patch:
        metadata["projectPersistence"] = {
            "scriptPath": script_path,
            "payload": {
                "target": "project",
                "patch": project_patch,
            },
        }
    if user_patch:
        metadata["userPersistence"] = {
            "scriptPath": script_path,
            "payload": {
                "target": "user",
                "patch": user_patch,
            },
        }
    return metadata



def ask(reason: str, metadata: dict[str, Any] | None = None) -> None:
    """Print JSON ask decision to stdout."""
    hook_output: dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }
    if metadata:
        hook_output["permissionDecisionMetadata"] = metadata
    print(json.dumps({
        "hookSpecificOutput": hook_output
    }))


def fail_close(func: Callable[[], None]) -> Callable[[], None]:
    """
    Decorator: wraps hook main() with fail-close error handling.
    On ANY exception (config parse, unexpected error), deny the operation.
    """
    @wraps(func)
    def wrapper() -> None:
        try:
            func()
        except Exception as e:
            deny(f"Hook error (fail-close): {e}")
            print(f"Hook error (fail-close): {e}", file=sys.stderr)
    return wrapper
