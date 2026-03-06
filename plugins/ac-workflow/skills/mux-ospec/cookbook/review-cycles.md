# Review Cycles

N-cycle review pattern for iterative quality improvement in o_spec workflows.

## Overview

Review cycles implement REVIEW + FIX loops until PASS or MAX_CYCLES reached. Each cycle produces its own signal for tracking.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_CYCLES` | 3 | Maximum review iterations per phase |
| `--cycles=N` | - | Override via command line |

## Loop Structure

```python
MAX_CYCLES = 3  # Default, override with --cycles=N

for cycle in range(1, MAX_CYCLES + 1):
    # 1. Launch REVIEW
    Task(
        prompt=f"""Invoke spec-reviewer.

SPEC: {spec_path}
IMPLEMENTATION: current working directory
PHASE: {phase_num}
CYCLE: {cycle}

OUTPUT: {{session}}/reviews/phase-{phase_num}-review-{cycle}.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-review-{cycle}.done

Return EXACTLY: done""",
        model="opus",
        run_in_background=True
    )

    # 2. Wait for task-notification (review completion)
    # 3. Parse grade from review output

    if grade == "PASS":
        break  # Early exit

    if cycle < MAX_CYCLES:
        # 4. Launch FIX
        Task(
            prompt=f"""Invoke spec-fixer.

REVIEW: {{session}}/reviews/phase-{phase_num}-review-{cycle}.md
IMPLEMENTATION: current working directory
SCOPE: targeted

Commit: spec(NNN): FIX phase-{phase_num} cycle-{cycle}

SIGNAL: {{session}}/.signals/phase-{phase_num}-fix-{cycle}.done

Return EXACTLY: done""",
            model="sonnet",
            run_in_background=True
        )
        # 5. Wait for fix signal, then continue to next cycle
```

## Grade-Based Control Flow

| Grade | Behavior |
|-------|----------|
| PASS | Exit loop immediately |
| WARN | Trigger fixer, continue to next cycle |
| FAIL | Trigger fixer, continue to next cycle |

### Grading Matrix

| Compliance | Quality | Final Grade |
|------------|---------|-------------|
| PASS | PASS | PASS |
| PASS | WARN | WARN |
| PASS | FAIL | FAIL |
| FAIL | - | FAIL |

## Signal Creation Per Cycle

Each cycle creates distinct signals:

```
session-dir/
├── .signals/
│   ├── phase-1-review-1.done    # Cycle 1 review
│   ├── phase-1-fix-1.done       # Cycle 1 fix
│   ├── phase-1-review-2.done    # Cycle 2 review
│   ├── phase-1-fix-2.done       # Cycle 2 fix
│   └── phase-1-review-3.done    # Cycle 3 review (final)
└── reviews/
    ├── phase-1-review-1.md
    ├── phase-1-review-2.md
    └── phase-1-review-3.md
```

## Early Exit Optimization

When grade is PASS:
1. No fixer launched
2. Loop terminates immediately
3. Phase proceeds to next stage

```python
# Grade extraction from review output
if "## Grade: PASS" in review_content:
    grade = "PASS"
elif "## Grade: WARN" in review_content:
    grade = "WARN"
else:
    grade = "FAIL"
```

## Cycle Tracking

Orchestrator tracks cycles via signal naming convention:

```bash
# Check current cycle status
uv run tools/verify.py "$SESSION_DIR" --action summary

# Output shows cycle progression:
# phase-1-review-1.done: success
# phase-1-fix-1.done: success
# phase-1-review-2.done: success (PASS - no fix needed)
```

## Multi-Phase Cycle Example

```python
phases = [1, 2, 3]

for phase_num in phases:
    # Wait for phase dependencies if any

    # Implementation first
    Task(prompt=f"IMPLEMENT phase-{phase_num}...", ...)

    # Then review cycles
    for cycle in range(1, MAX_CYCLES + 1):
        Task(prompt=f"REVIEW phase-{phase_num} cycle-{cycle}...", ...)

        # Wait, check grade
        if grade == "PASS":
            break

        if cycle < MAX_CYCLES:
            Task(prompt=f"FIX phase-{phase_num} cycle-{cycle}...", ...)
```

## Commit Protocol

Each fix creates a commit:

```bash
# Commit message format
spec(NNN): FIX phase-{phase_num} cycle-{cycle} - {title}

# Examples
spec(042): FIX phase-1 cycle-1 - Address compliance issues
spec(042): FIX phase-2 cycle-2 - Quality improvements
```

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| PASS on cycle 1 | No fix, immediate exit |
| WARN/FAIL on final cycle | STAGE_FAILED, escalate to user (ONLY PASS proceeds) |
| Fixer timeout | Retry once, then escalate |
| MAX_CYCLES=1 | Single review, no fix attempts. WARN/FAIL = escalate to user |
