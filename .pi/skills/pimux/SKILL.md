---
name: pimux
description: "Uses the local `pimux` extension to launch and manage minimal tmux-backed Pi agents with explicit parent-child messaging, session-scoped supervision, and nested hierarchy support. Triggers on keywords: pimux, tmux pi agents, tmux orchestration, tmux hierarchy, team in tmux, brainstorm in tmux, scout-and-plan replacement"
project-agnostic: false
allowed-tools:
  - Read
  - Bash
  - pimux
  - subagent
---

# pimux

Use `pimux` when work should continue in its own tmux-backed Pi session while remaining visible and manageable from the current Pi session.

## Core contract

- Parent -> child messaging uses `pimux send_message`.
- Child -> parent reporting uses `pimux report_parent`.
- Reporting is one hop only.
- Local helpers inside a pimux child are local-only and must not call `pimux` or `report_parent`.
- Success settles only after `report_parent(closeout)` plus child exit.
- After a terminal report, the pimux runtime should finalize the managed session promptly; children must not linger in a post-closeout state.
- `progress` is non-terminal.
- For same-session parent input that a child needs before continuing, use `report_parent(progress, requiresResponse=true)`.
- `question` is terminal waiting-on-parent settlement; do not use it when the child should continue after the answer.
- Session surfaces (`list`, `tree`, `status`) default to the current session hierarchy.
- Parent-side interface delivery should also show bridge message traffic concisely; parent -> child messages stay visible without forcing an extra turn.
- `list`, `tree`, and `navigate` should keep agent IDs visible while adding role/goal labels, clearer hierarchy connectors, and best-effort safe styling when the host interface supports it.
- Use `navigate` for interactive node selection and `prune` for registry hygiene.

## Use cases

- launch a long-lived worker in tmux
- create a small team and supervise it live
- replace scout-and-plan with explicit tmux scout -> planner handoff
- run nested orchestrators for `mux`, `mux-ospec`, or `mux-roadmap`

## Strict trigger rule

If the user explicitly invokes `pimux`, `mux`, `mux-ospec`, or `mux-roadmap`, treat that as a commitment to the pimux runtime.

- adopt the control-plane role immediately
- for explicit mux-family wrappers (`mux`, `mux-ospec`, `mux-roadmap`), the authoritative `pimux` extension now applies a fail-closed parent control-plane lock: only `pimux`, `AskUserQuestion`, and `say` remain allowed until the user explicitly runs `/pimux unlock`
- do only the minimum parent-side setup needed to prepare bounded handoff and launch the right child or hierarchy
- route the substantive task through pimux child sessions rather than doing the real work directly in the parent
- for analysis, comparison, planning, or review requests, the parent may frame the task from the user request and explicit handoff paths, but the actual analysis must happen inside spawned child session(s)
- do not silently fall back to a non-pimux direct answer while the skill remains active

## First reads

- [commands](references/commands.md)
- [protocol](references/protocol.md)
- [patterns](references/patterns.md)

## Defaults

- headless by default; open visually only when the user wants to watch
- notification behavior is fixed to `notify-and-follow-up`; alternative notification modes are not supported
- live-session actions such as `open`, `capture`, `send`, and `kill` should prefer currently running agents in interactive selectors
- keep prompts narrow and role-specific
- prefer file-path context handoff over large pasted context
- supervise asynchronously by default: after spawn, let the child work and return control unless the user asked to watch live or the next control-plane step truly depends on settlement now
- do not poll pimux; wait for delivered child activity, and treat `status` / `capture` / `tree` / `list` / `open` as recovery-only
- do not busy-wait with sleep loops or repeated nudges; wait for explicit child reports and use `status` / `capture` only at real recovery, handoff, or inspection points
- terminated or missing historical entries aged at least `1d` are auto-pruned from the active registry
