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
- `declared_dispatch` `{worker_type, objective, scope, report_path, signal_path, expected_artifacts, no_nested_subagents}`
- `prerequisites` `{required, missing, status}`
- `verification` `{status, checked_artifacts, summary_path, verified_at}`
- `blocker` `{active, reason, missing_prerequisites, opened_at, cleared_at}`
- `recovery` `{required, trigger, plan, started_at, completed_at}`
- `transition_history[]` `{from_state, to_state, reason, actor, timestamp}`

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

## Boundary for later phases
- This foundation does not claim automatic task-notification support.
- This foundation does not claim nested skill loading inside workers.
- This foundation does not claim generic shared runtime parity beyond the mux-specific file/session protocol described here.
- Phase 004 owns fail-closed runtime enforcement of coordinator behavior from this persisted ledger contract.
- Later phases should consume this asset root and protocol, not recreate local copies of the same helpers.
