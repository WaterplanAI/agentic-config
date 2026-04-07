# notebook-edit

Shared `NotebookEdit` compat tool exported by `@agentic-config/pi-compat`.

## Purpose
- Close the current pi `NotebookEdit` runtime gap with a reusable notebook-edit tool.
- Preserve compatibility with existing hook-backed guardrails that already reason about Claude `NotebookEdit` events.
- Give later generated wrappers a narrow, deterministic way to update notebook cell source.

## Tool name
- `NotebookEdit`

## Supported edit surface
- target a `.ipynb` file via `notebook_path`
- replace one cell's `source` via `cell_index` or `cell_id`
- optionally append one new cell when `create_if_missing` is true and `cell_index` points to the next slot
- `cell_type` supports `code` and `markdown` when appending

## Scope limits
- No notebook execution
- No output regeneration
- No metadata-only edits
- No multi-cell diff engine
