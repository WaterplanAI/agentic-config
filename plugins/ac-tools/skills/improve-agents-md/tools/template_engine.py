#!/usr/bin/env -S uv run
# /// script
# dependencies = ["typer>=0.9.0", "rich>=13.0.0", "pyyaml>=6.0"]
# requires-python = ">=3.12"
# ///
"""Template rendering engine for AGENTS.md generation.

Reads tooling.yml for per-type values, renders AGENTS.md.template with
{{VAR}} substitution, and injects optional extras (e.g., pep723.md).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from rich.console import Console

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)

VAR_PATTERN = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
TOOLING_PATH = ASSETS_DIR / "tooling.yml"
TEMPLATE_PATH = ASSETS_DIR / "AGENTS.md.template"
EXTRAS_DIR = ASSETS_DIR / "extras"

# Maps tooling.yml keys to template {{VAR}} names
TOOLING_KEY_MAP: dict[str, str] = {
    "package_manager": "PACKAGE_MANAGER",
    "type_checker": "TYPE_CHECKER",
    "linter": "LINTER",
    "after_edit": "AFTER_EDIT",
    "style": "STYLE",
}

NULL_PLACEHOLDER = "(customizable)"


def load_tooling(project_type: str) -> dict[str, Any]:
    """Load tooling config for a project type from tooling.yml."""
    if not TOOLING_PATH.exists():
        msg = f"tooling.yml not found: {TOOLING_PATH}"
        raise FileNotFoundError(msg)
    data = yaml.safe_load(TOOLING_PATH.read_text())
    if project_type not in data:
        msg = f"Unknown project type '{project_type}' in tooling.yml"
        raise KeyError(msg)
    return data[project_type]


def tooling_to_variables(tooling: dict[str, Any]) -> dict[str, str]:
    """Convert tooling config dict to template variable dict.

    Null values become '(customizable)'.
    """
    variables: dict[str, str] = {}
    for yml_key, tmpl_var in TOOLING_KEY_MAP.items():
        value = tooling.get(yml_key)
        variables[tmpl_var] = str(value) if value is not None else NULL_PLACEHOLDER
    return variables


def get_null_keys(tooling: dict[str, Any]) -> list[str]:
    """Return tooling.yml keys that have null values (need questionnaire)."""
    return [k for k in TOOLING_KEY_MAP if tooling.get(k) is None]


def get_extras(tooling: dict[str, Any]) -> list[str]:
    """Return list of extra section names from tooling config."""
    extras = tooling.get("extras", [])
    return extras if isinstance(extras, list) else []


def load_extra_content(name: str) -> str | None:
    """Load an extra section file by name (e.g., 'pep723' -> extras/pep723.md)."""
    path = EXTRAS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text()
    console.print(f"[yellow]Warning: extra '{name}' not found at {path}[/yellow]")
    return None


def render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a template file with {{VAR}} substitution."""
    if not template_path.exists():
        msg = f"Template not found: {template_path}"
        raise FileNotFoundError(msg)
    content = template_path.read_text()
    for var_name, var_value in variables.items():
        content = content.replace(f"{{{{{var_name}}}}}", var_value)
    return content


def inject_extras(content: str, extras: list[str]) -> str:
    """Inject extra sections after '## Style & Conventions' section."""
    if not extras:
        return content
    extra_blocks: list[str] = []
    for name in extras:
        block = load_extra_content(name)
        if block:
            extra_blocks.append(block.rstrip())
    if not extra_blocks:
        return content
    # Find insertion point: after Style & Conventions, before next ## heading
    marker = "## Style & Conventions"
    marker_idx = content.find(marker)
    if marker_idx == -1:
        marker = "## Core Rules"
        marker_idx = content.find(marker)
        if marker_idx == -1:
            return content + "\n" + "\n\n".join(extra_blocks) + "\n"
    next_heading = content.find("\n## ", marker_idx + len(marker))
    if next_heading == -1:
        return content + "\n" + "\n\n".join(extra_blocks) + "\n"
    injection = "\n\n".join(extra_blocks) + "\n"
    return content[:next_heading] + "\n" + injection + content[next_heading:]


def find_unresolved_vars(content: str) -> list[str]:
    """Find any remaining unresolved {{VAR}} placeholders."""
    return VAR_PATTERN.findall(content)


def render_agents_md(project_type: str, overrides: dict[str, str] | None = None) -> str:
    """Full render pipeline: load tooling -> substitute -> inject extras.

    Args:
        project_type: Key from tooling.yml (e.g., 'python-uv', 'typescript').
        overrides: Optional dict of VAR_NAME -> value to override tooling values.

    Returns:
        Fully rendered AGENTS.md content.
    """
    tooling = load_tooling(project_type)
    variables = tooling_to_variables(tooling)
    if overrides:
        variables.update(overrides)
    content = render_template(TEMPLATE_PATH, variables)
    extras = get_extras(tooling)
    content = inject_extras(content, extras)
    unresolved = find_unresolved_vars(content)
    if unresolved:
        console.print(f"[yellow]Warning: unresolved vars: {unresolved}[/yellow]")
    return content


@app.command()
def render(
    project_type: Annotated[str, typer.Argument(help="Project type from tooling.yml")],
    output: Annotated[Path, typer.Argument(help="Output file path")],
    var: Annotated[list[str], typer.Option("--var", help="Override: KEY=value")] = [],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without writing")] = False,
) -> None:
    """Render AGENTS.md for a project type."""
    overrides: dict[str, str] = {}
    for arg in var:
        if "=" in arg:
            key, _, value = arg.partition("=")
            overrides[key.strip().upper()] = value

    rendered = render_agents_md(project_type, overrides or None)

    if dry_run:
        console.print(f"[dim]DRY-RUN: Would write {output}[/dim]")
        console.print(rendered)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        console.print(f"[green]Wrote {output}[/green]")


@app.command()
def list_types() -> None:
    """List available project types from tooling.yml."""
    if not TOOLING_PATH.exists():
        console.print("[red]tooling.yml not found[/red]")
        raise SystemExit(1)
    data = yaml.safe_load(TOOLING_PATH.read_text())
    for ptype in data:
        tooling = data[ptype]
        extras = tooling.get("extras", [])
        suffix = f" (extras: {', '.join(extras)})" if extras else ""
        console.print(f"  {ptype}{suffix}")


if __name__ == "__main__":
    app()
