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
# ]
# requires-python = ">=3.12"
# ///
"""Google Drive CLI for file operations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.table import Table

# Import auth module for credential loading
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402
from utils import confirm_action, merge_extra  # noqa: E402

app = typer.Typer(help="Google Drive CLI operations.")
console = Console(stderr=True)
stdout_console = Console()

# Role mappings
ROLES = {
    "reader": "reader",
    "writer": "writer",
    "commenter": "commenter",
    "owner": "owner",
}

# File type to MIME type mappings
FILE_TYPES = {
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "document": "application/vnd.google-apps.document",
    "doc": "application/vnd.google-apps.document",
    "presentation": "application/vnd.google-apps.presentation",
    "slides": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
    "pdf": "application/pdf",
    "image": "image/",  # Partial match
    "video": "video/",  # Partial match
    "audio": "audio/",  # Partial match
}


def get_file_url(file_id: str, mime_type: str) -> str:
    """Generate correct URL based on file type."""
    if "spreadsheet" in mime_type:
        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
    elif "document" in mime_type:
        return f"https://docs.google.com/document/d/{file_id}/edit"
    elif "presentation" in mime_type:
        return f"https://docs.google.com/presentation/d/{file_id}/edit"
    elif "folder" in mime_type:
        return f"https://drive.google.com/drive/folders/{file_id}"
    else:
        return f"https://drive.google.com/file/d/{file_id}/view"


def get_drive_service(account: str | None = None):
    """Get authenticated Drive API service."""
    creds = get_credentials(account)
    return build("drive", "v3", credentials=creds)


def get_docs_service(account: str | None = None):
    """Get authenticated Docs API v1 service."""
    creds = get_credentials(account)
    return build("docs", "v1", credentials=creds)


def get_driveactivity_service(account: str | None = None):
    """Get authenticated Drive Activity API v2 service."""
    creds = get_credentials(account)
    return build("driveactivity", "v2", credentials=creds)


def extract_suggestions_from_doc(doc: dict) -> dict[str, dict]:
    """Extract suggestions from Google Doc, grouped by suggestion ID."""
    suggestions: dict[str, dict] = {}

    for tab in doc.get("tabs", []):
        tab_title = tab.get("tabProperties", {}).get("title", "Untitled")
        body = tab.get("documentTab", {}).get("body", {})

        for element in body.get("content", []):
            if "paragraph" not in element:
                continue
            for elem in element["paragraph"].get("elements", []):
                text_run = elem.get("textRun", {})
                content = text_run.get("content", "")

                for sid in text_run.get("suggestedInsertionIds", []):
                    if sid not in suggestions:
                        suggestions[sid] = {"tab": tab_title, "type": "insertion", "content": []}
                    suggestions[sid]["content"].append(content)

                for sid in text_run.get("suggestedDeletionIds", []):
                    if sid not in suggestions:
                        suggestions[sid] = {"tab": tab_title, "type": "deletion", "content": []}
                    suggestions[sid]["content"].append(content)

    return suggestions


def get_suggestion_activities(file_id: str, since: str | None = None, account: str | None = None) -> list[dict]:
    """Get suggestion activities from Drive Activity API."""
    try:
        service = get_driveactivity_service(account)
    except Exception:
        return []

    try:
        results = service.activity().query(body={
            "itemName": f"items/{file_id}",
            "pageSize": 100,
        }).execute()
    except HttpError:
        return []

    activities = []
    today_filter = since or ""

    for act in results.get("activities", []):
        timestamp = act.get("timestamp", "")
        if today_filter and not timestamp.startswith(today_filter):
            continue

        primary = act.get("primaryActionDetail", {})
        comment = primary.get("comment", {})
        suggestion = comment.get("suggestion", {})

        if not suggestion:
            continue

        # Get actor from actors list
        actors = act.get("actors", [])
        person_id = ""
        for actor in actors:
            user = actor.get("user", {}).get("knownUser", {})
            person_id = user.get("personName", "")

        activities.append({
            "timestamp": timestamp,
            "person_id": person_id,
            "subtype": suggestion.get("subtype", "UNKNOWN"),
        })

    return activities


@app.command("list")
def list_files(
    folder_id: Annotated[str | None, typer.Option("--folder", "-f", help="Folder ID")] = None,
    query: Annotated[str | None, typer.Option("--query", "-q", help="Search query")] = None,
    shared_with_me: Annotated[bool, typer.Option("--shared-with-me", help="List files shared with me")] = False,
    owner: Annotated[str | None, typer.Option("--owner", "-o", help="Filter by owner email")] = None,
    file_type: Annotated[str | None, typer.Option("--type", "-t", help="File type: spreadsheet, document, presentation, folder, pdf, image, video, audio")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List files in Drive or folder."""
    try:
        service = get_drive_service(account)

        # Build query
        q_parts = ["trashed = false"]
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        if shared_with_me:
            q_parts.append("sharedWithMe = true")
        if owner:
            q_parts.append(f"'{owner}' in owners")
        if file_type:
            type_lower = file_type.lower()
            if type_lower not in FILE_TYPES:
                console.print(f"[red]Error:[/red] Unknown file type '{file_type}'")
                console.print(f"Available: {', '.join(sorted(set(FILE_TYPES.keys())))}")
                raise typer.Exit(1)
            mime = FILE_TYPES[type_lower]
            if mime.endswith("/"):
                q_parts.append(f"mimeType contains '{mime}'")
            else:
                q_parts.append(f"mimeType = '{mime}'")
        if query:
            q_parts.append(query)

        results = service.files().list(
            q=" and ".join(q_parts),
            pageSize=limit,
            fields="files(id, name, mimeType, modifiedTime, size, owners)",
            orderBy="modifiedTime desc",
        ).execute()

        files = results.get("files", [])

        # Enrich files with correct URLs
        for f in files:
            f["url"] = get_file_url(f.get("id", ""), f.get("mimeType", ""))

        if json_output:
            stdout_console.print_json(json.dumps({
                "folder_id": folder_id,
                "count": len(files),
                "files": files,
            }))
            return

        if not files:
            console.print("[yellow]No files found.[/yellow]")
            return

        table = Table(title="Drive Files")
        table.add_column("Name", style="cyan", overflow="fold")
        table.add_column("Type", style="dim")
        table.add_column("URL", style="blue", overflow="fold")

        for f in files:
            mime = f.get("mimeType", "")
            file_id = f.get("id", "")
            # Extract readable type: folder, or MIME subtype (e.g., "pdf" from "application/pdf")
            type_short = "folder" if "folder" in mime else mime.split("/")[-1].split(".")[-1][:10]
            url = get_file_url(file_id, mime)
            table.add_row(f.get("name"), type_short, url)

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query (full-text)")],
    shared_with_me: Annotated[bool, typer.Option("--shared-with-me", help="Search in shared files")] = False,
    owner: Annotated[str | None, typer.Option("--owner", "-o", help="Filter by owner email")] = None,
    file_type: Annotated[str | None, typer.Option("--type", "-t", help="File type: spreadsheet, document, presentation, folder, pdf, image, video, audio")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search files by name or content."""
    try:
        service = get_drive_service(account)

        # Build query with full-text search
        q_parts = [f"fullText contains '{query}'", "trashed = false"]
        if shared_with_me:
            q_parts.append("sharedWithMe = true")
        if owner:
            q_parts.append(f"'{owner}' in owners")
        if file_type:
            type_lower = file_type.lower()
            if type_lower not in FILE_TYPES:
                console.print(f"[red]Error:[/red] Unknown file type '{file_type}'")
                console.print(f"Available: {', '.join(sorted(set(FILE_TYPES.keys())))}")
                raise typer.Exit(1)
            mime = FILE_TYPES[type_lower]
            if mime.endswith("/"):  # Partial match for image/, video/, audio/
                q_parts.append(f"mimeType contains '{mime}'")
            else:
                q_parts.append(f"mimeType = '{mime}'")

        results = service.files().list(
            q=" and ".join(q_parts),
            pageSize=limit,
            fields="files(id, name, mimeType, modifiedTime, size, owners)",
            orderBy="modifiedTime desc",
        ).execute()

        files = results.get("files", [])

        # Enrich files with correct URLs
        for f in files:
            f["url"] = get_file_url(f.get("id", ""), f.get("mimeType", ""))

        if json_output:
            stdout_console.print_json(json.dumps({
                "query": query,
                "count": len(files),
                "files": files,
            }))
            return

        if not files:
            console.print(f"[yellow]No files found matching '{query}'.[/yellow]")
            return

        table = Table(title=f"Search: {query}")
        table.add_column("Name", style="cyan", overflow="fold")
        table.add_column("Type", style="dim")
        table.add_column("URL", style="blue", overflow="fold")

        for f in files:
            mime = f.get("mimeType", "")
            file_id = f.get("id", "")
            type_short = "folder" if "folder" in mime else mime.split("/")[-1].split(".")[-1][:10]
            url = get_file_url(file_id, mime)
            table.add_row(f.get("name"), type_short, url)

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def share(
    file_id: Annotated[str, typer.Argument(help="File ID")],
    email: Annotated[str, typer.Argument(help="Email to share with")],
    role: Annotated[str, typer.Option("--role", "-r", help="Permission role")] = "reader",
    notify: Annotated[bool, typer.Option("--notify/--no-notify", help="Send notification")] = True,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params (e.g., transferOwnership)")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Share a file with a user."""
    if role.lower() not in ROLES:
        console.print(f"[red]Error:[/red] Unknown role '{role}'")
        console.print(f"Available: {', '.join(ROLES.keys())}")
        raise typer.Exit(1)

    try:
        service = get_drive_service(account)

        # Get file name for confirmation
        try:
            file_info = service.files().get(fileId=file_id, fields="name").execute()
            file_name = file_info.get("name", file_id)
        except Exception:
            file_name = file_id

        # Build confirmation details with extra warning for owner transfer
        details = f"File: {file_name}\nShare with: {email}\nRole: {role}"
        if role.lower() == "owner":
            details += "\n\n[red]WARNING: Owner transfer is IRREVERSIBLE![/red]"

        if not confirm_action("Share file", details, "drive", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        permission = {
            "type": "user",
            "role": role.lower(),
            "emailAddress": email,
        }

        # Merge --extra options
        try:
            permission, api_params = merge_extra(permission, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        result = service.permissions().create(
            fileId=file_id,
            body=permission,
            sendNotificationEmail=notify,
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "file_id": file_id,
                "email": email,
                "role": role,
                "permission_id": result.get("id"),
            }))
        else:
            console.print(f"[green]Shared with {email} as {role}[/green]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def mkdir(
    name: Annotated[str, typer.Argument(help="Folder name")],
    parent: Annotated[str | None, typer.Option("--parent", "-p", help="Parent folder ID")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new folder."""
    try:
        service = get_drive_service(account)

        metadata: dict[str, str | list[str]] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent:
            metadata["parents"] = [parent]

        # Merge --extra options
        try:
            metadata, api_params = merge_extra(metadata, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        folder = service.files().create(
            body=metadata,
            fields="id, name, webViewLink",
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "folder_id": folder.get("id"),
                "name": folder.get("name"),
                "url": folder.get("webViewLink"),
            }))
        else:
            console.print(f"[green]Created folder:[/green] {name}")
            console.print(f"ID: {folder.get('id')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def permissions(
    file_id: Annotated[str, typer.Argument(help="File ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List permissions for a file."""
    try:
        service = get_drive_service(account)

        # Get file name for display
        file_info = service.files().get(fileId=file_id, fields="name").execute()

        results = service.permissions().list(
            fileId=file_id,
            fields="permissions(id, type, role, emailAddress, displayName)",
        ).execute()

        perms = results.get("permissions", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "file_id": file_id,
                "file_name": file_info.get("name"),
                "count": len(perms),
                "permissions": perms,
            }))
            return

        if not perms:
            console.print("[yellow]No permissions found.[/yellow]")
            return

        table = Table(title=f"Permissions: {file_info.get('name')}")
        table.add_column("Email/Type", style="cyan")
        table.add_column("Name", style="dim")
        table.add_column("Role", style="green")

        for p in perms:
            email = p.get("emailAddress") or p.get("type", "unknown")
            name = p.get("displayName", "")
            role = p.get("role", "")
            table.add_row(email, name, role)

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def comments(
    file_id: Annotated[str, typer.Argument(help="File ID")],
    include_deleted: Annotated[bool, typer.Option("--include-deleted", help="Include deleted comments")] = False,
    suggestions: Annotated[bool, typer.Option("--suggestions", "-s", help="Include suggestions (Google Docs only)")] = False,
    author: Annotated[str | None, typer.Option("--author", help="Filter by author name")] = None,
    since: Annotated[str | None, typer.Option("--since", help="Filter since date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 100,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List comments on a file. Use --suggestions for Google Docs tracked changes."""
    try:
        service = get_drive_service(account)

        # Get file info including mimeType
        file_info = service.files().get(fileId=file_id, fields="name,mimeType").execute()
        file_name = file_info.get("name", "")
        mime_type = file_info.get("mimeType", "")
        is_google_doc = mime_type == "application/vnd.google-apps.document"

        # Get comments
        results = service.comments().list(
            fileId=file_id,
            fields="comments(id, content, author, createdTime, modifiedTime, resolved, deleted, replies)",
            pageSize=limit,
            includeDeleted=include_deleted,
        ).execute()

        all_comments = results.get("comments", [])

        # Apply author filter
        if author:
            author_lower = author.lower()
            all_comments = [
                c for c in all_comments
                if author_lower in c.get("author", {}).get("displayName", "").lower()
            ]

        # Apply since filter
        if since:
            all_comments = [
                c for c in all_comments
                if c.get("createdTime", "").startswith(since) or c.get("createdTime", "") > since
            ]

        # Get suggestions if requested
        suggestion_list: list[dict] = []
        suggestion_activities: list[dict] = []

        if suggestions:
            if not is_google_doc:
                console.print("[yellow]Warning:[/yellow] --suggestions only works with Google Docs")
            else:
                try:
                    docs_service = get_docs_service(account)
                    doc = docs_service.documents().get(
                        documentId=file_id,
                        includeTabsContent=True,
                    ).execute()

                    raw_suggestions = extract_suggestions_from_doc(doc)
                    for sid, data in raw_suggestions.items():
                        suggestion_list.append({
                            "suggestion_id": sid,
                            "tab": data["tab"],
                            "type": data["type"],
                            "content": "".join(data["content"]),
                        })

                    suggestion_activities = get_suggestion_activities(file_id, since, account)
                except HttpError as e:
                    console.print(f"[yellow]Warning:[/yellow] Could not fetch suggestions: {e.reason}")

        # JSON output
        if json_output:
            output: dict = {
                "file_id": file_id,
                "file_name": file_name,
                "comment_count": len(all_comments),
                "comments": all_comments,
            }
            if suggestions:
                output["suggestion_count"] = len(suggestion_list)
                output["suggestions"] = suggestion_list
                output["suggestion_activities"] = suggestion_activities
            stdout_console.print_json(json.dumps(output))
            return

        # Table output for comments
        if all_comments:
            table = Table(title=f"Comments: {file_name}")
            table.add_column("Author", style="cyan")
            table.add_column("Created", style="dim")
            table.add_column("Content", overflow="fold")
            table.add_column("Resolved", style="green")

            for c in all_comments:
                c_author = c.get("author", {}).get("displayName", "Unknown")
                created = c.get("createdTime", "")[:10]
                content = c.get("content", "")
                resolved = "Yes" if c.get("resolved") else "No"
                table.add_row(c_author, created, content, resolved)

                # Show replies if any
                for reply in c.get("replies", []):
                    r_author = reply.get("author", {}).get("displayName", "Unknown")
                    r_created = reply.get("createdTime", "")[:10]
                    r_content = reply.get("content", "")
                    table.add_row(f"  └─ {r_author}", r_created, r_content, "")

            console.print(table)
        else:
            console.print("[yellow]No comments found.[/yellow]")

        # Table output for suggestions
        if suggestions and suggestion_list:
            console.print()
            s_table = Table(title=f"Suggestions: {file_name}")
            s_table.add_column("ID", style="dim", max_width=20)
            s_table.add_column("Tab", style="cyan")
            s_table.add_column("Type", style="green")
            s_table.add_column("Content", overflow="fold")

            for s in suggestion_list:
                s_table.add_row(
                    s["suggestion_id"][:20],
                    s["tab"],
                    s["type"],
                    s["content"][:100] + ("..." if len(s["content"]) > 100 else ""),
                )

            console.print(s_table)

        if suggestions and suggestion_activities:
            console.print()
            a_table = Table(title="Suggestion Activities")
            a_table.add_column("Timestamp", style="dim")
            a_table.add_column("Action", style="green")

            for a in suggestion_activities:
                a_table.add_row(a["timestamp"][:19], a["subtype"])

            console.print(a_table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def copy(
    file_id: Annotated[str, typer.Argument(help="File ID to copy")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New file name")] = None,
    parent: Annotated[str | None, typer.Option("--parent", "-p", help="Destination folder ID")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Copy a file."""
    try:
        service = get_drive_service(account)

        metadata: dict[str, str | list[str]] = {}
        if name:
            metadata["name"] = name
        if parent:
            metadata["parents"] = [parent]

        # Merge --extra options
        try:
            metadata, api_params = merge_extra(metadata, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        copy = service.files().copy(
            fileId=file_id,
            body=metadata,
            fields="id, name, webViewLink",
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "original_id": file_id,
                "copy_id": copy.get("id"),
                "name": copy.get("name"),
                "url": copy.get("webViewLink"),
            }))
        else:
            console.print(f"[green]Copied:[/green] {copy.get('name')}")
            console.print(f"ID: {copy.get('id')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def upload(
    file_path: Annotated[Path, typer.Argument(help="Local file path to upload")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="File name in Drive (default: local filename)")] = None,
    folder_id: Annotated[str | None, typer.Option("--folder", "-f", help="Destination folder ID")] = None,
    mime_type: Annotated[str | None, typer.Option("--mime-type", "-m", help="MIME type (auto-detected if omitted)")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Upload a local file to Google Drive (always private).

    Files are uploaded with no sharing permissions beyond the owner.
    To share after upload, use the 'share' command explicitly.
    """
    from googleapiclient.http import MediaFileUpload
    import mimetypes

    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    if not file_path.is_file():
        console.print(f"[red]Error:[/red] Not a file: {file_path}")
        raise typer.Exit(1)

    # Determine file name
    upload_name = name or file_path.name

    # Auto-detect MIME type if not provided
    if not mime_type:
        detected, _ = mimetypes.guess_type(str(file_path))
        mime_type = detected or "application/octet-stream"

    try:
        service = get_drive_service(account)

        # Build file metadata
        metadata: dict[str, str | list[str]] = {"name": upload_name}
        if folder_id:
            metadata["parents"] = [folder_id]

        # Create media upload
        media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

        # Upload file (no permissions = private to owner only)
        file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name, mimeType, webViewLink, webContentLink",
        ).execute()

        file_id = file.get("id", "")
        result_mime = file.get("mimeType", mime_type)
        url = get_file_url(file_id, result_mime)

        if json_output:
            stdout_console.print_json(json.dumps({
                "file_id": file_id,
                "name": file.get("name"),
                "mime_type": result_mime,
                "url": url,
            }))
        else:
            console.print(f"[green]Uploaded:[/green] {upload_name}")
            console.print(f"ID: {file_id}")
            console.print(f"URL: {url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
