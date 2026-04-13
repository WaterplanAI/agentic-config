# mux subagent protocol

This file is the authoritative **data-plane** worker contract for the pi-adapted mux family.

## Companion protocol artifacts
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/guardrail-policy.md`
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-happy-path-transcript.md`
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-blocker-path-transcript.md`
- `${CLAUDE_PLUGIN_ROOT}/mux/protocol/strict-regression-checklist.md`

## Worker rules
- Write substantive results to the report file path provided by the parent coordinator.
- Create a success or failure signal with `${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py` before returning.
- Keep the final textual response exactly `0` on success.
- Do not launch nested subagents from inside a mux worker.
- Do not call control-plane bridge tools or `report_parent`; mux workers communicate through report/signal artifacts only.
- Keep workers in the data plane only; do not perform control-plane state transitions.
- Put routing guidance in the report executive summary so the parent coordinator can decide the next wave without rereading the entire artifact.

## Required report shape
```markdown
# <Report Title>

## Table of Contents
(all markdown headers)

## Executive Summary
- **Finding**: keyword-dense value
- **Status**: pass|warn|fail with concrete scope

### Next Steps
- **Recommended action**: what the coordinator should do next
- **Dependencies**: file paths or reports to read next
- **Routing hint**: which worker type should consume this next
```

## Signal command
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py <signal-path> --path <report-path> --status success
```

## Runtime note
The current pi runtime does not provide a `TaskOutput` tool or nested `Skill(...)` loading inside a worker. Parent mux coordinators must pass this protocol inline or reference this bundled artifact path directly.

## Pre-return checklist
Before returning `0`, verify:
- [ ] report written to the declared report path
- [ ] signal created via `${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py`
- [ ] report includes `## Executive Summary` + `### Next Steps`
- [ ] no nested `subagent` calls
- [ ] no control-plane bridge tools or `report_parent` calls
- [ ] no substantive content in final response
