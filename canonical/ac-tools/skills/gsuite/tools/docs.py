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


@app.command()
def edit(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    find: Annotated[str | None, typer.Option("--find", "-f", help="Text to find (single edit mode)")] = None,
    replace: Annotated[str | None, typer.Option("--replace", "-r", help="Replacement text (single edit mode)")] = None,
    plan: Annotated[Path | None, typer.Option("--plan", "-p", help="JSON file with batch edits")] = None,
    tab: Annotated[str | None, typer.Option("--tab", "-t", help="Tab ID or title to scope edits to")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Replace text in a Google Doc using find-and-replace.

    Single edit mode:
        uv run docs.py edit <doc_id> --find "old text" --replace "new text"

    Batch mode from JSON plan:
        uv run docs.py edit <doc_id> --plan /tmp/edit-plan.json

    Plan JSON format:
        {"edits": [{"find": "old text", "replace": "new text"}, ...]}

    Uses replaceAllText API -- no index math required.
    """
    try:
        # Validate mode: either --find/--replace or --plan, not both
        if plan and (find or replace):
            console.print("[red]Error:[/red] Cannot combine --plan with --find/--replace")
            raise typer.Exit(1)
        if not plan and not (find and replace):
            console.print("[red]Error:[/red] Provide either --find and --replace, or --plan")
            raise typer.Exit(1)

        # Build edits list
        edits: list[dict[str, str]] = []
        if plan:
            if not plan.exists():
                console.print(f"[red]Error:[/red] Plan file not found: {plan}")
                raise typer.Exit(1)
            plan_data = json.loads(plan.read_text())
            if isinstance(plan_data, dict) and "edits" in plan_data:
                edits = plan_data["edits"]
            elif isinstance(plan_data, list):
                edits = plan_data
            else:
                console.print("[red]Error:[/red] Plan must be {\"edits\": [...]} or a JSON array")
                raise typer.Exit(1)
            # Validate each edit
            for i, e in enumerate(edits):
                if "find" not in e or "replace" not in e:
                    console.print(f"[red]Error:[/red] Edit {i} missing 'find' or 'replace' key")
                    raise typer.Exit(1)
        else:
            assert find is not None and replace is not None
            edits = [{"find": find, "replace": replace}]

        if not edits:
            console.print("[yellow]No edits to apply[/yellow]")
            raise typer.Exit(0)

        # Confirmation
        if not yes:
            console.print(f"[bold]Edits to apply ({len(edits)}):[/bold]")
            for i, e in enumerate(edits):
                find_preview = e["find"][:50] + ("..." if len(e["find"]) > 50 else "")
                replace_preview = e["replace"][:50] + ("..." if len(e["replace"]) > 50 else "")
                console.print(f"  [{i}] \"{find_preview}\" -> \"{replace_preview}\"")
            confirm = typer.confirm("Apply?")
            if not confirm:
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)

        # Resolve tab if specified
        tab_id: str | None = None
        tab_title: str | None = None
        if tab:
            service = get_docs_service(account)
            doc = get_doc_with_tabs(service, doc_id)
            tab_id, tab_title = resolve_tab(doc, tab)
        else:
            service = get_docs_service(account)

        # Build replaceAllText requests
        requests: list[dict[str, Any]] = []
        for e in edits:
            contains_text: dict[str, Any] = {
                "text": e["find"],
                "matchCase": True,
            }
            if tab_id:
                contains_text["tabId"] = tab_id
            requests.append({
                "replaceAllText": {
                    "containsText": contains_text,
                    "replaceText": e["replace"],
                }
            })

        # Execute single batchUpdate for atomicity
        result = service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        # Parse response for replacement counts
        replies = result.get("replies", [])
        edit_results: list[dict[str, Any]] = []
        total_replacements = 0
        warnings: list[str] = []

        for i, (e, reply) in enumerate(zip(edits, replies)):
            count = reply.get("replaceAllText", {}).get("occurrencesChanged", 0)
            total_replacements += count
            edit_results.append({
                "index": i,
                "find": e["find"],
                "replace": e["replace"],
                "occurrences_changed": count,
            })
            if count == 0:
                warnings.append(f"Edit {i}: no occurrences of \"{e['find'][:50]}\"")

        # Output
        if json_output:
            out: dict[str, Any] = {
                "doc_id": doc_id,
                "edits": edit_results,
                "total_replacements": total_replacements,
            }
            if tab_id:
                out["tab_id"] = tab_id
                out["tab_title"] = tab_title
            if warnings:
                out["warnings"] = warnings
            stdout_console.print_json(json.dumps(out))
        else:
            if tab_title:
                console.print(f"[dim](tab: {tab_title})[/dim]")
            for er in edit_results:
                status = "[green]OK[/green]" if er["occurrences_changed"] > 0 else "[yellow]NONE[/yellow]"
                console.print(
                    f"  [{er['index']}] {status} {er['occurrences_changed']} replacement(s): "
                    f"\"{er['find'][:40]}\" -> \"{er['replace'][:40]}\""
                )
            console.print(f"\n[bold]Total replacements: {total_replacements}[/bold]")
            for w in warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


def build_text_with_indices(body: dict) -> tuple[str, list[tuple[int, int]]]:
    """Build flat text from document body, tracking API index per character.

    Returns:
        (flat_text, index_map) where index_map[i] = (doc_start_index, doc_end_index)
        for each character in flat_text.
    """
    flat_text: list[str] = []
    index_map: list[tuple[int, int]] = []

    for element in body.get("content", []):
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                if "textRun" in elem:
                    text = elem["textRun"].get("content", "")
                    start = elem.get("startIndex", 0)
                    for i, ch in enumerate(text):
                        flat_text.append(ch)
                        index_map.append((start + i, start + i + 1))
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for cell_elem in cell.get("content", []):
                        if "paragraph" in cell_elem:
                            for elem in cell_elem["paragraph"].get("elements", []):
                                if "textRun" in elem:
                                    text = elem["textRun"].get("content", "")
                                    start = elem.get("startIndex", 0)
                                    for i, ch in enumerate(text):
                                        flat_text.append(ch)
                                        index_map.append((start + i, start + i + 1))

    return "".join(flat_text), index_map


@app.command()
def find(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    query: Annotated[str, typer.Argument(help="Text to search for")],
    tab: Annotated[str | None, typer.Option("--tab", "-t", help="Tab ID or title")] = None,
    context_chars: Annotated[int, typer.Option("--context", "-c", help="Characters of surrounding context")] = 50,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Find text in a Google Doc and return index positions.

    Eliminates manual index calculation by returning exact start/end indices
    that match the Docs API index system.

    Examples:
        uv run docs.py find <doc_id> "search text"
        uv run docs.py find <doc_id> "search text" --json --context 100
        uv run docs.py find <doc_id> "search text" --tab "My Tab"
    """
    try:
        service = get_docs_service(account)

        if tab:
            doc = get_doc_with_tabs(service, doc_id)
            tab_id, _ = resolve_tab(doc, tab)
            body = get_tab_body(doc, tab_id)
        else:
            doc = service.documents().get(documentId=doc_id).execute()
            body = doc.get("body", {})

        flat_text, index_map = build_text_with_indices(body)

        # Find all occurrences
        matches: list[dict[str, Any]] = []
        search_start = 0
        occurrence = 0

        while True:
            pos = flat_text.find(query, search_start)
            if pos == -1:
                break
            occurrence += 1
            end_pos = pos + len(query)

            # Map flat positions to document indices
            doc_start = index_map[pos][0]
            doc_end = index_map[end_pos - 1][1]

            # Build context
            ctx_start = max(0, pos - context_chars)
            ctx_end = min(len(flat_text), end_pos + context_chars)
            context_text = flat_text[ctx_start:ctx_end]

            matches.append({
                "start_index": doc_start,
                "end_index": doc_end,
                "text": query,
                "context": context_text,
                "occurrence": occurrence,
            })

            search_start = pos + 1

        # Output
        if json_output:
            stdout_console.print_json(json.dumps(matches))
        else:
            if not matches:
                console.print(f"[yellow]No occurrences found for:[/yellow] \"{query}\"")
                raise typer.Exit(0)
            console.print(f"Found {len(matches)} occurrence(s) of \"{query}\":")
            for m in matches:
                console.print(
                    f"  {m['occurrence']}. [{m['start_index']}-{m['end_index']}] "
                    f"...{m['context']}..."
                )

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
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
