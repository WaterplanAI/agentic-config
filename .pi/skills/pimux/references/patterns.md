# pimux patterns

## Single worker

Use one child when the task is bounded but should stay long-lived or visually inspectable.

## Scout -> planner replacement

1. spawn a `scout`-style child to inventory the codebase
2. let it run and wait for explicit `closeout`
3. pass the artifact or report path into a `planner`-style child
4. let the planner return the execution plan

Do not rely on prose inference between steps; hand off file paths or bounded summaries.
Do not keep the parent blocked with sleep loops or repeated pings while waiting; inspect only at a real handoff, live-watch request, or suspected problem.

## Team / brainstorm pattern

Use one orchestrator child plus a few role-specific children.

Rules:
- explicit roles
- explicit message routing
- explicit stop conditions
- no ambient cross-talk unless deliberately instructed

## mux family adaptation

Use pimux as the control-plane runtime for:
- mux
- mux-ospec
- mux-roadmap

Keep wrappers thin:
- wrapper skill owns prompt and file conventions
- pimux owns tmux launch, messaging, settlement, visual supervision, and the fail-closed parent control-plane lock
- wrapper-triggered parents do not do repo inspection before spawn; they hand off the user objective and let the child read the repo
- for `mux-ospec`, explicit spec paths pass through unchanged; inline prompts without a path auto-derive/create the next current-branch spec path through the authoritative runtime; only missing user input falls back to `AskUserQuestion`, never parent-side `Read` / `Bash`

## Explicit trigger discipline

If `pimux`, `mux`, `mux-ospec`, or `mux-roadmap` is explicitly invoked, follow the pattern all the way:
- activate the authoritative control-plane behavior immediately
- for explicit mux-family wrappers (`mux`, `mux-ospec`, `mux-roadmap`), the parent is fail-closed to `pimux`, `AskUserQuestion`, and `say`
- spawn the child or hierarchy before substantive repo work
- hand off via files or bounded user-provided paths
- wait asynchronously for bridge reports

Do not stop at planning to spawn, and do not replace the run with parent-side domain work.
