---
name: ac-workflow-mux
description: "pi-adapted mux coordinator. Uses pimux as the authoritative runtime while preserving shared mux foundation semantics."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
---

# MUX - pi coordinator pattern (pimux runtime)

Use this when the task is too large for one uninterrupted context window and you need mux wave semantics with tmux-backed long-lived execution.

## Binding activation

If the user explicitly invokes `mux` / `ac-workflow-mux`, or embeds this skill text as the runtime for the task, treat this document as a binding runtime contract, not as optional guidance, commentary, or a planning reference.

## Absolute compliance rule

For explicit mux-family triggers in pi, the current session is a `pimux`-only control plane.

- FIRST after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child bridge activity.
- The authoritative `pimux` extension applies a fail-closed parent control-plane lock for explicit mux-family wrappers.
- Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`, `subagent`, or any other non-`pimux` tool for substantive repo work.
- Do not do substantive repo or domain work in the parent session.
- Do not use parent-side repo discovery, file inspection, implementation planning, or direct edits before spawn.
- The first real move is to spawn the authoritative `pimux` child coordinator.
- The first observable parent tool call must be `pimux spawn`.
- If you have not spawned that child yet, you are not allowed to analyze, compare, implement, or answer the task from the parent.
- If the parent performs substantive repo inspection or any forbidden tool call before spawn, stop immediately, acknowledge a protocol violation, discard any parent-side conclusions, and restart from `pimux spawn`.

## Parent tool surface

While this skill is active, the parent session is runtime-locked to `pimux`, `AskUserQuestion`, and `say` only:

- before the first child exists: `pimux spawn` only
- `AskUserQuestion` is allowed only for explicit user clarification that blocks spawn
- after spawn: notify-first, not poll-first; wait for delivered child bridge activity instead of inspecting live state
- do not poll pimux or use Bash sleep/wait loops; if you are about to inspect routine progress, stop and wait for delivered child activity instead
- happy path after spawn forbids `status`, `capture`, `tree`, `list`, and `open`; those are recovery-only tools for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity watchdog
- after a child progress report arrives, use at most one `send_message` when the child needs input; then wait for closeout or another child report
- terminal settlement re-arms exactly one final `pimux status` verification before advancing
- `say` is allowed only for short user-attention prompts

The parent does not use repo `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`, or local helper orchestration for the substantive task.

## Mandatory first actions

1. Build a short handoff from the user request only.
2. `pimux spawn` the bounded mux coordinator before any substantive analysis or implementation.
3. Pass the raw objective, constraints, and any explicit file paths from the user into that child.
4. Let the child read mux foundation assets and repo context.

## Semantics to preserve

The migration is runtime/orchestration adaptation only. Preserve mux semantics:

- strict control-plane vs data-plane discipline
- declared dispatch before worker execution
- report/signal/summary evidence gates for advancement
- strict `ADVANCE | BLOCK | RECOVER` routing
- no manual fallback outside protocol

## Child coordinator contract

The authoritative `pimux` child owns the substantive mux run:

- child reads `../../assets/mux/protocol/foundation.md` and `../../assets/mux/protocol/subagent.md`
- child initializes strict session state with `../../assets/mux/tools/session.py --strict-runtime --session-key <key>`
- child declares worker dispatch payloads before execution
- child requires report + signal + summary evidence for advancement
- child keeps one worker layer (`coordinator -> subagent`) inside the child
- child keeps workers data-plane only; no `pimux` / `report_parent` from helpers

## Parent/session contract

- Parent -> child messaging: `pimux send_message`
- Child -> parent reporting: `pimux report_parent`
- success settles only after terminal `closeout` + child exit
- if child outcomes are intentionally non-success, propagate matching terminal kind (`question` / `blocker` / `failure`)
- for a child that must ask and continue in the same session, use `report_parent(progress, requiresResponse=true)`; `question` is terminal waiting-on-parent settlement

## Completion

Complete only when the authoritative child settles and exits with protocol-valid reporting.
Do not treat interim captures, local notes, or helper output as completion.
