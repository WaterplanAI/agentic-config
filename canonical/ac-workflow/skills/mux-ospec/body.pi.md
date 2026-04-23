# MUX Spec Orchestrator - pi adaptation (pimux runtime)

Use this skill to execute explicit spec stages through `pimux` while preserving mux-ospec semantics.

## Binding activation

If the user explicitly invokes `mux-ospec` / `ac-workflow-mux-ospec`, or embeds this skill text as the runtime for the task, treat this document as a binding runtime contract, not as optional guidance, commentary, or a planning reference.

## Absolute compliance rule

For explicit `mux-ospec` requests in pi, the current session is a `pimux`-only cross-stage orchestrator.

- The authoritative `pimux` extension applies a fail-closed parent control-plane lock for explicit `mux-ospec` execution.
- Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`, `subagent`, or any other non-`pimux` tool for substantive repo work.
- Do not execute substantive stage work directly in the parent.
- Do not read, grep, or inspect repo files in the parent to figure out implementation details.
- The first real move is to spawn the authoritative stage-owning `pimux` child.
- The first observable parent tool call must be `pimux spawn`.
- If the parent does substantive inspection before spawn, stop, acknowledge protocol violation, discard parent-side conclusions, and restart from `pimux spawn`.

## Parent tool surface

While this skill is active, the parent is runtime-locked to `pimux`, `AskUserQuestion`, and `say` only:

- before first child: `pimux spawn` only
- `AskUserQuestion` is allowed only when the user has not provided an explicit spec path or inline prompt, or when a later required user gate is reached
- after spawn: notify-first, not poll-first; wait for delivered child bridge activity instead of inspecting live state
- happy path after spawn forbids `status`, `capture`, `tree`, `list`, and `open`; those are recovery-only tools for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity watchdog
- after a child progress report arrives, use at most one `send_message` when the child needs input; then wait for closeout or another child report
- `say` is allowed only for short user-attention prompts

## Locked stage model

- no-spec invocation starts at Stage `000 CREATE`
- then execute explicit named stages by modifier (below)
- exactly one direct stage-owning `pimux` child at a time
- explicit spec paths pass through unchanged; if the canonical target is missing, the authoritative `pimux` runtime creates it before spawn
- when the user provides an inline prompt without a spec path, the authoritative `pimux` runtime auto-derives and creates the next current-branch spec path by following recent current-branch spec-path patterns and the spec-skill convention `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`
- use `AskUserQuestion` only when the user provided neither a spec path nor an inline prompt
- invalid spec path must route to `BLOCK`

## Workflow by modifier (authoritative)

`GATHER` is the mux-ospec name for `RESEARCH`.

- `full`: `CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL`
- `lean`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION`
- `leanest`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION`

## Gate and pacing rules

- `SUCCESS_CRITERIA` content is required before `CONFIRM_SC`
- `CONFIRM_SC` is a mandatory user gate before `PLAN`
- only `PASS` advances through `REVIEW`, `TEST`, `SENTINEL`, and `SELF_VALIDATION`
- `WARN`/`FAIL` route to `FIX`; retry exhaustion escalates to user
- child bridge notifications are delivered automatically; default pacing is notify-first
- do not poll pimux; if you are about to inspect routine progress, stop and wait for delivered child activity instead
- after spawn, do not call `status`, `capture`, `tree`, `list`, or `open` on the happy path
- terminal settlement re-arms exactly one final `pimux status` verification before advancing
- optional watchdog is inactivity-only and concise
- default blocked/stuck behavior escalates to user unless explicit override exists

## Stage commit contract (mandatory)

Every authoritative stage child MUST commit all changed repos.

Signal/report metadata must include:

- `repo_scope`: `spec-only` | `root-only` | `root+spec`
- `root_commit`: short hash or `N/A`
- `spec_commit`: short hash or `N/A`

When both repos changed, commit root first, then commit spec through the resolver.

## Child stage contract

Each authoritative stage-owning `pimux` child must:

- read `../../assets/agents/spec/` stage references needed for that stage
- read `../../assets/mux/protocol/foundation.md` and `../../assets/mux/protocol/subagent.md`
- read `.pi/skills/pimux/references/patterns.md` (or package-local equivalent)
- execute only assigned stage scope
- preserve evidence-gated reporting with repo-scoped commit metadata
- use `pimux report_parent` exactly once for terminal settlement
- for same-session parent input needed before continuing, use `report_parent(progress, requiresResponse=true)`; `question` is terminal waiting-on-parent settlement
- exit promptly after terminal report

Local helpers under the stage child are data-plane only and must not call `pimux` / `report_parent`.

## Completion

A stage is complete only after terminal report + child exit.
Cross-stage parent advances only after verifying settlement via `pimux status`.
