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
"""Google Tasks CLI for task operations."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
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
from auth import get_credentials, get_active_account  # noqa: E402
from utils import confirm_action, merge_extra  # noqa: E402


def get_local_timezone() -> str:
    """Get local IANA timezone name (e.g., 'America/New_York')."""
    # Check TZ env var
    tz = os.environ.get("TZ")
    if tz and "/" in tz:
        return tz

    # macOS/Linux: Parse /etc/localtime symlink
    localtime = "/etc/localtime"
    if os.path.islink(localtime):
        link = os.readlink(localtime)
        if "zoneinfo/" in link:
            return link.split("zoneinfo/")[-1]

    return "UTC"  # Fallback


def parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM or HH:MM:SS to (hour, minute)."""
    parts = time_str.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid time format: {time_str}")
    return int(parts[0]), int(parts[1])


def get_tz_offset(tz_name: str) -> str:
    """Get UTC offset string for a timezone (e.g., '-05:00')."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        offset = now.strftime("%z")
        return f"{offset[:3]}:{offset[3:]}"  # Convert +0500 to +05:00
    except Exception:
        return "Z"


app = typer.Typer(help="Google Tasks CLI operations.")
console = Console(stderr=True)
stdout_console = Console()


def get_tasks_service(account: str | None = None):
    """Get authenticated Tasks API service."""
    creds = get_credentials(account)
    return build("tasks", "v1", credentials=creds)


def get_calendar_service(account: str | None = None):
    """Get authenticated Calendar API service."""
    creds = get_credentials(account)
    return build("calendar", "v3", credentials=creds)


def get_default_calendar(account: str | None = None) -> str:
    """Get default calendar ID (specified account, active account, or 'primary')."""
    if account:
        return account
    active = get_active_account()
    return active if active else "primary"


@app.command("list-lists")
def list_task_lists(
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all task lists."""
    try:
        service = get_tasks_service(account)
        results = service.tasklists().list().execute()
        task_lists = results.get("items", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "count": len(task_lists),
                "tasklists": task_lists,
            }))
            return

        if not task_lists:
            console.print("[yellow]No task lists found.[/yellow]")
            return

        table = Table(title="Task Lists")
        table.add_column("Title", style="cyan", overflow="fold")
        table.add_column("ID", style="dim")

        for tl in task_lists:
            table.add_row(tl.get("title", ""), tl.get("id", ""))

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("list-tasks")
def list_tasks(
    tasklist_id: Annotated[str, typer.Argument(help="Task list ID")],
    show_completed: Annotated[bool, typer.Option("--completed", "-c", help="Show completed tasks")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 50,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List tasks in a task list."""
    try:
        service = get_tasks_service(account)
        results = service.tasks().list(
            tasklist=tasklist_id,
            maxResults=limit,
            showCompleted=show_completed,
            showHidden=show_completed,
        ).execute()

        tasks = results.get("items", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "tasklist_id": tasklist_id,
                "count": len(tasks),
                "tasks": tasks,
            }))
            return

        if not tasks:
            console.print("[yellow]No tasks found.[/yellow]")
            return

        table = Table(title="Tasks")
        table.add_column("Status", style="dim", width=3)
        table.add_column("Title", style="cyan", overflow="fold")
        table.add_column("Due", style="dim", width=16)
        table.add_column("ID", style="dim", width=20)

        for task in tasks:
            status = "[green]x[/green]" if task.get("status") == "completed" else "[ ]"
            due_raw = task.get("due", "")
            if due_raw:
                # Show time if present (not midnight UTC)
                if "T" in due_raw and not due_raw.endswith("T00:00:00.000Z"):
                    due = due_raw[:16].replace("T", " ")
                else:
                    due = due_raw[:10]
            else:
                due = ""
            table.add_row(
                status,
                task.get("title", ""),
                due,
                task.get("id", "")[:20],
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    tasklist_id: Annotated[str, typer.Argument(help="Task list ID")],
    title: Annotated[str, typer.Argument(help="Task title")],
    notes: Annotated[str | None, typer.Option("--notes", "-n", help="Task notes")] = None,
    due: Annotated[str | None, typer.Option("--due", "-d", help="Due date (YYYY-MM-DD)")] = None,
    time_opt: Annotated[str | None, typer.Option("--time", "-t", help="Due time (HH:MM)")] = None,
    duration: Annotated[int | None, typer.Option("--duration", help="Duration in minutes (creates calendar event)")] = None,
    timezone_str: Annotated[str | None, typer.Option("--timezone", "-z", help="IANA timezone (default: local)")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new task."""
    details = f"Title: {title}"
    if due:
        due_display = due
        if time_opt:
            due_display += f" {time_opt}"
        details += f"\nDue: {due_display}"
    if duration:
        details += f"\nDuration: {duration} min (calendar event)"
    if notes:
        details += f"\nNotes: {notes[:50]}..."

    if time_opt and not due:
        console.print("[red]Error:[/red] --time requires --due")
        raise typer.Exit(1)

    if duration and not (due and time_opt):
        console.print("[red]Error:[/red] --duration requires --due and --time")
        raise typer.Exit(1)

    if not confirm_action("Create task", details, "tasks", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_tasks_service(account)
        tz = timezone_str or get_local_timezone()

        task_body: dict = {"title": title}
        if notes:
            task_body["notes"] = notes
        if due:
            if time_opt:
                # Combine date + time + timezone -> RFC 3339
                hour, minute = parse_time(time_opt)
                offset = get_tz_offset(tz)
                task_body["due"] = f"{due}T{hour:02d}:{minute:02d}:00{offset}"
            else:
                # Date-only: use midnight UTC
                task_body["due"] = f"{due}T00:00:00.000Z"

        # Merge --extra options
        try:
            task_body, api_params = merge_extra(task_body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        task = service.tasks().insert(
            tasklist=tasklist_id,
            body=task_body,
            **api_params,
        ).execute()

        # Create calendar event if duration specified
        event_id = None
        if duration and due and time_opt:
            cal_service = get_calendar_service(account)
            hour, minute = parse_time(time_opt)
            start_dt = f"{due}T{hour:02d}:{minute:02d}:00"
            # Calculate end time
            from datetime import timedelta
            start = datetime.fromisoformat(start_dt)
            end = start + timedelta(minutes=duration)
            end_dt = end.strftime("%Y-%m-%dT%H:%M:%S")

            event_body = {
                "summary": f"[Task] {title}",
                "start": {"dateTime": start_dt, "timeZone": tz},
                "end": {"dateTime": end_dt, "timeZone": tz},
                "description": f"Task ID: {task.get('id')}\nTask list: {tasklist_id}",
            }
            event = cal_service.events().insert(
                calendarId=get_default_calendar(account),
                body=event_body,
            ).execute()
            event_id = event.get("id")

        if json_output:
            result = {
                "id": task.get("id"),
                "title": task.get("title"),
                "status": task.get("status"),
                "due": task.get("due"),
            }
            if event_id:
                result["calendar_event_id"] = event_id
            stdout_console.print_json(json.dumps(result))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"Task ID: {task.get('id')}")
            if event_id:
                console.print(f"Calendar event: {event_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def complete(
    tasklist_id: Annotated[str, typer.Argument(help="Task list ID")],
    task_id: Annotated[str, typer.Argument(help="Task ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Mark a task as completed."""
    try:
        service = get_tasks_service(account)

        # Get task details for confirmation
        task = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id,
        ).execute()

        details = f"Task: {task.get('title', '(no title)')}\nID: {task_id}"
        if not confirm_action("Complete task", details, "tasks", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        # Update status
        task["status"] = "completed"
        updated = service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=task,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": updated.get("id"),
                "title": updated.get("title"),
                "status": updated.get("status"),
                "completed": updated.get("completed"),
            }))
        else:
            console.print(f"[green]Completed:[/green] {task.get('title')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def update(
    tasklist_id: Annotated[str, typer.Argument(help="Task list ID")],
    task_id: Annotated[str, typer.Argument(help="Task ID")],
    title: Annotated[str | None, typer.Option("--title", help="New title")] = None,
    notes: Annotated[str | None, typer.Option("--notes", "-n", help="New notes")] = None,
    due: Annotated[str | None, typer.Option("--due", "-d", help="New due date (YYYY-MM-DD)")] = None,
    time_opt: Annotated[str | None, typer.Option("--time", "-t", help="New due time (HH:MM)")] = None,
    timezone_str: Annotated[str | None, typer.Option("--timezone", "-z", help="IANA timezone")] = None,
    clear_due: Annotated[bool, typer.Option("--clear-due", help="Clear due date")] = False,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Update an existing task."""
    updates = []
    if title:
        updates.append(f"Title: {title}")
    if notes:
        updates.append(f"Notes: {notes[:50]}...")
    if due:
        due_display = due
        if time_opt:
            due_display += f" {time_opt}"
        updates.append(f"Due: {due_display}")
    if clear_due:
        updates.append("Clear due date")

    if not updates:
        console.print("[red]Error:[/red] No updates specified")
        raise typer.Exit(1)

    if time_opt and not due:
        console.print("[red]Error:[/red] --time requires --due")
        raise typer.Exit(1)

    try:
        service = get_tasks_service(account)

        # Get task details for confirmation
        task = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id,
        ).execute()

        details = f"Task: {task.get('title', '(no title)')}\n" + "\n".join(updates)
        if not confirm_action("Update task", details, "tasks", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        # Apply updates
        if title:
            task["title"] = title
        if notes:
            task["notes"] = notes
        if clear_due:
            task.pop("due", None)
        elif due:
            if time_opt:
                hour, minute = parse_time(time_opt)
                tz = timezone_str or get_local_timezone()
                offset = get_tz_offset(tz)
                task["due"] = f"{due}T{hour:02d}:{minute:02d}:00{offset}"
            else:
                task["due"] = f"{due}T00:00:00.000Z"

        # Merge --extra options
        try:
            task, api_params = merge_extra(task, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        updated = service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=task,
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": updated.get("id"),
                "title": updated.get("title"),
                "due": updated.get("due"),
                "updated": updated.get("updated"),
            }))
        else:
            console.print(f"[green]Updated:[/green] {updated.get('title')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def delete(
    tasklist_id: Annotated[str, typer.Argument(help="Task list ID")],
    task_id: Annotated[str, typer.Argument(help="Task ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a task."""
    try:
        service = get_tasks_service(account)

        # Get task details for confirmation
        task = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id,
        ).execute()

        details = f"Task: {task.get('title', '(no title)')}\nID: {task_id}"
        if not confirm_action("Delete task", details, "tasks", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        service.tasks().delete(
            tasklist=tasklist_id,
            task=task_id,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "deleted": True,
                "id": task_id,
                "title": task.get("title"),
            }))
        else:
            console.print(f"[green]Deleted:[/green] {task.get('title')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
