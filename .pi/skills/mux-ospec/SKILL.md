---
name: mux-ospec
description: "Thin workflow alias for `ac-workflow-mux-ospec`. Uses `pimux` as runtime-only stage orchestration control plane."
project-agnostic: false
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux-ospec

Use this alias when you want tmux-backed spec stage orchestration.

## Mandatory trigger behavior

If the user explicitly triggers `mux-ospec`, keep work in the tmux-backed stage lane.

Required sequence:
1. pass through an explicit spec path unchanged when the user provides one; if the target is valid but missing, let the authoritative `pimux` runtime create it instead of blocking
2. if the user provides an inline prompt without a spec path, let the authoritative `pimux` runtime derive/create the next current-branch spec path by following recent current-branch spec-path patterns and the spec skill convention
3. use `AskUserQuestion` only when the user provided neither a spec path nor an inline prompt that is sufficient to spawn
4. let the authoritative `pimux` extension enforce the fail-closed parent control-plane lock
5. spawn the stage-owning `pimux` child before substantive stage work
6. after spawn, rely on child notifications first: at most one initial verification check and at most one recovery `send_message` per activity window, then wait for new child activity or the inactivity watchdog
7. after terminal settlement, do one final `pimux status` verification and then advance

Do not run spec-stage execution directly in the parent while this skill is active.
Do not use parent-side `Read`, `Bash`, or manual repo discovery to figure out the spec before spawn.
