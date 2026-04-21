---
name: ac-audit-configure-audit
description: "Configures audit logging for pi-ac-audit by reviewing defaults, proposing overrides, and updating project-level or user-level audit.yaml. Triggers on keywords: configure audit, audit config, audit yaml"
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
---

# Configure Audit

Interactive `audit.yaml` configuration for `pi-ac-audit`.

## Compatibility Note

Use normal chat questions and confirmations for the interactive steps. Do not assume a separate prompt tool.

## Trigger

`/skill:ac-audit-configure-audit`

## Behavior

1. Read the 3-tier config resolution and display the current effective config:
   - Package defaults: `../../assets/config/audit.default.yaml`
   - User-level: `~/.claude/audit.yaml`
   - Project-level: `./audit.yaml` (relative to project root)
2. Display the current effective settings:
   - `log_dir`: audit log output directory
   - `log_permissions`: file permissions for log files (max `0o600`)
   - `max_words`: word truncation limit for `systemMessage` display
   - `display_tools`: list of tools that trigger `systemMessage` in the UI
3. Ask which setting(s) to customize.
4. For each selected setting, present the current value and ask for changes:
   - `log_dir`: accept a directory path (supports `~` expansion)
   - `log_permissions`: accept an octal value and validate `<= 0o600`
   - `max_words`: accept a positive integer
   - `display_tools`: show the current list and ask for additions/removals
5. Ask the target location: project-level (`./audit.yaml`) or user-level (`~/.claude/audit.yaml`).
6. Generate or update the YAML file at the chosen location.
   - Only write overrides; do not duplicate defaults.
   - Deep-merge with existing content if the file already exists.
7. Validate by loading the merged config and displaying the effective result.

## Steps

```text
1. Read ../../assets/config/audit.default.yaml
2. Read ~/.claude/audit.yaml (if it exists)
3. Read ./audit.yaml (if it exists)
4. Display the merged effective config as a table
5. Ask: "Which setting should be customized? (log_dir/log_permissions/max_words/display_tools/all)"
6. For each selected setting:
   a. Show the current value
   b. Ask for the new value (or skip)
   c. For display_tools, show additions/removals explicitly
7. Ask: "Save to project-level or user-level? (project/user)"
8. Write YAML with overrides only
9. Re-read and display the new effective config
```

## Constraints

- Never modify `../../assets/config/audit.default.yaml`
- Only write overrides; do not duplicate default values
- Validate `log_permissions` does not exceed `0o600`
- Validate `max_words` is a positive integer
- Preserve any existing file content by deep-merging updates
