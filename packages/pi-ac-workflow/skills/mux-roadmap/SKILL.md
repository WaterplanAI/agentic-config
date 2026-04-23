---
name: mux-roadmap
description: "Thin package-owned alias for `ac-workflow-mux-roadmap`. Uses `pimux` as the runtime-only roadmap orchestration control plane."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux-roadmap

FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.

This skill is a package-owned trigger alias for `ac-workflow-mux-roadmap`. It is not an independent roadmap workflow definition.

When explicitly triggered, keep the parent as a `pimux` control plane and spawn the authoritative roadmap or phase-owning `pimux` child before substantive roadmap work. Delegate workflow semantics to `../ac-workflow-mux-roadmap/SKILL.md` and runtime semantics to `../../extensions/pimux/docs/`.

Pass explicit roadmap/spec paths through unchanged. If the user provides an inline prompt without a path, let the authoritative `pimux` runtime derive/create the target path. Use `AskUserQuestion` only when missing input blocks spawn.
