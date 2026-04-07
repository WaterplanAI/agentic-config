---
name: ac-workflow-mux
description: "pi-adapted mux coordinator. Uses the shared mux foundation plus one-layer subagent orchestration with explicit session, report, and signal tracking."
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - subagent
  - say
---

# MUX - pi coordinator pattern

Use this when the task is too large or too broad for one uninterrupted context window and you need one coordinator plus bounded worker waves.

## Purpose

This pi adaptation keeps the important MUX behavior:
- one coordinator owns the plan
- worker output lives in explicit report files
- completion is tracked with explicit signal files
- parallelism is allowed only when write scopes are disjoint
- orchestration depth stays at exactly one worker layer: coordinator -> subagent

Use the shared mux foundation shipped with this package:
- `../../assets/mux/protocol/foundation.md`
- `../../assets/mux/protocol/subagent.md`
- `../../assets/mux/tools/`

## Mandatory first actions

1. Read `../../assets/mux/protocol/foundation.md` and `../../assets/mux/protocol/subagent.md` if they are not already in context.
2. Start a session immediately:

```bash
uv run ../../assets/mux/tools/session.py "<topic-slug>"
```

3. Treat the returned `SESSION_DIR=tmp/mux/...` path as project-local state.
4. Create any additional session subdirectories you need before launching workers.

## pi runtime contract

This is not a mechanical Claude MUX clone.

Assume all of the following are true:
- the runtime gives you synchronous `subagent` calls, not task notifications
- there is no nested skill loader inside a worker
- user approvals happen in the main chat, not through a dedicated ask-user tool
- voice alerts, when needed, use the current runtime `say` tool

That means you launch a worker wave, wait for the `subagent` call to return, then verify the report and signal files yourself.

## Coordinator rules

- You are the only coordinator.
- Keep direct coordinator edits limited to orchestration state, consolidation, and small shared-surface reconciliations.
- Delegate domain work, research, and large implementation chunks to fresh subagents whenever isolated context helps.
- Never let a worker launch another worker.
- Prefer one fresh worker per wave or per review/fix retry.
- Reuse the shared mux tools instead of inventing ad hoc session or signal helpers.

## Worker contract

Every worker you launch must follow the bundled mux-subagent protocol.

At minimum, every worker prompt must tell the worker to:
- read or follow `../../assets/mux/protocol/subagent.md`
- write substantive output to a report file path you provide
- create a success or failure signal with `../../assets/mux/tools/signal.py`
- return exactly `0` on success
- avoid nested `subagent` calls

## Recommended worker roles

Use any functionally equivalent agents available in the runtime. If your environment provides dedicated roles, prefer:
- `scout` for inventory and targeted codebase recon
- `planner` for turning gathered evidence into a file-by-file plan
- `worker` for implementation or consolidation
- `reviewer` for independent review

If only one general-purpose worker exists, keep the same protocol and specialize the prompt instead of inventing another coordinator layer.

## Prompt scaffold for every worker

Use this structure in every worker task:

```text
Read and follow ../../assets/mux/protocol/subagent.md.

Objective:
- <exact outcome>

Inputs to read first:
- <paths>

Constraints:
- <scope boundaries>
- No nested subagents
- Write only the files in scope

Required report path:
- <session-relative or repo-relative report path>

Required signal path:
- <session-relative signal path>

Before returning:
- Write the report
- Create the signal with ../../assets/mux/tools/signal.py
- Return exactly 0 on success
```

## Wave pattern

### Single worker
Use a single `subagent` call when one worker owns the entire bounded task.

### Parallel wave
Use `subagent.parallel` only when the workers write to disjoint files or to separate report artifacts.

Good parallel examples:
- research split by topic
- inventories split by package
- reviews split by non-overlapping file sets

Bad parallel examples:
- two workers editing the same source file
- two workers producing competing plans for the same stage artifact
- two workers mutating the same shared package surface

If the same source file or shared asset root might change in more than one task, serialize the wave.

## Verification loop

After each worker or worker wave:

1. Check the signal state:

```bash
uv run ../../assets/mux/tools/verify.py <session-dir> --action summary
```

2. When you only need a completion count, you may use:

```bash
uv run ../../assets/mux/tools/check-signals.py <session-dir> --expected <N>
```

3. Prefer bounded report inspection through:

```bash
uv run ../../assets/mux/tools/extract-summary.py <report-path>
```

4. Route the next wave from the report's Executive Summary and Next Steps section.

## User gates

Stay autonomous by default.

Only stop for the user when one of these appears:
- a real scope trade-off
- a product or UX decision that changes the plan materially
- a blocker you cannot resolve with the available files, tools, or worker outputs

When the user needs to notice you, use one short `say` message and keep the details in writing.

## Completion

When the orchestration is done:
- write or update the final deliverable and any persisted state
- confirm the last worker wave is reflected in signals and reports
- optionally deactivate the session marker:

```bash
uv run ../../assets/mux/tools/deactivate.py
```

The goal is not to imitate Claude-only hooks or task notifications. The goal is to preserve the useful MUX behavior honestly on top of the shared pi mux foundation.
