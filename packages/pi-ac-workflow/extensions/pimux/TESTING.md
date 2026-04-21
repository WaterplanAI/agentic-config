# pimux testing and latest validated results

This document records the test surfaces we use for the local `pimux` extension and the latest validated outcomes from the nested routing and settlement hardening work.

## Automated test command

Primary regression command:

```text
pytest -q tests/test_pimux_*.py
```

Latest observed result:

- Date: 2026-04-13
- Result: `44 passed in 2.29s`
- Notes: includes the wrapper clean-exit guidance follow-up checks

## Automated test coverage

The current pytest surface covers these areas:

- `tests/test_pimux_render.py`
  - parent-to-child payload rendering
  - parent report formatting and settlement presentation
- `tests/test_pimux_registry.py`
  - registry persistence
  - manifest writes
  - queued update safety around concurrent mutation paths
- `tests/test_pimux_runtime_surface.py`
  - runtime command surface
  - nested descendant termination hooks
  - shutdown-request handling
- `tests/test_pimux_file_queue_surface.py`
  - file-scoped queued mutation helper behavior
- `tests/test_pimux_prune_navigation.py`
  - prune and navigation surface behavior
- `tests/test_pimux_settlement.py`
  - bridge settlement classification
- `tests/test_pimux_authority.py`
  - authoritative child binding rules
- `tests/test_pimux_notification_surface.py`
  - notification surface behavior
- `tests/test_pimux_skill_surface.py`
  - skill and command-surface expectations

## Focused targeted reruns used during implementation

During the fix cycle, these narrower commands were also used before the full regression pass:

```text
pytest -q tests/test_pimux_runtime_surface.py tests/test_pimux_render.py tests/test_pimux_registry.py tests/test_pimux_file_queue_surface.py tests/test_pimux_prune_navigation.py
```

Latest observed result for that targeted subset:

- Date: 2026-04-13
- Result: `23 passed in 0.75s`

## Live validation scenarios

In addition to pytest, the extension was validated with real headless `pimux` agents.

### 1. Exact payload fidelity

Goal:

- confirm that parent-to-child delivery preserves the raw payload text without wrapper corruption

Observed validation:

- sent payload: `exact-token:alpha-123`
- child progress: `seen:exact-token:alpha-123`
- child closeout: `done:exact-token:alpha-123`
- settlement: `settled_completion`

### 2. Full nested live smoke

A fresh root-session smoke run validated four scenarios with deterministic IDs under the prefix `root-smoke-20260413-*`.

Latest observed result:

- Date: 2026-04-13
- Commit: `66ebaab`
- Overall verdict: PASS

Scenarios:

1. Happy path nested L0 -> L1 -> L2 routing
   - exact payload fidelity preserved across hops
   - target agents settled `settled_completion`
2. Blocker path
   - intentional blocker leaf settled `settled_blocked`
3. Protocol-violation path
   - killed pre-terminal leaf settled `protocol_violation`
4. Cascade-kill path
   - killing the parent also terminated the descendant child
   - descendant observed a `shutdown_request` with the ancestor-kill reason

## Current expectations for changes in this extension

When modifying files under `packages/pi-ac-workflow/extensions/pimux/` (or the project-local shim at `.pi/extensions/pimux/index.ts`), the minimum expected validation is:

1. run the focused tests relevant to the changed surface
2. run the full regression command
3. if the change touches routing, settlement, shutdown, or nested orchestration behavior, run at least one real live smoke scenario with headless agents
4. record any important new runtime findings in a local `tmp/` artifact during investigation, then update this document if the persistent validation story changes

## Wrapper clean-exit guidance

The latest fresh full smoke confirmed the target routing and settlement behaviors, but some scenario wrapper agents were manually torn down after the leaf verdicts were captured. That means a wrapper agent for a scenario may still show `protocol_violation` even when the intended leaf-level assertion passed.

Use this mapping going forward so wrappers exit cleanly whenever the wrapper itself is not the thing being killed for the test:

- all direct children `settled_completion` -> wrapper emits `closeout`
- any direct child `settled_waiting_on_parent` -> wrapper emits `question`
- any direct child `settled_blocked` -> wrapper emits `blocker`
- any direct child `settled_failure` or `protocol_violation` -> wrapper emits `failure`

For cascade-kill validation, let a supervising wrapper kill a disposable parent/descendant pair and verify the descendant shutdown, then let the wrapper itself exit cleanly.
