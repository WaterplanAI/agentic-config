# Sheets Operation Prompts

Common prompts for Google Sheets operations via the gsuite skill.

## Read Data

```
Read data from spreadsheet {SPREADSHEET_ID} range {RANGE}

Execute:
uv run core/skills/gsuite/tools/sheets.py read {SPREADSHEET_ID} "{RANGE}" --json
```

## Write Single Value

```
Write "{VALUE}" to cell {CELL} in spreadsheet {SPREADSHEET_ID}

Execute:
uv run core/skills/gsuite/tools/sheets.py write {SPREADSHEET_ID} "{CELL}" "{VALUE}"
```

## Write Row

```
Write row [{VALUES}] to spreadsheet {SPREADSHEET_ID} at {RANGE}

Execute:
uv run core/skills/gsuite/tools/sheets.py write {SPREADSHEET_ID} "{RANGE}" '[{VALUES}]'
```

## Append Row

```
Append row [{VALUES}] to sheet {SHEET_NAME} in spreadsheet {SPREADSHEET_ID}

Execute:
uv run core/skills/gsuite/tools/sheets.py append {SPREADSHEET_ID} "{SHEET_NAME}" '[{VALUES}]'
```

## Create Spreadsheet

```
Create a new spreadsheet titled "{TITLE}"

Execute:
uv run core/skills/gsuite/tools/sheets.py create "{TITLE}" --json
```

## Common Patterns

### Bulk Data Import

1. Read source data
2. Transform to 2D array format
3. Write to target range:
   ```bash
   uv run sheets.py write {ID} "Sheet1!A1" '[[row1], [row2], ...]'
   ```

### Data Export

1. Read full sheet:
   ```bash
   uv run sheets.py read {ID} "Sheet1" --json
   ```
2. Parse JSON output for downstream processing
