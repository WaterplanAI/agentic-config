---
name: ac-safety-configure-safety
description: "Configures guardian behavior for pi-ac-safety by reviewing defaults, proposing overrides, and updating project-level or user-level safety.yaml. Triggers on keywords: configure safety, safety config, safety yaml, guardian config"
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
---

# Configure Safety

Interactive `safety.yaml` configuration for `pi-ac-safety`.

## Compatibility Note

Use normal chat questions and confirmations for the interactive steps. Do not assume a separate prompt tool.

## Trigger

`/skill:ac-safety-configure-safety`

## Behavior

1. Read the 3-tier config resolution and display the current effective config:
   - Package defaults: `../../assets/config/safety.default.yaml`
   - User-level: `~/.claude/safety.yaml`
   - Project-level: `./safety.yaml` (relative to project root)
2. Display current effective settings per currently shipped guardian:
   - `credential_guardian`: blocked paths and allowed files
   - `destructive_bash`: category decisions (`deny` / `ask` / `allow`)
   - `write_scope`: allowed/blocked prefixes and files
   - `supply_chain`: category decisions and allowlists
   - `playwright`: allowed domains, always-blocked/always-allowed tools, and category decisions for blocked-domain navigation, file uploads, and unknown actions on the current Playwright surface
3. Ask which guardian(s) to customize.
4. For each selected guardian, present the current category decisions and ask for changes:
   - Show `category: current_decision`
   - Accept `deny`, `ask`, or `allow` per category
   - For list fields, show the current values and ask for additions/removals
5. Ask the target location: project-level (`./safety.yaml`) or user-level (`~/.claude/safety.yaml`).
6. Generate or update the YAML file at the chosen location.
   - Only write overrides; do not duplicate defaults.
   - Deep-merge with existing content if the file already exists.
7. Validate by loading the merged config and displaying the effective result.

## Steps

```text
1. Read ../../assets/config/safety.default.yaml
2. Read ~/.claude/safety.yaml (if it exists)
3. Read ./safety.yaml (if it exists)
4. Display the merged effective config as a table
5. Ask: "Which guardian should be customized? (credential/destructive_bash/write_scope/supply_chain/playwright/all)"
6. For each selected guardian:
   a. Show categories with current decisions
   b. Ask for a new decision per category (or skip)
   c. For list fields, show current values and ask for additions/removals
7. Ask: "Save to project-level or user-level? (project/user)"
8. Write YAML with overrides only
9. Re-read and display the new effective config
```

## Constraints

- Never modify `../../assets/config/safety.default.yaml`
- Only write overrides; do not duplicate default values
- Validate decisions are one of `deny`, `ask`, or `allow`
- Treat `playwright` settings as active policy for the shipped guardian parity on the current Playwright surface
- Preserve any existing file content by deep-merging updates
