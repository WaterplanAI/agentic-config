# extensions

Package-local pi extensions exported by `@agentic-config/pi-ac-workflow`.

## Current extension set
- `pimux/`
  - `index.ts`: repo-owned migration of the local pimux runtime
  - authoritative runtime for generated mux-family skills (`ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`)
  - also covers generic long-lived non-mux tmux hierarchies in the shipped pi workflow surface
  - preserves explicit bridge messaging, authority binding, settlement, session-scoped supervision, nested hierarchy safety checks, and a fail-closed parent control-plane lock for explicit mux-family wrapper turns
  - exposes `/pimux unlock` to release that parent lock and restore the prior tool surface when the wrapper run is intentionally finished or aborted
- `strict-mux-runtime/`
  - `index.js`: workflow-owned strict mux runtime guard for deliberately activated strict sessions
  - activates only after `assets/mux/tools/session.py --strict-runtime` writes the session-key-scoped activation artifacts for the current pi session
  - consumes the shared mux ledger/gate substrate to fail closed on missing/invalid strict runtime state, validate the single declared strict `subagent` dispatch shape, and block coordinator-side mutations outside bounded orchestration paths

The current workflow package now ships both package-local workflow extensions above.

For the user-facing topology guide and naming contract (`ac-workflow-*` canonical IDs with `mux*` aliases, runtime-only `pimux`), see [../README.md](../README.md) and [../../../docs/pimux-workflow-topologies.md](../../../docs/pimux-workflow-topologies.md).
