# Error Recovery


> Authoritative contract (wins on conflict):
> - full: CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
> - lean: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
> - leanest: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
> - GATHER = RESEARCH; CONFIRM_SC is mandatory before PLAN
> - REVIEW/TEST/SENTINEL/SELF_VALIDATION are PASS-only gates
> - notify-first pacing; no polling loops; blocked/stuck defaults to user escalation
> - every stage must commit every changed repo and report `repo_scope`, `root_commit`, `spec_commit` (root first, spec second when both changed)


Handling failures in the o_spec workflow via MUX orchestration.

## Error Categories

| Category | Severity | Recovery Strategy |
|----------|----------|-------------------|
| Agent Timeout | WARN | Run inactivity watchdog one-shot verify, then escalate to user by default |
| Signal Missing | WARN | Verify output once; recreate signal if output exists, otherwise escalate to user |
| Grade FAIL | WARN | Launch fixer, retry cycle |
| Context Overflow | FATAL | Consolidate partial artifacts, escalate to user before any restart |
| Tool Failure | ERROR | Delegate retry to agent |
| Network Failure | ERROR | Retry with backoff, then escalate to user |

## Agent Timeout Recovery

### Detection

Check signals after task-notification.

```bash
uv run tools/verify.py "$SESSION_DIR" --action missing --expected 5
```

Output indicates missing signals:
```
Expected: 5
Found: 3
Missing:
- research-product-c.done
- audit-integration.done
```

### Recovery Pattern

Escalate first with evidence. Relaunch is allowed only when the user (or a documented explicit override) approves it.

```python
# Original task appears stalled after inactivity watchdog
watchdog_summary = uv_run(
    f"tools/verify.py {session_dir}/.signals --action summary"
)

AskUserQuestion(
    question=f"""Worker inactivity detected.

Summary:
{watchdog_summary}

Default action is escalation. Choose next step:
1. Keep waiting for task-notification
2. Relaunch with tighter scope (explicit override)
3. Abort stage
""",
    format="number"
)

# Only execute if option 2 / explicit override is selected
Task(
    prompt=f"""Invoke Skill(skill="spec", args="RESEARCH {spec_path} --focus {topic} --max-depth 1").

SCOPE: Reduced to single topic
REASON: Explicit override after user escalation

OUTPUT: {{session}}/research/{topic}.md
SIGNAL: {{session}}/.signals/research-{topic}.done

Return EXACTLY: done""",
    model="medium-tier",
    run_in_background=True
)
```

## Review Grade FAIL Recovery

### Review Cycle Protocol

```
IMPLEMENT -> REVIEW -> [PASS?] -> TEST
                |
               FAIL
                |
              FIX -> REVIEW (loop)
```

### Max Loops Enforcement

```python
MAX_LOOPS = 3  # Configurable via --cycles=N

for cycle in range(1, MAX_LOOPS + 1):
    # Review
    review_grade = await_review_signal()

    if review_grade == "PASS":
        break  # Early exit

    if cycle == MAX_LOOPS:
        # ONLY PASS proceeds - escalate to user
        raise StageFailedError(f"Phase {phase_num}: grade={review_grade} after {MAX_LOOPS} cycles. ONLY PASS proceeds.")
        # Orchestrator escalates to user via AskUserQuestion

    # Fix
    Task(
        prompt=f"""Invoke spec-fixer.

REVIEW: {{session}}/reviews/phase-{phase_num}-review-{cycle}.md
SCOPE: targeted

SIGNAL: {{session}}/.signals/phase-{phase_num}-fix-{cycle}.done

Return EXACTLY: done""",
        model="medium-tier",
        run_in_background=True
    )
```

### Grade Interpretation

| Grade | Action |
|-------|--------|
| PASS | Proceed to next stage |
| WARN | Launch fixer, continue loop |
| FAIL | Launch fixer, continue loop |

## Context Overflow Recovery

### Detection

Agent reports context limit reached.

### Recovery Strategy

1. Stop current phase
2. Run consolidation on partial work
3. Escalate to user with the consolidated evidence
4. Restart only when an explicit override is approved

```python
# Consolidate partial work
Task(
    prompt=f"""Read agents/consolidator.md.

SESSION: {{session}}
SCOPE: phase-{phase_num} partial artifacts

OUTPUT: {{session}}/phases/phase-{phase_num}/consolidated-partial.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-consolidated.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)

AskUserQuestion(
    question=f"""Context overflow detected in phase {phase_num}.

Consolidated partial artifact:
{{session}}/phases/phase-{phase_num}/consolidated-partial.md

Default action is escalation. Approve restart?""",
    format="yes/no"
)

# Only run if explicit override/user approval is YES
Task(
    prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} --phase {phase_num}").

CONTEXT: {{session}}/phases/phase-{phase_num}/consolidated-partial.md
REASON: Explicit override after escalation

SIGNAL: {{session}}/.signals/phase-{phase_num}-implement.done

Return EXACTLY: done""",
    model="medium-tier",
    run_in_background=True
)
```

## Test Failure Recovery

### Framework Detection Failure

```python
# If detect-repo-type.py fails
Task(
    prompt=f"""Invoke spec-tester with explicit framework.

SPEC: {spec_path}
FRAMEWORK: pytest  # Manual override
SCOPE: unit

OUTPUT: {{session}}/tests/test-results.json
SIGNAL: {{session}}/.signals/test.done

Return EXACTLY: done""",
    model="medium-tier",
    run_in_background=True
)
```

### Test Execution Failure

```python
# If tests fail
test_results = read_test_results()

if test_results["failed"] > 0:
    # Launch fixer for test failures
    Task(
        prompt=f"""Invoke spec-fixer.

REVIEW: {{session}}/tests/test-results.json
SCOPE: targeted

Fix failing tests:
{format_failing_tests(test_results)}

SIGNAL: {{session}}/.signals/test-fix.done

Return EXACTLY: done""",
        model="medium-tier",
        run_in_background=True
    )
```

## Signal Protocol Errors

### Missing Signal File

```python
# Signal file not created
# Check if output exists
if output_exists and not signal_exists:
    # Agent forgot to signal - create manually
    uv_run(f"tools/signal.py {signal_path} --path {output_path} --status success")
```

### Corrupted Signal

```python
# Signal JSON invalid
try:
    signal_data = json.loads(signal_content)
except json.JSONDecodeError:
    # Recreate signal from output
    uv_run(f"tools/signal.py {signal_path} --path {output_path} --status success")
```

## State Recovery

### Workflow State Schema

```yaml
session_id: "HHMMSS-xxxxxxxx"
command: "mux-ospec"
status: "in_progress"
current_stage: "IMPLEMENT"
current_step: 4
current_step_status: "in_progress"
error_context:
  type: "agent_timeout"
  phase: 2
  cycle: 1
  message: "Review agent timed out after 300s"
resume_instruction: "Resume from IMPLEMENT phase-2 with: /mux-ospec resume"
```

### Resume From Error

```python
# Read state file
state = load_state(session_dir)

if state["error_context"]:
    error = state["error_context"]

    if error["type"] == "agent_timeout":
        # Default: escalate with inactivity evidence
        escalate_timeout_to_user(error["phase"])

    elif error["type"] == "grade_fail":
        # Continue fix cycle
        continue_fix_cycle(error["phase"], error["cycle"])

    elif error["type"] == "context_overflow":
        # Consolidate evidence and escalate before restart
        consolidate_then_escalate(error["phase"])
```

## Completion Timeout Recovery

### Never Poll for Completion

If task-notification is delayed, use verify.py one-shot check - never poll in a loop.

```python
# WRONG - polling loop
while not signal_exists:
    time.sleep(5)  # NEVER DO THIS

# RIGHT - inactivity-only watchdog (one-shot)
# Bash("uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py {session}/.signals --action summary")
# If worker still active (signal missing), wait for next task-notification
# If worker appears stuck (no progress), escalate to user with evidence
# Relaunch is allowed only when explicit override/user approval exists
```

## Error Escalation

### Automatic Retry Limits

| Error Type | Max Retries | Escalation |
|------------|-------------|------------|
| Agent Timeout | 2 | Ask user |
| Grade WARN/FAIL | cycles (default 3) | STAGE_FAILED, escalate to user (ONLY PASS proceeds) |
| Test Failure | 2 | Ask user |
| Network Failure | 3 | Abort |

### User Escalation

```python
# After max retries
AskUserQuestion(
    question=f"""Phase {phase_num} failed after {max_retries} attempts.

Error: {error_message}

Options:
1. Retry with different model (high-tier -> medium-tier)
2. Abort workflow

Note: pass-only gates prohibit skip-and-continue.
Select option:""",
    format="number"
)
```

## Self-Validation Loop

Post-SENTINEL validation with recovery.

```
SENTINEL -> [ALL SC PASS?]
                |
               yes -> COMPLETE
               no  -> DEBUG -> FIX -> REVALIDATE (loop)
```

### Max Validation Iterations

```python
MAX_VALIDATION_LOOPS = 3

for iteration in range(1, MAX_VALIDATION_LOOPS + 1):
    # Run validation
    validation_result = await_validation()

    if validation_result["all_pass"]:
        break  # Success

    if iteration == MAX_VALIDATION_LOOPS:
        # ONLY PASS completes workflow - escalate to user
        raise StageFailedError(f"Validation failed after {MAX_VALIDATION_LOOPS} attempts. Failing SC: {validation_result['failing_sc']}")
        # Orchestrator escalates to user via AskUserQuestion

    # Fix failing criteria
    Task(
        prompt=f"""Fix failing success criteria.

FAILING: {validation_result['failing_sc']}

SIGNAL: {{session}}/.signals/validation-fix-{iteration}.done

Return EXACTLY: done""",
        model="medium-tier",
        run_in_background=True
    )
```

## Logging Protocol

### Error Log Location

```
{session}/
  logs/
    error-{timestamp}.log
    recovery-{timestamp}.log
```

### Log Format

```
[2026-02-04T10:30:00Z] ERROR phase-2/review: Agent timeout after inactivity threshold
[2026-02-04T10:30:05Z] ESCALATION: Sent evidence summary to user for decision
[2026-02-04T10:34:00Z] DECISION: User approved relaunch override with tighter scope
```
