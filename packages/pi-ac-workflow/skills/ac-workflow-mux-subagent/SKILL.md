---
name: ac-workflow-mux-subagent
description: "MUX data-plane worker protocol reference for pi. Defines the report, signal, and return-code contract that strict mux coordinators consume."
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - web_search
---

# MUX Subagent Protocol

## Purpose

This is the pi-adapted worker contract for mux.

## Binding activation

If the parent coordinator explicitly invokes `ac-workflow-mux-subagent`, or embeds this skill text as the worker runtime for the task, treat this document as a binding runtime contract, not as optional guidance, commentary, or a planning reference.

Workers stay **data-plane only** and do not own control-plane progression. Coordinators own ledger transitions and strict gate progression.

Companion protocol artifacts:
- `../../assets/mux/protocol/subagent.md`
- `../../assets/mux/protocol/guardrail-policy.md`
- `../../assets/mux/protocol/strict-happy-path-transcript.md`
- `../../assets/mux/protocol/strict-blocker-path-transcript.md`
- `../../assets/mux/protocol/strict-regression-checklist.md`

## Runtime Differences From the Source Runtime

- There is no `TaskOutput` tool in current pi runtime.
- There is no nested `Skill(...)` loader inside a pi worker.
- Worker depth stays at one layer: coordinator -> subagent.
- Completion is verified through report/signal artifacts plus summary evidence gating.

## Mandatory Worker Rules

- Write all substantive results to the report file path provided by the parent coordinator.
- Create a success or failure signal before finishing.
- Keep the final textual response exactly `0` on success.
- Do not launch nested `subagent` calls.
- Do not call control-plane bridge tools or `report_parent`; mux workers communicate through report/signal artifacts only.
- Do not mutate control-plane state (`ledger.py transition`, coordinator dispatch mutation, or manual ADVANCE fallback).
- Put routing guidance in the report Executive Summary so the coordinator can route the next wave efficiently.

## Signal Command

```bash
uv run ../../assets/mux/tools/signal.py <signal-path> --path <report-path> --status success
```

## Report Format

```markdown
# <Report Title>

## Table of Contents
(all markdown headers)

## Executive Summary
- **Finding/Result**: keyword-dense value
- **Finding/Result**: keyword-dense value
- (max 5-7 bullets)

### Next Steps
- **Recommended action**: what the coordinator should do next
- **Dependencies**: files or reports this connects to
- **Routing hint**: which worker type should consume this next

## <Sections>
(your detailed content)
```

## Checklist

Before returning `0`, verify:

- [ ] Report written to the specified file path
- [ ] Report has an Executive Summary section with bullets only
- [ ] Executive Summary has a `### Next Steps` subsection
- [ ] Signal file created via `../../assets/mux/tools/signal.py`
- [ ] No nested `subagent` calls were made
- [ ] No control-plane bridge tools or `report_parent` calls were made
- [ ] No substantive content appears in the final response
