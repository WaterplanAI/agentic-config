# @agentic-config/pi-all

## Scope
- Package role: umbrella package
- Topology status: `active`
- Current exported pi resources: aggregation of the current shipped package set through bundled dependencies
- Package-local first-party resources: none

## What this package aggregates today
`@agentic-config/pi-all` is the one-shot install surface for the current shipped pi package set.

It aggregates:
- `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-audit`
- `@agentic-config/pi-ac-git`
- `@agentic-config/pi-ac-meta`
- `@agentic-config/pi-ac-qa`
- `@agentic-config/pi-ac-safety`
- `@agentic-config/pi-ac-tools`
- `@agentic-config/pi-ac-workflow`

Current aggregated shipped surface:
- `42` namespaced skills across the plugin packages
- shared `hook-compat`, `AskUserQuestion`, `NotebookEdit`, and worker-wave orchestration support via `@agentic-config/pi-compat`
- package-level hook-backed parity registrations from the shipped audit/git/safety/tools subset
- shared mux foundation assets plus the shipped `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`, and `ac-workflow-mux-subagent` surfaces in `@agentic-config/pi-ac-workflow`
- package-owned `pimux` runtime authority for tmux-backed workflow orchestration in `@agentic-config/pi-ac-workflow`

The shipped pi mux family is an honest adaptation, not a mechanical clone of the source orchestration prompts: `mux-ospec` and `mux-roadmap` pass explicit paths through unchanged, auto-derive/create the next current-branch spec path from sufficient inline prompts, and reserve `AskUserQuestion` for missing spawn input.

This package does **not** add its own skills or extensions. It exposes the shipped package set from `node_modules/...` paths so teams can install the current surface in one step.

## When to choose `pi-all`
Choose `@agentic-config/pi-all` when you want the full shipped surface.

Choose per-plugin packages instead when you want:
- tighter project scope
- smaller team package lists
- explicit plugin-by-plugin rollout
- package-level control over partial/deferred surfaces

## Install
### One-shot manual install
```bash
pi install npm:@agentic-config/pi-all@0.2.6
```

### Recommended team adoption with committed `.pi/settings.json`
```json
{
  "packages": [
    "npm:@agentic-config/pi-all@0.2.6"
  ]
}
```

Committed `.pi/settings.json` is the preferred team path because pi can auto-install missing packages on startup and keep every teammate on the same package set.

## How this relates to the generated-wrapper strategy
The current package set is mostly Option C canonical-source + generated-wrapper, with package-owned workflow runtime surfaces under `@agentic-config/pi-ac-workflow` centered on `pimux`.

In this package, that means:
- the aggregated generated skill outputs still come from `canonical/`
- the aggregated package set should be treated as generated-first plus package-owned `pimux` workflow runtime surfaces
- hook-backed parity still comes from the bundled package-local registrations plus `@agentic-config/pi-compat`
- current gaps stay explicit instead of being hidden behind the umbrella package name

This package does **not** imply:
- full generic `Task` / subagent runtime is solved as a shared compat primitive
- every marketplace surface already has full pi parity

## Explicit deferred boundary
Still explicitly deferred in the current shipped surface:
- broader generic nested/background `Task` / subagent runtime primitives beyond the shared `AskUserQuestion` + `NotebookEdit` + worker-wave foundation and the shipped package-owned `pimux` workflow runtime

## Roadmap evidence
The roadmap evidence artifact is:

- [`.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md`](../../.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md)

Use `packages/README.md`, the package-level README surfaces, and the roadmap `## Implementation Progress` section as the current package-level evidence set.
