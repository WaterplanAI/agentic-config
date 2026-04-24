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

This skill is a package-owned trigger alias for `ac-workflow-mux`. It is not an independent workflow definition.

Delegate workflow semantics to `../ac-workflow-mux/SKILL.md` and runtime semantics to `../../extensions/pimux/docs/`.

## Mandatory trigger behavior

If the user explicitly triggers `mux`, the parent must actually run through `pimux`.

Required sequence:
1. after spawn, do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity
2. treat the authoritative `pimux` extension as the fail-closed parent control-plane lock
3. prepare bounded handoff from the user request only
4. spawn the authoritative `pimux` child before substantive analysis
5. keep the parent control-plane only; use `AskUserQuestion` only for explicit user clarification
6. after spawn, run notify-first rather than poll-first: do not call `status`, `capture`, `tree`, `list`, or `open` on the happy path
7. after a child progress report, use at most one `send_message` if input is needed, then wait again
8. use `status` / `capture` / `tree` / `list` / `open` only for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity watchdog
9. after terminal settlement, do one final `pimux status` verification and then advance

Do not satisfy `mux` requests by directly doing domain work in the parent.
Do not use parent-side `Read`, `Bash`, or repo inspection to figure out the task before spawn.
Do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity, and treat `status` / `capture` / `tree` / `list` / `open` as recovery-only.
