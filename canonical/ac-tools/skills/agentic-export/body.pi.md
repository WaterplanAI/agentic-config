# Agentic Export

Export assets from a project into this repository.

## Compatibility Note

This pi wrapper preserves the original export workflow without relying on the original Claude-only delegation primitive.

## Arguments

- **asset_type**: `skill` | `template` | `agent`
- **asset_name_or_path**: source asset name/path in project
- **agentic_config_path**: optional path to this repository
- **options**: optional flags (`--plugin`, `--force`, `--dry-run`)

Request: `$ARGUMENTS`

## Execution

1. Run the pre-flight checks below.
2. Read `../ac-tools-agentic-share/SKILL.md`.
3. Apply the bundled `Agentic Asset Share` workflow in **`export`** mode to the current request.
4. Do **not** ask the user to rerun the command under another skill; continue in the current invocation.

## Examples

```bash
# Export project skill into ac-tools plugin
/skill:ac-tools-agentic-export skill my-skill --plugin ac-tools

# Export template directory
/skill:ac-tools-agentic-export template templates/release-checklist

# Export an agent markdown file
/skill:ac-tools-agentic-export agent /absolute/path/to/spec-reviewer.md

# Dry run preview
/skill:ac-tools-agentic-export skill my-skill --plugin ac-qa --dry-run
```

## Pre-Flight Check

Before continuing into the shared export workflow, verify:

1. Source asset exists in the project.
2. Destination repository path is resolvable.
3. For `skill`, destination plugin is explicit or inferable.

If checks fail, provide a clear error and stop.

## Path Resolution

Repository path resolution order:

1. Explicit argument
2. Current working directory (skill runs inside repo)
3. Abort if not in agentic-config repo
