# ask-user

Shared `AskUserQuestion` compat tool exported by `@agentic-config/pi-compat`.

## Purpose
- Provide a reusable interactive user-decision primitive for generated pi wrappers.
- Cover the repeated confirmation, selection, and short free-text gates used by deferred complex skills.
- Keep behavior explicit when UI is unavailable instead of silently auto-approving decisions.

## Tool name
- `AskUserQuestion`

## Supported prompt shapes
- single selection via `options`
- sequential multi-question batches via `questions[]`
- bounded multi-select prompts via `multiSelect: true`
- free-text input when no `options` are provided

## Non-interactive behavior
Use `nonInteractive` to control fallback when UI is unavailable:
- `unavailable` (default) — return an unavailable result and tell the agent to stop and ask in chat
- `cancel` — return a cancelled result
- `default` — use `defaultValue` / `defaultValues` when provided

## Scope limits
- No mux-specific escalation workflow
- No persistent wizard/session state
- No custom form renderer beyond the current pi UI primitives
