# MUX Subagent Protocol

## Purpose

This is the pi-adapted worker protocol for the mux family.

Use it as the authoritative contract for any bounded worker launched by later mux orchestrators. The current pi runtime does not support nested skill loading inside a worker, so parent mux skills must paste or reference this protocol explicitly when they call the `subagent` tool.

Bundled foundation assets live under:
- `{{MUX_ROOT}}/tools/`
- `{{MUX_ROOT}}/protocol/`

The shared protocol reference for later prompt reuse is:
- `{{MUX_ROOT}}/protocol/subagent.md`

## Runtime Differences From Claude

- There is no Claude-style `TaskOutput` tool in the current pi runtime.
- There is no nested `Skill(...)` loader inside a pi worker.
- Depth stays at one worker layer: coordinator -> subagent.
- Completion is still verified through report files plus explicit signal files.

## Mandatory Worker Rules

- Write all substantive results to the report file path provided by the parent coordinator.
- Create a success or failure signal before you finish.
- Keep the final textual response exactly `0` on success.
- Do not launch nested subagents from inside this protocol.
- Put routing guidance in the report executive summary so the parent coordinator can decide the next wave efficiently.

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
- [ ] Signal file created via `{{MUX_ROOT}}/tools/signal.py`
- [ ] No nested `subagent` calls were made
- [ ] No substantive content appears in the final response
