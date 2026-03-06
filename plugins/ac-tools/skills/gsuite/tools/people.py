#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""People API CLI for contact lookup and search."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console

# Import auth module
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402

app = typer.Typer(help="People API CLI for contact search.")
console = Console(stderr=True)
stdout_console = Console()


def get_people_service(account: str | None = None):
    """Get authenticated People API service."""
    creds = get_credentials(account)
    return build("people", "v1", credentials=creds)


def format_contact(person: dict) -> dict:
    """Extract name and email from person resource."""
    names = person.get("names", [])
    emails = person.get("emailAddresses", [])

    name = names[0].get("displayName", "") if names else ""
    email = emails[0].get("value", "") if emails else ""

    return {"name": name, "email": email, "resourceName": person.get("resourceName", "")}


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Name or email to search for")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search contacts by name or email."""
    try:
        service = get_people_service(account)

        # Search in "Other Contacts" (auto-saved from interactions)
        results = (
            service.otherContacts()
            .search(
                query=query,
                readMask="names,emailAddresses",
                pageSize=limit,
            )
            .execute()
        )

        contacts = []
        for result in results.get("results", []):
            person = result.get("person", {})
            contact = format_contact(person)
            if contact["email"]:  # Only include contacts with email
                contacts.append(contact)

        if json_output:
            stdout_console.print_json(json.dumps({"count": len(contacts), "contacts": contacts}))
            return

        if not contacts:
            console.print(f"[yellow]No contacts found for '{query}'[/yellow]")
            return

        for contact in contacts:
            stdout_console.print(f"Name: {contact['name']}")
            stdout_console.print(f"Email: {contact['email']}")
            stdout_console.print("---")

    except HttpError as e:
        if e.resp.status == 403:
            console.print("[red]Error:[/red] People API not enabled or insufficient permissions.")
            console.print("Enable at: https://console.cloud.google.com/apis/library/people.googleapis.com")
            console.print("\nIf recently enabled, re-authenticate:")
            console.print("  uv run auth.py remove <email>")
            console.print("  uv run auth.py add")
        else:
            console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("list")
def list_contacts(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List contacts from your connections."""
    try:
        service = get_people_service(account)

        # List from primary connections (your contacts)
        results = (
            service.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="names,emailAddresses",
                pageSize=limit,
                sortOrder="LAST_MODIFIED_DESCENDING",
            )
            .execute()
        )

        contacts = []
        for person in results.get("connections", []):
            contact = format_contact(person)
            if contact["email"]:
                contacts.append(contact)

        if json_output:
            stdout_console.print_json(json.dumps({"count": len(contacts), "contacts": contacts}))
            return

        if not contacts:
            console.print("[yellow]No contacts found.[/yellow]")
            return

        for contact in contacts:
            stdout_console.print(f"Name: {contact['name']}")
            stdout_console.print(f"Email: {contact['email']}")
            stdout_console.print("---")

    except HttpError as e:
        if e.resp.status == 403:
            console.print("[red]Error:[/red] People API not enabled or insufficient permissions.")
            console.print("Enable at: https://console.cloud.google.com/apis/library/people.googleapis.com")
            console.print("\nIf recently enabled, re-authenticate:")
            console.print("  uv run auth.py remove <email>")
            console.print("  uv run auth.py add")
        else:
            console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
