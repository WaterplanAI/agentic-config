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
"""Google Docs Comments extractor."""
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

console = Console(stderr=True)
stdout_console = Console()


def get_drive_service(account: str | None = None):
    """Get authenticated Drive API service (comments are via Drive API)."""
    creds = get_credentials(account)
    return build("drive", "v3", credentials=creds)


def get_docs_service(account: str | None = None):
    """Get authenticated Docs API service."""
    creds = get_credentials(account)
    return build("docs", "v1", credentials=creds)


def main(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    include_resolved: Annotated[bool, typer.Option("--resolved", help="Include resolved comments")] = False,
) -> None:
    """List all comments from a Google Doc."""
    try:
        # Get Drive API service (comments endpoint is in Drive API, not Docs API)
        drive_service = get_drive_service(account)
        docs_service = get_docs_service(account)

        # Get document to extract text for context
        doc = docs_service.documents().get(documentId=doc_id).execute()
        doc_title = doc.get("title", "Untitled")

        # Extract full text content with indices
        content = doc.get("body", {}).get("content", [])
        text_map = {}
        for element in content:
            if "paragraph" in element:
                paragraph = element["paragraph"]
                for elem in paragraph.get("elements", []):
                    if "textRun" in elem:
                        start_idx = elem.get("startIndex", 0)
                        end_idx = elem.get("endIndex", 0)
                        text_content = elem["textRun"].get("content", "")
                        text_map[start_idx] = (end_idx, text_content)

        # Get comments from Drive API
        comments_response = drive_service.comments().list(
            fileId=doc_id,
            fields="comments(id,content,author,createdTime,modifiedTime,resolved,quotedFileContent,replies,anchor)",
            includeDeleted=False,
        ).execute()

        comments = comments_response.get("comments", [])

        if not include_resolved:
            comments = [c for c in comments if not c.get("resolved", False)]

        if json_output:
            stdout_console.print_json(json.dumps({
                "doc_id": doc_id,
                "title": doc_title,
                "comment_count": len(comments),
                "comments": comments,
            }, indent=2))
        else:
            console.print(f"[bold]{doc_title}[/bold]")
            console.print(f"Found {len(comments)} comment(s)\n")

            for idx, comment in enumerate(comments, 1):
                console.print(f"[cyan]Comment {idx}:[/cyan]")
                console.print(f"  ID: {comment.get('id')}")
                console.print(f"  Author: {comment.get('author', {}).get('displayName', 'Unknown')}")
                console.print(f"  Created: {comment.get('createdTime', 'Unknown')}")
                console.print(f"  Resolved: {comment.get('resolved', False)}")
                console.print(f"  Content: {comment.get('content', '(empty)')}")

                # Show quoted context if available
                if "quotedFileContent" in comment:
                    quoted = comment["quotedFileContent"].get("value", "")
                    console.print(f"  Context: \"{quoted}\"")

                # Show replies if any
                replies = comment.get("replies", [])
                if replies:
                    console.print(f"  Replies ({len(replies)}):")
                    for reply in replies:
                        console.print(f"    - {reply.get('author', {}).get('displayName', 'Unknown')}: {reply.get('content', '')}")

                console.print()

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
