# MUX Subagent Protocol

## Purpose

This is the bounded leaf-worker contract for the mux family.

## Binding activation

If the parent coordinator explicitly invokes `mux-subagent`, or embeds this skill text as the worker runtime for the task, treat this document as a binding runtime contract, not as optional guidance, commentary, or a planning reference.

Workers stay **data-plane only**. Control-plane ownership (`LOCK/RESOLVE/DECLARE/DISPATCH/VERIFY/ADVANCE/BLOCK/RECOVER`) stays with the coordinator plus shared mux tools.

Companion protocol artifacts:
- `{{MUX_ROOT}}/protocol/subagent.md`
- `{{MUX_ROOT}}/protocol/guardrail-policy.md`
- `{{MUX_ROOT}}/protocol/strict-happy-path-transcript.md`
- `{{MUX_ROOT}}/protocol/strict-blocker-path-transcript.md`
- `{{MUX_ROOT}}/protocol/strict-regression-checklist.md`

## Return Code Convention

Your final textual response to the parent coordinator must be exactly: `0`

- `0` = success
- Any other final response = protocol violation
- All substantive content belongs in the report file

## Mandatory Worker Rules

- Write all substantive findings and results to the report file path provided by the coordinator.
- Create a success or failure signal before finishing.
- Keep final response text exactly `0` on success.
- Do not launch nested `subagent` calls.
- Do not call control-plane bridge tools or `report_parent`; worker-to-coordinator communication is report/signal artifacts only.
- Do not perform control-plane transitions from a worker.
- Do not use `TaskOutput`.

## Signal Command

```bash
uv run {{MUX_ROOT}}/tools/signal.py <signal-path> --path <report-path> --status success
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
- **Recommended action**: what the orchestrator should do next
- **Dependencies**: files or reports this connects to
- **Routing hint**: which worker type should consume this next

## <Sections>
(your detailed content)
```

### Executive Summary Rules

- Bullets only — no paragraphs.
- Each bullet uses `**Label**: keyword-dense value`.
- Include concrete file paths, counts, statuses, and findings.
- Never be vague when a concrete count or path is available.

### Next Steps Rules

- Always include the subsection.
- Tell the coordinator what to do next.
- Reference specific file paths the next worker should read.
- Flag blockers or decisions that need user input.

## Pre-Return Checklist

Before returning `0`, verify:

- [ ] Report written to the specified file path
- [ ] Report has an Executive Summary section with bullets only
- [ ] Executive Summary has a `### Next Steps` subsection
- [ ] Signal file created via `{{MUX_ROOT}}/tools/signal.py`
- [ ] No nested `subagent` calls were made
- [ ] No control-plane bridge tools or `report_parent` calls were made
- [ ] No substantive content appears in the final response
