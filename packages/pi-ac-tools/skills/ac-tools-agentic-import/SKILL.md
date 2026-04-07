---
name: ac-tools-agentic-import
description: "Import external reusable assets into this repository's v0.2 plugin architecture (skills, templates, agents)."
project-agnostic: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Agentic Import

Import an external asset into this repository.

## Compatibility Note

This pi wrapper preserves the original import workflow without relying on the original Claude-only delegation primitive.

## Arguments

- **asset_type**: `skill` | `template` | `agent`
- **source_path**: absolute path to source asset
- **target_name**: optional destination name
- **options**: optional flags (`--plugin`, `--force`, `--dry-run`)

Request: `$ARGUMENTS`

## Execution

1. Run the pre-flight checks below.
2. Read `../ac-tools-agentic-share/SKILL.md`.
3. Apply the bundled `Agentic Asset Share` workflow in **`import`** mode to the current request.
4. Do **not** ask the user to rerun the command under another skill; continue in the current invocation.

## Examples

```bash
# Import a skill into ac-tools
/skill:ac-tools-agentic-import skill /path/to/project/.claude/skills/my-skill --plugin ac-tools

# Import template directory
/skill:ac-tools-agentic-import template /path/to/project/templates/onboarding

# Import workflow agent file
/skill:ac-tools-agentic-import agent /path/to/project/agents/spec-reviewer.md

# Preview without writing
/skill:ac-tools-agentic-import skill /path/to/skill --plugin ac-git --dry-run
```

## Pre-Flight Check

Before continuing into the shared import workflow, verify:

1. Current directory is repository root (contains `.claude-plugin/marketplace.json` and `packages/`).
2. `source_path` exists.
3. `source_path` is absolute.
4. If `asset_type=skill`, a target plugin is provided or inferable.

If any check fails, stop with a clear error.
