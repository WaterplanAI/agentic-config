# MUX-OSPEC - O_SPEC Workflow Orchestrator

## Dependency guard

This skill requires `spec`.

If the dependency is missing, stop and return:

```text
DEPENDENCY_MISSING: mux-ospec requires the `spec` skill from ac-workflow.
Install: claude plugin install ac-workflow@agentic-plugins
```

Do not run manual fallback stages.

## Mandatory first action

Before any other tool call, run:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/session.py "mux-ospec-{topic}"
```

## Runtime role

You are an orchestrator, not an implementer.

- delegate all stage work
- do not do stage work directly
- use background tasks (`run_in_background=True`)
- use notify-first pacing (wait for task notifications)
- no polling loops or repeated nudges

## Workflow by modifier (authoritative)

`GATHER` is the mux-ospec name for `RESEARCH`.

- `full`: `CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL`
- `lean`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION`
- `leanest`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION`

Rules:
- `SUCCESS_CRITERIA` is mandatory content before `CONFIRM_SC`
- `CONFIRM_SC` is a mandatory user approval gate before `PLAN`
- `SENTINEL` is final ruthless validation for `full`
- `SELF_VALIDATION` is final validation for `lean/leanest`

## PASS-only quality gates

Only `PASS` can advance through `REVIEW`, `TEST`, `SENTINEL`, or `SELF_VALIDATION`.

- `WARN` or `FAIL` => route to `FIX`
- if retry budget is exhausted => escalate to user via `AskUserQuestion`
- never continue with a non-`PASS` gate result

## Stage delegation contract

Each stage subagent must:

1. invoke `Skill(skill="spec", args="<STAGE> <spec_path>")` as its first meaningful action
2. stay within that stage scope only
3. commit every repository it changed
4. return structured signal metadata for routing

Do not invoke `Skill(skill="spec")` directly in the orchestrator context.
NEVER invoke Skill() directly from the orchestrator; always delegate through `Task(...)`.

## Mandatory repo-scoped commit policy

Every stage agent MUST commit changes in every changed repository.

Signal metadata must include:

- `repo_scope`: `spec-only` | `root-only` | `root+spec`
- `root_commit`: short hash or `N/A`
- `spec_commit`: short hash or `N/A`

Order rule when both repos changed:
1. commit root repo first
2. commit spec repo second (via spec resolver)

## Stage model tiers

Use tier names in core flow text:

- high-tier: CREATE, CONSOLIDATE, SUCCESS_CRITERIA, PLAN, REVIEW, SENTINEL, SELF_VALIDATION
- medium-tier: GATHER, IMPLEMENT, FIX, TEST, DOCUMENT
- user gate: CONFIRM_SC

## Pacing and escalation defaults

- default pacing: wait for notification and evidence, then route
- optional watchdog: inactivity-only, concise, non-spammy
- default blocked/stuck behavior: escalate to user
- do not silently reroute, replace, or downgrade behavior unless explicitly instructed

## Signal reader template

After each stage notification, delegate one low-tier signal-reader task and return only routing fields.
Signals must live under `{session}/.signals/`.

```python
Task(
    prompt="Read {session}/.signals/<stage>.done and return routing fields only.",
    model="low-tier",
    run_in_background=True,
)
```

```text
status: <success|failed>
grade: <PASS|WARN|FAIL|N/A>
repo_scope: <spec-only|root-only|root+spec|N/A>
root_commit: <hash|N/A>
spec_commit: <hash|N/A>
error: <none|text>
```

## Completion

Workflow completes only when the final validation stage returns `PASS` and all required repo-scoped commits are present for changed repos.
