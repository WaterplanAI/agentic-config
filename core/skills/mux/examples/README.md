# Worker-Monitor Pattern Examples

This directory contains examples and documentation for the **mandatory worker-monitor orchestration pattern** used in swarm agent delegation.

## Quick Start

Run the demonstration:

```bash
./run_monitor_example.sh
```

This executes a complete example of monitoring 2 background workers analyzing a directory.

## Files

### Documentation

- **WORKER_MONITOR_PATTERN.md** - Complete pattern specification and compliance requirements
  - Architecture diagram
  - Detailed execution flow
  - Configuration requirements
  - Anti-patterns to avoid
  - Compliance test examples

### Implementation

- **monitor_workers.py** - Python implementation of the worker-monitor pattern
  - WorkerMonitorCoordinator class
  - Worker launch and background execution
  - Monitor polling for completion signals
  - Summary aggregation from worker findings
  - Runnable example with 2 directory analysis workers

- **run_monitor_example.sh** - Quick demonstration script
  - Shows pattern in action
  - Explains key requirements
  - Demonstrates successful completion

## Pattern Summary

### Requirements

```
1. Workers: run_in_background=True, agent_type="worker"
2. Monitor: run_in_background=True, agent_type="monitor", expected_count=2
3. Both launched in SAME message
4. Monitor receives task IDs of all workers
5. Monitor knows EXPECTED worker count
```

### Execution

```
[Director Agent]
    |
    ├─► Launch 2 Workers (background)
    |       • worker-dir-analyzer-001 (analyze directory structure)
    |       • worker-file-scanner-002 (scan file contents)
    |
    └─► Launch Monitor (background, same message)
            • Monitor polls for 2 completion signals
            • Combines findings when both complete
            • Returns aggregated summary
```

### Output

When both workers complete, the monitor generates a summary:

```json
{
  "analysis_target": "$PROJECT_ROOT",
  "monitor_status": "success",
  "workers_completed": 2,
  "workers_expected": 2,
  "total_poll_time_seconds": 4.02,
  "worker_findings": [
    {
      "worker_id": "worker-dir-analyzer-001",
      "role": "Directory structure analyzer",
      "analysis_type": "directory_structure",
      "metrics": {
        "total_files": 247,
        "total_directories": 34
      }
    },
    {
      "worker_id": "worker-file-scanner-002",
      "role": "File content scanner",
      "analysis_type": "file_content_scan",
      "metrics": {
        "python_files": 89,
        "test_files": 45
      }
    }
  ],
  "combined_metrics": {
    "total_files": 247,
    "total_directories": 34,
    "python_files": 89,
    "test_files": 45
  },
  "completion_status": "SUCCESS"
}
```

## Key Concepts

### Worker Agent

- Runs in **background** (doesn't block caller)
- Has explicit **agent_type="worker"**
- Receives **unique task_id** (e.g., "worker-001")
- Creates **.done** or **.fail** signal file when complete
- Does NOT poll or manually check completion

### Monitor Agent

- Runs in **background** (doesn't block caller)
- Has explicit **agent_type="monitor"**
- Receives **expected_count** parameter (number of workers)
- Polls **.signals/** directory for completion signals
- Returns when expected count of signals received
- Aggregates findings from all completed workers

### Same-Message Launch

Both workers and monitor MUST be created in the same agent message batch:

```python
# Correct: All in same message
Task(agent_type="worker", ...)
Task(agent_type="worker", ...)
Task(agent_type="monitor", expected_count=2, ...)

# Wrong: Workers first, monitor later
Task(agent_type="worker", ...)
Task(agent_type="worker", ...)
# New message
Task(agent_type="monitor", ...)  # Too late!
```

## Compliance

The pattern includes compliance tests to ensure correct usage:

```python
# Every worker requires a monitor
assert len(monitors) > 0, "Workers require monitor"

# Monitor knows expected count
assert "expected_count" in monitor.parameters

# Same-message launch (within 1 second)
assert abs(worker.timestamp - monitor.timestamp) < 1.0

# Monitor references worker task IDs
assert all(wid in monitor.instructions for wid in worker_ids)
```

See WORKER_MONITOR_PATTERN.md for complete test specifications.

## Use Cases

### 1. Parallel Directory Analysis

**Goal:** Analyze a large directory in parallel

**Setup:**
- 2 workers: one scans directory structure, one scans file contents
- Monitor waits for both to complete

**Result:** Combined metrics about directory

### 2. Distributed Code Review

**Goal:** Review code in parallel sections

**Setup:**
- 2 workers: one reviews classes, one reviews functions
- Monitor aggregates findings

**Result:** Complete code review summary

### 3. Data Processing Pipeline

**Goal:** Process large dataset in chunks

**Setup:**
- 2 workers: one processes first half, one processes second half
- Monitor combines results

**Result:** Fully processed dataset

## Common Mistakes

### ❌ Manual Polling

```python
# WRONG: Director manually polls signals
while not all_signals_present:
    time.sleep(1)
```

**Fix:** Use monitor agent to poll.

### ❌ Missing Agent Type

```python
# WRONG: No agent_type specified
Task(run_in_background=True, task_id="worker-001", ...)
```

**Fix:** Set `agent_type="worker"` or `agent_type="monitor"`.

### ❌ Monitor Without Count

```python
# WRONG: Monitor doesn't know how many workers
Task(agent_type="monitor", instructions="Monitor workers", ...)
```

**Fix:** Include `expected_count=2` parameter.

### ❌ Separate Messages

```python
# WRONG: Workers and monitor launched separately
Task(agent_type="worker", ...)
Task(agent_type="worker", ...)
# ... some code ...
Task(agent_type="monitor", ...)
```

**Fix:** Launch all in same message.

## Related Resources

- **Full Pattern Spec:** WORKER_MONITOR_PATTERN.md
- **Compliance Tests:** /core/skills/mux/tests/compliance/test_worker_monitor.py
- **Polling Tool:** /core/skills/mux/tools/poll-signals.py
- **Task Manager:** /core/skills/mux/a2a/task-manager.py

## Running the Example

### Basic Run

```bash
./run_monitor_example.sh
```

### With Custom Directory

```bash
python3 monitor_workers.py /path/to/analyze --expected 2
```

### With Custom Timeout

```bash
python3 monitor_workers.py /path/to/analyze --expected 2 --timeout 60
```

## Understanding the Output

The example output shows:

1. **LAUNCHING WORKERS** - 2 workers created with task IDs and configurations
2. **LAUNCHING MONITOR** - Monitor created with expected_count=2
3. **SIMULATING BACKGROUND EXECUTION** - Workers run in parallel
4. **MONITOR POLLING** - Monitor polls for signals until 2 completions detected
5. **GENERATING SUMMARY** - Aggregates findings from both workers
6. **FINAL SUMMARY** - JSON output with combined metrics
7. **COMPLETION REPORT** - Human-readable status and findings

## Testing the Pattern

To verify correct implementation:

```python
from tests.conftest import inspector

def test_implementation(inspector):
    # Your agent code...

    # Verify workers created
    workers = [c for c in inspector.get_calls("Task")
              if c.parameters.get("agent_type") == "worker"]
    assert len(workers) == 2

    # Verify monitor created with expected count
    monitors = [c for c in inspector.get_calls("Task")
               if c.parameters.get("agent_type") == "monitor"]
    assert len(monitors) == 1
    assert monitors[0].parameters.get("expected_count") == 2

    # Verify same-message launch
    for m in monitors:
        for w in workers:
            assert abs(m.timestamp - w.timestamp) < 1.0
```

## Next Steps

1. Review WORKER_MONITOR_PATTERN.md for complete specification
2. Study monitor_workers.py for implementation details
3. Run run_monitor_example.sh to see pattern in action
4. Implement pattern in your own agents following these examples
