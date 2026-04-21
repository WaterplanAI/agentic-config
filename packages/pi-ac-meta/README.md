# @agentic-config/pi-ac-meta

## Scope
- Package role: ac-meta plugin package
- Topology status: `active`
- Package surface status: `shipped-core-surface`
- Current exported pi resources:
  - `ac-meta-hook-writer`
  - `ac-meta-skill-writer`

## Current surface
### Shipped generated skill surface
- `ac-meta-hook-writer`
- `ac-meta-skill-writer`

### Deferred surface
- None.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface

## Status signaling
- The generated `ac-meta` skill surface now ships from this package.
- This package does not imply broader plugin-parity work outside the current shipped surface.
