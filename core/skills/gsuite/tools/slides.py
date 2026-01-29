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


if __name__ == "__main__":
    app()
