# pimux commands and tool

## Command

Use `/pimux` with:

- `spawn`
- `open`
- `list`
- `tree`
- `navigate`
- `status`
- `capture`
- `send`
- `kill`
- `prune`
- `unlock`
- `smoke-nested`

## Tool

Use the `pimux` tool with actions:

- `spawn`
- `open`
- `list`
- `tree`
- `status`
- `capture`
- `send_message`
- `report_parent`
- `kill`
- `prune`

## Minimal spawn

Spawned pimux children always use `notify-and-follow-up`.

```text
/pimux spawn "Scout the repo and report only the relevant files."
```

## Visual spawn

```text
/pimux spawn --open "Act as an orchestrator and keep the session watchable."
```

## Messaging

Parent -> child:
- `send_message`

Child -> parent:
- `report_parent`

Valid `report_parent` kinds:
- `progress`
- `question`
- `blocker`
- `failure`
- `closeout`

Parent-side interface delivery should also show parent -> child bridge messages as concise pimux events without triggering an extra turn.

After a terminal `report_parent`, the pimux runtime should finalize the managed session promptly.

## Inspection

- `list` for current-session agents by default
- `tree` for hierarchy shape
- `status` for one agent plus settlement state
- `capture` for pane text
- `open` to inspect live in iTerm
- `navigate` to select a node from the current-session hierarchy and act on it
- list/tree/navigation labels keep the agent ID visible while adding role/goal context for easier selection
- hierarchy output should use clearer tree connectors and plain-text badges, with best-effort safe styling when the host interface supports it
- interactive `open`, `capture`, `send`, and `kill` pickers should prefer live agents when no target is provided
- `prune --dry-run` to preview historical cleanup candidates

Auto-prune removes `terminated` or `missing` pimux registry entries aged at least `1d`.

## Control-plane recovery

```text
/pimux unlock
```

Releases the fail-closed mux-family parent control-plane lock and restores the pre-lock tool surface for the current session.

## Canned smoke guide

```text
/pimux smoke-nested
```

Writes a deterministic nested smoke-test guide under `tmp/pimux/` with stable ID patterns and the simplified scaffold flow used for routing and settlement checks.
