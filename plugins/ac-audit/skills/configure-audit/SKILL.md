# configure-audit

Interactive audit.yaml configuration for ac-audit plugin.

## Trigger

`/configure-audit` or `/ac-audit:configure-audit`

## Behavior

1. Read the 3-tier config resolution and display current effective config:
   - Plugin defaults: `${CLAUDE_PLUGIN_ROOT}/config/audit.default.yaml`
   - User-level: `~/.claude/audit.yaml`
   - Project-level: `./audit.yaml` (relative to project root)

2. Display current effective settings:
   - log_dir: audit log output directory
   - log_permissions: file permissions for log files (max 0o600)
   - max_words: word truncation limit for systemMessage display
   - display_tools: list of tools that trigger systemMessage in Claude Code UI

3. Ask user which setting(s) to customize.

4. For each selected setting, present current value and ask for changes:
   - log_dir: accept a directory path (supports ~ expansion)
   - log_permissions: accept octal value, validate <= 0o600
   - max_words: accept positive integer
   - display_tools: show current list, ask for additions/removals

5. Ask target location: project-level (`./audit.yaml`) or user-level (`~/.claude/audit.yaml`).

6. Generate or update the YAML file at chosen location.
   - Only write overrides (do not duplicate defaults).
   - Deep-merge with existing content if file already exists.

7. Validate by loading the merged config and displaying effective result.

## Steps

```
1. Read ${CLAUDE_PLUGIN_ROOT}/config/audit.default.yaml
2. Read ~/.claude/audit.yaml (if exists)
3. Read ./audit.yaml (if exists)
4. Display merged effective config as table
5. Prompt: "Which setting to customize? (log_dir/log_permissions/max_words/display_tools/all)"
6. For selected setting(s):
   a. Show current value
   b. Ask for new value (or skip)
   c. For display_tools list, show current and ask for additions/removals
7. Prompt: "Save to project-level or user-level? (project/user)"
8. Write YAML with only the overrides
9. Re-read and display new effective config
```

## Constraints

- Never modify plugin defaults (`audit.default.yaml`)
- Only write overrides -- do not duplicate default values
- Validate log_permissions does not exceed 0o600
- Validate max_words is a positive integer
- Existing file content must be preserved (deep-merge on write)
