---
name: pimux
description: "Thin trigger alias for the package-owned pimux runtime extension. Use for tmux-backed Pi agents with explicit bridge messaging and notify-first supervision."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# pimux

FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.

This skill is a non-authoritative trigger shim for the package-owned `pimux` extension runtime. Runtime semantics are owned by `packages/pi-ac-workflow/extensions/pimux/` and its docs.

Use `/pimux` or the `pimux` tool to spawn and supervise tmux-backed Pi agents. The notification behavior is fixed to `notify-and-follow-up`.

See:
- `../../extensions/pimux/docs/commands.md`
- `../../extensions/pimux/docs/protocol.md`
- `../../extensions/pimux/docs/patterns.md`

Do not duplicate runtime protocol text here. Keep this alias minimal so package docs and extension prompts remain the single source of truth.
