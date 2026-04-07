# @agentic-config/pi-ac-safety

## Scope
- Package role: ac-safety plugin package
- Topology status: `active`
- Package surface status: `active`
- Current exported pi resources:
  - `ac-safety-configure-safety`
  - `ac-safety-harden-supply-chain-sec`

## Current surface
### Shipped generated skill surface
- `ac-safety-harden-supply-chain-sec`

### Shipped adapter-backed surface
- `ac-safety-configure-safety`
- credential guardian parity
- destructive bash guardian parity
- supply-chain guardian parity
- write-scope guardian parity
- playwright guardian parity for the current Bash-based `playwright-cli` surface

### Deferred surface
- External raw-tool host adoption outside the active pi/Claude runtime remains out of scope for this package. This matches the current Claude-package scope: hooks enforce the host runtime's own tool surfaces, not arbitrary external executors.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for bundled config defaults and guardian scripts consumed through the shared compat adapter
- `package.json` wires shared compat extensions through `node_modules/@agentic-config/pi-compat/extensions`

## Status signaling
- This package now ships the generated safety configuration surface, the generated `ac-safety-harden-supply-chain-sec` skill, and the current guardian parity surface through the shared `pi-compat` adapter.
- The shipped Playwright guardian parity enforces the configured allowlist/blocklist policy on the current `playwright-cli` Bash surface; it does not introduce a first-party browser tool of its own.
- External raw-tool endpoint adoption is follow-up hardening, not part of the current Claude-parity completion claim.
- Presence of this package directory does not imply that broader generic nested/background subagent parity is solved repository-wide.
