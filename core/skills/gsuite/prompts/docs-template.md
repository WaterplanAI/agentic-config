# Docs Operation Prompts

Common prompts for Google Docs operations via the gsuite skill.

## Read Document

```
Read content from document {DOC_ID}

Execute:
uv run core/skills/gsuite/tools/docs.py read {DOC_ID} --json
```

## Append Text

```
Append "{TEXT}" to document {DOC_ID}

Execute:
uv run core/skills/gsuite/tools/docs.py write {DOC_ID} "{TEXT}" --append
```

## Insert Text at Position

```
Insert "{TEXT}" at index {INDEX} in document {DOC_ID}

Execute:
uv run core/skills/gsuite/tools/docs.py write {DOC_ID} "{TEXT}" --index {INDEX}
```

## Create Document

```
Create a new document titled "{TITLE}"

Execute:
uv run core/skills/gsuite/tools/docs.py create "{TITLE}" --json
```

## Export to PDF

```
Export document {DOC_ID} to PDF at {OUTPUT_PATH}

Execute:
uv run core/skills/gsuite/tools/docs.py export {DOC_ID} --format pdf --output {OUTPUT_PATH}
```

## Common Patterns

### Generate Report

1. Create new document
2. Build content sections
3. Append each section with proper formatting
4. Export to PDF if needed

### Document Analysis

1. Read document content with `--json`
2. Parse JSON for text content
3. Process/analyze as needed
