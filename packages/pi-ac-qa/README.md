# @agentic-config/pi-ac-qa

## Scope
- Package role: ac-qa plugin package
- Topology status: `active`
- Package surface status: `active`
- Current exported pi resources:
  - `ac-qa-browser`
  - `ac-qa-e2e-review`
  - `ac-qa-e2e-template`
  - `ac-qa-gh-pr-review`
  - `ac-qa-playwright-cli`
  - `ac-qa-prepare-app`
  - `ac-qa-test-e2e`

## Current surface
### Shipped generated skill surface
- `ac-qa-browser`
- `ac-qa-e2e-review`
- `ac-qa-e2e-template`
- `ac-qa-gh-pr-review`
- `ac-qa-playwright-cli`
- `ac-qa-prepare-app`
- `ac-qa-test-e2e`

### Shipped shared-runtime-backed surface
- `ac-qa-gh-pr-review` now uses the bundled `@agentic-config/pi-compat` worker-wave helpers for the fixed review-worker fan-out and `AskUserQuestion` for user-confirmed `gh pr review` actions.

### Deferred surface
- None.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `package.json` wires shared compat extensions through `node_modules/@agentic-config/pi-compat/extensions`

## Status signaling
- The full current generated `ac-qa` skill surface now ships from this package.
- `ac-qa-gh-pr-review` now consumes the shared `pi-compat` worker-wave and `AskUserQuestion` foundations instead of a package-local orchestration copy.
- Presence of this package directory does not imply that broader generic nested/background subagent parity is solved repository-wide.
