# Signal Protocol

Signal file format and usage for mux-ospec orchestration.

## Path Convention (CRITICAL)

All signal paths are RELATIVE to the project root. The `{session}` variable resolves to a relative path like `tmp/mux/20260209-1430-topic/`. Signal files live at `{session}/.signals/stage-name.done`.

**`tmp/` is a project-local directory, NOT the system `/tmp/`.** When passing signal paths to subagents, always include: "Path is RELATIVE to project root. Do NOT prepend '/'."

## Signal Schema

```json
{
  "$schema": "signal-v1.json",
  "phase": "implement",
  "phase_num": 2,
  "status": "completed",
  "timestamp": "2026-02-04T10:30:00Z",
  "duration_seconds": 342,
  "artifacts": ["path/to/output.md"],
  "sc_contributions": {"SC-007": "implemented"},
  "validation": {"tests": {"passed": 10, "failed": 0}},
  "grade": "PASS"
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| phase | string | Stage name (gather, plan, implement, review, test, document, sentinel) |
| phase_num | int | Phase number (for multi-phase implementations) |
| status | string | completed, failed, skipped |
| timestamp | string | ISO 8601 timestamp |
| duration_seconds | int | Execution time |
| artifacts | array | Paths to generated files |
| sc_contributions | object | SC-ID to contribution mapping |
| validation | object | Test/lint results |
| grade | string | PASS, WARN, FAIL (for review stages) |

## Signal Creation

```bash
uv run $MUX_TOOLS/signal.py $PATH --status success --output '{"key": "value"}'
```

## Signal Polling

```bash
uv run $MUX_TOOLS/check-signals.py $DIR --expected N
```

Returns when N signals detected or timeout.

## Signal Verification

```bash
uv run $MUX_TOOLS/verify.py $DIR --action summary
```

Returns summary of all signals in directory.

## Grade Values

| Grade | Meaning | Action |
|-------|---------|--------|
| PASS | All checks pass | Proceed to next stage |
| WARN | Minor issues | Trigger FIX cycle (ONLY PASS proceeds) |
| FAIL | Critical issues | Trigger FIX cycle (ONLY PASS proceeds) |

## Status Values

| Status | Meaning |
|--------|---------|
| completed | Stage finished successfully |
| failed | Stage encountered error |
| skipped | Stage intentionally skipped |
