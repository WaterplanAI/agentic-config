# mux foundation assets

This tree is the shared mux runtime substrate for canonical `ac-workflow` mux surfaces.

## Purpose
- keep session/signal/report helpers in one package-owned location
- give pi and Claude mux surfaces one stable asset root
- let later mux orchestrators consume shared protocol docs instead of inventing local copies

## Layout
- `tools/` — session, signal, ledger, verification, and bounded-summary helpers
- `subagent-hooks/` — subagent-only hook guards for harnesses that support skill-scoped hooks
- `protocol/` — pi-adapted foundation and worker-protocol reference docs

## Shared protocol-state ledger
- Authoritative session-local ledger file: `<session_dir>/.mux-ledger.json`
- Owner tool: `tools/ledger.py`
- Session bootstrap (`tools/session.py`) initializes the ledger with Phase 002 minimum schema:
  - `session_id`, `phase_id`, `stage_id`, `wave_id`, `control_state`
  - `declared_dispatch`, `prerequisites`, `verification`, `blocker`, `recovery`
  - append-only `transition_history` records `{from, to, reason, actor, timestamp}`
- Persisted artifact paths (`report_path`, `signal_path`, summary evidence paths) are project-root-relative.
- `verification.checked_artifacts` records concrete artifact descriptors only (no sentinel markers).
- `blocker.missing_prerequisites` may include missing prerequisite identifiers and missing evidence descriptors.

## Gate helpers
- `tools/verify.py --action gate` consumes the declared dispatch + persisted prerequisites and writes verification/blocker/recovery outcomes through the shared ledger.
- `tools/extract-summary.py --evidence --evidence-path <path>` emits machine-readable summary evidence for gate checks.
- Existing signal summary/count actions remain available for smoke-flow compatibility.

## Phase boundary
- This asset root now owns shared protocol-state and gate helper behavior.
- Runtime fail-closed enforcement of coordinator behavior remains Phase 004 scope.

## Current rendered root
- `../../assets/mux`

The generator resolves `../../assets/mux` per harness so wrappers can reference one logical foundation root while the copied assets land in the correct package or plugin path for the current render.
