#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
#   "httpx>=0.27.0",
# ]
# requires-python = ">=3.12"
# ///
"""Mermaid diagram CLI for rendering and uploading to Drive."""
from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

# Import auth module for credential loading
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402

app = typer.Typer(help="Mermaid diagram rendering and Drive upload.")
console = Console(stderr=True)
stdout_console = Console()


def encode_mermaid_for_ink(code: str) -> str:
    """Encode mermaid code for mermaid.ink URL.

    Uses pako-compatible zlib compression + base64url encoding.
    """
    # Compress with zlib (pako default settings)
    compressed = zlib.compress(code.encode("utf-8"), level=9)
    # Base64url encode (no padding)
    encoded = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
    return encoded


def get_mermaid_ink_url(code: str, format: str = "png", background: str = "white") -> str:
    """Generate mermaid.ink URL for diagram rendering."""
    encoded = encode_mermaid_for_ink(code)
    # mermaid.ink expects format: /img/pako:{encoded}
    # Background via query param: ?bgColor=white
    bg_param = f"?bgColor={background}" if background else ""
    ext = "svg" if format.lower() == "svg" else "png"

    if ext == "svg":
        return f"https://mermaid.ink/svg/pako:{encoded}{bg_param}"
    return f"https://mermaid.ink/img/pako:{encoded}{bg_param}"


def render_mermaid(code: str, format: str = "png", background: str = "white") -> bytes:
    """Render mermaid code to image bytes via mermaid.ink API."""
    url = get_mermaid_ink_url(code, format, background)

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def read_code_input(code: str) -> str:
    """Read mermaid code from string or @filepath."""
    if code.startswith("@"):
        filepath = Path(code[1:])
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return filepath.read_text()
    return code


def get_drive_service(account: str | None = None):
    """Get authenticated Drive API service."""
    from googleapiclient.discovery import build
    creds = get_credentials(account)
    return build("drive", "v3", credentials=creds)


def get_file_url(file_id: str) -> str:
    """Generate Drive file URL."""
    return f"https://drive.google.com/file/d/{file_id}/view"


@app.command()
def render(
    code: Annotated[str, typer.Argument(help="Mermaid code or @filepath")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: png, svg")] = "png",
    background: Annotated[str, typer.Option("--background", "-b", help="Background color")] = "white",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Render mermaid diagram to local file.

    Code can be inline or read from file using @filepath syntax.

    Examples:
        mermaid.py render "graph TD; A-->B"
        mermaid.py render @diagram.mmd -o output.png
    """
    format_lower = format.lower()
    if format_lower not in ("png", "svg"):
        console.print(f"[red]Error:[/red] Unsupported format '{format}'. Use 'png' or 'svg'.")
        raise typer.Exit(1)

    try:
        mermaid_code = read_code_input(code)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Generate output path if not provided
    if output is None:
        output = Path(f"diagram.{format_lower}")

    try:
        image_data = render_mermaid(mermaid_code, format_lower, background)
        output.write_bytes(image_data)

        if json_output:
            stdout_console.print_json(json.dumps({
                "output": str(output.absolute()),
                "format": format_lower,
                "size_bytes": len(image_data),
                "background": background,
            }))
        else:
            console.print(f"[green]Rendered:[/green] {output}")
            console.print(f"Size: {len(image_data)} bytes")

    except httpx.HTTPStatusError as e:
        console.print(f"[red]Render Error:[/red] HTTP {e.response.status_code}")
        if e.response.status_code == 400:
            console.print("[yellow]Hint:[/yellow] Check mermaid syntax")
        raise typer.Exit(1)
    except httpx.RequestError as e:
        console.print(f"[red]Network Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def upload(
    code: Annotated[str, typer.Argument(help="Mermaid code or @filepath")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="File name in Drive")] = None,
    folder_id: Annotated[str | None, typer.Option("--folder", "-f", help="Destination folder ID")] = None,
    format: Annotated[str, typer.Option("--format", help="Image format: png, svg")] = "png",
    background: Annotated[str, typer.Option("--background", "-b", help="Background color")] = "white",
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Render mermaid diagram and upload to Drive (private).

    The uploaded file is private to the account owner only.
    Use for inserting diagrams into Google Docs via insertInlineImage.

    Examples:
        mermaid.py upload "graph TD; A-->B" --name architecture.png
        mermaid.py upload @diagram.mmd --folder <folder_id>
    """
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaInMemoryUpload

    format_lower = format.lower()
    if format_lower not in ("png", "svg"):
        console.print(f"[red]Error:[/red] Unsupported format '{format}'. Use 'png' or 'svg'.")
        raise typer.Exit(1)

    try:
        mermaid_code = read_code_input(code)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Generate file name if not provided
    if name is None:
        name = f"diagram.{format_lower}"
    elif not name.endswith(f".{format_lower}"):
        name = f"{name}.{format_lower}"

    # Render diagram
    try:
        image_data = render_mermaid(mermaid_code, format_lower, background)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Render Error:[/red] HTTP {e.response.status_code}")
        if e.response.status_code == 400:
            console.print("[yellow]Hint:[/yellow] Check mermaid syntax")
        raise typer.Exit(1)
    except httpx.RequestError as e:
        console.print(f"[red]Network Error:[/red] {e}")
        raise typer.Exit(1)

    # Upload to Drive
    try:
        service = get_drive_service(account)

        mime_type = "image/svg+xml" if format_lower == "svg" else "image/png"

        # Build file metadata
        metadata: dict[str, str | list[str]] = {"name": name}
        if folder_id:
            metadata["parents"] = [folder_id]

        # Create media upload from memory
        media = MediaInMemoryUpload(image_data, mimetype=mime_type, resumable=True)

        # Upload file (no permissions = private to owner only)
        file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name, mimeType, webViewLink",
        ).execute()

        file_id = file.get("id", "")
        result_mime = file.get("mimeType", mime_type)
        url = get_file_url(file_id)

        if json_output:
            stdout_console.print_json(json.dumps({
                "file_id": file_id,
                "name": file.get("name"),
                "mime_type": result_mime,
                "url": url,
                "size_bytes": len(image_data),
                "format": format_lower,
            }))
        else:
            console.print(f"[green]Uploaded:[/green] {name}")
            console.print(f"ID: {file_id}")
            console.print(f"URL: {url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def url(
    code: Annotated[str, typer.Argument(help="Mermaid code or @filepath")],
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: png, svg")] = "png",
    background: Annotated[str, typer.Option("--background", "-b", help="Background color")] = "white",
) -> None:
    """Generate mermaid.ink URL for diagram (no upload).

    Useful for quick previews or embedding in markdown.
    Note: URL encodes the diagram, may be long for complex diagrams.
    """
    format_lower = format.lower()
    if format_lower not in ("png", "svg"):
        console.print(f"[red]Error:[/red] Unsupported format '{format}'. Use 'png' or 'svg'.")
        raise typer.Exit(1)

    try:
        mermaid_code = read_code_input(code)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    url = get_mermaid_ink_url(mermaid_code, format_lower, background)
    stdout_console.print(url)


if __name__ == "__main__":
    app()
