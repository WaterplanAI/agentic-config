# hook-compat

Shared hook-adapter foundation for `@agentic-config/pi-compat`.

## Purpose
- Provide one compat-owned runtime for Claude-style pre-tool hook scripts.
- Keep matcher parsing, payload mapping, env normalization, script execution, and decision handling centralized.
- Expose a registration helper for package-local wiring.

## Public surface
- Extension entrypoint: `packages/pi-compat/extensions/hook-compat/index.js`
  - default export when importing `@agentic-config/pi-compat/extensions/hook-compat`
- Registration helper export: `@agentic-config/pi-compat/extensions/hook-compat`
  - `registerHookCompatPackage(pi, registration)`
  - `listRegisteredHookCompatPackages(pi)`

## Registration shape
```js
import { registerHookCompatPackage } from "@agentic-config/pi-compat/extensions/hook-compat";

export default function registerGitCompat(pi) {
  registerHookCompatPackage(pi, {
    packageId: "@agentic-config/pi-ac-git",
    pluginRoot: "/absolute/path/to/plugin-root",
    askFallback: {
      nonInteractive: "deny", // default
    },
    hooks: [
      {
        matcher: "Bash",
        hooks: [
          {
            id: "git-commit-guard",
            scriptPath: "scripts/hooks/git-commit-guard.py",
            timeoutMs: 5000,
            failureMode: "fail-close", // or "fail-open"
            env: {
              EXTRA_FLAG: "1",
            },
          },
        ],
      },
    ],
  });
}
```

## Locked pi-to-Claude payload mapping
| pi tool | Claude `tool_name` | Mapping |
|---|---|---|
| `read` | `Read` | `input.path -> tool_input.file_path` |
| `grep` | `Grep` | preserve `pattern`, `path`, `glob` |
| `find` | `Glob` | preserve `pattern`, `path` |
| `write` | `Write` | `input.path -> tool_input.file_path` |
| `edit` | `Edit` | `input.path -> tool_input.file_path` |
| `bash` | `Bash` | preserve `command` (and optional `timeout`) |
| `NotebookEdit` | `NotebookEdit` | `input.path -> tool_input.notebook_path` when needed; preserve notebook-specific fields |

## Runtime behavior
- Ordered execution is deterministic within each pi runtime by registration order.
- For each matched hook:
  - `allow`: continue
  - `deny`: block immediately
  - `ask`: use UI confirmation when available; otherwise block by default
  - no `permissionDecision`: continue (side-effects and optional `systemMessage` are valid)
- Script execution uses:
  - `uv run --no-project --script <scriptPath>`
  - `cwd = ctx.cwd`
  - `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR`, `CLAUDE_SESSION_ID`
- Adapter-layer failures follow each hook's `failureMode` (`fail-open` or `fail-close`).

## Validation
Run the current validation suites:

```bash
node --test packages/pi-compat/extensions/hook-compat/tests/*.test.js
node --test packages/pi-compat/extensions/notebook-edit/tests/*.test.js
```

The hook-compat suite currently covers:
- package export/import wiring through the package `exports` map
- runtime-object scoping and shutdown cleanup
- malformed `hookSpecificOutput` handling without premature user notification
- locked pi-to-Claude mapping and matcher behavior, including explicit `NotebookEdit` mapping
- representative deny, ask, ordered-chain, side-effect/systemMessage, fail-open/fail-close, and malformed-decision runtime scenarios
- packaged asset-root registrations for `pi-ac-audit`, `pi-ac-git`, `pi-ac-safety`, and `pi-ac-tools`
- packaged dry-run and write-scope coverage for notebook-edit events
- packaged `playwright-cli` allow/block coverage for `pi-ac-safety`

## Current shipped consumers
- `pi-ac-audit` — `tool-audit.py`
- `pi-ac-git` — `git-commit-guard.py`
- `pi-ac-safety` — credential/destructive-bash/supply-chain/write-scope/playwright guardians
- `pi-ac-tools` — `dry-run-guard.py` plus `gsuite-public-asset-guard.py`

## Current limits
- Plugin packages should import the named helper surface for registration and treat the default export as the shared extension entrypoint already loaded through the package manifest.
- Deferred surfaces remain explicit: generic subagent/runtime orchestration and mux hooks.
