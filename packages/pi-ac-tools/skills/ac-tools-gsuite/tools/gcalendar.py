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
"""Google Calendar CLI for event operations."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
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


class EventTypeFilter(str, Enum):
    """Filter for event types."""
    all = "all"
    meeting = "meeting"  # Has other attendees besides self
    block = "block"      # No other attendees (focus, OOO, personal)


class ResponseStatus(str, Enum):
    """RSVP response status values."""
    accepted = "accepted"
    declined = "declined"
    tentative = "tentative"


def get_local_timezone() -> str:
    """Get local IANA timezone name (e.g., 'America/New_York')."""
    import os

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


app = typer.Typer(help="Google Calendar CLI operations.")
console = Console(stderr=True)
stdout_console = Console()


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


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string (ISO format or common formats)."""
    # Try ISO format first
    for fmt in [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime: {dt_str}")


def format_event_time(event: dict) -> str:
    """Format event start time for display."""
    start = event.get("start", {})
    if "dateTime" in start:
        dt = start["dateTime"][:16].replace("T", " ")
        return dt
    elif "date" in start:
        return start["date"] + " (all day)"
    return ""


def get_meet_link(event: dict) -> str:
    """Extract Google Meet link from event if present."""
    # Check conferenceData first
    conf = event.get("conferenceData", {})
    for entry in conf.get("entryPoints", []):
        if entry.get("entryPointType") == "video":
            return entry.get("uri", "")
    # Fallback: check hangoutLink
    return event.get("hangoutLink", "")


def format_attendees(event: dict, max_display: int = 2) -> str:
    """Format attendees list for display."""
    attendees = event.get("attendees", [])
    if not attendees:
        return ""
    emails = [a.get("email", "") for a in attendees[:max_display]]
    result = ", ".join(emails)
    if len(attendees) > max_display:
        result += f" +{len(attendees) - max_display}"
    return result


def get_self_response_status(event: dict) -> str | None:
    """Get the current user's response status for an event."""
    for attendee in event.get("attendees", []):
        if attendee.get("self"):
            return attendee.get("responseStatus")
    return None


def get_event_type(event: dict) -> str:
    """Classify event as 'meeting' or 'block'.

    - meeting: has attendees other than self
    - block: no other attendees (focus time, OOO, personal events)
    """
    attendees = event.get("attendees", [])
    other_attendees = [a for a in attendees if not a.get("self")]
    return "meeting" if other_attendees else "block"


@app.command("list-events")
def list_events(
    calendar_id: Annotated[str | None, typer.Option("--calendar", "-c", help="Calendar ID")] = None,
    days: Annotated[int, typer.Option("--days", "-d", help="Days to show (from start date)", min=1)] = 7,
    start: Annotated[str | None, typer.Option("--start", "-s", help="Start date (YYYY-MM-DD, default: today)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
    with_attendees: Annotated[bool, typer.Option("--with-attendees", help="Only events with attendees")] = False,
    attendee: Annotated[str | None, typer.Option("--attendee", help="Filter by attendee email")] = None,
    exclude_declined: Annotated[bool, typer.Option("--exclude-declined", "-x", help="Exclude events user declined")] = False,
    event_type: Annotated[EventTypeFilter, typer.Option("--type", "-t", help="Filter: meeting|block|all")] = EventTypeFilter.all,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List events from a start date."""
    if calendar_id is None:
        calendar_id = get_default_calendar(account)
    try:
        service = get_calendar_service(account)

        if start:
            start_dt = parse_datetime(start)
            # Make timezone-aware at start of day
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            time_min = start_dt.replace(tzinfo=timezone.utc).isoformat()
        else:
            start_dt = datetime.now(timezone.utc)
            time_min = start_dt.isoformat()
        time_max = (start_dt.replace(tzinfo=timezone.utc) + timedelta(days=days)).isoformat()

        # When filtering, over-fetch then filter client-side
        type_filter = event_type != EventTypeFilter.all
        needs_filtering = with_attendees or attendee or exclude_declined or type_filter
        fetch_limit = min(limit * 5, 250) if needs_filtering else limit

        all_events: list[dict] = []
        page_token = None

        while len(all_events) < limit:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=fetch_limit,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute()

            batch = events_result.get("items", [])

            if needs_filtering:
                for event in batch:
                    event_attendees = event.get("attendees", [])
                    # Filter: exclude declined events
                    if exclude_declined:
                        self_status = get_self_response_status(event)
                        if self_status == "declined":
                            continue
                    # Filter: by event type (meeting/block)
                    if type_filter:
                        evt_type = get_event_type(event)
                        if event_type == EventTypeFilter.meeting and evt_type != "meeting":
                            continue
                        if event_type == EventTypeFilter.block and evt_type != "block":
                            continue
                    # Filter: only events with attendees
                    if with_attendees and not event_attendees:
                        continue
                    # Filter: specific attendee
                    if attendee:
                        if not event_attendees:
                            continue
                        emails = [a.get("email", "").lower() for a in event_attendees]
                        if attendee.lower() not in emails:
                            continue
                    all_events.append(event)
                    if len(all_events) >= limit:
                        break
            else:
                all_events.extend(batch)

            if len(all_events) >= limit:
                all_events = all_events[:limit]
                break

            page_token = events_result.get("nextPageToken")
            if not page_token:
                break

        events = all_events

        if json_output:
            # Add computed event_type to each event
            for evt in events:
                evt["_type"] = get_event_type(evt)
            stdout_console.print_json(json.dumps({
                "calendar_id": calendar_id,
                "count": len(events),
                "filter": {
                    "with_attendees": with_attendees,
                    "attendee": attendee,
                    "exclude_declined": exclude_declined,
                    "type": event_type.value if type_filter else None,
                } if needs_filtering else None,
                "events": events,
            }))
            return

        if not events:
            console.print(f"[yellow]No events in next {days} days.[/yellow]")
            return

        table = Table(title=f"Events (next {days} days)")
        table.add_column("Date/Time", style="dim", width=12)
        table.add_column("Type", style="yellow", width=7)
        table.add_column("Summary", style="cyan", width=23, overflow="ellipsis")
        table.add_column("Meet", style="blue", width=14, overflow="ellipsis")
        table.add_column("Attendees", style="dim", width=26, overflow="ellipsis")

        for event in events:
            meet_link = get_meet_link(event)
            # Show just the meeting code for brevity
            meet_short = meet_link.split("/")[-1] if meet_link else ""
            evt_type = get_event_type(event)
            table.add_row(
                format_event_time(event),
                evt_type,
                event.get("summary", "(no title)"),
                meet_short,
                format_attendees(event),
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    title: Annotated[str, typer.Argument(help="Event title")],
    start: Annotated[str, typer.Argument(help="Start time (ISO format)")],
    end: Annotated[str, typer.Argument(help="End time (ISO format)")],
    calendar_id: Annotated[str | None, typer.Option("--calendar", "-c", help="Calendar ID")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="Description")] = None,
    location: Annotated[str | None, typer.Option("--location", "-l", help="Location")] = None,
    attendees: Annotated[str | None, typer.Option("--attendees", help="Comma-separated attendee emails")] = None,
    meet: Annotated[bool, typer.Option("--meet", "-m", help="Add Google Meet link")] = False,
    timezone_str: Annotated[str | None, typer.Option("--timezone", "-z", help="IANA timezone (default: local)")] = None,
    visibility: Annotated[str | None, typer.Option("--visibility", "-v", help="Visibility: default, public, private")] = None,
    show_as: Annotated[str | None, typer.Option("--show-as", help="Show as: busy, free")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a calendar event."""
    if calendar_id is None:
        calendar_id = get_default_calendar(account)
    details = f"Title: {title}\nStart: {start}\nEnd: {end}"
    if attendees:
        details += f"\nAttendees: {attendees}"
    if meet:
        details += "\nGoogle Meet: Yes"
    if location:
        details += f"\nLocation: {location}"
    if description:
        details += f"\nDescription: {description[:100]}..."
    if visibility:
        details += f"\nVisibility: {visibility}"
    if show_as:
        details += f"\nShow as: {show_as}"

    if not confirm_action("Create event", details, "calendar", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_calendar_service(account)

        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)

        tz = timezone_str or get_local_timezone()
        event_body: dict = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
        if meet:
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"meet-{start_dt.timestamp():.0f}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        if visibility:
            event_body["visibility"] = visibility
        if show_as:
            event_body["transparency"] = "transparent" if show_as == "free" else "opaque"

        # Merge --extra options
        try:
            event_body, api_params = merge_extra(event_body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1 if meet else 0,
            **api_params,
        ).execute()

        meet_link = get_meet_link(event)
        if json_output:
            stdout_console.print_json(json.dumps({
                "id": event.get("id"),
                "summary": event.get("summary"),
                "htmlLink": event.get("htmlLink"),
                "meetLink": meet_link,
            }))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"Event ID: {event.get('id')}")
            console.print(f"Link: {event.get('htmlLink')}")
            if meet_link:
                console.print(f"Meet: {meet_link}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def update(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    calendar_id: Annotated[str | None, typer.Option("--calendar", "-c", help="Calendar ID")] = None,
    title: Annotated[str | None, typer.Option("--title", "-t", help="New title")] = None,
    start: Annotated[str | None, typer.Option("--start", "-s", help="New start time")] = None,
    end: Annotated[str | None, typer.Option("--end", "-e", help="New end time")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
    location: Annotated[str | None, typer.Option("--location", "-l", help="New location")] = None,
    timezone_str: Annotated[str | None, typer.Option("--timezone", "-z", help="IANA timezone for time changes")] = None,
    visibility: Annotated[str | None, typer.Option("--visibility", "-v", help="Visibility: default, public, private")] = None,
    show_as: Annotated[str | None, typer.Option("--show-as", help="Show as: busy, free")] = None,
    attendees: Annotated[str | None, typer.Option("--attendees", help="Comma-separated attendee emails (replaces existing)")] = None,
    add_attendees: Annotated[str | None, typer.Option("--add-attendees", help="Comma-separated attendee emails to add")] = None,
    remove_attendees: Annotated[str | None, typer.Option("--remove-attendees", help="Comma-separated attendee emails to remove")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Update an existing event."""
    if calendar_id is None:
        calendar_id = get_default_calendar(account)
    updates = []
    if title:
        updates.append(f"Title: {title}")
    if start:
        updates.append(f"Start: {start}")
    if end:
        updates.append(f"End: {end}")
    if location:
        updates.append(f"Location: {location}")
    if description:
        updates.append(f"Description: {description[:50]}...")
    if visibility:
        updates.append(f"Visibility: {visibility}")
    if show_as:
        updates.append(f"Show as: {show_as}")
    if attendees:
        updates.append(f"Attendees: {attendees}")
    if add_attendees:
        updates.append(f"Add attendees: {add_attendees}")
    if remove_attendees:
        updates.append(f"Remove attendees: {remove_attendees}")

    if not updates:
        console.print("[red]Error:[/red] No updates specified")
        raise typer.Exit(1)

    details = f"Event ID: {event_id}\n" + "\n".join(updates)
    if not confirm_action("Update event", details, "calendar", skip_confirmation=yes):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        service = get_calendar_service(account)

        # Get existing event
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        # Apply updates
        if title:
            event["summary"] = title
        if start:
            start_dt = parse_datetime(start)
            tz = timezone_str or event.get("start", {}).get("timeZone") or get_local_timezone()
            # Preserve all-day event format if original was all-day and input is date-only
            if "date" in event.get("start", {}) and len(start) == 10:  # YYYY-MM-DD
                event["start"] = {"date": start}
            else:
                event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": tz}
        if end:
            end_dt = parse_datetime(end)
            tz = timezone_str or event.get("end", {}).get("timeZone") or get_local_timezone()
            # Preserve all-day event format if original was all-day and input is date-only
            if "date" in event.get("end", {}) and len(end) == 10:  # YYYY-MM-DD
                event["end"] = {"date": end}
            else:
                event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": tz}
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if visibility:
            event["visibility"] = visibility
        if show_as:
            event["transparency"] = "transparent" if show_as == "free" else "opaque"
        if attendees:
            event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
        if add_attendees:
            existing = event.get("attendees", [])
            new_emails = [e.strip() for e in add_attendees.split(",")]
            existing_emails = {a.get("email", "").lower() for a in existing}
            for email in new_emails:
                if email.lower() not in existing_emails:
                    existing.append({"email": email})
            event["attendees"] = existing
        if remove_attendees:
            existing = event.get("attendees", [])
            remove_emails = {e.strip().lower() for e in remove_attendees.split(",")}
            event["attendees"] = [
                a for a in existing
                if a.get("email", "").lower() not in remove_emails
            ]

        # Merge --extra options
        try:
            event, api_params = merge_extra(event, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        updated = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": updated.get("id"),
                "summary": updated.get("summary"),
                "updated": updated.get("updated"),
            }))
        else:
            console.print(f"[green]Updated:[/green] {updated.get('summary')}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def delete(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    calendar_id: Annotated[str | None, typer.Option("--calendar", "-c", help="Calendar ID")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete an event."""
    if calendar_id is None:
        calendar_id = get_default_calendar(account)
    try:
        service = get_calendar_service(account)

        # Get event details for confirmation
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        details = f"Event: {event.get('summary', '(no title)')}\nID: {event_id}"
        if not confirm_action("Delete event", details, "calendar", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "deleted": True,
                "id": event_id,
                "summary": event.get("summary"),
            }))
        else:
            console.print(f"[green]Deleted:[/green] {event.get('summary')}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def rsvp(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    response: Annotated[ResponseStatus, typer.Argument(help="Response: accepted, declined, tentative")],
    calendar_id: Annotated[str | None, typer.Option("--calendar", "-c", help="Calendar ID")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Set RSVP response for an event (accept, decline, tentative)."""
    if calendar_id is None:
        calendar_id = get_default_calendar(account)
    try:
        service = get_calendar_service(account)

        # Get event details
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        # Find self in attendees
        attendees = event.get("attendees", [])
        self_attendee = None
        self_index = -1
        for i, attendee in enumerate(attendees):
            if attendee.get("self"):
                self_attendee = attendee
                self_index = i
                break

        # Edge case: organizer without attendee entry
        if self_attendee is None:
            # Check if we're the organizer
            organizer = event.get("organizer", {})
            if organizer.get("self"):
                # Add self as attendee with response
                active = get_active_account()
                self_attendee = {
                    "email": active or organizer.get("email", ""),
                    "self": True,
                    "responseStatus": response.value,
                }
                attendees.append(self_attendee)
                self_index = len(attendees) - 1
            else:
                console.print("[red]Error:[/red] You are not an attendee of this event")
                raise typer.Exit(1)

        current_status = self_attendee.get("responseStatus", "needsAction")
        details = f"Event: {event.get('summary', '(no title)')}\nCurrent: {current_status}\nNew: {response.value}"
        if not confirm_action("Update RSVP", details, "calendar", skip_confirmation=yes):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        # Update response status
        attendees[self_index]["responseStatus"] = response.value
        event["attendees"] = attendees

        updated = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "id": updated.get("id"),
                "summary": updated.get("summary"),
                "responseStatus": response.value,
                "previous": current_status,
            }))
        else:
            console.print(f"[green]RSVP updated:[/green] {event.get('summary')} → {response.value}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("calendars")
def list_calendars(
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List available calendars."""
    try:
        service = get_calendar_service(account)
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "count": len(calendars),
                "calendars": calendars,
            }))
            return

        if not calendars:
            console.print("[yellow]No calendars found.[/yellow]")
            return

        table = Table(title="Calendars")
        table.add_column("Name", style="cyan", overflow="fold")
        table.add_column("ID", style="dim", overflow="fold")
        table.add_column("Primary", style="yellow")

        for cal in calendars:
            table.add_row(
                cal.get("summary", ""),
                cal.get("id", ""),
                "*" if cal.get("primary") else "",
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
