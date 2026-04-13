# @agentic-config/pi-compat

## Scope
- Package role: shared compatibility package
- Package topology status: `active`
- Current capability state: `interactive-notebook-and-worker-wave-runtime-foundation`

## Current exported surface
- Shared extension runtimes under `extensions/`
  - `hook-compat/` — shared compat pre-tool hook runtime plus registration helpers
  - `ask-user/` — shared `AskUserQuestion` compat tool for confirmations, selections, and short text answers
  - `notebook-edit/` — shared `NotebookEdit` compat tool for targeted `.ipynb` cell-source edits
- Shared package assets under `assets/`
  - `orchestration/` — bounded worker-wave helper surface on top of the runtime `subagent` tool
  - `orchestration/protocol/worker.md` — locked worker contract for result-writing workers
  - `orchestration/tools/write-result.js` — deterministic worker-result JSON writer
  - `orchestration/tools/summarize-results.js` — ordered result validation and summarization helper
- Importable helper export:
  - `@agentic-config/pi-compat/extensions/hook-compat`
  - named helpers: `registerHookCompatPackage(pi, registration)` and `listRegisteredHookCompatPackages(pi)`
- Foundation modules for:
  - hook matcher evaluation
  - compat payload mapping
  - compatibility env construction
  - hook script execution (`uv run --no-project --script`)
  - decision handling (`allow`, `deny`, `ask`, no decision)
  - interactive user-decision fallbacks and notebook-edit serialization
  - synchronous worker-wave result normalization and ordered summary validation

## Compatibility boundary
- This package ships the shared compat substrate used by the current package-local registrations in:
  - `pi-ac-audit`
  - `pi-ac-git`
  - `pi-ac-safety`
  - `pi-ac-tools`
- The shared `AskUserQuestion` and worker-wave foundations are now also consumed directly by shipped generated skills in:
  - `pi-ac-git`
  - `pi-ac-qa`
- Shared runtime additions intentionally stay narrow in the current shipped surface:
  - `AskUserQuestion` for explicit approval/selection/input gates
  - `NotebookEdit` for targeted notebook cell-source updates
  - worker-wave orchestration helpers for synchronous single-worker and parallel-worker waves
- Deferred surfaces remain out of scope here:
  - generic nested/background `Task` / subagent runtime primitives beyond the worker-wave helper surface
  - mux hooks and mux session/signal protocol
- Package-local guard consumers such as `playwright-guardian.py` and `gsuite-public-asset-guard.py` ship on top of this shared runtime without becoming shared compat primitives themselves.

## Layout conventions
- `extensions/` for shared pi extensions exported by this package
- `extensions/hook-compat/` for the shared hook adapter modules and tests
- `extensions/ask-user/` for the shared interactive prompt tool
- `extensions/notebook-edit/` for the shared notebook edit tool
- `assets/orchestration/` for the bounded shared worker-wave helper surface consumed through bundled package paths
- `README.md` as the package status and boundary surface

## Validation commands
```bash
node --test packages/pi-compat/extensions/hook-compat/tests/*.test.js
node --test packages/pi-compat/extensions/ask-user/tests/*.test.js
node --test packages/pi-compat/extensions/notebook-edit/tests/*.test.js
node --test packages/pi-compat/assets/orchestration/tests/*.test.js
```

Current automated coverage includes hook registration/runtime behavior, explicit `NotebookEdit` payload mapping, packaged dry-run + write-scope notebook coverage, packaged `playwright-cli` safety coverage, `AskUserQuestion` interactive/non-interactive behavior, notebook cell update/append behavior, deterministic worker-result writing, ordered summary validation, representative `worktree`-style mixed success/warn waves, representative `gh-pr-review`-style fail detection, and package export/import smoke checks.
