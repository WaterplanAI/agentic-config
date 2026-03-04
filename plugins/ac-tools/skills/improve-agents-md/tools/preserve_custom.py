#!/usr/bin/env -S uv run
# /// script
# dependencies = ["typer>=0.9.0", "rich>=13.0.0"]
# requires-python = ">=3.12"
# ///
"""Customization preservation for agentic-config bootstrap.

Preserves existing project-specific content in PROJECT_AGENTS.md.
Creates timestamped backups before overwriting files.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


def create_backup(target_dir: Path, *, dry_run: bool = False) -> Path | None:
    """Create timestamped backup of agentic-config files.

    Returns backup directory path, or None if nothing to back up.
    """
    files_to_backup = [
        "CLAUDE.md", "AGENTS.md", "PROJECT_AGENTS.md",
    ]
    existing = [f for f in files_to_backup if (target_dir / f).exists()]
    if not existing:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = target_dir / f".agentic-config.backup.{ts}"

    if dry_run:
        console.print(f"[dim]DRY-RUN: Would create backup at {backup_dir}[/dim]")
        return backup_dir

    backup_dir.mkdir(parents=True, exist_ok=True)
    for fname in existing:
        src = target_dir / fname
        dst = backup_dir / fname
        shutil.copy2(src, dst)
        console.print(f"  Backed up {fname}")

    console.print(f"[green]Backup created: {backup_dir}[/green]")
    return backup_dir


def preserve_to_project_agents(target_dir: Path, *, dry_run: bool = False) -> bool:
    """Preserve existing CLAUDE.md/AGENTS.md content to PROJECT_AGENTS.md.

    If CLAUDE.md or AGENTS.md is a real file (not symlink) with custom content,
    migrate that content to PROJECT_AGENTS.md before template overwrite.

    Returns True if content was preserved.
    """
    project_agents = target_dir / "PROJECT_AGENTS.md"

    # If PROJECT_AGENTS.md already exists, never overwrite
    if project_agents.exists():
        console.print("[dim]PROJECT_AGENTS.md exists -- preserving as-is[/dim]")
        return False

    # Check for custom content in CLAUDE.md or AGENTS.md (real files, not symlinks)
    for source_name in ["CLAUDE.md", "AGENTS.md"]:
        source = target_dir / source_name
        if source.exists() and not source.is_symlink():
            content = source.read_text().strip()
            if content:
                if dry_run:
                    console.print(
                        f"[dim]DRY-RUN: Would preserve {source_name} "
                        f"({len(content)} chars) to PROJECT_AGENTS.md[/dim]"
                    )
                    return True
                project_agents.write_text(content + "\n")
                console.print(
                    f"[green]Preserved {source_name} content to "
                    f"PROJECT_AGENTS.md ({len(content)} chars)[/green]"
                )
                return True

    return False


@app.command()
def preserve(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without writing")] = False,
) -> None:
    """Preserve project customizations before setup/update."""
    target = target.resolve()
    if not target.is_dir():
        console.print(f"[red]Error: {target} is not a directory[/red]")
        raise SystemExit(1)

    preserved = preserve_to_project_agents(target, dry_run=dry_run)
    if preserved:
        console.print("[green]Customizations preserved[/green]")
    else:
        console.print("[dim]No customizations to preserve[/dim]")


@app.command()
def backup(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without writing")] = False,
) -> None:
    """Create timestamped backup of agentic-config files."""
    target = target.resolve()
    backup_dir = create_backup(target, dry_run=dry_run)
    if backup_dir:
        console.print(f"Backup: {backup_dir}")
    else:
        console.print("[dim]Nothing to back up[/dim]")


if __name__ == "__main__":
    app()
