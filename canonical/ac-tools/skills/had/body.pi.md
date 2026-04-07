# HAD Alias Skill

Shorthand wrapper for the `ac-tools-human-agentic-design` workflow.

## Compatibility Note

This pi wrapper preserves the original shorthand intent without relying on the original Claude-only delegation primitive.

## Usage

```
/skill:ac-tools-had <design request>
```

## Behavior

1. Read `../ac-tools-human-agentic-design/SKILL.md`.
2. Treat the current request as if the user had invoked `/skill:ac-tools-human-agentic-design $ARGUMENTS`.
3. Do **not** ask the user to rerun the request under another skill.
4. Preserve the same fallback behavior when preview tooling is unavailable.
