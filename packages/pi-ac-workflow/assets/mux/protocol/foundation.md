# pi-adapted mux foundation

This document is the shared foundation contract for the pi mux family.

## Locked runtime assumptions
- Session state lives under project-local `tmp/mux/<session>/`.
- Completion signals are explicit files under `.signals/`; they are not implied by worker chat output.
- Report files are the authoritative worker artifact.
- Coordinator depth stays at one worker layer: coordinator -> subagent.
- User approvals happen in the main chat when a real product or scope decision appears.
- Voice alerts use the current runtime `say` tool when a later orchestrator explicitly asks for them.

## Shared helper entry points
- `../../assets/mux/tools/session.py`
- `../../assets/mux/tools/ledger.py`
- `../../assets/mux/tools/signal.py`
- `../../assets/mux/tools/check-signals.py`
- `../../assets/mux/tools/verify.py`
- `../../assets/mux/tools/extract-summary.py`
- `../../assets/mux/tools/agents.py`
- `../../assets/mux/tools/deactivate.py`

## Authoritative persisted ledger (Phase 002 minimum)
Ledger location: `<session_dir>/.mux-ledger.json`

Required fields:
- `session_id`, `phase_id`, `stage_id`, `wave_id`
- `control_state`
- `declared_dispatch` `{worker_type, objective, scope, report_path, signal_path, expected_artifacts, no_nested_subagents}` where `report_path` and `signal_path` are project-root-relative artifact paths.
- `prerequisites` `{required, missing, status}`
- `verification` `{status, checked_artifacts, summary_path, verified_at}` where `checked_artifacts` records only concrete validated artifact descriptors (report/signal/summary paths), and `summary_path` is project-root-relative.
- `blocker` `{active, reason, missing_prerequisites, opened_at, cleared_at}` where `missing_prerequisites` may contain unresolved prerequisite identifiers and/or missing evidence descriptors.
- `recovery` `{required, trigger, plan, started_at, completed_at}`
- `transition_history[]` `{from, to, reason, actor, timestamp}`

## Legal control-plane transitions
The shared ledger enforces these transitions:
- `LOCK -> RESOLVE`
- `RESOLVE -> DECLARE`
- `DECLARE -> DISPATCH`
- `DISPATCH -> VERIFY`
- `VERIFY -> ADVANCE | BLOCK | RECOVER`
- `BLOCK -> RESOLVE`
- `RECOVER -> RESOLVE`

## Gate semantics
- `DECLARE -> DISPATCH` requires schema-valid `declared_dispatch` including explicit `no_nested_subagents=true`.
- `verify.py --action gate` drives `DISPATCH -> VERIFY -> ADVANCE | BLOCK | RECOVER` from persisted evidence.
- `extract-summary.py --evidence --evidence-path <path>` is the machine-readable summary-evidence producer consumed by gate checks.
- Missing report/signal/summary evidence yields `BLOCK`.
- Inconsistent or protocol-invalid evidence yields `RECOVER`.

## Strict runtime activation
- The workflow package-local strict runtime extension activates only for explicit `session.py --strict-runtime --session-key <key>` sessions.
- Activation artifacts:
  - session-local `<session_dir>/.mux-runtime.json`
  - session-key registry `outputs/session/mux-runtime/<session-key-hash>.json`
- The legacy `mux-active` marker remains observability-only; it is not the strict runtime trigger by itself.
- `deactivate.py --session-key <key>` removes the strict activation artifacts for the current pi session.

## Artifact path base rule
- Persisted mux artifact paths are interpreted as project-root-relative unless explicitly absolute.
- The contract requires declared dispatch `report_path` / `signal_path` to be project-root-relative.
- Worker reports and summary-evidence artifacts should use project-root-relative paths so verification stays deterministic across sessions.

## Shipped Phase 004 runtime boundary
- The package-local `strict-mux-runtime` extension consumes the strict activation artifacts plus this persisted ledger contract to enforce fail-closed coordinator behavior.
- Strict Phase 004 dispatch supports one authoritative declared dispatch at a time; ambiguous `subagent.tasks` / `subagent.chain` launches remain out of scope and should fail closed under strict mode.
- Strict Phase 004 coordinator mutation allowance stays narrow and orchestration-focused; later phases own the canonical strict mux skill-family alignment.

## Boundary for later phases
- This foundation does not claim automatic task-notification support.
- This foundation does not claim nested skill loading inside workers.
- Phase 004 now ships the package-local strict runtime seam, but later phases still own strict mux skill hardening, transcripts/checklists, and final release-surface alignment.
- Later phases should consume this asset root and protocol, not recreate local copies of the same helpers.
