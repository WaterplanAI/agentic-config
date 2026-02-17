# Worker-Monitor Architecture

## High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                          DIRECTOR AGENT                             │
│                                                                      │
│  "Monitor 2 workers analyzing $PROJECT_ROOT"│
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ MESSAGE BATCH 1: Launch Workers & Monitor                     │ │
│  │ (All created with run_in_background=True)                     │ │
│  │                                                                │ │
│  │  Task 1: Create Worker Agent                                 │ │
│  │  ├─ agent_type: "worker"                                     │ │
│  │  ├─ task_id: "worker-dir-analyzer-001"                       │ │
│  │  ├─ run_in_background: True                                  │ │
│  │  └─ instructions: "Analyze directory structure..."           │ │
│  │                                                                │ │
│  │  Task 2: Create Worker Agent                                 │ │
│  │  ├─ agent_type: "worker"                                     │ │
│  │  ├─ task_id: "worker-file-scanner-002"                       │ │
│  │  ├─ run_in_background: True                                  │ │
│  │  └─ instructions: "Scan file contents..."                    │ │
│  │                                                                │ │
│  │  Task 3: Create Monitor Agent                                │ │
│  │  ├─ agent_type: "monitor"                                    │ │
│  │  ├─ task_id: "monitor-coordinator-001"                       │ │
│  │  ├─ expected_count: 2                                        │ │
│  │  ├─ run_in_background: True                                  │ │
│  │  └─ instructions: "Monitor 2 workers:                        │ │
│  │      worker-dir-analyzer-001, worker-file-scanner-002"       │ │
│  │                                                                │ │
│  │  ✓ Timestamp separation: < 1000ms (same message)             │ │
│  │  ✓ All run_in_background=True                                │ │
│  │  ✓ Monitor has expected_count=2                              │ │
│  │  ✓ Monitor references both worker IDs                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
        │                                    │
        ├────────────────────────────────────┴──────────────────┐
        │                                                        │
        ▼                                                        ▼
┌──────────────────────────────────┐    ┌──────────────────────────────┐
│   WORKER AGENT 1                 │    │  WORKER AGENT 2              │
│   (Background Process)           │    │  (Background Process)        │
│                                  │    │                              │
│ task_id:                         │    │ task_id:                     │
│  worker-dir-analyzer-001         │    │  worker-file-scanner-002     │
│                                  │    │                              │
│ Role: Directory Structure        │    │ Role: File Content Scanner   │
│                                  │    │                              │
│ Work:                            │    │ Work:                        │
│ ├─ Walk directory tree           │    │ ├─ Read all files            │
│ ├─ Count files & directories     │    │ ├─ Detect file types         │
│ ├─ Track depth levels            │    │ ├─ Count code lines          │
│ └─ Find largest files            │    │ └─ Analyze content patterns  │
│                                  │    │                              │
│ Results:                         │    │ Results:                     │
│ ├─ total_files: 247              │    │ ├─ python_files: 89          │
│ ├─ total_directories: 34         │    │ ├─ test_files: 45            │
│ ├─ max_depth: 6                  │    │ ├─ config_files: 23          │
│ └─ largest_file_mb: 12.5         │    │ └─ code_lines_total: 14250   │
└──────────────────────────────────┘    └──────────────────────────────┘
        │                                        │
        │ Creates signal file on complete      │ Creates signal file on complete
        ▼                                        ▼
┌──────────────────────────────────┐    ┌──────────────────────────────┐
│ Signal: .done                    │    │ Signal: .done                │
├──────────────────────────────────┤    ├──────────────────────────────┤
│ File: /tmp/swarm-session/.signals│    │ File: /tmp/swarm-session/.signals
│        /worker-dir-analyzer-001  │    │        /worker-file-scanner-002
│        .done                     │    │        .done                 │
├──────────────────────────────────┤    ├──────────────────────────────┤
│ Content:                         │    │ Content:                     │
│ {                                │    │ {                            │
│   "worker_id":                   │    │   "worker_id":               │
│     "worker-dir-analyzer-001",   │    │     "worker-file-scanner-002",
│   "status": "completed",         │    │   "status": "completed",     │
│   "metrics": {...},              │    │   "metrics": {...},          │
│   "timestamp": "2026-02-04..."   │    │   "timestamp": "2026-02-04..." │
│ }                                │    │ }                            │
└──────────────────────────────────┘    └──────────────────────────────┘
        │                                        │
        └────────────┬───────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ SIGNAL DIRECTORY           │
        │ .signals/                  │
        ├────────────────────────────┤
        │ worker-dir-analyzer-001.   │
        │ done ✓                     │
        │                            │
        │ worker-file-scanner-002.   │
        │ done ✓                     │
        │                            │
        │ Total signals: 2           │
        │ Expected: 2                │
        │ Status: COMPLETE ✓         │
        └────────────────────────────┘
                     │
                     │ Monitor polls this directory
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│         MONITOR AGENT (Background Process)                           │
│         task_id: monitor-coordinator-001                             │
│         expected_count: 2                                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ POLLING LOOP                                                 │  │
│  │                                                              │  │
│  │ while elapsed < timeout:                                   │  │
│  │     complete = len(glob("*.done"))   = 0                    │  │
│  │     failed = len(glob("*.fail"))     = 0                    │  │
│  │     total = complete + failed        = 0                    │  │
│  │     print(f"Poll #1: {complete}/{expected} complete")       │  │
│  │                                                              │  │
│  │     [delay 1 second]                                         │  │
│  │                                                              │  │
│  │     complete = len(glob("*.done"))   = 1                    │  │
│  │     failed = len(glob("*.fail"))     = 0                    │  │
│  │     total = complete + failed        = 1                    │  │
│  │     print(f"Poll #2: {complete}/{expected} complete")       │  │
│  │                                                              │  │
│  │     [delay 1 second]                                         │  │
│  │                                                              │  │
│  │     complete = len(glob("*.done"))   = 2                    │  │
│  │     failed = len(glob("*.fail"))     = 0                    │  │
│  │     total = complete + failed        = 2                    │  │
│  │                                                              │  │
│  │     if total >= expected_count (2 >= 2):   ✓                │  │
│  │         BREAK LOOP                                           │  │
│  │         status = "success"                                  │  │
│  │         return poll_result                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Poll Result:                                                        │
│  ├─ status: "success"                                              │
│  ├─ complete: 2                                                    │
│  ├─ failed: 0                                                      │
│  ├─ expected: 2                                                    │
│  ├─ elapsed: 4.02 seconds                                          │
│  └─ polling_iterations: 5                                          │
└──────────────────────────────────────────────────────────────────────┘
                     │
                     │ Poll completed successfully
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│        SUMMARY AGGREGATION                                           │
│                                                                      │
│  Read both signal files:                                            │
│  ├─ /tmp/swarm-session/.signals/worker-dir-analyzer-001.done       │
│  └─ /tmp/swarm-session/.signals/worker-file-scanner-002.done       │
│                                                                      │
│  Combine metrics:                                                   │
│  ├─ total_files: 247 (from worker-dir-analyzer-001)                │
│  ├─ total_directories: 34 (from worker-dir-analyzer-001)           │
│  ├─ python_files: 89 (from worker-file-scanner-002)                │
│  ├─ test_files: 45 (from worker-file-scanner-002)                  │
│  ├─ config_files: 23 (from worker-file-scanner-002)                │
│  └─ code_lines_total: 14250 (from worker-file-scanner-002)         │
│                                                                      │
│  Generate report:                                                   │
│  ├─ completion_status: "SUCCESS"                                   │
│  ├─ workers_completed: 2                                           │
│  ├─ workers_expected: 2                                            │
│  ├─ total_poll_time_seconds: 4.02                                  │
│  ├─ polling_iterations: 5                                          │
│  ├─ worker_findings: [...]                                         │
│  └─ combined_metrics: {...}                                        │
└──────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
            ┌─────────────────────┐
            │   FINAL SUMMARY     │
            │   (JSON OUTPUT)     │
            │                     │
            │  {                  │
            │    "status":        │
            │      "success",     │
            │    "workers":       │
            │      2/2,           │
            │    "metrics":       │
            │      {...},         │
            │    "time":          │
            │      4.02s          │
            │  }                  │
            └─────────────────────┘
```

## Data Flow Sequence

```
TIME │ DIRECTOR           │ WORKER 1          │ WORKER 2          │ MONITOR
─────┼────────────────────┼───────────────────┼───────────────────┼─────────────────
 t0  │ Create 2 workers + │
     │ 1 monitor          │
     │ (same message)     │
     │                    │
 t1  │ ✓ (returns)        │ START             │ START             │ START
     │                    │ "Analyzing..."    │ "Scanning..."     │ "Polling..."
     │
 t2  │                    │ [working]         │ [working]         │ Poll: 0/2
     │                    │                   │                   │
 t3  │                    │ [working]         │ [working]         │ Poll: 0/2
     │
 t4  │                    │ COMPLETE          │ [working]         │ Poll: 1/2 ✓
     │                    │ Create signal     │                   │ (detected)
     │                    │
 t5  │                    │                   │ COMPLETE          │ Poll: 2/2 ✓
     │                    │                   │ Create signal     │ BREAK
     │                    │                   │                   │
 t6  │                    │                   │                   │ Aggregate
     │                    │                   │                   │ Combine findings
     │
 t7  │                    │                   │                   │ Generate summary
     │
 t8  │ REQUEST: Check     │                   │                   │ RETURN
     │ monitor status     │                   │                   │ JSON summary
     │
 t9  │ RECEIVE: Summary   │                   │                   │
     │ Process results    │                   │                   │
     │ Output to user     │                   │                   │
```

## State Machine

```
DIRECTOR AGENT
├─ Initial: Ready to delegate
├─ Action: Create workers
├─ Action: Create monitor (same message)
├─ State: Awaiting completion
└─ Final: Process monitor results

WORKER AGENTS
├─ State: PENDING
├─ Transition: ► WORKING (when started)
├─ Transition: ► COMPLETED (when done)
│   └─ Action: Create .done signal file
└─ Transition: ► FAILED (on error)
    └─ Action: Create .fail signal file

MONITOR AGENT
├─ Initial: PENDING
├─ Transition: ► WORKING (starts polling)
│   └─ Loop: Check signal count
│       ├─ while total_signals < expected_count:
│       │   └─ sleep(interval)
│       │   └─ recount signals
│       └─ else: BREAK
├─ Transition: ► COMPLETED (when expected signals found)
│   ├─ Action: Read signal files
│   ├─ Action: Aggregate metrics
│   ├─ Action: Generate summary
│   └─ State: Ready to return results
└─ Transition: ► TIMEOUT (if elapsed > timeout)
    └─ State: Return partial results
```

## Signal File Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│ WORKER: worker-dir-analyzer-001                                │
│                                                                 │
│ t=0: Created by director                                       │
│      Status: PENDING                                           │
│                                                                 │
│ t=1: Started background execution                             │
│      Status: WORKING                                           │
│      Signal file: Does not exist yet                          │
│                                                                 │
│ t=4: Completed analysis                                       │
│      Status: COMPLETED                                         │
│      Signal file: /tmp/swarm-session/.signals/                │
│                   worker-dir-analyzer-001.done                │
│      Content: {                                               │
│                  "worker_id": "worker-dir-analyzer-001",      │
│                  "status": "completed",                       │
│                  "metrics": {                                 │
│                    "total_files": 247,                        │
│                    "total_directories": 34,                   │
│                    ...                                        │
│                  },                                           │
│                  "timestamp": "2026-02-04T14:35:38..."       │
│                }                                              │
│      Disk State: File exists at .signals/                    │
│                  worker-dir-analyzer-001.done                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ MONITOR: Polls every 1 second                                  │
│                                                                 │
│ Poll #1 (t=1): list(.signals/*.done) = []                     │
│                 list(.signals/*.fail) = []                     │
│                 Total: 0/2                                     │
│                 Action: sleep(1), continue                     │
│                                                                 │
│ Poll #2 (t=2): list(.signals/*.done) = []                     │
│                 list(.signals/*.fail) = []                     │
│                 Total: 0/2                                     │
│                 Action: sleep(1), continue                     │
│                                                                 │
│ Poll #3 (t=3): list(.signals/*.done) = []                     │
│                 list(.signals/*.fail) = []                     │
│                 Total: 0/2                                     │
│                 Action: sleep(1), continue                     │
│                                                                 │
│ Poll #4 (t=4): list(.signals/*.done) =                        │
│                   [worker-dir-analyzer-001.done]              │
│                 list(.signals/*.fail) = []                     │
│                 Total: 1/2                                     │
│                 Action: sleep(1), continue                     │
│                                                                 │
│ Poll #5 (t=5): list(.signals/*.done) =                        │
│                   [worker-dir-analyzer-001.done,              │
│                    worker-file-scanner-002.done]              │
│                 list(.signals/*.fail) = []                     │
│                 Total: 2/2 ✓                                   │
│                 Action: BREAK LOOP                             │
│                         status = "success"                     │
│                         return result                          │
│                                                                 │
│ Summary Generation:                                            │
│   - Read worker-dir-analyzer-001.done                          │
│   - Read worker-file-scanner-002.done                          │
│   - Combine metrics from both files                            │
│   - Generate final JSON summary                               │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling

```
SCENARIO 1: Worker Fails
└─ worker-file-scanner-002 encounters permission error
   ├─ Action: Create .fail signal file
   ├─ File: /tmp/swarm-session/.signals/
   │         worker-file-scanner-002.fail
   ├─ Content: {
   │     "error": "Permission denied: /restricted",
   │     "worker_id": "worker-file-scanner-002"
   │   }
   └─ Monitor behavior:
       ├─ Detects total signals = 1 done + 1 fail = 2
       ├─ Completion triggered (total >= expected)
       ├─ status = "partial" (because failed > 0)
       └─ Returns summary with failure flag

SCENARIO 2: Worker Hangs (Timeout)
└─ worker-file-scanner-002 never completes
   ├─ Monitor polls for timeout duration (300s default)
   ├─ At t=300: elapsed >= timeout
   ├─ Signals detected: 1 done, 0 fail = 1/2
   ├─ status = "timeout"
   └─ Returns partial results with timeout flag

SCENARIO 3: Both Workers Complete Successfully
└─ (Nominal path - see main flow above)
   ├─ Both create .done signals
   ├─ Total signals = 2 done, 0 fail = 2/2
   ├─ status = "success"
   └─ Returns complete summary
```

## Performance Characteristics

```
TIMELINE
────────────────────────────────────────────────────
Worker 1 (dir-analyzer)    [██████] (3 sec)
Worker 2 (file-scanner)    [        ██████████] (5 sec)
Monitor (polling)          [████████████████] (4 sec polling)
────────────────────────────────────────────────────
0s       1s       2s       3s       4s       5s

Critical Path: Worker 2 (5s) + Monitor detection (1s) = ~6s total

Polling Overhead:
- Poll interval: 1 second
- Expected signals: 2
- Worst case: 2 * interval = 2 seconds to detect completion
- Typical case: 1-2 polls after completion detected

Resource Usage:
- Director: Minimal (just creates tasks)
- Worker 1: CPU-bound (directory walk)
- Worker 2: I/O-bound (file reads)
- Monitor: CPU + I/O minimal (just polling)
```

## Compliance Checklist

```
✓ Workers and Monitor both have agent_type specified
✓ Workers have agent_type="worker"
✓ Monitor has agent_type="monitor"
✓ All tasks have run_in_background=True
✓ All tasks have unique task_id
✓ Monitor has expected_count parameter
✓ Monitor instructions reference worker task_ids
✓ Workers and monitor launched in same message (< 1s)
✓ No manual polling in director code
✓ Monitor handles completion detection
✓ Signals stored in standard .signals/ directory
✓ Summary aggregation from all worker results
```
