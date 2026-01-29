# Signal Tool Usage

Tool for creating completion signals from any agent type, including Explore agents.

## Why This Tool Exists

Explore agents have Bash access but cannot use Write/Edit tools. This tool allows
them to create signal files via Bash while maintaining the file-based protocol.

## Basic Usage

```bash
# Success signal (auto-calculates size from output file)
uv run tools/signal.py "$SESSION_DIR/.signals/001-research.done" \
    --path "$SESSION_DIR/research/001-topic.md" \
    --status success

# Success signal with explicit size
uv run tools/signal.py "$SESSION_DIR/.signals/001-research.done" \
    --path "$SESSION_DIR/research/001-topic.md" \
    --size 4523 \
    --status success

# Failure signal with error message
uv run tools/signal.py "$SESSION_DIR/.signals/001-research.fail" \
    --path "$SESSION_DIR/research/001-topic.md" \
    --status fail \
    --error "API rate limit exceeded"
```

## Signal File Format

```
path: tmp/swarm/20260129-1500-topic/research/001-topic.md
size: 4523
status: success
```

For failures:
```
path: tmp/swarm/20260129-1500-topic/research/001-topic.md
size: 0
status: fail
error: API rate limit exceeded
```

## Agent Integration

### For Explore Agents (Read-Only Research)

Explore agents research but delegate file writing. They signal completion after
the writer agent confirms:

```
1. Research topic using WebSearch, Read, Glob, Grep
2. Delegate file writing to general-purpose agent
3. After writer confirms, create signal:
   uv run tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
       --path "$SESSION_DIR/research/001-name.md" \
       --status success
4. Return: "done"
```

### For General-Purpose Agents (Writers)

Writers create both the output file AND the signal:

```
1. Write output to specified path
2. Create signal:
   uv run tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
       --path "$OUTPUT_PATH" \
       --status success
3. Return: "done"
```

## Verification

Orchestrator verifies via `tools/verify.py` without reading files:

```bash
# Count completions
uv run tools/verify.py "$SESSION_DIR" --action count

# Check for failures
uv run tools/verify.py "$SESSION_DIR" --action failures

# Get all paths and sizes
uv run tools/verify.py "$SESSION_DIR" --action paths
uv run tools/verify.py "$SESSION_DIR" --action sizes

# Full summary
uv run tools/verify.py "$SESSION_DIR" --action summary
```
