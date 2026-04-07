"""Shared utilities for GSuite CLI tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

# Configuration directory (must match auth.py)
CONFIG_DIR = Path(os.environ.get("GSUITE_CONFIG_DIR", Path.home() / ".agents" / "gsuite"))
CONFIG_FILE = CONFIG_DIR / "config.yml"


def load_config() -> dict[str, Any]:
    """Load config from ~/.agents/gsuite/config.yml."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_FILE.read_text()) or {}
    except yaml.YAMLError as e:
        from rich.console import Console
        Console(stderr=True).print(f"[yellow]Warning:[/yellow] Config parse error: {e}")
        return {}


def is_confirmation_enabled(tool: str) -> bool:
    """Check if confirmation is enabled for a tool.

    Priority:
    1. Tool-specific config (confirmation.<tool>)
    2. Default config (confirmation.default)
    3. Fallback: True (confirmation enabled)

    Args:
        tool: Tool name (gmail, calendar, tasks)

    Returns:
        True if confirmation should be shown
    """
    config = load_config()
    confirmation = config.get("confirmation", {})

    # Check tool-specific override
    if tool in confirmation:
        return bool(confirmation[tool])

    # Check default
    return bool(confirmation.get("default", True))


def confirm_action(
    action: str,
    details: str,
    tool: str,
    *,
    skip_confirmation: bool = False,
) -> bool:
    """Prompt user confirmation for write operations.

    Args:
        action: Action name (e.g., "Send email", "Create event")
        details: Details to display
        tool: Tool name for config lookup
        skip_confirmation: If True, skip confirmation (--yes flag)

    Returns:
        True if action should proceed
    """
    # Skip if --yes flag or config disables confirmation
    if skip_confirmation or not is_confirmation_enabled(tool):
        return True

    # Interactive confirmation
    import typer
    from rich.console import Console
    from rich.panel import Panel

    console = Console(stderr=True)
    console.print(Panel(details, title=f"[yellow]{action}[/yellow]", border_style="yellow"))

    return typer.confirm("Proceed?", default=False)


def merge_extra(
    base_body: dict[str, Any],
    extra_json: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge --extra JSON into request body and extract API params.

    Convention:
    - Top-level keys (except '_api') = merged into request body
    - '_api' key = API method parameters

    Examples:
        '{"recurrence": ["RRULE:..."]}' -> body gets recurrence
        '{"recurrence": [...], "_api": {"sendUpdates": "all"}}' -> body + api params

    Args:
        base_body: Base request body dict
        extra_json: JSON string from --extra option

    Returns:
        Tuple of (merged_body, api_params)

    Raises:
        ValueError: If extra_json is invalid JSON
    """
    if not extra_json:
        return base_body, {}

    try:
        extra = json.loads(extra_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid --extra JSON: {e}") from e

    if not isinstance(extra, dict):
        raise ValueError("--extra must be a JSON object")

    # Extract API params from _api key
    api_params = extra.pop("_api", {})
    if not isinstance(api_params, dict):
        raise ValueError("--extra '_api' must be a JSON object")

    # Remaining keys are body fields
    merged_body = {**base_body, **extra}

    return merged_body, api_params
