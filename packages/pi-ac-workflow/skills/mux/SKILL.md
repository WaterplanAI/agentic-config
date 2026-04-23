---
name: mux
description: "Thin package-owned alias for `ac-workflow-mux`. Uses `pimux` as the runtime-only control plane for mux-style tmux orchestration."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux

FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.

This skill is a package-owned trigger alias for `ac-workflow-mux`. It is not an independent workflow definition.

When explicitly triggered, keep the parent as a `pimux` control plane and spawn the authoritative `pimux` child coordinator before substantive analysis or implementation. Delegate workflow semantics to `../ac-workflow-mux/SKILL.md` and runtime semantics to `../../extensions/pimux/docs/`.

Do not satisfy `mux` requests by doing domain work directly in the parent. Do not poll pimux or inspect routine progress after spawn.
