# MUX Completion Tracking

## Overview

MUX uses **runtime task-notification** as the sole completion detection mechanism.
Workers write signal files as structured result metadata; the orchestrator reads
them AFTER receiving task-notification, not via polling.

## Completion Flow

```
1. Orchestrator launches N workers (all run_in_background=True)
2. Each worker does work, writes output, creates signal file
3. Runtime delivers task-notification to orchestrator per worker
4. Orchestrator counts: received N notifications?
5. Yes -> run verify.py --action summary once -> proceed to next phase
6. No (timeout) -> run check-signals.py as fallback -> decide recovery
```

## Signal Files

Signal files are **structured result metadata**, not a completion mechanism:

```
path: tmp/swarm/.../research/001-topic.md
size: 4523
status: success
created_at: 2026-02-04T10:54:32+00:00
```

Workers create signals via:
```bash
uv run .claude/skills/mux/tools/signal.py "$SIGNAL_PATH" \
  --path "$OUTPUT_PATH" --status success
```

## Verification

After all task-notifications received:
```bash
# Full summary
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action summary

# One-shot count check (fallback)
uv run .claude/skills/mux/tools/check-signals.py "$SESSION_DIR" --expected N
```

## Worker Launch Pattern

```python
# Launch all workers in ONE message
for subject in subjects:
    Task(
        prompt=f"""Read .claude/skills/mux/agents/researcher.md for protocol.

TASK: Research {subject}
OUTPUT: {session_dir}/research/{subject_slug}.md
SIGNAL: {session_dir}/.signals/research-{subject_slug}.done

FINAL: Return EXACTLY: done""",
        subagent_type="general-purpose",
        model="sonnet",
        run_in_background=True
    )

# Checkpoint
# N workers launched
# Continuing immediately -- runtime notifies on each completion
# After N notifications: run verify.py once, then proceed

voice(f"{len(subjects)} research workers launched")
```

## Error Recovery

| Scenario | Action |
|----------|--------|
| All notifications received, 0 failures | Proceed to next phase |
| All notifications received, some failures | Check verify.py failures, relaunch failed |
| Timeout (fewer than N notifications) | Run check-signals.py, relaunch missing |

## Archive

The former worker-monitor pattern is archived in `_archive/`. It was removed
because the monitor agent reimplemented runtime task-notification as filesystem
polling, adding complexity without value.
