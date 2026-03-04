#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "typer>=0.9.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""GSuite setup automation CLI for simplified project configuration."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

# Configuration
CONFIG_DIR = Path(os.environ.get("GSUITE_CONFIG_DIR", Path.home() / ".agents" / "gsuite"))
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

# Required Google APIs
REQUIRED_APIS = [
    "sheets.googleapis.com",
    "docs.googleapis.com",
    "slides.googleapis.com",
    "drive.googleapis.com",
    "gmail.googleapis.com",
    "calendar-json.googleapis.com",
    "tasks.googleapis.com",
]

# Direct console URLs
ENABLE_APIS_URL = (
    "https://console.cloud.google.com/flows/enableapi?apiid="
    + ",".join(REQUIRED_APIS)
)
CONSENT_URL = "https://console.cloud.google.com/apis/credentials/consent"
CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials/oauthclient"

app = typer.Typer(help="GSuite setup automation CLI.")
console = Console(stderr=True)


def get_gcloud_project() -> str | None:
    """Get current gcloud project from config."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


@app.command()
def init(
    project: str | None = typer.Option(None, "--project", "-p", help="Google Cloud project ID"),
) -> None:
    """Initialize Google Cloud project for GSuite skill.

    Enables required APIs via gcloud CLI (if available) or prints direct console URLs.
    """
    gcloud_available = shutil.which("gcloud") is not None

    console.print("[bold]GSuite Setup[/bold]\n")

    # Try gcloud if available
    if gcloud_available:
        project_id = project or get_gcloud_project()

        if project_id:
            console.print(f"Project: [cyan]{project_id}[/cyan]")
            console.print(f"Enabling {len(REQUIRED_APIS)} APIs...\n")

            cmd = ["gcloud", "services", "enable", *REQUIRED_APIS, f"--project={project_id}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                console.print(f"[green]Enabled {len(REQUIRED_APIS)} APIs successfully.[/green]\n")
            else:
                console.print(f"[red]Error enabling APIs:[/red]\n{result.stderr}")
                console.print("\n[yellow]Fallback: Use the URL below to enable manually.[/yellow]\n")
        else:
            console.print("[yellow]No project specified.[/yellow]")
            console.print("Run: [cyan]gcloud config set project YOUR_PROJECT_ID[/cyan]")
            console.print("Or use: [cyan]uv run setup.py init --project YOUR_PROJECT_ID[/cyan]\n")
    else:
        console.print("[dim]gcloud CLI not found. Using manual setup URLs.[/dim]\n")

    # Print next steps with direct URLs
    console.print("[bold]Next Steps[/bold]\n")

    step = 1
    if not gcloud_available or not (project or get_gcloud_project()):
        console.print(f"{step}. [cyan]Enable APIs[/cyan] (one click):")
        console.print(f"   {ENABLE_APIS_URL}\n")
        step += 1

    console.print(f"{step}. [cyan]Configure OAuth consent screen[/cyan]:")
    console.print(f"   {CONSENT_URL}")
    console.print("   - Select 'External' (or 'Internal' for Workspace)")
    console.print("   - App name: GSuite Skill")
    console.print("   - Add your email as test user\n")
    step += 1

    console.print(f"{step}. [cyan]Create Desktop credentials[/cyan]:")
    console.print(f"   {CREDENTIALS_URL}")
    console.print("   - Type: Desktop application")
    console.print(f"   - Download JSON to: {CREDENTIALS_FILE}\n")
    step += 1

    console.print(f"{step}. [cyan]Authenticate[/cyan]:")
    console.print("   uv run auth.py add")


@app.command()
def check() -> None:
    """Verify GSuite setup is complete."""
    issues: list[str] = []

    # Check credentials.json
    console.print("[bold]Checking Setup[/bold]\n")

    if CREDENTIALS_FILE.exists():
        console.print(f"[green]OK[/green] credentials.json: {CREDENTIALS_FILE}")
    else:
        console.print(f"[red]MISSING[/red] credentials.json: {CREDENTIALS_FILE}")
        issues.append("Download credentials.json from Google Cloud Console")

    # Check for authenticated accounts
    accounts_dir = CONFIG_DIR / "accounts"
    accounts: list[str] = []
    if accounts_dir.exists():
        accounts = [d.name for d in accounts_dir.iterdir() if (d / "token.json").exists()]

    if accounts:
        console.print(f"[green]OK[/green] Authenticated accounts: {len(accounts)}")
        for acc in accounts:
            console.print(f"   - {acc}")
    else:
        console.print("[red]MISSING[/red] No authenticated accounts")
        issues.append("Run: uv run auth.py add")

    # Check active account
    active_file = CONFIG_DIR / "active_account"
    if active_file.exists():
        active = active_file.read_text().strip()
        console.print(f"[green]OK[/green] Active account: {active}")
    elif accounts:
        console.print("[yellow]WARN[/yellow] No active account set")
        issues.append(f"Run: uv run auth.py switch {accounts[0]}")

    # Summary
    console.print()
    if issues:
        console.print("[yellow]Issues found:[/yellow]")
        for issue in issues:
            console.print(f"  - {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]Setup complete![/green]")


@app.command()
def urls() -> None:
    """Print direct console URLs for manual setup."""
    console.print("[bold]Google Cloud Console URLs[/bold]\n")
    console.print("[cyan]Enable All APIs:[/cyan]")
    console.print(f"  {ENABLE_APIS_URL}\n")
    console.print("[cyan]OAuth Consent Screen:[/cyan]")
    console.print(f"  {CONSENT_URL}\n")
    console.print("[cyan]Create OAuth Credentials:[/cyan]")
    console.print(f"  {CREDENTIALS_URL}\n")


if __name__ == "__main__":
    app()
