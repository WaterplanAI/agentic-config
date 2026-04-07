# Agentic Import

Import an external asset into this repository.

## Arguments

- **asset_type**: `skill` | `template` | `agent`
- **source_path**: absolute path to source asset
- **target_name**: optional destination name
- **options**: optional flags (`--plugin`, `--force`, `--dry-run`)

Request: `$ARGUMENTS`

## Execution

Delegate to shared logic via explicit skill invocation:

```python
Skill(skill="agentic-share", args="import $ARGUMENTS")
```

## Examples

```bash
# Import a skill into ac-tools
/agentic-import skill /path/to/project/.claude/skills/my-skill --plugin ac-tools

# Import template directory
/agentic-import template /path/to/project/templates/onboarding

# Import workflow agent file
/agentic-import agent /path/to/project/agents/spec-reviewer.md

# Preview without writing
/agentic-import skill /path/to/skill --plugin ac-git --dry-run
```

## Pre-Flight Check

Before delegating, verify:

1. Current directory is repository root (contains `.claude-plugin/marketplace.json` and `plugins/`).
2. `source_path` exists.
3. `source_path` is absolute.
4. If `asset_type=skill`, a target plugin is provided or inferable.

If any check fails, stop with a clear error.
