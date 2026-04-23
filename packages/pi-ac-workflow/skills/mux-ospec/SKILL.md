---
name: mux-ospec
description: "Thin package-owned alias for `ac-workflow-mux-ospec`. Uses `pimux` as the runtime-only stage orchestration control plane."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux-ospec

FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.

This skill is a package-owned trigger alias for `ac-workflow-mux-ospec`. It is not an independent spec-stage workflow definition.

When explicitly triggered, keep the parent as a `pimux` control plane and spawn the authoritative stage-owning `pimux` child before substantive stage work. Delegate workflow semantics to `../ac-workflow-mux-ospec/SKILL.md` and runtime semantics to `../../extensions/pimux/docs/`.

Pass explicit spec paths through unchanged. If the user provides an inline prompt without a path, let the authoritative `pimux` runtime derive/create the next current-branch spec path. Use `AskUserQuestion` only when missing input blocks spawn.
