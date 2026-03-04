# MUX Examples Index

## Current Pattern: Task-Notification Completion

Workers write signal files as structured result metadata. Orchestrator receives
task-notifications from the runtime and uses `verify.py` for post-completion
verification.

### Documentation
- **README.md** - Completion tracking pattern overview

### Tools
- `check-signals.py` - One-shot signal checker (no polling)
- `verify.py` - Signal verification and summary
- `signal.py` - Signal file creation

## Archive

Historical worker-monitor pattern documentation (deprecated):
- `_archive/WORKER_MONITOR_PATTERN.md` - Former mandatory pattern specification
- `_archive/ARCHITECTURE.md` - Former visual data flows with monitor polling
- `_archive/monitor_workers.py` - Former reference implementation

These files are preserved for audit trail. The monitor agent was removed because
it reimplemented runtime task-notification as filesystem polling, introducing
signal-path divergence, orchestrator bypass patterns, dual completion channels,
expected-count mismatches, and wasted compute.

## Integration

- `tools/verify.py` - Post-completion signal verification
- `tools/check-signals.py` - One-shot signal count (fallback)
- `tools/signal.py` - Signal file creation by workers
