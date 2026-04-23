#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Persist narrow safety allow overrides to project or user safety.yaml."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import _deep_merge, _strip_broad_entries  # noqa: E402


MAX_CONFIG_SIZE = 1_048_576


def _safe_read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return {}
    except IsADirectoryError as exc:
        raise ValueError(f"Config target is a directory: {path}") from exc
    except PermissionError as exc:
        raise ValueError(f"Config target is not readable: {path}") from exc

    if len(content) > MAX_CONFIG_SIZE:
        raise ValueError(f"Config file exceeds {MAX_CONFIG_SIZE} bytes: {path}")

    loaded = yaml.safe_load(content)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return loaded


def _resolve_target_path(target: str) -> Path:
    normalized = target.strip().lower()
    if normalized == "project":
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        return project_dir / "safety.yaml"
    if normalized == "user":
        return Path.home() / ".claude" / "safety.yaml"
    raise ValueError(f"Unsupported persistence target: {target}")


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("Persistence payload must be a JSON object.")

    target = payload.get("target")
    patch = payload.get("patch")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("Persistence payload requires a non-empty 'target'.")
    if not isinstance(patch, dict) or not patch:
        raise ValueError("Persistence payload requires a non-empty object 'patch'.")

    target_path = _resolve_target_path(target)
    existing = _safe_read_yaml(target_path)
    merged = _deep_merge(existing, patch)
    merged = _strip_broad_entries(merged)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(merged, sort_keys=False, allow_unicode=False)
    target_path.write_text(rendered, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "targetPath": str(target_path),
                "message": f"Saved safety allow override in {target_path}.",
            }
        )
    )


if __name__ == "__main__":
    main()
