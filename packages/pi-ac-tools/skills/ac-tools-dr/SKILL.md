---
name: ac-tools-dr
description: "Short alias for ac-tools-dry-run. Applies the same dry-run workflow and constraints to the provided command or prompt. Triggers on keywords: dr, dry run shorthand, preview safely"
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# DR Alias

Short alias for `ac-tools-dry-run`.

## Behavior

Treat this invocation exactly as if the user had run:

```text
/skill:ac-tools-dry-run <same arguments>
```

Apply the same workflow and constraints as `ac-tools-dry-run`:
1. Resolve the session status path under `outputs/session/<claude_pid>/status.yml`
2. Set `dry_run: true`
3. Execute the delegated command or prompt exactly as given
4. Do not perform file writes other than the session status file
5. Reset `dry_run: false` on success or failure
6. Report what would have changed

## Constraint

Do not rely on raw Claude skill-delegation syntax. This alias must remain pi-native and preserve the same dry-run semantics directly.
