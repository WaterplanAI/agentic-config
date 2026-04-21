# extensions

Shared pi extensions exported by `@agentic-config/pi-compat`.

## Current extension set
- `ask-user/`
  - `index.js`: registers the shared `AskUserQuestion` compat tool
  - `runtime.js`: argument normalization plus interactive/non-interactive prompt execution
  - `tests/`: package export/import coverage and prompt-behavior validation
- `hook-compat/`
  - `index.js`: extension entrypoint plus registration helper exports
  - `registry.js`: runtime-scoped registration store with package-id dedupe
  - `payload.js`: locked compat payload mapping, including `NotebookEdit`
  - `matchers.js`: `*`, alternation, and suffix-wildcard matcher evaluation
  - `env.js`: `CLAUDE_*` env construction and spawn-cwd normalization
  - `runner.js`: `uv run --no-project --script` execution and stdout parsing
  - `decision.js`: allow/deny/ask/no-decision semantics
  - `runtime.js`: ordered `tool_call` chain orchestration
  - `tests/`: package surface, mapping/matcher, and representative runtime validation
- `notebook-edit/`
  - `index.js`: registers the shared `NotebookEdit` compat tool
  - `runtime.js`: notebook argument normalization, targeted cell updates, and serialized file writes
  - `tests/`: package export/import coverage and notebook-edit validation
- `_shared/`
  - `install-guard.js`: once-per-runtime registration guard shared by the compat extensions

This shared foundation backs the package-local hook registrations shipped in `pi-ac-audit`, `pi-ac-git`, `pi-ac-safety`, and `pi-ac-tools`, and it gives later generated wrappers a reusable `AskUserQuestion` / `NotebookEdit` surface through the existing `node_modules/@agentic-config/pi-compat/extensions` package wiring. The shared worker-wave helper assets for later IT003 ports live separately under `node_modules/@agentic-config/pi-compat/assets/orchestration/`.
