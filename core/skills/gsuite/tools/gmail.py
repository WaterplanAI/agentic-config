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
"""Gmail CLI for email operations."""
from __future__ import annotations

import base64
import json
import re
import sys
from email.mime.text import MIMEText
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Annotated

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.table import Table

# Import auth and utils modules
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402
from utils import confirm_action, merge_extra  # noqa: E402

app = typer.Typer(help="Gmail CLI operations.")
label_app = typer.Typer(help="Manage message labels.")
app.add_typer(label_app, name="label")
console = Console(stderr=True)
stdout_console = Console()


def get_gmail_service(account: str | None = None):
    """Get authenticated Gmail API service."""
    creds = get_credentials(account)
    return build("gmail", "v1", credentials=creds)


def extract_email(addr_string: str) -> str:
    """Extract email from 'Name <email>' format."""
    _, email = parseaddr(addr_string)
    return email.lower().strip()


def get_current_user_email(service) -> str:
    """Get authenticated user's email."""
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "").lower()


def validate_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))


def decode_body(payload: dict, depth: int = 0, max_depth: int = 10) -> str:
    """Decode email body from payload."""
    if depth > max_depth:
        return "[Body too deeply nested]"

    body = payload.get("body", {})
    data = body.get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Check parts for multipart messages
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime_type == "text/html" and not any(p.get("mimeType") == "text/plain" for p in parts):
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime_type.startswith("multipart/"):
            result = decode_body(part, depth + 1, max_depth)
            if result and result != "[Body could not be decoded - unsupported format]":
                return result

    return "[Body could not be decoded - unsupported format]"


def get_header(headers: list[dict], name: str) -> str:
    """Get header value by name."""
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


@app.command("list")
def list_messages(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    query: Annotated[str | None, typer.Option("--query", "-q", help="Search query")] = None,
    labels: Annotated[str | None, typer.Option("--labels", "-l", help="Label IDs (comma-separated)")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List messages from inbox."""
    try:
        service = get_gmail_service(account)

        # Build request params
        params: dict = {"userId": "me", "maxResults": limit}
        if query:
            params["q"] = query
        if labels:
            params["labelIds"] = [label.strip() for label in labels.split(",")]

        results = service.users().messages().list(**params).execute()
        messages = results.get("messages", [])

        if json_output:
            # Fetch message details for JSON output
            detailed = []
            for msg in messages:
                detail = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                ).execute()
                headers = detail.get("payload", {}).get("headers", [])
                detailed.append({
                    "id": msg["id"],
                    "threadId": msg.get("threadId"),
                    "subject": get_header(headers, "Subject"),
                    "from": get_header(headers, "From"),
                    "date": get_header(headers, "Date"),
                    "snippet": detail.get("snippet", ""),
                })
            stdout_console.print_json(json.dumps({"count": len(detailed), "messages": detailed}))
            return

        if not messages:
            console.print("[yellow]No messages found.[/yellow]")
            return

        table = Table(title="Messages")
        table.add_column("Date", style="dim", width=12)
        table.add_column("From", style="cyan", width=25, overflow="ellipsis")
        table.add_column("Subject", overflow="fold")
        table.add_column("ID", style="dim", width=16)

        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = detail.get("payload", {}).get("headers", [])
            date = get_header(headers, "Date")[:12] if get_header(headers, "Date") else ""
            table.add_row(
                date,
                get_header(headers, "From")[:25],
                get_header(headers, "Subject"),
                msg["id"],
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def read(
    message_id: Annotated[str, typer.Argument(help="Message ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Read a message's content."""
    try:
        service = get_gmail_service(account)
        message = service.users().messages().get(
            userId="me", id=message_id, format="full",
        ).execute()

        payload = message.get("payload", {})
        headers = payload.get("headers", [])
        body = decode_body(payload)

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": message_id,
                "threadId": message.get("threadId"),
                "subject": get_header(headers, "Subject"),
                "from": get_header(headers, "From"),
                "to": get_header(headers, "To"),
                "date": get_header(headers, "Date"),
                "body": body,
                "labels": message.get("labelIds", []),
            }))
            return

        console.print(f"[cyan]From:[/cyan] {get_header(headers, 'From')}")
        console.print(f"[cyan]To:[/cyan] {get_header(headers, 'To')}")
        console.print(f"[cyan]Date:[/cyan] {get_header(headers, 'Date')}")
        console.print(f"[cyan]Subject:[/cyan] {get_header(headers, 'Subject')}")
        console.print("")
        console.print(body)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def send(
    to: Annotated[str, typer.Argument(help="Recipient email")],
    subject: Annotated[str, typer.Argument(help="Email subject")],
    body: Annotated[str, typer.Argument(help="Email body")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: cc, bcc arrays or additional headers")] = None,
    account: Annotated[str | None, typer.Option("--account", "-A", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Send an email."""
    if not validate_email(to):
        console.print(f"[red]Error:[/red] Invalid email format: {to}")
        raise typer.Exit(1)

    # Parse extra options for confirmation display
    cc_list: list[str] = []
    bcc_list: list[str] = []
    extra_headers: dict = {}
    if extra:
        try:
            _, extra_headers = merge_extra({}, extra)
            cc_list = extra_headers.pop("cc", [])
            bcc_list = extra_headers.pop("bcc", [])
            if isinstance(cc_list, str):
                cc_list = [cc_list]
            if isinstance(bcc_list, str):
                bcc_list = [bcc_list]
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    details = f"To: {to}"
    if cc_list:
        details += f"\nCc: {', '.join(cc_list)}"
    if bcc_list:
        details += f"\nBcc: {', '.join(bcc_list)}"
    details += f"\nSubject: {subject}\n\n{body[:200]}{'...' if len(body) > 200 else ''}"

    if not confirm_action("Send email", details, "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        if cc_list:
            message["cc"] = ", ".join(cc_list)
        if bcc_list:
            message["bcc"] = ", ".join(bcc_list)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", body={"raw": raw},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": result.get("id"),
                "threadId": result.get("threadId"),
                "to": to,
                "subject": subject,
            }))
        else:
            console.print(f"[green]Sent:[/green] {subject}")
            console.print(f"Message ID: {result.get('id')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def reply(
    message_id: Annotated[str, typer.Argument(help="Message ID to reply to")],
    body: Annotated[str, typer.Argument(help="Reply body")],
    to: Annotated[str | None, typer.Option("--to", "-t", help="Override recipient")] = None,
    cc: Annotated[str | None, typer.Option("--cc", help="Additional CC recipients")] = None,
    reply_all: Annotated[bool, typer.Option("--all", help="Reply to all recipients")] = False,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: bcc array or additional headers")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Reply to an email."""
    try:
        service = get_gmail_service(account)

        # Get original message
        original = service.users().messages().get(
            userId="me", id=message_id, format="full",
        ).execute()

        payload = original.get("payload", {})
        headers = payload.get("headers", [])

        # Extract headers
        orig_from = get_header(headers, "From")
        orig_to = get_header(headers, "To")
        orig_cc = get_header(headers, "Cc")
        orig_subject = get_header(headers, "Subject")
        orig_message_id = get_header(headers, "Message-ID")
        orig_references = get_header(headers, "References")
        thread_id = original.get("threadId")

        # Determine recipient(s)
        if to:
            reply_to = to
        else:
            # Extract email from "Name <email>" format
            email_match = re.search(r'<([^>]+)>', orig_from)
            reply_to = email_match.group(1) if email_match else orig_from

        # Build subject
        subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

        # Build references header
        references = f"{orig_references} {orig_message_id}".strip() if orig_references else orig_message_id

        # Build CC list
        cc_list: list[str] = []
        if reply_all:
            current_user = get_current_user_email(service)
            sender_email = extract_email(reply_to)
            all_addrs = getaddresses([orig_to, orig_cc])
            for _, email_addr in all_addrs:
                email_lower = email_addr.lower().strip()
                if email_lower and email_lower != sender_email and email_lower != current_user:
                    cc_list.append(email_addr)
        if cc:
            cc_list.extend([addr.strip() for addr in cc.split(",") if addr.strip()])

        # Parse extra options for BCC
        bcc_list: list[str] = []
        if extra:
            try:
                _, extra_headers = merge_extra({}, extra)
                bcc_list = extra_headers.pop("bcc", [])
                if isinstance(bcc_list, str):
                    bcc_list = [bcc_list]
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1)

        cc_display = f"\nCc: {', '.join(cc_list)}" if cc_list else ""
        bcc_display = f"\nBcc: {', '.join(bcc_list)}" if bcc_list else ""
        details = f"To: {reply_to}{cc_display}{bcc_display}\nSubject: {subject}\n\n{body[:200]}{'...' if len(body) > 200 else ''}"
        if not confirm_action("Send reply", details, "gmail", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        # Create message
        message = MIMEText(body)
        message["to"] = reply_to
        if cc_list:
            message["cc"] = ", ".join(cc_list)
        if bcc_list:
            message["bcc"] = ", ".join(bcc_list)
        message["subject"] = subject
        message["In-Reply-To"] = orig_message_id
        message["References"] = references

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": result.get("id"),
                "threadId": result.get("threadId"),
                "to": reply_to,
                "subject": subject,
                "in_reply_to": message_id,
            }))
        else:
            console.print(f"[green]Reply sent:[/green] {subject}")
            console.print(f"Message ID: {result.get('id')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def draft(
    to: Annotated[str, typer.Argument(help="Recipient email")],
    subject: Annotated[str, typer.Argument(help="Email subject")],
    body: Annotated[str, typer.Argument(help="Email body")],
    html: Annotated[bool, typer.Option("--html", help="Send as HTML (enables bold, links, etc.)")] = False,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: cc, bcc arrays or additional headers")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a draft email."""
    if not validate_email(to):
        console.print(f"[red]Error:[/red] Invalid email format: {to}")
        raise typer.Exit(1)

    # Parse extra options for confirmation display
    cc_list: list[str] = []
    bcc_list: list[str] = []
    if extra:
        try:
            _, extra_headers = merge_extra({}, extra)
            cc_list = extra_headers.pop("cc", [])
            bcc_list = extra_headers.pop("bcc", [])
            if isinstance(cc_list, str):
                cc_list = [cc_list]
            if isinstance(bcc_list, str):
                bcc_list = [bcc_list]
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    details = f"To: {to}"
    if cc_list:
        details += f"\nCc: {', '.join(cc_list)}"
    if bcc_list:
        details += f"\nBcc: {', '.join(bcc_list)}"
    details += f"\nSubject: {subject}\n\n{body[:200]}{'...' if len(body) > 200 else ''}"

    if not confirm_action("Create draft", details, "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)

        # Create message with appropriate content type
        content_type = "html" if html else "plain"
        message = MIMEText(body, content_type)
        message["to"] = to
        message["subject"] = subject
        if cc_list:
            message["cc"] = ", ".join(cc_list)
        if bcc_list:
            message["bcc"] = ", ".join(bcc_list)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": result.get("id"),
                "message_id": result.get("message", {}).get("id"),
                "to": to,
                "subject": subject,
            }))
        else:
            console.print(f"[green]Draft created:[/green] {subject}")
            console.print(f"Draft ID: {result.get('id')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query (Gmail syntax)")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search messages using Gmail query syntax."""
    # Delegate to list with query
    list_messages(limit=limit, query=query, labels=None, account=account, json_output=json_output)


@app.command("labels")
def list_labels(
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all labels."""
    try:
        service = get_gmail_service(account)
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        if json_output:
            stdout_console.print_json(json.dumps({"count": len(labels), "labels": labels}))
            return

        if not labels:
            console.print("[yellow]No labels found.[/yellow]")
            return

        table = Table(title="Labels")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Type", style="dim")

        for label in sorted(labels, key=lambda x: x.get("name", "")):
            table.add_row(
                label.get("name"),
                label.get("id"),
                label.get("type", "user"),
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def archive(
    message_id: Annotated[str, typer.Argument(help="Message ID to archive")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Archive a message (remove from INBOX)."""
    if not confirm_action("Archive message", f"ID: {message_id}", "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)
        result = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "archived": True,
                "id": message_id,
                "labels": result.get("labelIds", []),
            }))
        else:
            console.print(f"[green]Archived:[/green] {message_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@label_app.command("show")
def label_show(
    message_id: Annotated[str, typer.Argument(help="Message ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show labels on a message."""
    try:
        service = get_gmail_service(account)
        message = service.users().messages().get(
            userId="me", id=message_id, format="minimal",
        ).execute()

        labels = message.get("labelIds", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": message_id,
                "labels": labels,
            }))
        else:
            console.print(f"[cyan]Message:[/cyan] {message_id}")
            console.print(f"[cyan]Labels:[/cyan] {', '.join(labels) if labels else '(none)'}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@label_app.command("add")
def label_add(
    message_id: Annotated[str, typer.Argument(help="Message ID")],
    label_id: Annotated[str, typer.Argument(help="Label ID to add")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add a label to a message."""
    if not confirm_action("Add label", f"Label: {label_id}\nMessage: {message_id}", "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)
        result = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": message_id,
                "added": label_id,
                "labels": result.get("labelIds", []),
            }))
        else:
            console.print(f"[green]Added label:[/green] {label_id} to {message_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@label_app.command("remove")
def label_remove(
    message_id: Annotated[str, typer.Argument(help="Message ID")],
    label_id: Annotated[str, typer.Argument(help="Label ID to remove")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Remove a label from a message."""
    if not confirm_action("Remove label", f"Label: {label_id}\nMessage: {message_id}", "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)
        result = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": [label_id]},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": message_id,
                "removed": label_id,
                "labels": result.get("labelIds", []),
            }))
        else:
            console.print(f"[green]Removed label:[/green] {label_id} from {message_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def delete(
    message_id: Annotated[str, typer.Argument(help="Message or draft ID to delete")],
    draft: Annotated[bool, typer.Option("--draft", "-d", help="Delete a draft instead of a message")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a message or draft."""
    item_type = "draft" if draft else "message"

    if not confirm_action(f"Delete {item_type}", f"ID: {message_id}", "gmail", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_gmail_service(account)

        if draft:
            service.users().drafts().delete(userId="me", id=message_id).execute()
        else:
            service.users().messages().delete(userId="me", id=message_id).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "deleted": True,
                "id": message_id,
                "type": item_type,
            }))
        else:
            console.print(f"[green]Deleted {item_type}:[/green] {message_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
