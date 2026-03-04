#!/usr/bin/env -S uv run
# /// script
# dependencies = ["typer>=0.9.0", "rich>=13.0.0", "pyyaml>=6.0"]
# requires-python = ">=3.12"
# ///
"""AGENTS.md generation entrypoint.

Orchestrates project type detection, tooling resolution, and AGENTS.md
rendering via the template engine.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_AGENTS_STUB = """# Project-Specific Instructions

Add repository-specific guidelines here. This file is preserved by
`/improve-agents-md update` and never overwritten automatically.
"""


def run_tool(name: str, args: list[str]) -> int:
    """Run a sibling tool script. Returns exit code."""
    tool_path = TOOLS_DIR / name
    if not tool_path.exists():
        console.print(f"[red]Tool not found: {name}[/red]")
        return 1
    cmd = ["uv", "run", str(tool_path), *args]
    result = subprocess.run(cmd)
    return result.returncode


def detect_type(target: Path) -> str:
    """Detect project type via project_type.py."""
    result = subprocess.run(
        ["uv", "run", str(TOOLS_DIR / "project_type.py"), str(target)],
        capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        if line.startswith("type="):
            return line.split("=", 1)[1]
    return "generic"


def ensure_project_agents_file(target: Path, *, dry_run: bool) -> None:
    """Create PROJECT_AGENTS.md if missing.

    The file is intentionally lightweight and user-editable.
    """
    project_agents_path = target / "PROJECT_AGENTS.md"
    if project_agents_path.exists():
        return

    if dry_run:
        console.print(f"[dim]DRY-RUN: Would write {project_agents_path}[/dim]")
        return

    project_agents_path.write_text(PROJECT_AGENTS_STUB)
    console.print(f"[green]Wrote {project_agents_path}[/green]")


@app.command()
def setup(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    project_type: Annotated[str, typer.Option("--type", help="Project type override")] = "",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without executing")] = False,
    force: Annotated[bool, typer.Option("--force", help="Force overwrite")] = False,
) -> None:
    """Generate AGENTS.md for a project."""
    target = target.resolve()
    console.print("[bold]improve-agents-md: setup[/bold]")
    console.print(f"Target: {target}")

    # 1. Detect project type
    if not project_type:
        project_type = detect_type(target)
    console.print(f"Project type: {project_type}")

    # 2. Preserve customizations
    dry_flag = ["--dry-run"] if dry_run else []
    if force:
        run_tool("preserve_custom.py", ["backup", str(target), *dry_flag])
    run_tool("preserve_custom.py", ["preserve", str(target), *dry_flag])

    # 3. Render AGENTS.md via template engine
    output_path = target / "CLAUDE.md"
    render_args = [
        "render", project_type, str(output_path),
        *dry_flag,
    ]
    rc = run_tool("template_engine.py", render_args)
    if rc != 0:
        console.print("[red]Template rendering failed[/red]")
        raise SystemExit(rc)

    # 4. Ensure user customization file exists
    ensure_project_agents_file(target, dry_run=dry_run)

    # 5. Render shared templates (e.g., .gitignore)
    shared_dir = TOOLS_DIR.parent / "assets" / "templates" / "shared"
    if shared_dir.is_dir():
        for tmpl in sorted(shared_dir.rglob("*.template")):
            rel = tmpl.relative_to(shared_dir)
            out_name = str(rel).removesuffix(".template")
            out_path = target / out_name
            if not out_path.exists() or force:
                if dry_run:
                    console.print(f"[dim]DRY-RUN: Would write {out_path}[/dim]")
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(tmpl.read_text())
                    console.print(f"[green]Wrote {out_path}[/green]")

    console.print("\n[bold green]Setup complete[/bold green]")


@app.command()
def update(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    force: Annotated[bool, typer.Option("--force", help="Force full template refresh")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without executing")] = False,
) -> None:
    """Update AGENTS.md in an existing project."""
    target = target.resolve()
    console.print("[bold]improve-agents-md: update[/bold]")

    # 1. Detect current project type (from config or re-detect)
    project_type = None
    if not project_type:
        project_type = detect_type(target)
    console.print(f"Project type: {project_type}")

    # 2. Preserve customizations if force
    dry_flag = ["--dry-run"] if dry_run else []
    if force:
        run_tool("preserve_custom.py", ["backup", str(target), *dry_flag])
        run_tool("preserve_custom.py", ["preserve", str(target), *dry_flag])

    # 3. Re-render AGENTS.md
    output_path = target / "CLAUDE.md"
    render_args = [
        "render", project_type, str(output_path),
        *dry_flag,
    ]
    rc = run_tool("template_engine.py", render_args)
    if rc != 0:
        console.print("[red]Template rendering failed[/red]")
        raise SystemExit(rc)

    console.print("\n[bold green]Update complete[/bold green]")


@app.command()
def validate(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
) -> None:
    """Validate AGENTS.md content against current template."""
    target = target.resolve()
    console.print("[bold]improve-agents-md: validate[/bold]")
    console.print(f"Target: {target}\n")

    issues: list[str] = []

    # Check CLAUDE.md exists
    claude_md = target / "CLAUDE.md"
    if not claude_md.exists():
        console.print("  [red]MISS[/red] CLAUDE.md not found")
        issues.append("CLAUDE.md missing -- Fix: run bootstrap.py setup .")
    else:
        content = claude_md.read_text()
        # Check for unresolved template vars
        import re
        unresolved = re.findall(r"\{\{[A-Z_][A-Z0-9_]*\}\}", content)
        if unresolved:
            console.print(f"  [red]ERR[/red]  Unresolved template vars: {unresolved}")
            issues.append(f"Unresolved vars in CLAUDE.md: {unresolved}")
        else:
            console.print("  [green]OK[/green]  No unresolved template variables")

        # Check required sections
        required_sections = [
            "## Environment & Tooling",
            "## Core Rules",
            "## Git Workflow",
        ]
        for section in required_sections:
            if section in content:
                console.print(f"  [green]OK[/green]  {section}")
            else:
                console.print(f"  [yellow]WARN[/yellow] Missing section: {section}")
                issues.append(f"Missing section '{section}' in CLAUDE.md")

    # Check template assets
    assets_dir = TOOLS_DIR.parent / "assets"
    for asset in ["AGENTS.md.template", "tooling.yml"]:
        path = assets_dir / asset
        if path.exists():
            console.print(f"  [green]OK[/green]  {asset}")
        else:
            console.print(f"  [red]MISS[/red] {asset}")
            issues.append(f"Asset missing: {asset}")

    # Report
    console.print()
    if issues:
        console.print(f"[red]{len(issues)} issue(s) found:[/red]")
        for i, issue in enumerate(issues, 1):
            console.print(f"  {i}. {issue}")
        raise SystemExit(1)
    else:
        console.print("[green]All checks passed.[/green]")


if __name__ == "__main__":
    app()
