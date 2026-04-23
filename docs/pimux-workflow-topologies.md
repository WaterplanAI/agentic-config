# pimux workflow topologies

This guide describes tmux-backed workflow surfaces shipped by `@agentic-config/pi-ac-workflow`.

## Naming contract

- canonical shipped IDs: `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`
- user-facing aliases: `mux`, `mux-ospec`, `mux-roadmap`
- package-owned alias skills are trigger shims only; canonical workflow behavior stays in `ac-workflow-*`
- runtime/tooling only: `pimux`
- package-owned `pimux` skill is a trigger shim for the runtime extension, not protocol authority

## At a glance

```text
pimux                     = raw tmux control plane
ac-workflow-mux           = mux-style flow on top of pimux
ac-workflow-mux-ospec     = explicit stage owner on top of pimux
ac-workflow-mux-roadmap   = roadmap -> phase -> stage hierarchy on top of pimux
```

## Topology shapes

```text
pimux
L0 parent
└─ L1 worker

mux / ac-workflow-mux
L0 parent
└─ L1 mux-coordinator
   ├─ L2 scout
   ├─ L2 planner
   └─ L2 worker(s)

mux-ospec / ac-workflow-mux-ospec
L0 parent
└─ L1 stage-owner
   └─ L2 helpers

mux-roadmap / ac-workflow-mux-roadmap
L0 parent
└─ L1 roadmap-coordinator
   └─ L2 phase-owners
      └─ L3 stage-workers
```

## Shared control-plane rules

- parent/child messaging is explicit (`send_message` / `report_parent`)
- reporting is one hop only
- success settles only on terminal report + child exit
- parent defaults to asynchronous supervision (no polling loops)
- default blocked/stuck behavior is user escalation
- `pimux` is runtime only; workflow semantics live in `ac-workflow-*` wrappers and `mux*` aliases only trigger those wrappers
