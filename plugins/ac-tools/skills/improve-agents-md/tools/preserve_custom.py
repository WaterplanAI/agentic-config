#!/usr/bin/env -S uv run
# /// script
# dependencies = ["typer>=0.9.0", "rich>=13.0.0"]
# requires-python = ">=3.12"
# ///
"""Backup and migration support for AGENTS.md generation.

Creates timestamped backups of AGENTS.md before overwriting.
Detects custom CLAUDE.md content for migration to AGENTS.md + symlink pattern.
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
    Skips symlinks (only backs up real files).
    """
    files_to_backup = ["CLAUDE.md", "AGENTS.md"]
    existing = [
        f for f in files_to_backup
        if (target_dir / f).exists() and not (target_dir / f).is_symlink()
    ]
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


def preserve_custom_content(target_dir: Path, *, dry_run: bool = False) -> str | None:
    """Read custom content from CLAUDE.md if it's a regular file (not symlink).

    Returns the content string if found, None otherwise.
    This content is reported for awareness; backup handles actual preservation.
    """
    claude_md = target_dir / "CLAUDE.md"
    if claude_md.exists() and not claude_md.is_symlink():
        content = claude_md.read_text().strip()
        if content:
            if dry_run:
                console.print(
                    f"[dim]DRY-RUN: Found custom content in CLAUDE.md "
                    f"({len(content)} chars) -- would be backed up[/dim]"
                )
            else:
                console.print(
                    f"[yellow]Found custom content in CLAUDE.md "
                    f"({len(content)} chars) -- backed up[/yellow]"
                )
            return content
    return None


@app.command()
def preserve(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print without writing")] = False,
) -> None:
    """Detect custom content before setup/update."""
    target = target.resolve()
    if not target.is_dir():
        console.print(f"[red]Error: {target} is not a directory[/red]")
        raise SystemExit(1)

    content = preserve_custom_content(target, dry_run=dry_run)
    if content:
        console.print("[green]Custom content detected and backed up[/green]")
    else:
        console.print("[dim]No custom content to preserve[/dim]")


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
