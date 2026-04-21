# @agentic-config/pi-ac-git

## Scope
- Package role: ac-git plugin package
- Topology status: `active`
- Package surface status: `active`
- Current exported pi resources:
  - `ac-git-branch`
  - `ac-git-gh-assets-branch-mgmt`
  - `ac-git-git-find-fork`
  - `ac-git-git-safe`
  - `ac-git-pull-request`
  - `ac-git-release`
  - `ac-git-worktree`

## Current surface
### Shipped generated skill surface
- `ac-git-branch`
- `ac-git-gh-assets-branch-mgmt`
- `ac-git-git-find-fork`
- `ac-git-git-safe`
- `ac-git-pull-request`
- `ac-git-release`
- `ac-git-worktree`

### Shipped adapter-backed surface
- package-level git commit guard parity via `git-commit-guard.py` and `@agentic-config/pi-compat`
- shared worker-wave environment orchestration for `ac-git-worktree` via `@agentic-config/pi-compat`

### Deferred surface
- None.

## Layout conventions
- `skills/` for exported pi skills using namespaced `<plugin>-<resource>` identifiers
- `extensions/` for package-local pi extensions and wiring
- `README.md` as the current package-status surface
- `assets/` subdirectories for shared non-exported helpers copied from the source plugin when wrappers or adapters need bundled support files
- `package.json` wires shared compat extensions through `node_modules/@agentic-config/pi-compat/extensions`

## Status signaling
- The full current generated `ac-git` skill surface now ships from this package.
- `ac-git-worktree` now uses the bundled branch/spec bootstrap helpers plus the shared `pi-compat` worker-wave foundation instead of a package-local orchestration copy.
- Package-level commit-guard parity now ships through the shared `pi-compat` adapter using the bundled script copy under `assets/`.
- Presence of this package directory does not imply that the broader repository has no remaining deferred work in other plugin families or in generic runtime parity.
