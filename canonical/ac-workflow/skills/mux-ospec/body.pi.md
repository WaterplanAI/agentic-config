# MUX Spec Orchestrator - pi adaptation

Use this skill to execute an existing spec or phase spec through an explicit stage loop while preserving the mux session/report/signal protocol.

## Purpose

This wrapper adapts the original mux-ospec idea to the current pi runtime:
- one coordinator owns the stage gates directly
- stage workers run through the runtime `subagent` tool
- phase state is persisted in the spec file plus a sibling `-stages/` directory
- verification is synchronous and file-based
- user escalation happens only for real scope or product decisions

## Current shipped boundary

This pi wrapper assumes you already have a target spec path.

It does not recreate the original inline CREATE/bootstrap flow inside the orchestrator.
If you need a brand-new spec, create it first with the repository's normal spec workflow, then invoke this wrapper against the resulting spec path.

## Mandatory first actions

1. Start a mux session:

```bash
uv run {{MUX_ROOT}}/tools/session.py "mux-ospec-<topic>"
```

2. Resolve the target spec path.
3. If the target does not exist yet, create the spec first using the repository's canonical spec location and then continue.
4. Create or confirm the sibling stage directory:

```text
<spec>.md
<spec-stages>/001-gather.md
...
<spec-stages>/008-phase_close.md
```

## Runtime differences from the original Claude workflow

Assume all of the following:
- no nested `Skill(...)` or `/skill:` loading inside workers
- no task-notification event loop
- no dedicated ask-user tool
- stage advancement happens only after you inspect the returned worker output plus the report/signal files

So do not try to recreate the original background notification choreography. Run one worker or wave, wait for the result, verify it, and then move to the next stage.

## Authoritative state model

For a phase spec, the authoritative state lives in two places:
- the phase spec itself
- the sibling `-stages/` directory

Use this default stage set unless the spec explicitly overrides it:
1. `001 GATHER`
2. `002 SUCCESS_CRITERIA`
3. `003 PLAN`
4. `004 IMPLEMENT`
5. `005 REVIEW_FIX`
6. `006 TEST`
7. `007 DOCUMENT`
8. `008 PHASE_CLOSE`

Update the current stage artifact first, then the phase file's progress section, then any roadmap-level mirror that references the phase.

## Bundled references

When you need the underlying spec workflow rules, use the bundled assets from this package:
- `../../assets/agents/spec/`
- `../../assets/scripts/spec-resolver.sh`
- `../../assets/scripts/external-specs.sh`
- `../../assets/scripts/lib/config-loader.sh`
- `../../assets/scripts/lib/source-helpers.sh`

Those files are the source of truth for stage semantics. This skill owns the orchestration and stage gating around them.

## Stage execution pattern

### 1. GATHER
- Inspect only the sources needed to lock the phase boundary.
- Use `subagent.parallel` for pure inventory or research when file ownership is disjoint.
- Record both gathered evidence and consolidated findings in `001-gather.md`.

### 2. SUCCESS_CRITERIA
- Convert the gathered evidence into an explicit evaluation contract.
- Record the exact shipped, deferred, blocked, or validation expectations in `002-success_criteria.md`.
- Continue autonomously unless the criteria expose a genuine scope or product ambiguity.

### 3. PLAN
- Launch a fresh planning worker.
- Produce a file-by-file implementation and validation plan.
- Record the approved plan in `003-plan.md` before editing code.

### 4. IMPLEMENT
- Launch a fresh implementation worker.
- Split large phases into bounded waves by package or file cluster.
- Keep shared surfaces serialized.
- Record concrete outputs and changed files in `004-implement.md`.

### 5. REVIEW / FIX
- Use a separate reviewer worker.
- If review finds issues, launch a fresh fixer worker instead of patching from the same context.
- Record the final verdict, findings, and any fix wave in `005-review_fix.md`.
- Only a real `PASS` advances the phase.

### 6. TEST
- Run direct coordinator verification with the repository's required commands.
- Add phase-specific smoke checks when the phase touches generation, runtime parity, or docs matrices.
- Record commands and objective results in `006-test.md`.

### 7. DOCUMENT
- Update package docs, canonical docs, spec notes, and any roadmap mirror that later phases will rely on.
- Record the documentation outputs in `007-document.md`.

### 8. PHASE_CLOSE
- Verify the acceptance criteria actually hold.
- Record the final verdict, accepted outputs, remaining deferred boundary, and next exact action in `008-phase_close.md`.
- Make the next unblocked phase explicit.

## Worker policy

Use only one worker layer: coordinator -> subagent.

Recommended agent roles when available:
- `scout` for GATHER
- `planner` for PLAN
- `worker` for IMPLEMENT and bounded fix waves
- `reviewer` for REVIEW

If your runtime only exposes a general-purpose worker, keep the same stage loop and specialize the prompt.

Every worker prompt must include:
- the stage objective
- the exact input paths to read first
- a precise report path
- a precise signal path
- the rule to follow `{{MUX_ROOT}}/protocol/subagent.md`
- the rule to return exactly `0` on success

## Verification contract

After every worker or worker wave:

```bash
uv run {{MUX_ROOT}}/tools/verify.py <session-dir> --action summary
uv run {{MUX_ROOT}}/tools/extract-summary.py <report-path>
```

Use `check-signals.py` when you only need an expected-count confirmation.

Do not advance stages on intent alone. Advance only on written artifacts and explicit verification.

## Parallelism policy

Parallelism is safe for:
- research split by package or topic
- read-only review across non-overlapping scopes
- independent documentation drafts

Parallelism is unsafe for:
- two workers editing the same source file
- two workers editing the same phase spec
- shared surfaces such as generator cores, top-level availability docs, or shared runtime packages

When in doubt, serialize.

## Escalation policy

Stay autonomous by default.

Escalate in the main chat only when you hit:
- a real scope trade-off
- a product/UX choice that changes the acceptance criteria
- an external blocker you cannot close from repo evidence and available tools

Use `say` only for short milestone or attention alerts.

## Completion

A phase is complete only when:
- all required stage artifacts are written
- the phase progress section matches those artifacts
- any higher-level roadmap mirror is reconciled
- tests and validation are recorded honestly
- the next exact action is explicit

This skill is intentionally honest about current runtime limits. It preserves the spec-owned stage discipline without pretending that pi has Claude-only nested skill execution or task-notification semantics.
