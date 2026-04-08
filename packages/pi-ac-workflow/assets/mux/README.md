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

## Strict runtime activation
- `tools/session.py --strict-runtime --session-key <key>` writes explicit strict-runtime activation artifacts for the current pi session.
- Session-local activation file: `<session_dir>/.mux-runtime.json`
- Session-key registry file: `outputs/session/mux-runtime/<session-key-hash>.json`
- Those artifacts are the package-local runtime extension handoff for strict sessions.
- The legacy `mux-active` marker remains observability-only and is not the strict runtime trigger by itself.
- `tools/deactivate.py --session-key <key>` removes the strict activation artifacts so strict enforcement does not leak after an explicit mux shutdown.

## Gate helpers
- `tools/verify.py --action gate` consumes the declared dispatch + persisted prerequisites and writes verification/blocker/recovery outcomes through the shared ledger.
- `tools/extract-summary.py --evidence --evidence-path <path>` emits machine-readable summary evidence for gate checks.
- Existing signal summary/count actions remain available for smoke-flow compatibility.

## Runtime boundary
- Shared assets own protocol-state and gate-helper behavior.
- The workflow package-local `strict-mux-runtime` extension consumes the strict activation artifacts plus the shared ledger to enforce fail-closed coordinator behavior for deliberately activated strict sessions.
- Phase 004 ships the runtime seam only; later IT005 phases still own strict mux skill-family alignment, transcript/checklist artifacts, and final release-surface closeout.

## Current rendered root
- `../../assets/mux`

The generator resolves `../../assets/mux` per harness so wrappers can reference one logical foundation root while the copied assets land in the correct package or plugin path for the current render.
