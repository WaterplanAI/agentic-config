# Tier 1: Signal-Based Verification

Zero-context verification using filesystem signals.

## Signal Mechanism

**Primary**: Filesystem signals (audit trail, zero-context)

### Signal Files
```python
# Agents create signals on completion
uv run .claude/skills/mux/tools/signal.py "{session_dir}/.signals/001-name.done" \
    --path "{output_path}" --status success
```

### Verification
```bash
# Count completed
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action count

# Check for failures
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action failures
```

## Signal Directory Structure

```
tmp/swarm/{SESSION_ID}/.signals/
  {NNN}-{agent-name}.done    # Success signal
  {NNN}-{agent-name}.fail    # Failure signal
```

## Signal File Format (~50 bytes)

```
path: tmp/swarm/.../research/001-topic.md
size: 4523
status: success
```

For failures:
```
path: tmp/swarm/.../research/001-topic.md
size: 0
status: fail
error: API rate limit exceeded
```

See `cookbook/signal-tool.md` for full documentation on signal creation.

## Verification Commands (via verify.py)

```bash
# Count completions
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action count

# Check for failures
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action failures

# Get all output paths
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action paths

# Get total output size
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action total-size

# Full summary (combines all above)
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

## When to Use

| Operation | Method |
|-----------|--------|
| Wait for workers | Runtime task-notification (then verify.py) |
| Count completed | verify.py --action count |
| List failures | verify.py --action failures |
| Get output paths | verify.py --action paths |

## Anti-Patterns

- Read output files to check completion (context pollution)
- Parse signal files manually (use verify.py)
