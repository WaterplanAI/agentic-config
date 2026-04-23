---
name: mux-roadmap
description: "Thin workflow alias for `ac-workflow-mux-roadmap`. Uses `pimux` as runtime-only roadmap orchestration control plane."
project-agnostic: false
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# mux-roadmap

Use this alias when you want roadmap-phase-stage orchestration in tmux.

## Mandatory trigger behavior

If the user explicitly triggers `mux-roadmap`, keep work in the tmux-backed roadmap lane.

Required sequence:
1. after spawn, do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity
2. pass through an explicit roadmap/spec path unchanged when the user provides one; if the target is valid but missing, let the authoritative `pimux` runtime create it instead of blocking
3. if the user provides an inline prompt without a path, let the authoritative `pimux` runtime derive/create the next current-branch spec path by following recent current-branch spec-path patterns and the spec skill convention
4. use `AskUserQuestion` only when the user provided neither a path nor an inline prompt that is sufficient to spawn
5. let the authoritative `pimux` extension enforce the fail-closed parent control-plane lock
6. spawn the roadmap coordinator or phase-owning `pimux` child before substantive work
7. keep parent control-plane only except bounded user-input handoff prep
8. after spawn, run notify-first rather than poll-first: do not call `status`, `capture`, `tree`, `list`, or `open` on the happy path
9. after a child progress report, use at most one `send_message` if input is needed, then wait again
10. use `status` / `capture` / `tree` / `list` / `open` only for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity watchdog
11. after terminal settlement, do one final `pimux status` verification and then advance

Do not execute roadmap work directly in the parent while this skill is active.
Do not use parent-side `Read`, `Bash`, or manual repo discovery to plan roadmap work before spawn.
Do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity, and treat `status` / `capture` / `tree` / `list` / `open` as recovery-only.
