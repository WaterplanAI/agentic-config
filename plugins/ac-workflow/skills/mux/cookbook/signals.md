# Signal Files

Structured result metadata for MUX orchestration.

## Overview

Signal files are **structured result metadata** that workers write as output.
Runtime task-notification is the primary completion detection mechanism.
Orchestrator reads signal files AFTER receiving task-notification.

FORBIDDEN methods:
- TaskOutput / TaskStop
- tail/grep/cat on output files
- sleep/while/for polling loops
- Manual ls polling

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
| `{agent-type}.done` | `sentinel.done` | Single-instance agent |
| `{seq}-{name}.done` | `001-context.done` | Sequential tasks |

## Creating Signals

Workers create signals when their work is complete.

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status success
```

Example:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py \
  "$SESSION_DIR/.signals/research-product-a.done" \
  --path "$SESSION_DIR/research/product-a.md" \
  --status success
```

## Signal Verification

Orchestrator uses verify.py to check completion.

```bash
# Summary of all signals
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

Output:
```
Signals: 5/5 complete
Outputs: 5 files, 42KB total
Missing: none
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
│   └── sentinel.done
├── research/
│   ├── product-a.md
│   └── product-b.md
└── audit/
    └── codebase.md
```

## verify.py Usage Examples

### Check Summary
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

### Check Total Size
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action total-size
```

Output:
```
Total: 42KB
Threshold: 80KB
Action: No consolidation needed
```

### List Missing Signals
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action missing --expected 5
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
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status error
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
