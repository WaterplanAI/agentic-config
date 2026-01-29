# Sheets Cookbook

Reference for `sheets.py` operations.

## Sheet ID vs Title

- **Sheet ID**: Numeric identifier (e.g., `0`, `1234567890`). Required for rename/delete operations.
- **Sheet Title**: Human-readable name (e.g., "Sheet1", "Data"). Used in range notation.

Get sheet IDs via `list-sheets`:
```bash
uv run sheets.py list-sheets <spreadsheet_id>
```

## Range Notation

| Pattern | Description |
|---------|-------------|
| `A1` | Single cell |
| `A1:D10` | Range on first sheet |
| `Sheet1!A1:D10` | Range on named sheet |
| `'My Sheet'!A1:B5` | Sheet name with spaces (quote it) |
| `A:A` | Entire column A |
| `1:1` | Entire row 1 |

## Sheet Management

### List Sheets
```bash
uv run sheets.py list-sheets <spreadsheet_id>
uv run sheets.py list-sheets <spreadsheet_id> --json
```

### Add Sheet
```bash
# Basic
uv run sheets.py add-sheet <spreadsheet_id> "New Tab" --yes

# At specific position
uv run sheets.py add-sheet <spreadsheet_id> "First Tab" --index 0 --yes

# With custom grid size
uv run sheets.py add-sheet <spreadsheet_id> "Small Grid" --yes \
  --extra '{"gridProperties": {"rowCount": 100, "columnCount": 10}}'

# With tab color (RGB 0-1 range)
uv run sheets.py add-sheet <spreadsheet_id> "Colored Tab" --yes \
  --extra '{"tabColorStyle": {"rgbColor": {"red": 0.2, "green": 0.6, "blue": 0.9}}}'
```

### Rename Sheet
```bash
# Basic rename
uv run sheets.py rename-sheet <spreadsheet_id> <sheet_id> "New Name"

# Rename with tab color change
uv run sheets.py rename-sheet <spreadsheet_id> <sheet_id> "Renamed" \
  --extra '{"tabColorStyle": {"rgbColor": {"red": 1, "green": 0.5, "blue": 0}}}'
```

### Delete Sheet
```bash
# With confirmation prompt
uv run sheets.py delete-sheet <spreadsheet_id> <sheet_id>

# Skip confirmation
uv run sheets.py delete-sheet <spreadsheet_id> <sheet_id> --yes
```

## Read/Write Operations

### Read Range
```bash
uv run sheets.py read <spreadsheet_id> "Sheet1!A1:D10"
uv run sheets.py read <spreadsheet_id> "A1:B5" --json
```

### Write Values
```bash
# Single value
uv run sheets.py write <spreadsheet_id> "A1" "Hello"

# Row of values
uv run sheets.py write <spreadsheet_id> "A1" '["a", "b", "c"]'

# Grid of values
uv run sheets.py write <spreadsheet_id> "A1" '[["a", "b"], ["c", "d"]]'
```

### Append Rows
```bash
# Single row
uv run sheets.py append <spreadsheet_id> "Sheet1" '["value1", "value2"]'

# Multiple rows
uv run sheets.py append <spreadsheet_id> "Sheet1" '[["row1a", "row1b"], ["row2a", "row2b"]]'
```

## --extra Parameter

Extended properties via JSON:

### Grid Properties (add-sheet)
```json
{"gridProperties": {"rowCount": 500, "columnCount": 26, "frozenRowCount": 1}}
```

### Tab Color (add-sheet, rename-sheet)
```json
{"tabColorStyle": {"rgbColor": {"red": 0.8, "green": 0.2, "blue": 0.2}}}
```

Or use theme colors:
```json
{"tabColorStyle": {"themeColor": "ACCENT1"}}
```

Theme colors: `TEXT`, `BACKGROUND`, `ACCENT1` through `ACCENT6`, `LINK`
