---
name: ac-workflow-tmux-agent
description: "Launch and manage long-lived tmux-backed Pi agents, optionally open them in iTerm, and coordinate multi-agent hierarchies such as chief-of-staff, heads, and doers. Use when work should continue in its own session, be visually inspectable later, or be structured across multiple long-lived agents."
project-agnostic: true
allowed-tools:
  - Read
  - Bash
  - tmux_agent
  - say
---

# Tmux Agent

Use the shipped `tmux_agent` tool and `/tmux-agent` command for long-lived tmux-backed Pi sessions.

Do not reimplement this workflow with raw `tmux`, `osascript`, or ad hoc shell scripts unless you are explicitly debugging the extension itself.

## When to use

Use this skill when:

- the user wants a new Pi agent running in its own tmux session
- the user wants to open or revisit a visible iTerm tab later
- the work should continue outside the current conversation
- the work benefits from persistent role ownership
- you need a small hierarchy of long-lived agents

Prefer normal short-lived subagents when the work is brief and does not need its own persistent session.

## Core rules

- Default to headless agents unless the user explicitly wants to watch them live.
- Open iTerm immediately only when the user asks, or when live oversight is clearly valuable.
- When opening a visual in iTerm, prefer creating a background tab in the current iTerm window without stealing focus.
- Prefer the minimal spawn UX: prompt first, overrides only when truly needed.
- Let the extension infer goal, role, agent ID seed, current cwd, current model, and hierarchy wiring when possible.
- Only set advanced fields manually when the task really needs them.
- Give agents stable, meaningful IDs and roles.
- Set `parentAgentId` and `rootAgentId` deliberately when building hierarchies.
- Keep prompts focused. One agent, one mission.
- For multi-phase work, prefer **one agent per phase** instead of a long-lived catch-all worker.
- When chaining phases autonomously, prefer `notificationMode: "notify-and-follow-up"`.
- Require a proper final completion report artifact before a phase agent stops.
- Use `send_message` for downward or lateral instructions rather than inventing unmanaged channels.
- Use the built-in private launch bridge and bounded report flow for upward child-to-parent reporting.
- Child completions are reported automatically; do not manually paste raw child transcripts back into the parent session.
- If a child needs input before finishing, use `report_parent` with a bounded summary and `requiresResponse: true` when the parent must answer.
- If a completion or failure artifact looks inconsistent, verify the real state with `status` and `capture` before acting.
- Treat `close_visual` as best-effort; treat `kill` as the authoritative cleanup step.
- After harvesting a finished agent's output, clean it up promptly instead of leaving it lingering.
- When the user wants to stop everything using `tmux-agent`, inspect the managed set with `/tmux-agent tree` or `/tmux-agent list` and then kill the managed agents with `/tmux-agent kill`, usually children first and the root last.
- Do not fall back to raw `tmux kill-session` for normal cleanup when the managed `/tmux-agent` command can do it.
- Avoid wide, vague swarms. Prefer a small number of clear roles.

## Commands and tool

Human command:

- `/tmux-agent spawn`
- `/tmux-agent open`
- `/tmux-agent close`
- `/tmux-agent list`
- `/tmux-agent status`
- `/tmux-agent capture`
- `/tmux-agent send`
- `/tmux-agent kill`
- `/tmux-agent tree`
- `/tmux-agent debate start|send|close`
- `/tmux-agent peer-mode`
- `/tmux-agent peer-list`

Model tool:

- `tmux_agent`

Read [references/commands.md](references/commands.md) when you need the action shapes.

## Recommended agent shapes

### Single persistent worker

Use one long-lived agent when the user wants:

- a background research or coding thread
- a visually inspectable Pi process in tmux/iTerm
- a separate working lane in another directory or model

### Chief of Staff -> Heads -> Doers

Use this only when the work truly has multiple domains.

- Chief of Staff: decomposes the overall objective and coordinates heads
- Head of X: owns one domain and delegates narrow tasks
- Doer: executes one bounded task and reports back compactly

Read [references/orchestration.md](references/orchestration.md) before creating a hierarchy.

## Messaging contract

When sending messages between agents, include:

- sender
- recipient
- intent
- concrete task or question
- expected output shape
- stop condition or completion signal

Use this default transport split:

- parent -> child: `send_message`
- child -> parent: bounded bridge reporting
- peer -> peer: explicit debate channels only

Reports upward should be compressed and decision-oriented.

## Practical defaults

- Use the current cwd unless the user asks otherwise.
- Use the current model unless the user asks otherwise.
- Infer goal from the prompt summary unless the user specifies one.
- Infer role from the task wording when possible.
- Infer visual mode from explicit user intent such as watching live; otherwise keep the agent headless.
- By default, launching a child creates a private temp bridge so the parent session can receive bounded completion summaries.
- For phase-based work, keep a small plan/status document outside the child session and update it between phases.
- For phase-based work, the usual sequence is: implementation -> verification/remediation -> browser QA.
- If you combine tmux-agent with voice notifications, speak only for meaningful milestones such as phase completion or required input, and keep the spoken text short.
- Peer communication defaults to isolated behavior. Open a debate channel explicitly before expecting peers to talk.
- Debate modes are `alone`, `all`, `subset`, and `direct`.
- For hierarchy roots, set `rootAgentId` to the root agent itself.
- For children, set `parentAgentId` to the direct supervisor and `rootAgentId` to the hierarchy root.

## Examples

- Spawn a long-lived git-history analyst and keep it headless.
- Spawn a worker and open it in iTerm so the user can watch live.
- Close one or more managed iTerm tabs with `/tmux-agent close`.
- Spawn a chief-of-staff agent, then heads for engineering and research, then message them for updates.
- If the user says to kill them all using `tmux-agent`, inspect the tree and kill the managed sessions in cleanup order with `/tmux-agent kill`.

## References

- [references/commands.md](references/commands.md)
- [references/orchestration.md](references/orchestration.md)
- [references/phase-lifecycle.md](references/phase-lifecycle.md)
- [references/roles.md](references/roles.md)
