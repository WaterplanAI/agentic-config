#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
#   "mistune>=3.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""Markdown to Google Docs converter with native table support.

Two-pass approach:
1. Insert text content with placeholders for tables
2. Insert native tables in reverse order (to maintain indices)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console

# Import auth module for credential loading
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402

# Type alias for mistune tokens
MistuneToken = dict[str, Any]

# Heading level to Google Docs named style mapping
HEADING_STYLES = {
    1: "HEADING_1",
    2: "HEADING_2",
    3: "HEADING_3",
    4: "HEADING_4",
    5: "HEADING_5",
    6: "HEADING_6",
}

# Placeholder for table position (single character to track index)
TABLE_PLACEHOLDER = "\n"


@dataclass
class CellData:
    """Cell content with formatting."""

    row: int
    col: int
    text: str
    is_header: bool
    format_actions: list[tuple[int, int, str, dict[str, Any]]]


@dataclass
class TableDef:
    """Table definition with position and cell data."""

    insert_index: int  # Where to insert in document
    rows: int
    cols: int
    cells: list[CellData]


@dataclass
class ParseResult:
    """Result of markdown parsing."""

    plain_text: str
    format_actions: list[tuple[int, int, str, dict[str, Any]]]
    tables: list[TableDef]


def process_cell_inline(
    tokens: list[MistuneToken],
) -> tuple[str, list[tuple[int, int, str, dict[str, Any]]]]:
    """Process inline tokens for a table cell, returning text and format actions.

    Similar to process_inline but returns format_actions instead of appending to global list.
    Position offsets are relative to cell start (0-based).
    """
    format_actions: list[tuple[int, int, str, dict[str, Any]]] = []

    def process_tokens(toks: list[MistuneToken], base_pos: int) -> tuple[str, int]:
        text = ""
        pos = base_pos
        for token in toks:
            token_type = token["type"]
            if token_type == "text":
                text += token["raw"]
                pos += len(token["raw"])
            elif token_type == "strong":
                inner_text, inner_pos = process_tokens(token["children"], pos)
                format_actions.append((pos, pos + len(inner_text), "bold", {}))
                text += inner_text
                pos = inner_pos
            elif token_type == "emphasis":
                inner_text, inner_pos = process_tokens(token["children"], pos)
                format_actions.append((pos, pos + len(inner_text), "italic", {}))
                text += inner_text
                pos = inner_pos
            elif token_type == "link":
                inner_text, inner_pos = process_tokens(token["children"], pos)
                format_actions.append(
                    (pos, pos + len(inner_text), "link", {"url": token["attrs"]["url"]})
                )
                text += inner_text
                pos = inner_pos
            elif token_type == "codespan":
                code_text = token["raw"]
                format_actions.append((pos, pos + len(code_text), "code", {}))
                text += code_text
                pos += len(code_text)
            elif token_type == "softbreak":
                text += " "
                pos += 1
            elif token_type == "linebreak":
                text += "\n"
                pos += 1
        return text, pos

    result_text, _ = process_tokens(tokens, 0)
    return result_text, format_actions


def parse_table_token(token: MistuneToken, insert_index: int) -> TableDef:
    """Parse a table token into TableDef."""
    cells: list[CellData] = []
    row_idx = 0
    num_cols = 0

    for child in token.get("children", []):
        if child["type"] == "table_head":
            col_idx = 0
            for cell_token in child.get("children", []):
                if cell_token["type"] == "table_cell":
                    text, fmt_actions = process_cell_inline(
                        cell_token.get("children", [])
                    )
                    cells.append(
                        CellData(row_idx, col_idx, text, True, fmt_actions)
                    )
                    col_idx += 1
            num_cols = col_idx
            row_idx += 1

        elif child["type"] == "table_body":
            for row_token in child.get("children", []):
                if row_token["type"] == "table_row":
                    col_idx = 0
                    for cell_token in row_token.get("children", []):
                        if cell_token["type"] == "table_cell":
                            text, fmt_actions = process_cell_inline(
                                cell_token.get("children", [])
                            )
                            cells.append(
                                CellData(row_idx, col_idx, text, False, fmt_actions)
                            )
                            col_idx += 1
                    row_idx += 1

    return TableDef(
        insert_index=insert_index,
        rows=row_idx,
        cols=num_cols,
        cells=cells,
    )


def parse_markdown(markdown_text: str) -> ParseResult:
    """Parse markdown and return plain text, formatting actions, and table definitions.

    Tables are replaced with placeholder newlines; actual tables inserted in pass 2.
    """
    import mistune

    format_actions: list[tuple[int, int, str, dict[str, Any]]] = []
    tables: list[TableDef] = []
    plain_parts: list[str] = []
    current_pos = 1  # Google Docs index starts at 1

    def process_inline(tokens: list[MistuneToken], base_pos: int) -> tuple[str, int]:
        """Process inline tokens, return text and update position."""
        text = ""
        pos = base_pos
        for token in tokens:
            token_type = token["type"]
            if token_type == "text":
                text += token["raw"]
                pos += len(token["raw"])
            elif token_type == "strong":
                inner_text, inner_pos = process_inline(token["children"], pos)
                format_actions.append((pos, pos + len(inner_text), "bold", {}))
                text += inner_text
                pos = inner_pos
            elif token_type == "emphasis":
                inner_text, inner_pos = process_inline(token["children"], pos)
                format_actions.append((pos, pos + len(inner_text), "italic", {}))
                text += inner_text
                pos = inner_pos
            elif token_type == "link":
                inner_text, inner_pos = process_inline(token["children"], pos)
                format_actions.append(
                    (pos, pos + len(inner_text), "link", {"url": token["attrs"]["url"]})
                )
                text += inner_text
                pos = inner_pos
            elif token_type == "codespan":
                code_text = token["raw"]
                format_actions.append((pos, pos + len(code_text), "code", {}))
                text += code_text
                pos += len(code_text)
            elif token_type == "softbreak":
                text += " "
                pos += 1
            elif token_type == "linebreak":
                text += "\n"
                pos += 1
        return text, pos

    # Parse markdown with table plugin
    md = mistune.create_markdown(renderer=None, plugins=["table", "url"])
    tokens = cast(list[MistuneToken], md(markdown_text))

    for token in tokens:
        token_type = token["type"]

        if token_type == "heading":
            level = token["attrs"]["level"]
            children = token["children"]
            heading_text, _ = process_inline(children, current_pos)
            heading_text += "\n"

            end_pos = current_pos + len(heading_text) - 1
            if level in HEADING_STYLES:
                format_actions.append(
                    (current_pos, end_pos, "heading", {"level": level})
                )

            plain_parts.append(heading_text)
            current_pos += len(heading_text)

        elif token_type == "paragraph":
            children = token["children"]
            para_text, _ = process_inline(children, current_pos)
            para_text += "\n\n"
            plain_parts.append(para_text)
            current_pos += len(para_text)

        elif token_type == "list":
            is_ordered = token["attrs"].get("ordered", False)
            items = token["children"]
            list_start = current_pos
            # Track nested item ranges: (start, end, nesting_level)
            nested_ranges: list[tuple[int, int, int]] = []

            def process_list_item(item: MistuneToken, indent: int = 0) -> None:
                """Process a list item, recursively handling nested lists."""
                nonlocal current_pos
                if item["type"] != "list_item":
                    return

                item_children = item["children"]
                item_text = ""
                item_start = current_pos

                for child in item_children:
                    if child["type"] in ("paragraph", "block_text"):
                        text, _ = process_inline(
                            child["children"], current_pos + len(item_text)
                        )
                        item_text += text
                    elif child["type"] == "list":
                        # First, close the current item if we have text
                        if item_text:
                            item_text += "\n"
                            plain_parts.append(item_text)
                            if indent > 0:
                                nested_ranges.append(
                                    (item_start, current_pos + len(item_text), indent)
                                )
                            current_pos += len(item_text)
                            item_text = ""
                        # Process nested list items
                        nested_items = child["children"]
                        for nested_item in nested_items:
                            process_list_item(nested_item, indent + 1)

                # Append remaining text if any
                if item_text:
                    item_text += "\n"
                    plain_parts.append(item_text)
                    if indent > 0:
                        nested_ranges.append(
                            (item_start, current_pos + len(item_text), indent)
                        )
                    current_pos += len(item_text)

            for item in items:
                process_list_item(item)

            list_end = current_pos
            format_actions.append(
                (list_start, list_end, "list", {"ordered": is_ordered, "nested": nested_ranges})
            )
            plain_parts.append("\n")
            current_pos += 1

        elif token_type == "thematic_break":
            hr_text = "\n"
            plain_parts.append(hr_text)
            current_pos += len(hr_text)

        elif token_type == "code_block":
            code = token.get("raw", token.get("text", ""))
            code_text = code + "\n"
            format_actions.append(
                (current_pos, current_pos + len(code_text) - 1, "code_block", {})
            )
            plain_parts.append(code_text)
            current_pos += len(code_text)

        elif token_type == "blank_line":
            pass

        elif token_type == "table":
            # Store table definition with current position
            table_def = parse_table_token(token, current_pos)
            tables.append(table_def)
            # Insert placeholder (just a newline for now, table goes before it)
            plain_parts.append(TABLE_PLACEHOLDER)
            current_pos += len(TABLE_PLACEHOLDER)

    plain_text = "".join(plain_parts)

    return ParseResult(
        plain_text=plain_text,
        format_actions=format_actions,
        tables=tables,
    )


def build_format_requests(
    format_actions: list[tuple[int, int, str, dict[str, Any]]], offset: int = 0
) -> list[dict[str, Any]]:
    """Build Google Docs API formatting requests from actions."""
    requests: list[dict[str, Any]] = []

    for start, end, style_type, style_data in format_actions:
        start += offset
        end += offset

        if style_type == "heading":
            level = style_data["level"]
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": HEADING_STYLES[level]},
                        "fields": "namedStyleType",
                    }
                }
            )
        elif style_type == "bold":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                }
            )
        elif style_type == "italic":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"italic": True},
                        "fields": "italic",
                    }
                }
            )
        elif style_type == "link":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"link": {"url": style_data["url"]}},
                        "fields": "link",
                    }
                }
            )
        elif style_type == "code":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                            "backgroundColor": {
                                "color": {
                                    "rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}
                                }
                            },
                        },
                        "fields": "weightedFontFamily,backgroundColor",
                    }
                }
            )
        elif style_type == "code_block":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                            "fontSize": {"magnitude": 10, "unit": "PT"},
                        },
                        "fields": "weightedFontFamily,fontSize",
                    }
                }
            )
        elif style_type == "list":
            # Apply indentation BEFORE createParagraphBullets
            # Google Docs interprets pre-indented paragraphs as nesting levels
            # 36 points = 0.5 inch per nesting level
            for nest_start, nest_end, level in style_data.get("nested", []):
                indent_pts = 36 * level
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": nest_start + offset,
                                "endIndex": nest_end + offset,
                            },
                            "paragraphStyle": {
                                "indentStart": {"magnitude": indent_pts, "unit": "PT"},
                                "indentFirstLine": {
                                    "magnitude": indent_pts,
                                    "unit": "PT",
                                },
                            },
                            "fields": "indentStart,indentFirstLine",
                        }
                    }
                )
            # Now apply bullets - interprets indentation as nesting
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": start, "endIndex": end},
                        "bulletPreset": "NUMBERED_DECIMAL_NESTED"
                        if style_data.get("ordered")
                        else "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
            )

    return requests


def find_table_cell_indices(doc: dict[str, Any], table_start_index: int) -> dict[tuple[int, int], int]:
    """Find cell paragraph start indices from document structure.

    Returns dict mapping (row, col) -> paragraph start index.
    """
    cell_indices: dict[tuple[int, int], int] = {}
    body = doc.get("body", {})
    content = body.get("content", [])

    # Find the table element
    for element in content:
        start_idx = element.get("startIndex", 0)
        if start_idx >= table_start_index and "table" in element:
            table = element["table"]
            for row_idx, row in enumerate(table.get("tableRows", [])):
                for col_idx, cell in enumerate(row.get("tableCells", [])):
                    # Get the first paragraph's start index in this cell
                    cell_content = cell.get("content", [])
                    if cell_content:
                        first_para = cell_content[0]
                        para_start = first_para.get("startIndex", 0)
                        cell_indices[(row_idx, col_idx)] = para_start
            return cell_indices

    return cell_indices


def insert_native_table(
    service: "Any", doc_id: str, table: TableDef, base_offset: int
) -> int:
    """Insert a native table and populate cells.

    Args:
        service: Google Docs API service
        doc_id: Document ID
        table: Table definition
        base_offset: Offset to add to table.insert_index

    Returns:
        Index offset caused by this table insertion
    """
    actual_index = table.insert_index + base_offset

    # Step 1: Insert table structure
    service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "insertTable": {
                        "rows": table.rows,
                        "columns": table.cols,
                        "location": {"index": actual_index},
                    }
                }
            ]
        },
    ).execute()

    # Step 2: Get document to find actual cell indices
    doc = service.documents().get(documentId=doc_id).execute()
    cell_indices = find_table_cell_indices(doc, actual_index)

    if not cell_indices:
        return 0  # Table structure not found, skip cell population

    # Step 3: Build cell content and formatting requests
    # Process cells in REVERSE order (bottom-right to top-left) to maintain indices
    cell_requests: list[dict[str, Any]] = []
    sorted_cells = sorted(table.cells, key=lambda c: (c.row, c.col), reverse=True)

    for cell in sorted_cells:
        cell_start = cell_indices.get((cell.row, cell.col))
        if cell_start is None:
            continue

        if cell.text:
            cell_requests.append(
                {"insertText": {"location": {"index": cell_start}, "text": cell.text}}
            )
            # Apply header bold formatting
            if cell.is_header:
                cell_requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": cell_start,
                                "endIndex": cell_start + len(cell.text),
                            },
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    }
                )
            # Apply inline formatting (links, bold, italic, code)
            for start, end, style_type, style_data in cell.format_actions:
                actual_start = cell_start + start
                actual_end = cell_start + end
                if style_type == "link":
                    cell_requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": actual_start,
                                    "endIndex": actual_end,
                                },
                                "textStyle": {"link": {"url": style_data["url"]}},
                                "fields": "link",
                            }
                        }
                    )
                elif style_type == "bold" and not cell.is_header:
                    # Skip if already bold from header
                    cell_requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": actual_start,
                                    "endIndex": actual_end,
                                },
                                "textStyle": {"bold": True},
                                "fields": "bold",
                            }
                        }
                    )
                elif style_type == "italic":
                    cell_requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": actual_start,
                                    "endIndex": actual_end,
                                },
                                "textStyle": {"italic": True},
                                "fields": "italic",
                            }
                        }
                    )
                elif style_type == "code":
                    cell_requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": actual_start,
                                    "endIndex": actual_end,
                                },
                                "textStyle": {
                                    "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                                    "backgroundColor": {
                                        "color": {
                                            "rgbColor": {
                                                "red": 0.95,
                                                "green": 0.95,
                                                "blue": 0.95,
                                            }
                                        }
                                    },
                                },
                                "fields": "weightedFontFamily,backgroundColor",
                            }
                        }
                    )

    if cell_requests:
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": cell_requests}
        ).execute()

    # Calculate index offset: table structure adds significant indices
    # Approximate: header row + overhead + cells
    # This is complex to calculate exactly; we re-query document for accuracy
    return 0  # Caller should re-query for accurate offsets if needed


def convert_markdown_to_docs(
    service: "Any",
    doc_id: str,
    markdown: str,
    start_index: int = 1,
) -> dict[str, Any]:
    """Convert markdown to Google Docs with native tables.

    Two-pass approach:
    1. Insert text content with table placeholders
    2. Insert native tables in reverse order

    Returns:
        dict with conversion stats
    """
    # Parse markdown
    result = parse_markdown(markdown)

    # Pass 1: Insert text content
    requests: list[dict[str, Any]] = [
        {"insertText": {"location": {"index": start_index}, "text": result.plain_text}}
    ]

    # Add formatting requests (adjusted for start_index offset)
    offset = start_index - 1
    format_requests = build_format_requests(result.format_actions, offset)
    requests.extend(format_requests)

    # Execute text insertion and formatting
    service.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()

    # Pass 2: Insert tables in REVERSE order (last table first)
    # This maintains correct indices as each table shifts content
    tables_inserted = 0
    if result.tables:
        # Sort by insert_index descending
        sorted_tables = sorted(result.tables, key=lambda t: t.insert_index, reverse=True)

        for table in sorted_tables:
            insert_native_table(service, doc_id, table, offset)
            tables_inserted += 1

    return {
        "text_length": len(result.plain_text),
        "format_rules": len(format_requests),
        "tables_inserted": tables_inserted,
    }


# CLI Interface
app = typer.Typer(help="Markdown to Google Docs converter with native tables.")
console = Console(stderr=True)
stdout_console = Console()


def get_docs_service(account: str | None = None) -> "Any":
    """Get authenticated Docs API service."""
    creds = get_credentials(account)
    return build("docs", "v1", credentials=creds)


@app.command()
def convert(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    markdown: Annotated[str, typer.Argument(help="Markdown text to convert")],
    index: Annotated[int, typer.Option("--index", help="Insert at index")] = 1,
    append: Annotated[bool, typer.Option("--append", help="Append to end")] = False,
    account: Annotated[
        str | None, typer.Option("--account", "-a", help="Account email")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Convert markdown to Google Docs with native tables."""
    try:
        service = get_docs_service(account)

        # If appending, get document length first
        if append:
            doc = service.documents().get(documentId=doc_id).execute()
            body_content = doc.get("body", {})
            content = body_content.get("content", [])
            if content:
                last_elem = content[-1]
                index = last_elem.get("endIndex", 1) - 1

        stats = convert_markdown_to_docs(service, doc_id, markdown, index)

        if json_output:
            stdout_console.print_json(
                json.dumps(
                    {
                        "doc_id": doc_id,
                        "index": index,
                        **stats,
                    }
                )
            )
        else:
            msg = f"[green]Inserted {stats['text_length']} characters at index {index}[/green]"
            if stats["format_rules"]:
                msg += f" [dim](+{stats['format_rules']} formatting rules)[/dim]"
            if stats["tables_inserted"]:
                msg += f" [dim](+{stats['tables_inserted']} native tables)[/dim]"
            console.print(msg)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def from_file(
    doc_id: Annotated[str, typer.Argument(help="Document ID")],
    file_path: Annotated[Path, typer.Argument(help="Markdown file path")],
    index: Annotated[int, typer.Option("--index", help="Insert at index")] = 1,
    append: Annotated[bool, typer.Option("--append", help="Append to end")] = False,
    account: Annotated[
        str | None, typer.Option("--account", "-a", help="Account email")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Convert markdown file to Google Docs with native tables."""
    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    try:
        service = get_docs_service(account)
        markdown = file_path.read_text()

        # If appending, get document length first
        if append:
            doc = service.documents().get(documentId=doc_id).execute()
            body_content = doc.get("body", {})
            content = body_content.get("content", [])
            if content:
                last_elem = content[-1]
                index = last_elem.get("endIndex", 1) - 1

        stats = convert_markdown_to_docs(service, doc_id, markdown, index)

        if json_output:
            stdout_console.print_json(
                json.dumps(
                    {
                        "doc_id": doc_id,
                        "file": str(file_path),
                        "index": index,
                        **stats,
                    }
                )
            )
        else:
            msg = f"[green]Inserted {stats['text_length']} characters from {file_path.name}[/green]"
            if stats["format_rules"]:
                msg += f" [dim](+{stats['format_rules']} formatting rules)[/dim]"
            if stats["tables_inserted"]:
                msg += f" [dim](+{stats['tables_inserted']} native tables)[/dim]"
            console.print(msg)

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
