# Worker-Monitor Orchestration Pattern

## Overview

The worker-monitor pattern is a **mandatory** orchestration approach for managing background agent delegation in swarm systems. This pattern ensures:

1. **No unmonitored workers** - Every background worker has a corresponding monitor
2. **Explicit delegation** - Workers and monitors are explicitly identified by `agent_type`
3. **Known completion** - Monitors know the EXPECTED count of workers via `expected_count` parameter
4. **Synchronized launch** - Workers and monitor are launched in the same message batch

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Director Agent                           │
│                                                              │
│  Launches 2 workers + 1 monitor in SAME message:            │
│                                                              │
│  ┌──────────────────┐       ┌─────────────────┐            │
│  │ Worker Agent     │       │  Monitor Agent  │            │
│  │ (run_background) │ ──┐   │ (run_background)│            │
│  │ agent_type:      │   │   │ agent_type:     │            │
│  │  "worker"        │   │   │  "monitor"      │            │
│  │ task_id:         │   │   │ expected_count: │            │
│  │  "worker-001"    │   │   │  2              │            │
│  └──────────────────┘   │   └─────────────────┘            │
│                         │                                   │
│  ┌──────────────────┐   │   Polls for signals:             │
│  │ Worker Agent     │   ├──►  .done files                  │
│  │ (run_background) │   │    .fail files                   │
│  │ agent_type:      │   │                                  │
│  │  "worker"        │   │   Completes when:                │
│  │ task_id:         │   │    received 2 signals            │
│  │  "worker-002"    │   │    (regardless of type)          │
│  └──────────────────┘   │                                  │
│                         │   References worker IDs:         │
│                         └──  worker-001, worker-002        │
└─────────────────────────────────────────────────────────────┘
```

## Pattern Requirements

### Worker Configuration

```python
Task(
    run_in_background=True,        # REQUIRED: Background execution
    agent_type="worker",            # REQUIRED: Explicit type
    task_id="worker-dir-001",       # REQUIRED: Unique identifier
    instructions="Analyze /path",   # REQUIRED: Work description
    subagent_type="executor",       # REQUIRED: How to run
)
```

### Monitor Configuration

```python
Task(
    run_in_background=True,                          # REQUIRED
    agent_type="monitor",                            # REQUIRED: Explicit type
    task_id="monitor-001",                           # REQUIRED: Unique ID
    expected_count=2,                                # REQUIRED: Worker count
    instructions="""Monitor 2 workers:
        - worker-dir-001
        - worker-file-002
        analyzing $PROJECT_ROOT""",
    subagent_type="director",                        # REQUIRED: How to run
)
```

### Key Constraints

1. **No Manual Polling** - Never manually poll signals; use monitor agents instead
2. **No Direct Execution** - Workers don't directly execute tasks; they're delegated
3. **Same-Message Launch** - Workers and monitor MUST be created in same agent message
4. **Pairing Required** - Every worker requires at least one monitor
5. **Explicit Count** - Monitor MUST know expected worker count via `expected_count` parameter or instructions

## Execution Flow

### Phase 1: Delegation

Director agent creates task delegation in a single message:

```python
# Create 2 workers
for i in range(1, 3):
    Task(
        run_in_background=True,
        agent_type="worker",
        task_id=f"worker-analyzer-{i:03d}",
        instructions=f"Analyze directory part {i}...",
        subagent_type="executor",
    )

# Create monitoring agent (SAME message)
Task(
    run_in_background=True,
    agent_type="monitor",
    task_id="monitor-coordinator-001",
    expected_count=2,  # CRITICAL: Know worker count
    instructions="Monitor 2 workers: worker-analyzer-001, worker-analyzer-002...",
    subagent_type="director",
)
```

### Phase 2: Background Execution

- **Workers** run in parallel, analyzing their assigned directory sections
- **Monitor** continuously polls `.signals/` directory for completion signals

### Phase 3: Signal Generation

Each worker creates completion signal when done:

```json
{
  "worker_id": "worker-analyzer-001",
  "status": "completed",
  "findings": {
    "files_analyzed": 247,
    "patterns_found": 12,
    "anomalies": 3
  },
  "timestamp": "2026-02-04T14:35:38.096932+00:00"
}
```

### Phase 4: Completion Detection

Monitor polls and detects completion when total signals >= expected_count:

```python
def poll_for_completion(signals_dir, expected_count=2, timeout=300):
    while elapsed < timeout:
        done = len(list(signals_dir.glob("*.done")))
        failed = len(list(signals_dir.glob("*.fail")))

        if done + failed >= expected_count:
            return {
                "status": "success" if failed == 0 else "partial",
                "complete": done,
                "failed": failed,
            }
```

### Phase 5: Summary Generation

Combine findings from all completed workers:

```python
summary = {
    "workers_completed": 2,
    "workers_expected": 2,
    "status": "SUCCESS",
    "combined_metrics": {
        "total_files": 247,
        "directories": 34,
        "python_files": 89,
        "code_lines": 14250,
    },
    "worker_findings": [
        {...},  # worker-analyzer-001 findings
        {...},  # worker-analyzer-002 findings
    ],
}
```

## Compliance Checks

### Test: Worker Requires Monitor

```python
def test_no_worker_without_monitor(inspector):
    """Verify every worker has a monitor."""
    workers = [c for c in inspector.get_calls("Task")
              if c.parameters.get("agent_type") == "worker"]
    monitors = [c for c in inspector.get_calls("Task")
               if c.parameters.get("agent_type") == "monitor"]

    assert len(monitors) > 0, "Workers require monitor - none found"
```

### Test: Monitor Knows Expected Count

```python
def test_monitor_has_expected_count(inspector):
    """Verify monitor receives EXPECTED count parameter."""
    monitors = [c for c in inspector.get_calls("Task")
               if c.parameters.get("agent_type") == "monitor"]

    for monitor in monitors:
        assert "expected_count" in monitor.parameters \
            or "EXPECTED" in monitor.parameters.get("instructions", "").upper()
```

### Test: Same-Message Launch

```python
def test_workers_and_monitor_same_message(inspector):
    """Verify workers and monitor launched in same message batch."""
    task_calls = inspector.get_calls("Task")
    workers = [c for c in task_calls if c.parameters.get("agent_type") == "worker"]
    monitors = [c for c in task_calls if c.parameters.get("agent_type") == "monitor"]

    # All should be created within 1 second (same message)
    for w in workers:
        for m in monitors:
            time_diff = abs(w.timestamp - m.timestamp)
            assert time_diff < 1.0, "Workers and monitor must launch in same message"
```

### Test: Monitor References Workers

```python
def test_monitor_references_worker_tasks(inspector):
    """Verify monitor instructions reference worker task IDs."""
    workers = [c for c in inspector.get_calls("Task")
              if c.parameters.get("agent_type") == "worker"]
    worker_ids = [w.parameters.get("task_id") for w in workers]

    monitors = [c for c in inspector.get_calls("Task")
               if c.parameters.get("agent_type") == "monitor"]

    for monitor in monitors:
        instructions = monitor.parameters.get("instructions", "")
        for worker_id in worker_ids:
            assert worker_id in instructions, \
                f"Monitor must reference {worker_id}"
```

## Example: 2 Workers Analyzing Directory

See `$PROJECT_ROOT/core/skills/mux/examples/monitor_workers.py` for complete implementation.

### Output

```
WORKER-MONITOR ORCHESTRATION EXAMPLE
================================================================================
Target Directory: $PROJECT_ROOT
Expected Workers: 2

=== LAUNCHING WORKERS ===

[WORKER] Launching worker-dir-analyzer-001
  Role: Directory structure analyzer
  Task ID: worker-dir-analyzer-001
  Agent Type: worker
  Run in Background: True

[WORKER] Launching worker-file-scanner-002
  Role: File content scanner
  Task ID: worker-file-scanner-002
  Agent Type: worker
  Run in Background: True

=== LAUNCHING MONITOR ===

[MONITOR] Launching monitor-coordinator-001
  Role: Director agent monitoring workers
  Agent Type: monitor
  Expected Worker Count: 2
  Monitoring Task IDs: worker-dir-analyzer-001, worker-file-scanner-002

=== MONITOR POLLING FOR COMPLETION ===

[MONITOR] Completion detected!
  Status: success
  Workers completed: 2/2
  Total poll time: 4.02s

=== COMPLETION REPORT ===
Status: SUCCESS
Workers Completed: 2/2
Total Analysis Time: 4.02s

Combined Metrics:
  total_files: 247
  total_directories: 34
  python_files: 89
  test_files: 45
  config_files: 23
  total_code_lines: 14250

All workers completed successfully!
```

## Anti-Patterns

### ❌ NO: Manual Polling Loop

```python
# FORBIDDEN: Director manually polls for signals
while True:
    signals = list(signals_dir.glob("*.done"))
    if len(signals) >= 2:
        break
    time.sleep(1)
```

**Why:** Director should delegate polling to monitor agent.

### ❌ NO: Workers Without Monitor

```python
# FORBIDDEN: Workers created without monitor
Task(run_in_background=True, agent_type="worker", ...)
Task(run_in_background=True, agent_type="worker", ...)
# No monitor created!
```

**Why:** Violates mandatory worker-monitor pairing.

### ❌ NO: Monitor Without Expected Count

```python
# FORBIDDEN: Monitor created without knowing worker count
Task(
    run_in_background=True,
    agent_type="monitor",
    instructions="Monitor workers analyzing directory",
    # NO expected_count!
)
```

**Why:** Monitor must know how many signals to expect.

### ❌ NO: Separate Messages

```python
# FORBIDDEN: Workers and monitor in different message batches
# First message:
Task(run_in_background=True, agent_type="worker", ...)
Task(run_in_background=True, agent_type="worker", ...)

# Second message:  # TOO LATE!
Task(run_in_background=True, agent_type="monitor", expected_count=2, ...)
```

**Why:** Workers and monitor must be created together.

## Signal Files

Completion signals are JSON files in `.signals/` directory:

### Success Signal (`.done` file)

```json
{
  "worker_id": "worker-dir-analyzer-001",
  "status": "completed",
  "analysis_type": "directory_structure",
  "metrics": {
    "total_files": 247,
    "total_directories": 34,
    "max_depth": 6
  },
  "summary": "Directory structure analyzed: 247 files across 34 directories",
  "timestamp": "2026-02-04T14:35:38.096932+00:00"
}
```

### Failure Signal (`.fail` file)

```json
{
  "worker_id": "worker-file-scanner-002",
  "status": "failed",
  "error": "Permission denied while accessing /restricted",
  "timestamp": "2026-02-04T14:35:40.123456+00:00"
}
```

## Summary Aggregation

Monitor combines all worker findings into a unified summary:

```python
def generate_summary(monitor_status, workers_completed, worker_findings):
    return {
        "analysis_target": "$PROJECT_ROOT",
        "monitor_status": "success",
        "workers_completed": 2,
        "workers_expected": 2,
        "total_poll_time_seconds": 4.02,
        "polling_iterations": 5,
        "worker_findings": [
            {
                "worker_id": "worker-dir-analyzer-001",
                "role": "Directory structure analyzer",
                "analysis_type": "directory_structure",
                "summary": "Directory structure analyzed: 247 files across 34 directories",
                "metrics": {...}
            },
            {
                "worker_id": "worker-file-scanner-002",
                "role": "File content scanner",
                "analysis_type": "file_content_scan",
                "summary": "File content scanned: 89 Python files, 45 tests, 23 config files",
                "metrics": {...}
            }
        ],
        "combined_metrics": {
            "total_files": 247,
            "total_directories": 34,
            "python_files": 89,
            "test_files": 45,
            "config_files": 23,
            "total_code_lines": 14250
        },
        "completion_status": "SUCCESS"
    }
```

## Related Files

- **Pattern Implementation:** `$PROJECT_ROOT/core/skills/mux/examples/monitor_workers.py`
- **Compliance Tests:** `$PROJECT_ROOT/core/skills/mux/tests/compliance/test_worker_monitor.py`
- **Polling Tool:** `$PROJECT_ROOT/core/skills/mux/tools/poll-signals.py`
- **Task Manager:** `$PROJECT_ROOT/core/skills/mux/a2a/task-manager.py`
