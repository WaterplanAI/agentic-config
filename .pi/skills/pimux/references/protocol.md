# pimux protocol

## Messaging model

- parent -> child: explicit bridge inbox events via `send_message`
- child -> parent: explicit bridge reports via `report_parent`
- one hop only: L2 reports to L1, L1 reports to L0

## Authority model

Only the authoritative direct child session for a bridge may call `report_parent`.

Implications:
- helper subagents are local-only
- helper completion is not settlement
- helper misuse of `pimux` / `report_parent` is invalid

## Settlement model

- `progress` is non-terminal
- for a child that must ask the parent and continue in the same session, use `progress` with `requiresResponse=true`
- `question` is terminal waiting-on-parent settlement; do not use it when the child should keep working after the answer
- `closeout + exit` -> `settled_completion`
- `failure + exit` -> `settled_failure`
- `blocker + exit` -> `settled_blocked`
- `question + exit` -> `settled_waiting_on_parent`
- exit without terminal declaration -> `protocol_violation`

After a terminal child report, the pimux runtime should finalize the managed session promptly instead of leaving the child alive in an ambiguous post-closeout state.
The child should not keep chatting or continue work after emitting a terminal report.

## Nested orchestrator rule

If a child spawns direct pimux children, it must not emit `closeout` until every direct pimux child is `settled_completion`.

When direct child outcomes are intentionally non-success, the supervising wrapper should propagate the matching terminal kind and exit cleanly instead of forcing `closeout` or relying on manual kill:

- `settled_waiting_on_parent` -> `question`
- `settled_blocked` -> `blocker`
- `settled_failure` or `protocol_violation` -> `failure`

For cascade-kill testing, keep the wrapper alive and kill a disposable child parent/descendant pair under it rather than making the wrapper itself the killed parent.

## Explicit skill-trigger rule

When the parent session entered this family through an explicit `pimux`, `mux`, `mux-ospec`, or `mux-roadmap` skill trigger, that trigger is a runtime commitment, not a suggestion.

- The parent must stay control-plane only.
- The parent may rely on wrapper/runtime-provided protocol references, prepare bounded handoff from explicit user input, and spawn or message children.
- The substantive domain work must be carried by the spawned authoritative child session(s).
- Do not replace the requested pimux flow with a direct parent-side answer, analysis, or implementation.
- For explicit mux-family wrappers, the parent is fail-closed to `pimux`, `AskUserQuestion`, and `say` until the user explicitly runs `/pimux unlock`.
- If the chosen wrapper is wrong for the task, say so and stop or switch cleanly; do not silently degrade to a non-pimux workflow.

## Supervision pacing rule

Default parent behavior is asynchronous.

After dispatch, the parent should let the child work instead of busy-waiting with sleep loops, repeated `status` checks, or repeated nudges.

Inspect or intervene only when:
- the child emits a bridge report
- the user asks to inspect live progress
- a real downstream handoff now depends on settlement
- there is concrete evidence of a stall, blocker, or protocol problem

For explicit mux-family wrappers, the notify-first default is stricter:
- child bridge notifications are delivered automatically
- after spawn, do not call `status`, `capture`, `tree`, `list`, or `open` on the happy path
- wait for delivered child activity; after a child progress report arrives, use at most one `send_message` when input is needed
- treat `status`, `capture`, `tree`, `list`, and `open` as recovery-only tools for explicit live inspection, suspected stall/protocol violation/failure, or the inactivity-only watchdog
- after terminal settlement, use one final `pimux status` check before advancing

Do not poll pimux; wait for delivered child activity. One targeted `status` / `capture` check at a real recovery decision point is fine. Continuous polling is not.

## Session scope rule

Default supervision is scoped to the current session hierarchy. Broaden scope only when explicitly needed.
