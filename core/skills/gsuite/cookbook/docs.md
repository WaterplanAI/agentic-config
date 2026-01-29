# Docs Cookbook

Google Docs operations including image insertion.

## Commands Reference

```bash
# Read document
uv run core/skills/gsuite/tools/docs.py read <doc_id>

# Read specific tab
uv run core/skills/gsuite/tools/docs.py read <doc_id> --tab "Tab Name"

# Write text (insert at index)
uv run core/skills/gsuite/tools/docs.py write <doc_id> "Text to insert"

# Write markdown with tables
uv run core/skills/gsuite/tools/docs.py write <doc_id> "# Heading" --markdown

# Append to document
uv run core/skills/gsuite/tools/docs.py write <doc_id> "Appended text" --append

# Create new document
uv run core/skills/gsuite/tools/docs.py create "Document Title"

# Export to PDF
uv run core/skills/gsuite/tools/docs.py export <doc_id> -o output.pdf

# List tabs
uv run core/skills/gsuite/tools/docs.py tabs <doc_id>

# Create tab
uv run core/skills/gsuite/tools/docs.py create-tab <doc_id> "New Tab"

# Rename tab
uv run core/skills/gsuite/tools/docs.py rename-tab <doc_id> <tab_id> "New Name"

# Delete tab
uv run core/skills/gsuite/tools/docs.py delete-tab <doc_id> <tab_id> --yes
```

## Image Insertion

Insert images into Google Docs using `insertInlineImage` via `--extra`.

### Image URI Formats

| Source | URI Format |
|--------|------------|
| Drive file (same account) | `https://drive.google.com/uc?id=<file_id>&export=download` |
| Public URL | Direct HTTPS URL |

**Important:** Drive files must be accessible to the authenticated account. Same-account private files work without sharing.

### Insert Image at Position

```bash
uv run docs.py write <doc_id> "" --extra '{
  "requests": [{
    "insertInlineImage": {
      "uri": "https://drive.google.com/uc?id=<file_id>&export=download",
      "location": {"index": 1}
    }
  }]
}'
```

### Insert Image with Size

```bash
uv run docs.py write <doc_id> "" --extra '{
  "requests": [{
    "insertInlineImage": {
      "uri": "https://drive.google.com/uc?id=<file_id>&export=download",
      "location": {"index": 1},
      "objectSize": {
        "width": {"magnitude": 400, "unit": "PT"},
        "height": {"magnitude": 300, "unit": "PT"}
      }
    }
  }]
}'
```

## Workflow: Mermaid Diagram to Google Doc

Complete workflow for inserting a mermaid diagram:

**Step 1: Render and upload to Drive**
```bash
uv run mermaid.py upload "graph TD; A[Start]-->B[End]" --name flow.png --json
# Output: {"file_id": "1ABC...", "name": "flow.png", ...}
```

**Step 2: Read document to find insertion point**
```bash
uv run docs.py read <doc_id> --json
# Note the character_count or specific index for insertion
```

**Step 3: Insert image**
```bash
uv run docs.py write <doc_id> "" --extra '{
  "requests": [{
    "insertInlineImage": {
      "uri": "https://drive.google.com/uc?id=1ABC...&export=download",
      "location": {"index": 1}
    }
  }]
}'
```

## Combined Operations with --extra

The `--extra` parameter accepts additional batchUpdate requests:

```bash
# Insert text then image
uv run docs.py write <doc_id> "Diagram:" --extra '{
  "requests": [{
    "insertInlineImage": {
      "uri": "https://drive.google.com/uc?id=<file_id>&export=download",
      "location": {"index": 9}
    }
  }]
}'
```

## Tab-Specific Operations

```bash
# Write to specific tab
uv run docs.py write <doc_id> "Content" --tab "Notes"

# Read from specific tab
uv run docs.py read <doc_id> --tab "Notes"
```

## Export Formats

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| PDF | .pdf | application/pdf |
| DOCX | .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| TXT | .txt | text/plain |
| HTML | .html | text/html |
| RTF | .rtf | application/rtf |
| ODT | .odt | application/vnd.oasis.opendocument.text |

## Tips

- Use `--json` for scripting and automation
- The `--markdown` flag converts markdown to native Google Docs formatting including tables
- Images from private Drive files work when the same account owns both the Doc and the image
- No public sharing required for same-account image insertion
