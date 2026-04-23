# @agentic-config/pi-ac-workflow

## Scope

- exported skills:
  - `ac-workflow-product-manager`
  - `ac-workflow-spec`
  - `ac-workflow-mux`
  - `ac-workflow-mux-ospec`
  - `ac-workflow-mux-roadmap`
  - `ac-workflow-mux-subagent`
  - `pimux` (thin runtime trigger alias)
  - `mux` (thin alias for `ac-workflow-mux`)
  - `mux-ospec` (thin alias for `ac-workflow-mux-ospec`)
  - `mux-roadmap` (thin alias for `ac-workflow-mux-roadmap`)
- package-local extensions:
  - `pimux` (runtime/tooling control plane)
  - `strict-mux-runtime` (strict ledger/runtime guard)

## Naming and runtime boundary

- canonical shipped workflow IDs stay `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`
- user-facing aliases are `mux`, `mux-ospec`, `mux-roadmap`
- package-owned alias skills for `mux`, `mux-ospec`, and `mux-roadmap` are trigger shims only; canonical workflow behavior stays in `ac-workflow-*`
- `pimux` is runtime/tooling only, not a workflow-family wrapper
- the package-owned `pimux` skill is a thin trigger shim for the runtime extension, not protocol authority

## mux-ospec workflow contract

- `full`: `CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL`
- `lean`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION`
- `leanest`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION`

Gate rules:
- first after spawn: do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity
- `GATHER = RESEARCH`
- `CONFIRM_SC` is mandatory before `PLAN`
- only `PASS` advances through REVIEW/TEST/SENTINEL/SELF_VALIDATION
- child bridge notifications are delivered automatically; default pacing is notify-first
- after spawn, do not call `status`, `capture`, `tree`, `list`, or `open` on the happy path; wait for delivered child activity instead
- `status` / `capture` / `tree` / `list` / `open` are recovery-only for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity watchdog
- terminal settlement re-arms exactly one final `pimux status` verification before advancing
- default blocked/stuck behavior escalates to user
- each stage must commit all changed repos with repo-scoped evidence (`repo_scope`, `root_commit`, `spec_commit`)

## Topology quick view

```text
pimux                     L0 -> L1 worker
ac-workflow-mux           L0 -> L1 mux-coordinator -> L2 scout/planner/workers
ac-workflow-mux-ospec     L0 -> L1 stage-owner -> L2 helpers
ac-workflow-mux-roadmap   L0 -> L1 roadmap -> L2 phases -> L3 stages
```

See `docs/pimux-workflow-topologies.md` for full hierarchy and messaging patterns.
