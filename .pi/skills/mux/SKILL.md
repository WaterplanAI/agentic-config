---
name: mux
description: "Thin workflow alias for `ac-workflow-mux`. Uses `pimux` as runtime-only control plane for mux-style tmux orchestration."
project-agnostic: false
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux

Use this alias when you want mux-style orchestration on top of `pimux`.

## Mandatory trigger behavior

If the user explicitly triggers `mux`, the parent must actually run through `pimux`.

Required sequence:
1. treat the authoritative `pimux` extension as the fail-closed parent control-plane lock
2. prepare bounded handoff from the user request only
3. spawn the authoritative `pimux` child before substantive analysis
4. keep the parent control-plane only; use `AskUserQuestion` only for explicit user clarification
5. after spawn, rely on child notifications first: at most one initial verification check and at most one recovery `send_message` per activity window, then wait for new child activity or the inactivity watchdog
6. after terminal settlement, do one final `pimux status` verification and then advance

Do not satisfy `mux` requests by directly doing domain work in the parent.
Do not use parent-side `Read`, `Bash`, or repo inspection to figure out the task before spawn.
