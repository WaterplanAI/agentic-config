#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "dateparser>=1.2.0",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""Date/time utility for parsing relative expressions to ISO format."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Annotated

import dateparser
import typer
from rich.console import Console

app = typer.Typer(help="Date/time parsing utility for natural language expressions.")
console = Console(stderr=True)
stdout_console = Console()

# Dateparser settings: future-biased for scheduling
DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
}


def get_local_timezone() -> str:
    """Get local IANA timezone name (e.g., 'America/New_York')."""
    tz = os.environ.get("TZ")
    if tz and "/" in tz:
        return tz
    localtime = "/etc/localtime"
    if os.path.islink(localtime):
        link = os.readlink(localtime)
        if "zoneinfo/" in link:
            return link.split("zoneinfo/")[-1]
    return "UTC"


def parse_end_time(start: datetime, duration: str) -> datetime:
    """Calculate end time by parsing duration relative to start.

    Supported formats (via dateparser):
    - "1 hour", "1h", "30 minutes", "30m", "1.5 hours"
    - "2 weeks", "3 months", "45 days"
    - "1h 30m", "1 hour 30 minutes" (space-separated compound)
    - NOT supported: "1h30m" (no space), "1.5 months" (fractional months)
    """
    # Prepend "in " if not present for dateparser
    if not duration.lower().startswith("in "):
        duration = f"in {duration}"

    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": start,
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    result = dateparser.parse(duration, settings=settings)  # type: ignore[arg-type]
    if result is None:
        raise ValueError(f"Unable to parse duration: {duration}")
    return result


def parse_relative_datetime(
    expression: str,
    reference: datetime | None = None,
) -> datetime:
    """Parse a relative date/time expression using dateparser.

    Examples:
    - "mon 3pm" -> next Monday at 3pm (future-biased)
    - "tomorrow 2pm" -> tomorrow at 2pm
    - "friday 10:30am" -> next Friday at 10:30am
    - "in 3 days" -> 3 days from now

    Args:
        expression: Natural language date/time expression
        reference: Reference datetime (defaults to now)

    Returns:
        Parsed datetime
    """
    if reference is None:
        reference = datetime.now()

    settings = {
        **DATEPARSER_SETTINGS,
        "RELATIVE_BASE": reference,
    }

    result = dateparser.parse(expression, settings=settings)  # type: ignore[arg-type]

    if result is None:
        raise ValueError(f"Unable to parse date expression: {expression}")

    return result


@app.command()
def parse(
    expression: Annotated[str, typer.Argument(help="Date/time expression (e.g., 'mon 3pm', 'tomorrow 2pm')")],
    duration: Annotated[str | None, typer.Option("--duration", "-d", help="Duration (e.g., '1 hour', '30 minutes')")] = None,
    now: Annotated[str | None, typer.Option("--now", "-n", help="Reference time (ISO format, for testing)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Parse relative date/time expression to ISO format.

    Examples:
        gdate.py parse "mon 3pm" --json
        gdate.py parse "tomorrow 2pm" --duration "1 hour" --json
        gdate.py parse "friday 10am" --duration "30 minutes"
    """
    try:
        # Parse reference time
        reference = datetime.now()
        if now:
            parsed_now = dateparser.parse(now)
            if parsed_now is None:
                raise ValueError(f"Unable to parse reference time: {now}")
            reference = parsed_now

        # Parse the expression
        start_dt = parse_relative_datetime(expression, reference)

        # Calculate end time if duration specified
        end_dt = None
        if duration:
            end_dt = parse_end_time(start_dt, duration)

        timezone = get_local_timezone()

        if json_output:
            result = {
                "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%dT%H:%M:%S") if end_dt else None,
                "timezone": timezone,
                "reference": reference.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            stdout_console.print_json(json.dumps(result))
        else:
            console.print(f"[cyan]Start:[/cyan] {start_dt.strftime('%Y-%m-%dT%H:%M:%S')}")
            if end_dt:
                console.print(f"[cyan]End:[/cyan] {end_dt.strftime('%Y-%m-%dT%H:%M:%S')}")
            console.print(f"[dim]Timezone: {timezone}[/dim]")
            console.print(f"[dim]Reference: {reference.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def now(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show current time information.

    Displays current datetime, timezone, and day of week.
    """
    current = datetime.now()
    timezone = get_local_timezone()

    if json_output:
        result = {
            "datetime": current.strftime("%Y-%m-%dT%H:%M:%S"),
            "date": current.strftime("%Y-%m-%d"),
            "time": current.strftime("%H:%M:%S"),
            "weekday": current.strftime("%A").lower(),
            "timezone": timezone,
        }
        stdout_console.print_json(json.dumps(result))
    else:
        console.print(f"[cyan]Now:[/cyan] {current.strftime('%Y-%m-%dT%H:%M:%S')}")
        console.print(f"[cyan]Day:[/cyan] {current.strftime('%A')}")
        console.print(f"[dim]Timezone: {timezone}[/dim]")


if __name__ == "__main__":
    app()
