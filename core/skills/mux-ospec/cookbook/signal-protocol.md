# Signal Protocol

Signal file format and usage for mux-ospec orchestration.

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
uv run $MUX_TOOLS/poll-signals.py $DIR --expected N
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
| WARN | Minor issues | Proceed with caution |
| FAIL | Critical issues | Trigger FIX cycle |

## Status Values

| Status | Meaning |
|--------|---------|
| completed | Stage finished successfully |
| failed | Stage encountered error |
| skipped | Stage intentionally skipped |
