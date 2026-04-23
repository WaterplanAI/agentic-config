# hook-compat

Shared hook-adapter foundation for `@agentic-config/pi-compat`.

## Purpose
- Provide one compat-owned runtime for pre-tool hook scripts.
- Keep matcher parsing, payload mapping, env normalization, script execution, and decision handling centralized.
- Expose registration helpers, direct preflight helpers, and guarded execution wrappers from one package surface.

## Coverage
Hook-compat now covers three entry paths:
- pi `tool_call`
- pi `user_bash` for interactive `!` / `!!`
- direct guarded API/harness wrappers imported from `@agentic-config/pi-compat/extensions/hook-compat`

## Public surface
Import path: `@agentic-config/pi-compat/extensions/hook-compat`

- default export: shared extension entrypoint
- registration helpers:
  - `registerHookCompatPackage(pi, registration)`
  - `listRegisteredHookCompatPackages(pi)`
- direct preflight helpers:
  - `runHookCompatPreflight({ toolName, input, cwd, ctx, runtime, registrations })`
  - `runHookCompatToolCall(event, ctx, options)`
- guarded execution wrappers:
  - `guardedToolExecution(toolName, ...)` for arbitrary/raw tool names
  - `guardedRead(...)`
  - `guardedGrep(...)`
  - `guardedGlob(...)`
  - `guardedBash(...)`
  - `guardedWrite(...)`
  - `guardedEdit(...)`
  - `guardedNotebookEdit(...)`
- direct-wrapper blocked error:
  - `HookCompatGuardBlockedError`

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

## Locked compat payload mapping
| caller tool name | compat `tool_name` | Mapping |
|---|---|---|
| `read` / `Read` | `Read` | `input.path -> tool_input.file_path` |
| `grep` / `Grep` | `Grep` | preserve `pattern`, `path`, `glob` |
| `find` / `glob` / `Glob` | `Glob` | preserve `pattern`, `path` |
| `write` / `Write` | `Write` | `input.path -> tool_input.file_path` |
| `edit` / `Edit` | `Edit` | `input.path -> tool_input.file_path` |
| `bash` / `Bash` | `Bash` | preserve `command` (and optional `timeout`) |
| `NotebookEdit` | `NotebookEdit` | `input.path -> tool_input.notebook_path` when needed; preserve notebook-specific fields |
| raw custom names | unchanged | passthrough `tool_name` + shallow-cloned `tool_input` |

## Runtime behavior
- Ordered execution is deterministic within each pi runtime by registration order.
- For each matched hook:
  - `allow`: continue
  - `deny`: block immediately
  - `ask`: use UI selection when available; otherwise apply `askFallback.nonInteractive`
    - default interactive options: `Allow once`, `Allow for rest of this session`, `Deny`
    - hooks may optionally provide project/user persistence metadata to add `Always allow in this project` and `Always allow from now on`
  - no `permissionDecision`: continue (side-effects and optional `systemMessage` are valid)
- `user_bash` deny paths return a synthetic blocked bash result so pi does not execute the command.
- Script execution uses:
  - `uv run --no-project --script <scriptPath>`
  - `cwd = resolved project dir`
  - `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR`, `CLAUDE_SESSION_ID`
- Adapter-layer failures follow each hook's `failureMode` (`fail-open` or `fail-close`).

## Non-interactive `ask` behavior
- If `ctx.hasUI` is true and `ctx.ui.select(...)` exists, `ask` opens a selection dialog.
- If select is unavailable but `ctx.ui.confirm(...)` exists, hook-compat falls back to a yes/no confirmation dialog.
- Otherwise hook-compat treats `ask` as non-interactive and applies the package registration fallback:
  - `askFallback.nonInteractive: "deny"` blocks by default
  - `askFallback.nonInteractive: "allow"` continues without prompting
- The guarded execution wrappers fail closed by throwing `HookCompatGuardBlockedError` when preflight blocks.

## Wrapping a harness tool
```js
import {
  guardedRead,
  listRegisteredHookCompatPackages,
} from "@agentic-config/pi-compat/extensions/hook-compat";

export async function readWithGuards(path, runtime) {
  const registrations = listRegisteredHookCompatPackages(runtime);

  return await guardedRead({
    path,
    cwd: process.cwd(),
    registrations,
    async execute({ input }) {
      return await rawRead(input.path);
    },
  });
}
```

For raw custom tools such as `mcp__playwright__browser_navigate`, either call `runHookCompatPreflight(...)` directly or use `guardedToolExecution(...)` and pass the custom tool name through unchanged.

```js
import { guardedToolExecution } from "@agentic-config/pi-compat/extensions/hook-compat";

await guardedToolExecution("mcp__playwright__browser_navigate", {
  input: { url: "https://example.com" },
  cwd: process.cwd(),
  registrations,
  async execute({ input }) {
    return await playwrightNavigate(input.url);
  },
});
```

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
- locked compat mapping and matcher behavior, including explicit `NotebookEdit` mapping and raw custom tool passthrough
- direct preflight coverage for packaged safety guards
- representative deny, ask, ordered-chain, side-effect/systemMessage, fail-open/fail-close, `user_bash`, and malformed-decision runtime scenarios
- packaged asset-root registrations for `pi-ac-audit`, `pi-ac-git`, `pi-ac-safety`, and `pi-ac-tools`
- packaged dry-run and write-scope coverage for notebook-edit events
- packaged `playwright-cli` and raw Playwright MCP coverage for `pi-ac-safety`

## Current shipped consumers
- `pi-ac-audit` — `tool-audit.py`
- `pi-ac-git` — `git-commit-guard.py`
- `pi-ac-safety` — credential/destructive-bash/supply-chain/write-scope/playwright guardians
- `pi-ac-tools` — `dry-run-guard.py` plus `gsuite-public-asset-guard.py`

## Current limits
- Plugin packages should import the named helper surface for registration and treat the default export as the shared extension entrypoint already loaded through the package manifest.
- Raw direct-tool endpoints still need host-side adoption of the guarded wrappers or `runHookCompatPreflight(...)`.
- Deferred surfaces remain explicit: generic subagent/runtime orchestration and mux hooks.
