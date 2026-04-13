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
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/session.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/check-signals.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/verify.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/extract-summary.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/agents.py`
- `${CLAUDE_PLUGIN_ROOT}/mux/tools/deactivate.py`

## Shipped protocol artifact set (Phase 007)
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/subagent.md` — authoritative leaf-worker data-plane contract.
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/guardrail-policy.md` — strict runtime vs hook guard vs protocol prose split.
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-happy-path-transcript.md` — representative strict `ADVANCE` flow.
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-blocker-path-transcript.md` — representative strict `BLOCK` flow.
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-regression-checklist.md` — deterministic checklist for regression validation waves.

## Guardrail ownership boundary
- **Strict runtime (`extensions/strict-mux-runtime/index.js`)**: coordinator-side, opt-in via `session.py --strict-runtime --session-key <key>`, enforces declared dispatch shape and strict orchestration constraints.
- **Subagent hook guard (`subagent-hooks/mux-subagent-guard.py`)**: harness-scoped hook that fail-closes and currently denies `TaskOutput` where skill-scoped hooks are supported.
- **Worker protocol prose (`protocol/subagent.md` + mux-subagent skills)**: data-plane contract requiring report/signal artifacts, exact `0` success response, and no nested `subagent`, control-plane bridge, or `report_parent` usage.

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

## Shipped Phase 004+005+006+007 runtime boundary
- The package-local `strict-mux-runtime` extension consumes the strict activation artifacts plus this persisted ledger contract to enforce fail-closed coordinator behavior.
- Strict Phase 004 dispatch supports one authoritative declared dispatch at a time; ambiguous `subagent.tasks` / `subagent.chain` launches remain out of scope and should fail closed under strict mode.
- Strict Phase 004 coordinator mutation allowance stays narrow and orchestration-focused; Phase 005 hardens `mux-ospec` as the canonical strict consumer.
- Phase 006 aligns sibling `mux` / `mux-roadmap` surfaces to the strict control-plane contract: strict bootstrap (`session.py --strict-runtime --session-key <key>`), declared dispatch plus report/signal/summary evidence gating, `BLOCK` for missing prerequisites/evidence, `RECOVER` for invalid dispatch or inconsistent evidence, and no manual fallback outside protocol.
- Phase 007 ships the guardrail-policy split plus transcript/checklist protocol artifacts for deterministic strict-flow documentation.

## Shared foundation boundary
- This foundation does not claim automatic task-notification support.
- This foundation does not claim nested skill loading inside workers.
- Consumers should consume this asset root and protocol artifacts, not recreate local copies of the same helpers.
- Package/roadmap release-surface bookkeeping consumes this shared foundation but lives in package status surfaces and `.specs` artifacts rather than inside the ledger contract itself.
