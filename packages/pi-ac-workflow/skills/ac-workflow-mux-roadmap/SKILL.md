---
name: ac-workflow-mux-roadmap
description: "pi-adapted roadmap coordinator. Uses pimux as the authoritative runtime for roadmap -> ospec -> stage hierarchy while preserving mux semantics."
project-agnostic: true
allowed-tools:
  - pimux
  - AskUserQuestion
  - say
argument-hint: '[roadmap_path|inline_prompt]'
---

# MUX Roadmap Orchestrator - pi adaptation (pimux runtime)

Use this skill to execute roadmap phases with mux-family semantics while using `pimux` as the authoritative orchestration runtime.

## Binding activation

If the user explicitly invokes `mux-roadmap` / `ac-workflow-mux-roadmap`, or embeds this skill text as the runtime for the task, treat this document as a binding runtime contract, not as optional guidance, commentary, or a planning reference.

## Absolute compliance rule

For explicit `mux-roadmap` requests in pi, the current session is a `pimux`-only roadmap orchestrator.

- The authoritative `pimux` extension applies a fail-closed parent control-plane lock for explicit `mux-roadmap` execution.
- Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`, `subagent`, or any other non-`pimux` tool for substantive repo work.
- Do not inspect roadmap files, phase docs, or repo targets in the parent before spawn.
- Do not resolve DAG details, implementation plans, or edit scopes from the parent.
- Do not collapse the roadmap -> phase -> stage ownership model by doing phase work directly in the current session.
- The first real move is to spawn the authoritative phase-owning `pimux` child.
- The first observable parent tool call must be `pimux spawn`.
- If you have not spawned that child yet, you are not allowed to analyze the roadmap or answer phase execution questions from the parent.
- If the parent performs substantive repo inspection or any forbidden tool call before spawn, stop immediately, acknowledge a protocol violation, discard any parent-side conclusions, and restart from `pimux spawn`.

## Parent tool surface

While this skill is active, the parent session is runtime-locked to `pimux`, `AskUserQuestion`, and `say` only:

- before the first child exists: `pimux spawn` only
- `AskUserQuestion` is allowed only when the user has not provided an explicit roadmap/spec path or inline prompt that is sufficient to spawn
- after spawn: `spawn` / `status` / `capture` / `tree` / `list` / `send_message` / `open` / `kill` only for supervision or recovery
- child bridge notifications are delivered automatically; use notify-first pacing
- after spawn, use at most one initial `status` / `capture` / `tree` / `list` check and at most one recovery `send_message` per activity window, then wait for new child activity or the inactivity watchdog
- terminal settlement re-arms exactly one final `pimux status` verification before advancing
- `say` is allowed only for short user-attention prompts

The parent does not use repo `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`, or local helper orchestration for roadmap execution.

## Mandatory first actions

1. Build a short handoff from the user request only.
2. Pass any explicit roadmap/spec path from the user directly to the child and let the authoritative `pimux` runtime create the canonical target first when it is missing.
3. When the user provides an inline prompt without a path, let the authoritative `pimux` runtime auto-derive/create the next current-branch spec path by following recent current-branch spec-path patterns and the spec-skill convention `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`.
4. Use `AskUserQuestion` only when the user provided neither a path nor an inline prompt that is sufficient to spawn.
5. `pimux spawn` the phase-owning child before any substantive roadmap execution work.
6. Let the child read roadmap progress state, mux references, and repo context.

## Runtime authority and default hierarchy

For explicit `mux-roadmap` requests, lock this default hierarchy:

1. current-session roadmap orchestrator (control-plane)
2. direct phase-owning `/mux-ospec` child
3. direct stage-owning `pimux` child under that phase child

Do not collapse or bypass these ownership layers by default.

## Semantics to preserve

Preserve ac-workflow mux-roadmap behavior:

- roadmap-level control-plane ownership
- phase-owned stage artifacts and roadmap progress mirror reconciliation
- declared dispatch and evidence-gated advancement
- serialized shared-surface updates when write scopes overlap
- no manual fallback outside protocol

## Phase execution contract

For each phase, the authoritative child owns the substantive work:

- child reads roadmap progress mirror, active phase handoff, mux foundation assets, and pimux protocol/pattern references
- phase child runs mux-ospec stage discipline
- stage work is owned by one direct stage child at a time
- phase artifacts reconcile first; roadmap mirror reconciles second
- parent roadmap orchestrator advances DAG only after child settlement evidence

## Reporting and settlement

- use `pimux send_message` for explicit parent -> child routing
- only authoritative direct child session calls `pimux report_parent`
- success settles on `closeout + exit`; non-success settles as `question` / `blocker` / `failure`
- do not emit roadmap closeout while direct child outcomes remain unsettled

## Completion

Roadmap advancement and closeout require protocol-valid settlement plus consistent phase and roadmap artifacts.
No silent fallback to non-`pimux` runtime for explicit mux-roadmap execution.
