# Resume

## Current Task

Sanitize every plugin's skill `description` field: wrap with double quotes AND validate valid YAML frontmatter.

### Scope

All `plugin.json` files under `plugins/` and root `.claude-plugin/`:

- `plugins/ac-meta/.claude-plugin/plugin.json`
- `plugins/ac-workflow/.claude-plugin/plugin.json`
- `plugins/ac-git/.claude-plugin/plugin.json`
- `plugins/ac-qa/.claude-plugin/plugin.json`
- `plugins/ac-tools/.claude-plugin/plugin.json`
- `.claude-plugin/plugin.json`

### Requirements

1. Every skill's `description` field must be wrapped in double quotes
2. Validate that all SKILL.md frontmatter is valid YAML after changes
3. Commit result
