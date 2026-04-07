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

### Shipped protocol / foundation surface
- `ac-workflow-mux-subagent`
- shared mux foundation assets under `assets/mux/`

### Deferred surface
- None.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for shared non-exported helpers copied from the source plugin when wrappers or adapters need bundled support files
- current shared asset trees include `assets/agents/spec/`, `assets/scripts/`, and `assets/mux/`

## Status signaling
- The generated `ac-workflow` skill surface plus the direct package-owned `tmux-agent` migration now ship from this package.
- The package-local `tmux-agent` extension preserves the exact proven `/tmux-agent` command and `tmux_agent` tool logic in a repo-owned, project-agnostic surface instead of relying on a user-global-only install.
- The migrated `ac-workflow-tmux-agent` skill and copied references preserve the same command/tool/bridge/hierarchy/report semantics as the proven global source, with only package-surface naming and ownership wording adjusted.
- The mux family consumes the shared `assets/mux/` foundation and the shipped `ac-workflow-mux-subagent` worker protocol instead of private per-skill copies.
- The generated pi `mux`, `mux-ospec`, and `mux-roadmap` surfaces are honest runtime adaptations: they use one coordinator layer plus synchronous `subagent` waves, not nested skill loading or task notifications.
- The shipped pi `mux-ospec` wrapper assumes an existing spec path, and the shipped pi `mux-roadmap` wrapper assumes an already-structured roadmap with a live `## Implementation Progress` mirror; neither wrapper recreates the original Claude bootstrap/flag surface inside pi.
- Presence of this package directory does not imply that the broader repository has no remaining deferred work in other plugin families or in broader generic subagent/runtime parity.
