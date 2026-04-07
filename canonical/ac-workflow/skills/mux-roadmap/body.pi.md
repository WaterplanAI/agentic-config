# MUX Roadmap Orchestrator - pi adaptation

Use this skill to execute a multi-track roadmap with explicit DAG ownership, phase-owned stage artifacts, and a roadmap-level progress mirror.

## Purpose

This pi adaptation keeps the useful roadmap-orchestration behavior without pretending the runtime has Claude-only nested skill loading or task notifications.

The coordinator should:
- own the roadmap DAG directly
- execute phases through the same stage discipline used by mux-ospec
- keep authoritative state in phase files plus sibling `-stages/` directories
- keep a roadmap-level progress mirror for cross-session resume
- use one worker layer only: coordinator -> subagent

## Current shipped boundary

This pi wrapper assumes:
- the roadmap file already exists
- the relevant phase specs already exist or are being managed outside this wrapper
- the roadmap already has, or can accept, a live `## Implementation Progress` mirror

It does not recreate the original Claude-only `start` / `continue` / `--wait-after-plan` bootstrap surface or split a monolithic roadmap into per-phase specs automatically.
Use it to execute an already-structured roadmap honestly on top of the shared pi mux foundation.

## Mandatory first actions

1. Read the roadmap file.
2. Start a mux session:

```bash
uv run {{MUX_ROOT}}/tools/session.py "mux-roadmap-<topic>"
```

3. Read the roadmap's live progress section before touching implementation.
4. Resolve the next unblocked phase from the roadmap's DAG and next-action notes.

## Default state model for pi roadmaps

Prefer this hierarchy unless the roadmap explicitly says otherwise:

1. Phase file + sibling `-stages/` directory = authoritative state for one phase.
2. Roadmap `## Implementation Progress` section = cross-phase mirror.
3. Roadmap `## Next Action` = orchestration intent.

Do not invent a separate `CONTINUE.md` by default when the roadmap already has an implementation-progress section. Use a standalone continue file only when:
- the roadmap explicitly requires it, or
- there is no roadmap-level progress section to mirror against.

## Coordinator rules

- You are the only roadmap coordinator.
- Do not introduce track coordinators or nested roadmap coordinators.
- Do not delegate “run this whole roadmap” or “run this whole phase” to another coordinator.
- Use fresh workers for bounded stage tasks, not for hidden orchestration layers.
- Keep shared surfaces serialized even when the DAG allows parallel tracks.

## Phase execution pattern

For each phase:

1. Read the roadmap handoff into that phase.
2. Read the phase spec and its latest `Next Action`.
3. Execute the phase through the standard stage loop:
   - `GATHER`
   - `SUCCESS_CRITERIA`
   - `PLAN`
   - `IMPLEMENT`
   - `REVIEW_FIX`
   - `TEST`
   - `DOCUMENT`
   - `PHASE_CLOSE`
4. Update the phase artifacts first.
5. Reconcile the roadmap mirror second.
6. Only then advance along the DAG.

The roadmap coordinator may conceptually reuse the mux-ospec stage model, but it should execute the stage gates directly in the current session. Do not rely on nested `/skill:` invocation.

## Track and DAG policy

- Sequential within a track.
- Parallel across tracks only when the active waves do not touch the same files or shared surfaces.
- Shared surfaces that should default to serialized execution include:
  - generator core tooling
  - shared runtime packages
  - umbrella package docs
  - common availability matrices
  - roadmap-level progress mirrors

If a downstream phase depends on a generated or runtime foundation, do not start it early just because the track graph looks parallel on paper.

## Worker pattern

Use `subagent` for bounded stage work.

Recommended agent roles when available:
- `scout` for roadmap/phase inventory
- `planner` for file-level implementation plans
- `worker` for implementation and doc updates
- `reviewer` for independent review

Every worker must follow `{{MUX_ROOT}}/protocol/subagent.md`:
- write a report
- write a signal
- return exactly `0` on success
- avoid nested subagents

## Update protocol

After every finished stage:

1. Update the corresponding phase stage artifact.
2. Update the parent phase file's progress section.
3. Reconcile the roadmap `## Implementation Progress` mirror.
4. Refresh these roadmap fields together so resume stays honest:
   - `Current State`
   - `Progress Tree`
   - `Test Status`
   - `Pending Refinements`
   - `Blockers`
   - `Next Action`
   - `Status`
   - `Lessons Learned`
   - `Last Updated`

If the phase file and roadmap disagree, the phase file wins.

## Validation pattern

Use the shared mux tools for bounded verification:

```bash
uv run {{MUX_ROOT}}/tools/verify.py <session-dir> --action summary
uv run {{MUX_ROOT}}/tools/extract-summary.py <report-path>
```

Use direct coordinator validation for repository commands, type checks, tests, and smoke checks.

Only advance the roadmap when the phase artifacts and the roadmap mirror both reflect reality.

## Resume behavior

When resuming:
- read the roadmap progress mirror first
- then read the referenced phase file and latest phase-close artifact for the active phase
- trust the roadmap's `Next Action` for intent, but confirm it still matches the phase files
- repair drift immediately before doing new implementation work

## Escalation policy

Stay autonomous by default.

Escalate in the main chat only for:
- scope changes that alter the roadmap DAG materially
- product or UX decisions the roadmap does not already answer
- blockers that cannot be closed from repository evidence and available tools

Use one short `say` alert when you need the user's attention.

## Post-track and final validation

Only run post-track fixer loops, broader QA sweeps, or release validation when the roadmap explicitly calls for them.
Do not invent a hidden sentinel or QA pipeline just because the original Claude skill had one.

## Completion

A roadmap phase is complete only when:
- the phase-owned artifacts are complete
- the roadmap mirror is reconciled
- the next exact action is explicit
- downstream blocked/unblocked state is honest

A roadmap is complete only when every track is reconciled, the final validation phase is closed, and the roadmap mirror tells one consistent story.

This adaptation favors truthful, resumable execution over a mechanical port of Claude-only orchestration machinery.
