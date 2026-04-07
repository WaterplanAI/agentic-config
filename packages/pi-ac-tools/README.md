# @agentic-config/pi-ac-tools

## Scope
- Package role: ac-tools plugin package
- Topology status: `active`
- Package surface status: `active`
- Current exported pi resources:
  - `ac-tools-ac-issue`
  - `ac-tools-adr`
  - `ac-tools-agentic-export`
  - `ac-tools-agentic-import`
  - `ac-tools-agentic-share`
  - `ac-tools-cpc`
  - `ac-tools-dr`
  - `ac-tools-dry-run`
  - `ac-tools-gcp-setup`
  - `ac-tools-gsuite`
  - `ac-tools-had`
  - `ac-tools-human-agentic-design`
  - `ac-tools-improve-agents-md`
  - `ac-tools-milestone`
  - `ac-tools-setup-voice-mode`
  - `ac-tools-single-file-uv-scripter`
  - `ac-tools-video-query`

## Current surface
### Shipped generated skill surface
- `ac-tools-ac-issue`
- `ac-tools-adr`
- `ac-tools-agentic-export`
- `ac-tools-agentic-import`
- `ac-tools-agentic-share`
- `ac-tools-cpc`
- `ac-tools-gcp-setup`
- `ac-tools-gsuite`
- `ac-tools-had`
- `ac-tools-human-agentic-design`
- `ac-tools-improve-agents-md`
- `ac-tools-milestone`
- `ac-tools-setup-voice-mode`
- `ac-tools-single-file-uv-scripter`
- `ac-tools-video-query`

### Shipped adapter-backed surface
- `ac-tools-dry-run`
- `ac-tools-dr`
- dry-run guard parity via `dry-run-guard.py` and `@agentic-config/pi-compat`
- GSuite public-share protection via `gsuite-public-asset-guard.py` and `@agentic-config/pi-compat`

### Deferred surface
- none

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for shared non-exported helpers copied from the source plugin when wrappers or adapters need bundled support files
- `package.json` wires shared compat extensions through `node_modules/@agentic-config/pi-compat/extensions`

## Status signaling
- The current generated `ac-tools` skill surface now ships from this package, including `gcp-setup`, `gsuite`, and `setup-voice-mode`.
- Dry-run parity still ships through the shared `pi-compat` adapter using the bundled `dry-run-guard.py` copy under `assets/`, including `NotebookEdit` coverage through the shared compat tool surface.
- GSuite public-share protection now also ships through the bundled `gsuite-public-asset-guard.py` registration.
- Presence of this package directory does not imply that the broader repository has no remaining deferred work in other plugin families.
