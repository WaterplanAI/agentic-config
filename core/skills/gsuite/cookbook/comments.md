# Comments Cookbook

Comment-review-edit-update loop for Google Docs, Sheets, and Slides.

## Convention

- `@ac` = agent-directed comment (default filter when scanning comments)
- `@ac-reply: <content>` = agent reply prefix (auto-added by `drive.py reply`)

## Commands Reference

### drive.py (comments, reply, resolve)

```bash
# List all comments on a file
uv run core/skills/gsuite/tools/drive.py comments <file_id> [--json] [--author NAME] [--since YYYY-MM-DD] [--include-deleted] [--suggestions] [--limit N] [--account EMAIL]

# Reply to a comment (auto-prefixes "@ac-reply: ")
uv run core/skills/gsuite/tools/drive.py reply <file_id> <comment_id> "<content>" [--resolve] [--yes] [--account EMAIL] [--json]

# Resolve a comment without replying
uv run core/skills/gsuite/tools/drive.py resolve <file_id> <comment_id> [--yes] [--account EMAIL] [--json]
```

### docs.py (find, edit)

```bash
# Find text and get document indices
uv run core/skills/gsuite/tools/docs.py find <doc_id> "<query>" [--tab TAB] [--context N] [--account EMAIL] [--json]

# Replace text (single edit)
uv run core/skills/gsuite/tools/docs.py edit <doc_id> --find "<old>" --replace "<new>" [--tab TAB] [--yes] [--account EMAIL] [--json]

# Replace text (batch from plan file)
uv run core/skills/gsuite/tools/docs.py edit <doc_id> --plan /tmp/edit-plan.json [--tab TAB] [--yes] [--account EMAIL] [--json]

# Read document content
uv run core/skills/gsuite/tools/docs.py read <doc_id> [--tab TAB] [--json] [--raw] [--account EMAIL]
```

### sheets.py (read, write)

```bash
# Read range
uv run core/skills/gsuite/tools/sheets.py read <spreadsheet_id> "<range>" [--json] [--account EMAIL]

# Write value(s)
uv run core/skills/gsuite/tools/sheets.py write <spreadsheet_id> "<range>" "<value>" [--account EMAIL] [--json]
```

### slides.py (read, edit)

```bash
# Read presentation
uv run core/skills/gsuite/tools/slides.py read <presentation_id> [--json] [--raw] [--account EMAIL]

# Replace text (single edit)
uv run core/skills/gsuite/tools/slides.py edit <presentation_id> --find "<old>" --replace "<new>" [--yes] [--account EMAIL] [--json]

# Replace text (batch from plan file)
uv run core/skills/gsuite/tools/slides.py edit <presentation_id> --plan /tmp/edit-plan.json [--yes] [--account EMAIL] [--json]
```

## The Comment Loop Pipeline

### Phase 1: Fetch @ac Comments (any model)

```bash
uv run core/skills/gsuite/tools/drive.py comments <file_id> --json
```

From the JSON output, extract comments where `content` starts with `@ac`.

For each matching comment, record:
- `id` -- comment identifier
- `content` -- the instruction (strip the `@ac` prefix)
- `quotedFileContent.value` -- the anchored text in the document

**Gate:** If 0 `@ac` comments found, STOP. Report "no actionable comments".

### Phase 2: Read Content + Plan Edits (medium-tier minimum)

This phase requires semantic understanding. Low-tier models cannot reliably interpret edit instructions or generate replacement text.

#### For Documents

1. Find the quoted text location:
   ```bash
   uv run core/skills/gsuite/tools/docs.py find <doc_id> "<quotedFileContent.value>" --json
   ```
   Returns matches with `start_index`, `end_index`, and surrounding `context`.

2. If multiple occurrences, use the `context` field to identify the correct one.

3. Read full document if broader context is needed:
   ```bash
   uv run core/skills/gsuite/tools/docs.py read <doc_id> --json
   ```

4. For each comment, determine the find/replace pair based on the `@ac` instruction.

#### For Spreadsheets

1. Read the relevant sheet range:
   ```bash
   uv run core/skills/gsuite/tools/sheets.py read <spreadsheet_id> "<range>" --json
   ```

2. Map the comment's `quotedFileContent.value` to a cell reference and determine the new value.

#### For Presentations

1. Read the presentation:
   ```bash
   uv run core/skills/gsuite/tools/slides.py read <presentation_id> --json
   ```

2. Identify the text to find and the replacement from the `@ac` instruction.

3. Optionally scope to specific slides using `page_ids` from the read output.

#### Build the Edit Plan

Write the appropriate plan file to `/tmp/edit-plan.json`.

**Document plan** (`docs.py edit --plan` format):
```json
{"edits": [{"find": "old text", "replace": "new text"}]}
```

**Slides plan** (`slides.py edit --plan` format):
```json
{"edits": [{"find": "old text", "replace": "new text", "page_ids": ["g1234abc"]}]}
```

The `page_ids` field is optional. Omit it to match across all slides.

**Sheets:** No plan file. Execute individual `write` commands per cell.

Alongside the plan, build a reply map (comment_id -> reply_text) for Phase 4.

**Gate:** If any `@ac` instruction is ambiguous or requires structural changes, classify it as a noop. Record `reply_text` = `"Skipped: <reason>"` and do not include an edit for that comment.

### Phase 3: Apply Edits (any model)

Execute the plan mechanically. Do NOT interpret or modify the plan.

#### Documents

```bash
uv run core/skills/gsuite/tools/docs.py edit <doc_id> --plan /tmp/edit-plan.json --yes
```

All edits execute as a single atomic `batchUpdate`.

#### Spreadsheets

For each cell change:
```bash
uv run core/skills/gsuite/tools/sheets.py write <spreadsheet_id> "<range>" "<value>"
```

#### Presentations

```bash
uv run core/skills/gsuite/tools/slides.py edit <presentation_id> --plan /tmp/edit-plan.json --yes
```

All edits execute as a single atomic `batchUpdate`.

**Error handling:** If any edit command fails, STOP immediately. Report the error. Do NOT continue to Phase 4.

### Phase 4: Reply + Resolve (any model)

For each processed comment:

**Edit applied:**
```bash
uv run core/skills/gsuite/tools/drive.py reply <file_id> <comment_id> "Applied: replaced '<old_snippet>' with '<new_snippet>'" --resolve --yes
```

**Noop (skipped):**
```bash
uv run core/skills/gsuite/tools/drive.py reply <file_id> <comment_id> "Skipped: <reason>" --yes
```

Do NOT use `--resolve` for noop actions -- the comment may need human attention.

The `reply` command auto-prefixes `@ac-reply:` for traceability.

## Edit Plan Formats

### docs.py edit --plan

```json
{
  "edits": [
    {"find": "quarterly report", "replace": "Q4 2025 report"},
    {"find": "acme corp", "replace": "Example Corp"}
  ]
}
```

Uses `replaceAllText` API. Case-sensitive. Matches all occurrences of each `find` string.

### slides.py edit --plan

```json
{
  "edits": [
    {"find": "Draft", "replace": "Final", "page_ids": ["g1234abc"]},
    {"find": "2024", "replace": "2025"}
  ]
}
```

Uses `replaceAllText` API. The `page_ids` array scopes replacements to specific slides.

### sheets.py (no plan file)

Execute individual write commands:
```bash
uv run core/skills/gsuite/tools/sheets.py write <id> "Sheet1!B3" "new value"
uv run core/skills/gsuite/tools/sheets.py write <id> "Sheet1!C5" '["val1", "val2"]'
```

## Examples

### Full Loop: Google Doc

```bash
# Phase 1: Fetch comments
uv run core/skills/gsuite/tools/drive.py comments abc123 --json
# Output includes comment id="AAAA1234", content="@ac change 'quarterly report' to 'Q4 2025 report'",
#   quotedFileContent.value="quarterly report"
# And comment id="BBBB5678", content="@ac is this section still relevant?"

# Phase 2: Find text indices (useful for verification)
uv run core/skills/gsuite/tools/docs.py find abc123 "quarterly report" --json
# Returns: [{"start_index": 142, "end_index": 159, "text": "quarterly report", ...}]

# Phase 2: Build plan -> /tmp/edit-plan.json
# {"edits": [{"find": "quarterly report", "replace": "Q4 2025 report"}]}
# Reply map: AAAA1234 -> "Applied: replaced 'quarterly report' with 'Q4 2025 report'"
#            BBBB5678 -> "Skipped: question, not an edit instruction"

# Phase 3: Apply
uv run core/skills/gsuite/tools/docs.py edit abc123 --plan /tmp/edit-plan.json --yes

# Phase 4: Reply + resolve
uv run core/skills/gsuite/tools/drive.py reply abc123 AAAA1234 "Applied: replaced 'quarterly report' with 'Q4 2025 report'" --resolve --yes
uv run core/skills/gsuite/tools/drive.py reply abc123 BBBB5678 "Skipped: question, not an edit instruction" --yes
```

### Full Loop: Google Sheet

```bash
# Phase 1: Fetch comments
uv run core/skills/gsuite/tools/drive.py comments def456 --json
# Comment id="CCCC9012", content="@ac change this to 500", quotedFileContent.value="350"

# Phase 2: Read sheet, identify cell
uv run core/skills/gsuite/tools/sheets.py read def456 "Sheet1!A1:Z100" --json
# Locate cell containing "350" -> Sheet1!D7

# Phase 3: Apply
uv run core/skills/gsuite/tools/sheets.py write def456 "Sheet1!D7" "500"

# Phase 4: Reply + resolve
uv run core/skills/gsuite/tools/drive.py reply def456 CCCC9012 "Applied: changed D7 from '350' to '500'" --resolve --yes
```

### Full Loop: Google Slides

```bash
# Phase 1: Fetch comments
uv run core/skills/gsuite/tools/drive.py comments ghi789 --json
# Comment id="DDDD3456", content="@ac change 'Draft' to 'Final' on this slide"

# Phase 2: Read presentation, identify page
uv run core/skills/gsuite/tools/slides.py read ghi789 --json
# Slide with objectId "g1234abc" contains "Draft"

# Phase 2: Build plan -> /tmp/edit-plan.json
# {"edits": [{"find": "Draft", "replace": "Final", "page_ids": ["g1234abc"]}]}

# Phase 3: Apply
uv run core/skills/gsuite/tools/slides.py edit ghi789 --plan /tmp/edit-plan.json --yes

# Phase 4: Reply + resolve
uv run core/skills/gsuite/tools/drive.py reply ghi789 DDDD3456 "Applied: replaced 'Draft' with 'Final' on slide g1234abc" --resolve --yes
```

## Model Tier Routing

| Phase | Tier | Rationale |
|-------|------|-----------|
| Phase 1: Fetch comments | Low-tier | CLI invocation + JSON filtering |
| Phase 2: Plan edits | **Medium-tier minimum** | Comment interpretation, text generation, disambiguation |
| Phase 3: Apply edits | Low-tier | Deterministic execution of pre-computed plan |
| Phase 4: Reply + resolve | Low-tier | Template-based replies + single command per comment |

## Escalation Rules

Classify as noop and escalate to human review when:

- The `@ac` instruction is vague ("make this better", "fix this section")
- The edit requires structural changes (reordering paragraphs, merging cells, adding slides)
- The comment references external context not present in the document
- Multiple valid interpretations exist
- The `quotedFileContent.value` matches more than one location and context is insufficient to disambiguate
- The comment requests deletion of content (not a text replacement)

## Deprecated

- `comments.py` is deprecated. Use `drive.py comments` instead. The `drive.py` version supports author/date filtering, suggestions, and works across all Google Drive file types (not just Docs).
