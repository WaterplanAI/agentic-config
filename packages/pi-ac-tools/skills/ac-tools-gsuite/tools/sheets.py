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
"""Google Sheets CLI for read/write operations."""
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

app = typer.Typer(help="Google Sheets CLI operations.")
console = Console(stderr=True)
stdout_console = Console()


def get_sheets_service(account: str | None = None):
    """Get authenticated Sheets API service."""
    creds = get_credentials(account)
    return build("sheets", "v4", credentials=creds)


@app.command()
def read(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    range_notation: Annotated[str, typer.Argument(help="Range (e.g., 'Sheet1!A1:D10')")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Read values from a spreadsheet range."""
    try:
        service = get_sheets_service(account)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
        ).execute()

        values = result.get("values", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "range": range_notation,
                "values": values,
                "rows": len(values),
            }))
            return

        if not values:
            console.print("[yellow]No data found.[/yellow]")
            return

        # Display as table
        table = Table(title=f"{spreadsheet_id} - {range_notation}")
        if values:
            # Use first row as headers or generate column letters
            num_cols = max((len(row) for row in values), default=1)
            for i in range(num_cols):
                table.add_column(f"Col {i+1}", overflow="fold")

            for row in values:
                # Pad row to match column count
                padded = row + [""] * (num_cols - len(row))
                table.add_row(*[str(cell) for cell in padded])

        console.print(table)
        console.print(f"\n[dim]{len(values)} rows[/dim]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def write(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    range_notation: Annotated[str, typer.Argument(help="Range (e.g., 'Sheet1!A1')")],
    value: Annotated[str, typer.Argument(help="Value to write (string or JSON array)")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Write value(s) to a spreadsheet range."""
    try:
        # Parse value - could be single value or JSON array
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], list):
                    values = parsed  # 2D array
                else:
                    values = [parsed]  # 1D array -> single row
            else:
                values = [[str(parsed)]]
        except json.JSONDecodeError:
            values = [[value]]  # Single string value

        # Merge --extra options
        body: dict = {"values": values}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body=body,
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "range": result.get("updatedRange"),
                "updated_cells": result.get("updatedCells"),
                "updated_rows": result.get("updatedRows"),
            }))
        else:
            console.print(f"[green]Updated {result.get('updatedCells')} cells[/green]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def append(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    sheet_name: Annotated[str, typer.Argument(help="Sheet name")],
    values: Annotated[str, typer.Argument(help="JSON array of values to append")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Append row(s) to a sheet."""
    try:
        parsed = json.loads(values)
        if not isinstance(parsed, list):
            parsed = [parsed]
        if parsed and not isinstance(parsed[0], list):
            parsed = [parsed]  # Wrap single row

        # Merge --extra options
        body: dict = {"values": parsed}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
            **api_params,
        ).execute()

        updates = result.get("updates", {})
        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "updated_range": updates.get("updatedRange"),
                "updated_rows": updates.get("updatedRows"),
            }))
        else:
            console.print(f"[green]Appended {updates.get('updatedRows')} rows[/green]")

    except json.JSONDecodeError:
        console.print('[red]Invalid data format.[/red] Expected JSON array like ["val1", "val2"]')
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    title: Annotated[str, typer.Argument(help="Spreadsheet title")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new spreadsheet."""
    try:
        # Merge --extra options
        body: dict = {"properties": {"title": title}}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        spreadsheet = service.spreadsheets().create(
            body=body,
            **api_params,
        ).execute()

        spreadsheet_id = spreadsheet.get("spreadsheetId")
        url = spreadsheet.get("spreadsheetUrl")

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "title": title,
                "url": url,
            }))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"ID: {spreadsheet_id}")
            console.print(f"URL: {url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("list-sheets")
def list_sheets(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all sheets (tabs) in a spreadsheet."""
    try:
        service = get_sheets_service(account)
        result = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties",
        ).execute()

        sheets = result.get("sheets", [])

        if json_output:
            sheets_data = []
            for sheet in sheets:
                props = sheet.get("properties", {})
                sheets_data.append({
                    "sheet_id": props.get("sheetId"),
                    "title": props.get("title"),
                    "index": props.get("index"),
                    "rows": props.get("gridProperties", {}).get("rowCount"),
                    "cols": props.get("gridProperties", {}).get("columnCount"),
                })
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "sheets": sheets_data,
            }))
            return

        if not sheets:
            console.print("[yellow]No sheets found.[/yellow]")
            return

        table = Table(title=f"Sheets in {spreadsheet_id}")
        table.add_column("Index", style="dim")
        table.add_column("Title")
        table.add_column("Sheet ID")
        table.add_column("Size")

        for sheet in sheets:
            props = sheet.get("properties", {})
            grid = props.get("gridProperties", {})
            rows = grid.get("rowCount", 0)
            cols = grid.get("columnCount", 0)
            table.add_row(
                str(props.get("index", "")),
                props.get("title", ""),
                str(props.get("sheetId", "")),
                f"{rows} x {cols}",
            )

        console.print(table)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("add-sheet")
def add_sheet(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    title: Annotated[str, typer.Argument(help="New sheet title")],
    index: Annotated[int | None, typer.Option("--index", "-i", help="Position index for new sheet")] = None,
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: tabColor, gridProperties")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add a new sheet (tab) to a spreadsheet."""
    try:
        # Confirmation
        details = f"Title: {title}"
        if index is not None:
            details += f"\nIndex: {index}"
        if not confirm_action("Add sheet", details, "sheets", skip_confirmation=yes):
            console.print("[yellow]Aborted[/yellow]")
            raise typer.Exit(0)

        # Build sheet properties
        sheet_props: dict = {"title": title}
        if index is not None:
            sheet_props["index"] = index

        # Merge --extra into sheet properties
        try:
            sheet_props, api_params = merge_extra(sheet_props, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        request = {"addSheet": {"properties": sheet_props}}

        service = get_sheets_service(account)
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [request]},
            **api_params,
        ).execute()

        # Extract new sheet info from response
        replies = result.get("replies", [{}])
        new_sheet = replies[0].get("addSheet", {}).get("properties", {})
        sheet_id = new_sheet.get("sheetId")
        new_title = new_sheet.get("title", title)
        new_index = new_sheet.get("index")

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "title": new_title,
                "index": new_index,
            }))
        else:
            console.print(f"[green]Created sheet:[/green] {new_title}")
            console.print(f"Sheet ID: {sheet_id}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("rename-sheet")
def rename_sheet(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    sheet_id: Annotated[int, typer.Argument(help="Sheet ID (numeric)")],
    new_title: Annotated[str, typer.Argument(help="New sheet title")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional properties (tabColor)")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Rename a sheet (tab) in a spreadsheet."""
    try:
        # Build properties with title
        props: dict = {"sheetId": sheet_id, "title": new_title}
        fields = ["title"]

        # Merge --extra
        try:
            props, api_params = merge_extra(props, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        # Add extra fields to update mask
        if "tabColor" in props or "tabColorStyle" in props:
            fields.append("tabColorStyle")

        request = {
            "updateSheetProperties": {
                "properties": props,
                "fields": ",".join(fields),
            }
        }

        service = get_sheets_service(account)
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [request]},
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "title": new_title,
            }))
        else:
            console.print(f"[green]Renamed sheet {sheet_id} to:[/green] {new_title}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command("delete-sheet")
def delete_sheet(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    sheet_id: Annotated[int, typer.Argument(help="Sheet ID (numeric)")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a sheet (tab) from a spreadsheet."""
    try:
        service = get_sheets_service(account)

        # Fetch sheet title for confirmation message
        sheet_title = f"Sheet {sheet_id}"
        try:
            meta = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets.properties",
            ).execute()
            for s in meta.get("sheets", []):
                if s.get("properties", {}).get("sheetId") == sheet_id:
                    sheet_title = s["properties"].get("title", sheet_title)
                    break
        except HttpError:
            pass  # Use default title if lookup fails

        # Confirmation
        details = f"Sheet: {sheet_title}\nSheet ID: {sheet_id}"
        if not confirm_action("Delete sheet", details, "sheets", skip_confirmation=yes):
            console.print("[yellow]Aborted[/yellow]")
            raise typer.Exit(0)

        request = {"deleteSheet": {"sheetId": sheet_id}}
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [request]},
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "title": sheet_title,
                "deleted": True,
            }))
        else:
            console.print(f"[green]Deleted sheet:[/green] {sheet_title}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
