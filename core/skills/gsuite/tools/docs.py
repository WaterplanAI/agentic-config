#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
#   "pyyaml>=6.0",
#   "mistune>=3.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""Google Docs CLI for read/write operations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console

# Import auth module and utilities
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402
from utils import merge_extra  # noqa: E402

# Import md2docs for markdown conversion with native tables
from md2docs import convert_markdown_to_docs  # noqa: E402


app = typer.Typer(help="Google Docs CLI operations.")
console = Console(stderr=True)
stdout_console = Console()


def get_docs_service(account: str | None = None):
    """Get authenticated Docs API service."""
    creds = get_credentials(account)
    return build("docs", "v1", credentials=creds)


def get_drive_service(account: str | None = None):
    """Get authenticated Drive API service (for export)."""
    creds = get_credentials(account)
    return build("drive", "v3", credentials=creds)


def extract_text_from_body(body: dict) -> str:
    """Extract plain text from body structure."""
    text_parts = []
    content = body.get("content", [])

    for element in content:
        if "paragraph" in element:
            paragraph = element["paragraph"]
            for elem in paragraph.get("elements", []):
                if "textRun" in elem:
                    text_parts.append(elem["textRun"].get("content", ""))

    return "".join(text_parts)


def extract_text_from_doc(doc: dict) -> str:
    """Extract plain text from document structure (legacy body)."""
    return extract_text_from_body(doc.get("body", {}))


def get_doc_with_tabs(service, doc_id: str) -> dict:
    """Fetch document with all tabs."""
    return service.documents().get(
        documentId=doc_id,
        includeTabsContent=True,
    ).execute()


def resolve_tab(doc: dict, tab_ref: str | None) -> tuple[str, str]:
    """Resolve tab reference to (tab_id, title). Returns first tab if None."""
    tabs = doc.get("tabs", [])
    if not tabs:
        raise ValueError("Document has no tabs")
    if not tab_ref:
        first = tabs[0]
        props = first.get("tabProperties", {})
        return props.get("tabId", ""), props.get("title", "")
    for tab in tabs:
        props = tab.get("tabProperties", {})
        tab_id = props.get("tabId", "")
        title = props.get("title", "")
        if tab_id == tab_ref:
            return tab_id, title
        if title == tab_ref:
            return tab_id, title
    raise ValueError(f"Tab not found: {tab_ref}")


def get_tab_body(doc: dict, tab_id: str) -> dict:
    """Get body content for a specific tab."""
    for tab in doc.get("tabs", []):
        if tab.get("tabProperties", {}).get("tabId") == tab_id:
            return tab.get("documentTab", {}).get("body", {})
    raise ValueError(f"Tab not found: {tab_id}")


@app.command()
def read(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    tab: Annotated[str | None, typer.Option("--tab", "-t", help="Tab ID or title to read from")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    raw: Annotated[bool, typer.Option("--raw", help="Output raw API response")] = False,
) -> None:
    """Read content from a Google Doc."""
    try:
        service = get_docs_service(account)

        if tab:
            doc = get_doc_with_tabs(service, doc_id)
            if raw:
                stdout_console.print_json(json.dumps(doc, indent=2))
                return
            tab_id, tab_title = resolve_tab(doc, tab)
            body = get_tab_body(doc, tab_id)
            text = extract_text_from_body(body)
            title = doc.get("title", "Untitled")
            if json_output:
                stdout_console.print_json(json.dumps({
                    "doc_id": doc_id,
                    "title": title,
                    "tab_id": tab_id,
                    "tab_title": tab_title,
                    "content": text,
                    "character_count": len(text),
                }))
            else:
                console.print(f"[bold]{title}[/bold] [dim](tab: {tab_title})[/dim]\n")
                stdout_console.print(text)
        else:
            doc = service.documents().get(documentId=doc_id).execute()
            if raw:
                stdout_console.print_json(json.dumps(doc, indent=2))
                return
            title = doc.get("title", "Untitled")
            text = extract_text_from_doc(doc)
            if json_output:
                stdout_console.print_json(json.dumps({
                    "doc_id": doc_id,
                    "title": title,
                    "content": text,
                    "character_count": len(text),
                }))
            else:
                console.print(f"[bold]{title}[/bold]\n")
                stdout_console.print(text)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def write(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    text: Annotated[str, typer.Argument(help="Text to insert")],
    tab: Annotated[str | None, typer.Option("--tab", "-t", help="Tab ID or title to write to")] = None,
    append: Annotated[bool, typer.Option("--append", help="Append to end")] = False,
    index: Annotated[int, typer.Option("--index", help="Insert at index")] = 1,
    markdown: Annotated[bool, typer.Option("--markdown", "-m", help="Parse markdown with native tables")] = False,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional batchUpdate requests or API params")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Insert text into a Google Doc.

    With --markdown flag, uses md2docs for native table support.
    """
    try:
        service = get_docs_service(account)
        tab_id: str | None = None
        tab_title: str | None = None

        # Resolve tab if specified
        if tab:
            doc = get_doc_with_tabs(service, doc_id)
            tab_id, tab_title = resolve_tab(doc, tab)

        # If appending, get document/tab length first
        if append:
            if tab_id:
                doc = get_doc_with_tabs(service, doc_id)
                body_content = get_tab_body(doc, tab_id)
            else:
                doc = service.documents().get(documentId=doc_id).execute()
                body_content = doc.get("body", {})
            content = body_content.get("content", [])
            if content:
                last_elem = content[-1]
                index = last_elem.get("endIndex", 1) - 1

        # Parse markdown if requested - delegate to md2docs for native table support
        if markdown:
            # Note: md2docs doesn't support tab_id yet; would need extension
            stats = convert_markdown_to_docs(service, doc_id, text, index)

            if json_output:
                result = {"doc_id": doc_id, "index": index, **stats}
                if tab_id:
                    result["tab_id"] = tab_id
                    result["tab_title"] = tab_title
                stdout_console.print_json(json.dumps(result))
            else:
                msg = f"[green]Inserted {stats['text_length']} characters at index {index}[/green]"
                if tab_title:
                    msg += f" [dim](tab: {tab_title})[/dim]"
                if stats["format_rules"]:
                    msg += f" [dim](+{stats['format_rules']} formatting rules)[/dim]"
                if stats["tables_inserted"]:
                    msg += f" [dim](+{stats['tables_inserted']} native tables)[/dim]"
                console.print(msg)
            return

        # Build location with optional tabId
        location: dict[str, Any] = {"index": index}
        if tab_id:
            location["tabId"] = tab_id

        # Plain text insertion (no markdown)
        requests: list[dict[str, Any]] = [
            {
                "insertText": {
                    "location": location,
                    "text": text,
                }
            }
        ]

        # Merge --extra options
        body: dict[str, Any] = {"requests": requests}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service.documents().batchUpdate(
            documentId=doc_id,
            body=body,
            **api_params,
        ).execute()

        if json_output:
            result = {"doc_id": doc_id, "inserted_text_length": len(text), "index": index}
            if tab_id:
                result["tab_id"] = tab_id
                result["tab_title"] = tab_title
            stdout_console.print_json(json.dumps(result))
        else:
            msg = f"[green]Inserted {len(text)} characters at index {index}[/green]"
            if tab_title:
                msg += f" [dim](tab: {tab_title})[/dim]"
            console.print(msg)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    title: Annotated[str, typer.Argument(help="Document title")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new Google Doc."""
    try:
        # Merge --extra options
        body: dict = {"title": title}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_docs_service(account)
        doc = service.documents().create(
            body=body,
            **api_params,
        ).execute()

        doc_id = doc.get("documentId")
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "title": title,
                "url": doc_url,
            }))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"ID: {doc_id}")
            console.print(f"URL: {doc_url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def export(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file path")],
    format: Annotated[str, typer.Option("--format", "-f", help="Export format")] = "pdf",
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
) -> None:
    """Export document to PDF, DOCX, or other format."""
    mime_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "html": "text/html",
        "rtf": "application/rtf",
        "odt": "application/vnd.oasis.opendocument.text",
    }

    if format.lower() not in mime_types:
        console.print(f"[red]Error:[/red] Unsupported format '{format}'")
        console.print(f"Supported: {', '.join(mime_types.keys())}")
        raise typer.Exit(1)

    try:
        service = get_drive_service(account)
        request = service.files().export_media(
            fileId=doc_id,
            mimeType=mime_types[format.lower()],
        )

        with open(output, "wb") as f:
            f.write(request.execute())

        console.print(f"[green]Exported to:[/green] {output}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def tabs(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all tabs in a Google Doc."""
    try:
        service = get_docs_service(account)
        doc = get_doc_with_tabs(service, doc_id)
        title = doc.get("title", "Untitled")
        tabs_list = doc.get("tabs", [])

        tab_data = []
        for i, tab in enumerate(tabs_list):
            props = tab.get("tabProperties", {})
            tab_data.append({
                "index": i,
                "tab_id": props.get("tabId", ""),
                "title": props.get("title", ""),
            })

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "title": title,
                "tabs": tab_data,
            }))
        else:
            console.print(f"[bold]{title}[/bold] ({len(tab_data)} tabs)\n")
            for t in tab_data:
                console.print(f"  [{t['index']}] {t['title'] or '(untitled)'} [dim]({t['tab_id']})[/dim]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("create-tab")
def create_tab(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    title: Annotated[str, typer.Argument(help="Tab title")],
    index: Annotated[int | None, typer.Option("--index", "-i", help="Position index for new tab")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new tab in a Google Doc."""
    try:
        service = get_docs_service(account)

        # Build addDocumentTab request
        add_tab: dict[str, Any] = {"tabProperties": {"title": title}}
        if index is not None:
            add_tab["location"] = {"index": index}

        requests: list[dict[str, Any]] = [{"addDocumentTab": add_tab}]
        result = service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        # Get the new tab ID from response
        replies = result.get("replies", [{}])
        new_tab_id = replies[0].get("addDocumentTab", {}).get("tabId", "")

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "tab_id": new_tab_id,
                "title": title,
            }))
        else:
            console.print(f"[green]Created tab:[/green] {title}")
            console.print(f"Tab ID: {new_tab_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("rename-tab")
def rename_tab(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    tab_id: Annotated[str, typer.Argument(help="Tab ID to rename")],
    title: Annotated[str, typer.Argument(help="New tab title")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Rename a tab in a Google Doc."""
    try:
        service = get_docs_service(account)

        requests: list[dict[str, Any]] = [{
            "updateDocumentTabProperties": {
                "tabProperties": {"tabId": tab_id, "title": title},
                "fields": "title",
            }
        }]

        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "tab_id": tab_id,
                "title": title,
            }))
        else:
            console.print(f"[green]Renamed tab {tab_id} to:[/green] {title}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("delete-tab")
def delete_tab(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    tab_id: Annotated[str, typer.Argument(help="Tab ID to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a tab from a Google Doc."""
    try:
        if not yes:
            confirm = typer.confirm(f"Delete tab {tab_id}?")
            if not confirm:
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)

        service = get_docs_service(account)

        requests: list[dict[str, Any]] = [{"deleteTab": {"tabId": tab_id}}]

        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "tab_id": tab_id,
                "deleted": True,
            }))
        else:
            console.print(f"[green]Deleted tab:[/green] {tab_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
