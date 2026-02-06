# Signal Files

Signal-based completion mechanism for MUX orchestration.

## Overview

Signals are the ONLY completion mechanism. All other methods are FORBIDDEN:
- TaskOutput
- TaskStop
- tail/grep/cat
- sleep/while/for loops
- Manual ls polling
- poll-signals.py direct loops (orchestrator only)

## Signal File Schema

```json
{
  "path": "/absolute/path/to/output.md",
  "status": "success|error",
  "timestamp": "2026-02-04T10:54:32Z",
  "agent_id": "researcher-001"
}
```

## Signal Naming Conventions

| Pattern | Example | Usage |
|---------|---------|-------|
| `{phase}-{name}.done` | `research-product-a.done` | Phase-specific worker |
| `{agent-type}.done` | `monitor.done` | Single-instance agent |
| `{seq}-{name}.done` | `001-context.done` | Sequential tasks |

## Creating Signals

Workers create signals when their work is complete.

```bash
uv run tools/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status success
```

Example:
```bash
uv run tools/signal.py \
  "$SESSION_DIR/.signals/research-product-a.done" \
  --path "$SESSION_DIR/research/product-a.md" \
  --status success
```

## Signal Verification

Orchestrator uses verify.py to check completion.

```bash
# Summary of all signals
uv run tools/verify.py "$SESSION_DIR" --action summary
```

Output:
```
Signals: 5/5 complete
Outputs: 5 files, 42KB total
Missing: none
```

## Monitor Agent Pattern

Monitor agents use subscribe.py to track worker completion (push via socket with fallback to file polling).

```python
Task(
    prompt=f"""Read agents/monitor.md for protocol.

SESSION: {session_dir}
EXPECTED: {worker_count}

Use subscribe.py to track completion.

FINAL: Return EXACTLY: done""",
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True
)
```

## Signal File Location

All signals go in `{session_dir}/.signals/`.

```bash
mkdir -p "$SESSION_DIR/.signals"
```

Directory structure:
```
session-dir/
├── .signals/
│   ├── research-product-a.done
│   ├── research-product-b.done
│   ├── audit-codebase.done
│   └── monitor.done
├── research/
│   ├── product-a.md
│   └── product-b.md
└── audit/
    └── codebase.md
```

## verify.py Usage Examples

### Check Summary
```bash
uv run tools/verify.py "$SESSION_DIR" --action summary
```

### Check Total Size
```bash
uv run tools/verify.py "$SESSION_DIR" --action total-size
```

Output:
```
Total: 42KB
Threshold: 80KB
Action: No consolidation needed
```

### List Missing Signals
```bash
uv run tools/verify.py "$SESSION_DIR" --action missing --expected 5
```

Output:
```
Expected: 5
Found: 3
Missing:
- research-product-c.done
- audit-integration.done
```

## Error Signals

Workers can signal errors.

```bash
uv run tools/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status error
```

Signal content:
```json
{
  "path": "/path/to/output.md",
  "status": "error",
  "timestamp": "2026-02-04T10:54:32Z",
  "agent_id": "researcher-001"
}
```

Output file should contain error details:
```markdown
# Error: Research Failed

Unable to fetch URL: timeout after 30s
```
