# Tier 1: Signal-Based Verification

Zero-context verification using filesystem signals + native TaskOutput.

## Completion Detection

**Primary**: Native TaskOutput (reliable)
**Secondary**: Signal files (metadata only)

### TaskOutput Pattern

```python
# Launch worker
worker_id = Task(..., run_in_background=True)

# Launch monitor (context firewall)
monitor_id = Task(
    prompt="Read agents/monitor.md. Monitor: {worker_ids}",
    model="haiku",
    run_in_background=True
)

# Non-blocking check (orchestrator stays interactive)
TaskOutput(monitor_id, block=False, timeout=1000)
# Error = still running
# "done" = complete
```

### Why Monitor Pattern

Direct TaskOutput on workers pollutes orchestrator context:
```
TaskOutput(worker_id) → worker's return value → into YOUR context
```

Monitor as firewall:
```
Monitor calls TaskOutput(worker_id) → pollution stays in monitor
Orchestrator calls TaskOutput(monitor_id) → only gets "done"
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

## Creating Signals

Agents use `tools/signal.py`:

```bash
uv run tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
    --path "$OUTPUT_PATH" \
    --status success
```

See `cookbook/signal-tool.md` for full documentation.

## Verification Commands (via verify.py)

```bash
# Count completions
uv run tools/verify.py "$SESSION_DIR" --action count

# Check for failures
uv run tools/verify.py "$SESSION_DIR" --action failures

# Get all output paths
uv run tools/verify.py "$SESSION_DIR" --action paths

# Get total output size
uv run tools/verify.py "$SESSION_DIR" --action total-size

# Full summary (combines all above)
uv run tools/verify.py "$SESSION_DIR" --action summary
```

## When to Use

| Situation | Method |
|-----------|--------|
| Wait for workers | TaskOutput via Monitor |
| Check progress | Signal file count |
| Get output paths | grep signal files |
| Validate sizes | grep signal files |

## NEVER Do

- Use bash polling loops for completion (unreliable)
- Call TaskOutput directly on workers (context pollution)
- Read output files for verification (use signals)
- Skip the monitor pattern
