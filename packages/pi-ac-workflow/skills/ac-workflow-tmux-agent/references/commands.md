# Commands and Tool Reference

## Human command

Use `/tmux-agent` with one of these subcommands:

- `spawn`
- `open`
- `close`
- `list`
- `status`
- `capture`
- `send`
- `kill`
- `tree`
- `debate start|send|close`
- `peer-mode`
- `peer-list`

### Minimal spawn example

```text
/tmux-agent spawn "Summarize yesterday and today's git history from a logic standpoint."
```

Only the prompt is required.

By default, spawn:

- uses the current cwd
- uses the current model
- infers goal from the prompt
- infers role when possible
- keeps the agent headless unless live viewing is clearly requested
- auto-links parent/root IDs when already inside a tmux-agent hierarchy
- creates a private temp bridge for bounded child-to-parent reporting
- notifies the launching session when the child completes

When autonomous follow-up matters, prefer `notificationMode: "notify-and-follow-up"` over plain notify.

### Watch-live spawn example

```text
/tmux-agent spawn --watch "Act as Chief of Staff. Coordinate the work and keep me able to inspect progress live."
```

`open` uses a managed background tab in the current iTerm window when possible, instead of stealing focus.

### Advanced spawn example

```text
/tmux-agent spawn --advanced --model openai-codex/gpt-5.3-codex --cwd /path/to/work "Decompose the work, create a plan, and coordinate any child agents."
```

Use advanced overrides only when the defaults are not enough.

### Debate examples

```text
/tmux-agent debate start --id architecture-review --participants head-eng,head-research "Compare option A vs option B"
/tmux-agent debate send architecture-review "Challenge option A from your domain perspective." --requires-response
/tmux-agent debate close architecture-review "Converged on rejecting option A."
/tmux-agent peer-mode head-eng subset --participants head-research,reviewer-1
/tmux-agent peer-list head-eng
```

## Model tool

Use the `tmux_agent` tool for deterministic orchestration.

### Actions

- `spawn`
- `open_visual`
- `close_visual`
- `list`
- `status`
- `send_message`
- `capture`
- `kill`
- `tree`
- `report_parent`
- `debate_start`
- `debate_send`
- `debate_close`
- `peer_mode_set`
- `peer_list`

## Spawn guidance

Fields you will commonly set:

- `agentId`
- `cwd`
- `model`
- `prompt`
- `role`
- `goal`
- `parentAgentId`
- `rootAgentId`
- `openIterm`
- `notificationMode`
- `contextBrief`

## Message guidance

When using `send_message`:

- set `target`
- set a concise `message`
- optionally set `senderAgentId` only when you must override the default sender

When using `report_parent` from a child session:

- set `reportKind` to `question`, `blocker`, `progress`, or `failure`
- set a concise bounded `summary`
- optionally include `reportMarkdown` when the parent needs a small artifact
- set `requiresResponse: true` when the parent must answer before the child can continue

When using `debate_start`:

- set `debateId` when you need a stable name
- choose `peerMode`: `alone`, `all`, `subset`, or `direct`
- set `participants` for `subset` and `direct`
- optionally set `topic`

When using `debate_send`:

- set `debateId`
- set a concise `message`
- optionally set `summary` for a tighter inline version
- optionally set `participants` to target a subset of an existing debate
- set `requiresResponse: true` when recipients should actively reply
- optionally include `reportMarkdown` for bounded long-form reasoning

When using `debate_close`:

- set `debateId`
- optionally set `summary`
- optionally include `reportMarkdown` for the final bounded synthesis

When using `peer_mode_set`:

- set `target`
- set `peerMode`
- optionally set `participants` for default subset/direct metadata

## Inspection guidance

Use:

- `list` to see all managed agents
- `status` for one agent plus a short capture preview
- `capture` for a larger pane snapshot
- `tree` to inspect hierarchy
- `peer_list` to inspect peer modes under one root

If a completion or failure artifact looks suspicious, compare it against `status` and `capture` before deciding to kill, relaunch, or report failure.

## Cleanup guidance

When the user says to kill them all using `tmux-agent`:

1. inspect the managed set with `tree` or `list`
2. close managed visuals first when that matters to the user
3. kill children before parents when there is a hierarchy
4. use repeated `/tmux-agent kill <agentId>` or tool `kill` calls
5. avoid raw `tmux kill-session` unless you are explicitly debugging the extension itself

For phase-based workflows, the usual completion flow is:

1. read the completion artifact
2. verify with `status` / `capture` if needed
3. update any plan or status document
4. close visuals if desired
5. kill the agent promptly
6. launch the next phase

Example cleanup flow:

```text
/tmux-agent tree
/tmux-agent close messaging-chief
/tmux-agent kill head-delivery
/tmux-agent kill head-risk
/tmux-agent kill messaging-chief
```

## Visual guidance

Use `open_visual` when:

- the user asks to watch a running agent
- you need human oversight on a specific node in the hierarchy
- a supervisory agent is actively coordinating several children

Use `close_visual` or `/tmux-agent close` when:

- the user wants to close only the managed iTerm tab(s) opened for an agent
- you want a deterministic managed close rather than a heuristic AppleScript sweep
- you want `kill` cleanup to avoid leaving behind managed visual tabs

Treat `close_visual` as best-effort visual cleanup, not as a substitute for killing the managed agent.

Prefer headless mode when live visual monitoring is not necessary.
