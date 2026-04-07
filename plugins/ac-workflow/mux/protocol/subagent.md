# mux subagent protocol

This file is the authoritative worker contract for the pi-adapted mux family.

## Worker rules
- Write substantive results to the report file path provided by the parent coordinator.
- Create a success or failure signal with `${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py` before returning.
- Keep the final textual response exactly `0` on success.
- Do not launch nested subagents from inside a mux worker.
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

## pi-specific note
The current pi runtime does not provide Claude-style `TaskOutput` or nested `Skill(...)` loading inside a worker. Parent mux orchestrators must pass this protocol inline or refer workers to this bundled asset path directly.
