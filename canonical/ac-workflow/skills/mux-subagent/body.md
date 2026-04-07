# MUX Subagent Protocol

## MANDATORY COMPLIANCE

You are operating under the MUX worker protocol. These rules are non-negotiable.

## Return Code Convention

Your final response to the parent orchestrator must be exactly: `0`

- `0` = success
- Any other final response = protocol violation
- All substantive content belongs in the report file

## File-Based Communication

- Write all findings and results to the report file path given in your task prompt
- Report files are your only substantive output channel
- The orchestrator reads only bounded summaries, not the full report body

## Signal File Creation

Before returning `0`, create a signal file:

```bash
uv run {{MUX_ROOT}}/tools/signal.py <signal-path> --path <your-report-path> --status success
```

If you fail to create a signal, the orchestrator cannot verify completion.

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

- Bullets only — no paragraphs
- Each bullet uses `**Label**: keyword-dense value`
- Include concrete file paths, counts, statuses, and findings
- Never be vague when a concrete count or path is available

### Next Steps Rules

- Always include the subsection
- Tell the orchestrator what to do next
- Reference specific file paths the next worker should read
- Flag blockers or decisions that need user input

## What Not To Do

- Never put substantive content in the final response
- Never skip signal creation
- Never use `TaskOutput`

## Pre-Return Checklist

Before returning `0`, verify:

- [ ] Report written to the specified file path
- [ ] Report has an Executive Summary section with bullets only
- [ ] Executive Summary has a `### Next Steps` subsection
- [ ] Signal file created via `{{MUX_ROOT}}/tools/signal.py`
- [ ] No substantive content in the final response
