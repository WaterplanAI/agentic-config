# configure-safety

Interactive safety.yaml configuration for ac-safety plugin.

## Trigger

`/configure-safety` or `/ac-safety:configure-safety`

## Behavior

1. Read the 3-tier config resolution and display current effective config:
   - Plugin defaults: `${CLAUDE_PLUGIN_ROOT}/config/safety.default.yaml`
   - User-level: `~/.claude/safety.yaml`
   - Project-level: `./safety.yaml` (relative to project root)

2. Display current effective settings per guardian:
   - credential_guardian: blocked paths, allowed files
   - destructive_bash: category decisions (deny/ask/allow per category)
   - write_scope: allowed/blocked prefixes and files
   - supply_chain: category decisions, allowlists
   - playwright: category decisions, domain allowlist

3. Ask user which guardian(s) to customize.

4. For each selected guardian, present current category decisions and ask for changes:
   - Show: `category: current_decision`
   - Accept: `deny`, `ask`, or `allow` per category
   - For list fields (allowlists, prefixes): show current, ask for additions/removals

5. Ask target location: project-level (`./safety.yaml`) or user-level (`~/.claude/safety.yaml`).

6. Generate or update the YAML file at chosen location.
   - Only write overrides (do not duplicate defaults).
   - Deep-merge with existing content if file already exists.

7. Validate by loading the merged config and displaying effective result.

## Steps

```
1. Read ${CLAUDE_PLUGIN_ROOT}/config/safety.default.yaml
2. Read ~/.claude/safety.yaml (if exists)
3. Read ./safety.yaml (if exists)
4. Display merged effective config as table
5. Prompt: "Which guardian to customize? (credential/destructive_bash/write_scope/supply_chain/playwright/all)"
6. For selected guardian(s):
   a. Show categories with current decisions
   b. Ask for new decision per category (or skip)
   c. For list fields, show current and ask for changes
7. Prompt: "Save to project-level or user-level? (project/user)"
8. Write YAML with only the overrides
9. Re-read and display new effective config
```

## Constraints

- Never modify plugin defaults (`safety.default.yaml`)
- Only write overrides -- do not duplicate default values
- Validate decisions are one of: deny, ask, allow
- Existing file content must be preserved (deep-merge on write)
