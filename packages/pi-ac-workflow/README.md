# @agentic-config/pi-ac-workflow

## Scope
- Package role: ac-workflow plugin package
- Topology status: `active`
- Package surface status: `active`
- Current exported pi resources:
  - `ac-workflow-product-manager`
  - `ac-workflow-spec`
  - `ac-workflow-mux`
  - `ac-workflow-mux-ospec`
  - `ac-workflow-mux-roadmap`
  - `ac-workflow-mux-subagent`
  - `ac-workflow-tmux-agent`
  - package-local `tmux-agent` extension
  - package-local `strict-mux-runtime` extension

## Current surface
### Shipped generated skill surface
- `ac-workflow-product-manager`
- `ac-workflow-spec`
- `ac-workflow-mux`
- `ac-workflow-mux-ospec`
- `ac-workflow-mux-roadmap`

### Shipped direct package-owned tmux-agent surface
- `ac-workflow-tmux-agent`
- package-local `tmux-agent` extension under `extensions/tmux-agent/index.ts`
- copied exact reference set under `skills/ac-workflow-tmux-agent/references/`

### Shipped strict mux runtime surface
- package-local `strict-mux-runtime` extension under `extensions/strict-mux-runtime/index.js`
- explicit strict-session activation via `assets/mux/tools/session.py --strict-runtime`
- session-key-scoped strict activation artifacts under `outputs/session/mux-runtime/`
- fail-closed ledger-backed coordinator enforcement for deliberately activated strict sessions only

### Shipped protocol / foundation surface
- `ac-workflow-mux-subagent`
- shared mux foundation assets under `assets/mux/`

### Deferred surface
- Later mux-family strict skill/prompt alignment remains deferred to the IT005 phases after this runtime foundation work.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for shared non-exported helpers copied from the source plugin when wrappers or adapters need bundled support files
- current shared asset trees include `assets/agents/spec/`, `assets/scripts/`, and `assets/mux/`

## Status signaling
- The generated `ac-workflow` skill surface plus the direct package-owned `tmux-agent` migration now ship from this package.
- The package-local `tmux-agent` extension preserves the exact proven `/tmux-agent` command and `tmux_agent` tool logic in a repo-owned, project-agnostic surface instead of relying on a user-global-only install.
- The package-local `strict-mux-runtime` extension keeps strict mux ownership inside the workflow package rather than shifting mux semantics into generic compat hooks or user-global runtime state.
- The strict mux runtime surface activates only for explicit `session.py --strict-runtime` sessions tied to a current pi session key; the legacy `mux-active` marker remains observability-only.
- The strict runtime surface consumes the shared `assets/mux/` ledger/gate substrate, validates one declared strict `subagent` dispatch at a time, and fails closed when strict activation exists but the ledger is missing or invalid.
- The migrated `ac-workflow-tmux-agent` skill and copied references preserve the same command/tool/bridge/hierarchy/report semantics as the proven global source, with only package-surface naming and ownership wording adjusted.
- The mux family consumes the shared `assets/mux/` foundation and the shipped `ac-workflow-mux-subagent` worker protocol instead of private per-skill copies.
- The generated pi `mux`, `mux-ospec`, and `mux-roadmap` surfaces are honest runtime adaptations: they use one coordinator layer plus synchronous `subagent` waves, not nested skill loading or task notifications.
- Phase 004 ships the strict runtime seam only; later Phase 005+ work still owns the canonical strict skill-response alignment for `mux-ospec` and the sibling `mux*` surfaces.
- The shipped pi `mux-ospec` wrapper assumes an existing spec path, and the shipped pi `mux-roadmap` wrapper assumes an already-structured roadmap with a live `## Implementation Progress` mirror; neither wrapper recreates the original Claude bootstrap/flag surface inside pi.
- Presence of this package directory does not imply that the broader repository has no remaining deferred work in other plugin families or in broader generic subagent/runtime parity.
