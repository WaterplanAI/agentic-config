# @agentic-config/pi-ac-audit

## Scope
- Package role: ac-audit plugin package
- Topology status: `active`
- Package surface status: `partial`
- Current exported pi resources:
  - `ac-audit-configure-audit`

## Current surface
### Shipped adapter-backed surface
- `ac-audit-configure-audit`
- tool audit runtime parity via `tool-audit.py` and `@agentic-config/pi-compat`

### Deferred surface
- None.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for bundled config defaults and hook scripts consumed through the shared compat adapter
- `package.json` wires shared compat extensions through `node_modules/@agentic-config/pi-compat/extensions`

## Status signaling
- This package now ships the generated pi-facing audit configuration skill plus package-local audit hook parity through the shared `pi-compat` adapter.
- The shipped runtime parity depends on the bundled `assets/` copy, not on the original source-plugin root.
- Presence of this package directory does not imply broader repository parity beyond the current shipped surface.
