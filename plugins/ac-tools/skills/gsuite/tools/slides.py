#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "pyyaml>=6.0",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""Google Slides CLI for presentation operations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.tree import Tree

# Import auth module for credential loading
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402
from utils import merge_extra  # noqa: E402

app = typer.Typer(help="Google Slides CLI operations.")
console = Console(stderr=True)
stdout_console = Console()

# Slide layout types
LAYOUTS = {
    "BLANK": "BLANK",
    "TITLE": "TITLE",
    "TITLE_AND_BODY": "TITLE_AND_BODY",
    "TITLE_AND_TWO_COLUMNS": "TITLE_AND_TWO_COLUMNS",
    "TITLE_ONLY": "TITLE_ONLY",
    "ONE_COLUMN_TEXT": "ONE_COLUMN_TEXT",
    "MAIN_POINT": "MAIN_POINT",
    "SECTION_HEADER": "SECTION_HEADER",
    "SECTION_TITLE_AND_DESCRIPTION": "SECTION_TITLE_AND_DESCRIPTION",
    "BIG_NUMBER": "BIG_NUMBER",
}


def get_slides_service(account: str | None = None):
    """Get authenticated Slides API service."""
    creds = get_credentials(account)
    return build("slides", "v1", credentials=creds)


def extract_slide_text(slide: dict) -> list[str]:
    """Extract text content from a slide."""
    texts = []
    for element in slide.get("pageElements", []):
        if "shape" in element:
            shape = element["shape"]
            if "text" in shape:
                for text_elem in shape["text"].get("textElements", []):
                    if "textRun" in text_elem:
                        texts.append(text_elem["textRun"].get("content", "").strip())
    return [t for t in texts if t]


@app.command()
def read(
    presentation_id: Annotated[str, typer.Argument(help="Presentation ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    raw: Annotated[bool, typer.Option("--raw", help="Output raw API response")] = False,
) -> None:
    """Read content from a Google Slides presentation."""
    try:
        service = get_slides_service(account)
        presentation = service.presentations().get(
            presentationId=presentation_id,
        ).execute()

        if raw:
            stdout_console.print_json(json.dumps(presentation, indent=2))
            return

        title = presentation.get("title", "Untitled")
        slides = presentation.get("slides", [])

        if json_output:
            slide_data = []
            for i, slide in enumerate(slides):
                slide_data.append({
                    "index": i,
                    "id": slide.get("objectId"),
                    "text": extract_slide_text(slide),
                })
            stdout_console.print_json(json.dumps({
                "presentation_id": presentation_id,
                "title": title,
                "slide_count": len(slides),
                "slides": slide_data,
            }))
            return

        # Display as tree
        tree = Tree(f"[bold]{title}[/bold] ({len(slides)} slides)")
        for i, slide in enumerate(slides):
            texts = extract_slide_text(slide)
            slide_branch = tree.add(f"Slide {i + 1}: {slide.get('objectId', 'unknown')}")
            for text in texts[:3]:  # Show first 3 text elements
                slide_branch.add(f"[dim]{text[:50]}{'...' if len(text) > 50 else ''}[/dim]")

        console.print(tree)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    title: Annotated[str, typer.Argument(help="Presentation title")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new Google Slides presentation."""
    try:
        # Merge --extra options
        body: dict = {"title": title}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_slides_service(account)
        presentation = service.presentations().create(
            body=body,
            **api_params,
        ).execute()

        presentation_id = presentation.get("presentationId")
        url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

        if json_output:
            stdout_console.print_json(json.dumps({
                "presentation_id": presentation_id,
                "title": title,
                "url": url,
            }))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"ID: {presentation_id}")
            console.print(f"URL: {url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("add-slide")
def add_slide(
    presentation_id: Annotated[str, typer.Argument(help="Presentation ID")],
    layout: Annotated[str, typer.Option("--layout", "-l", help="Slide layout")] = "BLANK",
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional batchUpdate requests or API params")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add a new slide to presentation."""
    if layout.upper() not in LAYOUTS:
        console.print(f"[red]Error:[/red] Unknown layout '{layout}'")
        console.print(f"Available: {', '.join(LAYOUTS.keys())}")
        raise typer.Exit(1)

    try:
        service = get_slides_service(account)
        requests = [
            {
                "createSlide": {
                    "slideLayoutReference": {
                        "predefinedLayout": layout.upper(),
                    }
                }
            }
        ]

        # Merge --extra options
        body: dict = {"requests": requests}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        result = service.presentations().batchUpdate(
            presentationId=presentation_id,
            body=body,
            **api_params,
        ).execute()

        replies = result.get("replies", [{}])
        slide_id = replies[0].get("createSlide", {}).get("objectId") if replies else None

        if json_output:
            stdout_console.print_json(json.dumps({
                "presentation_id": presentation_id,
                "slide_id": slide_id,
                "layout": layout.upper(),
            }))
        else:
            console.print(f"[green]Added slide:[/green] {slide_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def edit(
    presentation_id: Annotated[str, typer.Argument(help="Presentation ID")],
    find: Annotated[str | None, typer.Option("--find", "-f", help="Text to find (single edit mode)")] = None,
    replace: Annotated[str | None, typer.Option("--replace", "-r", help="Replacement text (single edit mode)")] = None,
    plan: Annotated[Path | None, typer.Option("--plan", "-p", help="JSON file with batch edits")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Replace text in a Google Slides presentation.

    Single edit mode:
        uv run slides.py edit <id> --find "old text" --replace "new text"

    Batch mode from JSON plan:
        uv run slides.py edit <id> --plan /tmp/edit-plan.json

    Plan JSON format:
        {"edits": [{"find": "old", "replace": "new", "page_ids": ["optional"]}]}

    Uses replaceAllText API -- matches text across all slides (or scoped by page_ids).
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
        edits: list[dict] = []
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
                scope = f" [dim](pages: {e['page_ids']})[/dim]" if e.get("page_ids") else ""
                console.print(f"  [{i}] \"{find_preview}\" -> \"{replace_preview}\"{scope}")
            confirm = typer.confirm("Apply?")
            if not confirm:
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)

        service = get_slides_service(account)

        # Build replaceAllText requests
        requests: list[dict] = []
        for e in edits:
            req: dict = {
                "replaceAllText": {
                    "containsText": {
                        "text": e["find"],
                        "matchCase": True,
                    },
                    "replaceText": e["replace"],
                }
            }
            page_ids = e.get("page_ids")
            if page_ids:
                req["replaceAllText"]["pageObjectIds"] = page_ids
            requests.append(req)

        # Execute single batchUpdate for atomicity
        result = service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests},
        ).execute()

        # Parse response for replacement counts
        replies = result.get("replies", [])
        edit_results: list[dict] = []
        total_replacements = 0
        warnings: list[str] = []

        for i, (e, reply) in enumerate(zip(edits, replies)):
            count = reply.get("replaceAllText", {}).get("occurrencesChanged", 0)
            total_replacements += count
            entry: dict = {
                "index": i,
                "find": e["find"],
                "replace": e["replace"],
                "occurrences_changed": count,
            }
            if e.get("page_ids"):
                entry["page_ids"] = e["page_ids"]
            edit_results.append(entry)
            if count == 0:
                warnings.append(f"Edit {i}: no occurrences of \"{e['find'][:50]}\"")

        # Output
        if json_output:
            out: dict = {
                "presentation_id": presentation_id,
                "edits": edit_results,
                "total_replacements": total_replacements,
            }
            if warnings:
                out["warnings"] = warnings
            stdout_console.print_json(json.dumps(out))
        else:
            for er in edit_results:
                status = "[green]OK[/green]" if er["occurrences_changed"] > 0 else "[yellow]NONE[/yellow]"
                console.print(
                    f"  [{er['index']}] {status} {er['occurrences_changed']} replacement(s): "
                    f"\"{er['find'][:40]}\" -> \"{er['replace'][:40]}\""
                )
            console.print(f"\n[bold]Total replacements: {total_replacements}[/bold]")
            for w in warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
