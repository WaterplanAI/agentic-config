# Stage Patterns

Patterns for executing o_spec stages via MUX delegation.

## Stage Delegation Template

All stages delegate via Task() with explicit Skill() invocation.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="{STAGE} {spec_path} [options]").

OUTPUT: {{session}}/{stage_dir}/output.md
SIGNAL: {{session}}/.signals/{stage_name}.done

Return EXACTLY: done""",
    model="{tier_model}",
    run_in_background=True
)
```

## Stage-Specific Patterns

### CREATE Stage

Generate spec from inline prompt.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="CREATE {inline_prompt}").

OUTPUT: {spec_path}
SIGNAL: {{session}}/.signals/create.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

**Skip Condition**: Spec file already exists.

### RESEARCH Stage

Deep investigation of spec domain.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="RESEARCH {spec_path} ultrathink").

OUTPUT: {{session}}/research/findings.md
SIGNAL: {{session}}/.signals/research.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

**Parallel Variant**: Split by research topic.

```python
topics = ["architecture", "integrations", "edge-cases"]
for topic in topics:
    Task(
        prompt=f"""Invoke Skill(skill="spec", args="RESEARCH {spec_path} --focus {topic}").

OUTPUT: {{session}}/research/{topic}.md
SIGNAL: {{session}}/.signals/research-{topic}.done

Return EXACTLY: done""",
        model="opus",
        run_in_background=True
    )
```

### PLAN Stage

Generate implementation strategy.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").

OUTPUT: {{session}}/plan/strategy.md
SIGNAL: {{session}}/.signals/plan.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

**TDD Strategy**: Plan includes test-first approach.

### PLAN_REVIEW Stage (Full Mode)

Review plan quality before implementation.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="PLAN_REVIEW {spec_path} ultrathink").

OUTPUT: {{session}}/plan/review.md
SIGNAL: {{session}}/.signals/plan-review.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

### IMPLEMENT Stage

Execute implementation per spec requirements.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} ultrathink").

Commit changes with: spec(NNN): IMPLEMENT - {title}

SIGNAL: {{session}}/.signals/implement.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

**Phased Variant**: Implementation split by phase.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} --phase {phase_num}").

Scope: Phase {phase_num} deliverables only
Commit changes with: spec(NNN): IMPLEMENT phase-{phase_num}

SIGNAL: {{session}}/.signals/phase-{phase_num}-implement.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### REVIEW Stage

Two-phase quality review (compliance + quality).

```python
Task(
    prompt=f"""Invoke spec-reviewer.

SPEC: {spec_path}
IMPLEMENTATION: current working directory
PHASE: {phase_num}
CYCLE: {cycle_num}

OUTPUT: {{session}}/reviews/phase-{phase_num}-review-{cycle_num}.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-review-{cycle_num}.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

**Grading Matrix**:

| Compliance | Quality | Final Grade |
|------------|---------|-------------|
| PASS | PASS | PASS |
| PASS | WARN | WARN |
| PASS | FAIL | FAIL |
| FAIL | - | FAIL |

### FIX Stage

Context-preserving fixes from review feedback.

```python
Task(
    prompt=f"""Invoke spec-fixer.

REVIEW: {{session}}/reviews/phase-{phase_num}-review-{cycle_num}.md
IMPLEMENTATION: current working directory
SCOPE: targeted

Commit changes with: spec(NNN): FIX phase-{phase_num} cycle-{cycle_num}

SIGNAL: {{session}}/.signals/phase-{phase_num}-fix-{cycle_num}.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

**Fix Scope**:

| Scope | Behavior |
|-------|----------|
| targeted | Fix only issues from review |
| comprehensive | Fix issues + improve related code |

### TEST Stage

Adaptive test execution.

```python
Task(
    prompt=f"""Invoke spec-tester.

SPEC: {spec_path}
FRAMEWORK: auto-detect
SCOPE: all

OUTPUT: {{session}}/tests/test-results.json
SIGNAL: {{session}}/.signals/test.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

**Test Scope**:

| Scope | Includes |
|-------|----------|
| unit | Unit tests only |
| e2e | End-to-end tests only |
| all | Unit + e2e |

### DOCUMENT Stage

Generate documentation updates.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="DOCUMENT {spec_path}").

OUTPUT: Documentation artifacts
SIGNAL: {{session}}/.signals/document.done

Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

## Review Cycle Pattern

Review cycles loop until PASS or MAX_LOOPS reached.

```python
MAX_LOOPS = 3  # Default, configurable via --cycles=N

for cycle in range(1, MAX_LOOPS + 1):
    # Launch REVIEW
    Task(
        prompt=f"""Invoke spec-reviewer for cycle {cycle}.

SIGNAL: {{session}}/.signals/phase-{phase_num}-review-{cycle}.done

Return EXACTLY: done""",
        model="opus",
        run_in_background=True
    )

    # Wait for review signal
    # Check grade from review output

    if grade == "PASS":
        break  # Early exit (SC-006)

    if cycle < MAX_LOOPS:
        # Launch FIX
        Task(
            prompt=f"""Invoke spec-fixer for cycle {cycle}.

SIGNAL: {{session}}/.signals/phase-{phase_num}-fix-{cycle}.done

Return EXACTLY: done""",
            model="sonnet",
            run_in_background=True
        )
```

## Parallel Stage Execution

Independent stages execute in parallel.

### Research Parallelism

```python
# Multiple researchers (parallel)
Task(prompt="Research architecture...", model="opus", run_in_background=True)
Task(prompt="Research integrations...", model="opus", run_in_background=True)
Task(prompt="Research edge-cases...", model="opus", run_in_background=True)

# Monitor (same message)
Task(prompt="Monitor 3 research tasks...", model="haiku", run_in_background=True)
```

### Phase Independence

Phases with no dependencies can parallelize:

```yaml
# From phase-manifest.yml
phases:
  - num: 1
    name: "Foundation"
    dependencies: []  # Can start immediately
  - num: 2
    name: "Core"
    dependencies:
      - phase: 1  # Waits for phase 1
  - num: 3
    name: "Extensions"
    dependencies:
      - phase: 1  # Can run parallel with phase 2
```

## Commit Protocol

Each stage commits its changes.

```bash
# Commit message format
spec(NNN): {STAGE} - {title}

# Examples
spec(042): CREATE - Add user authentication
spec(042): IMPLEMENT phase-1 - Foundation
spec(042): FIX phase-2 cycle-1 - Address review
spec(042): DOCUMENT - API reference
```

## Stage Skip Behavior

Stages can be skipped via `--skip` flag.

```python
# Parse skip list
skip_stages = args.skip.split(",") if args.skip else []

# Check before execution
if "TEST" in skip_stages:
    # Skip TEST stage, signal as skipped
    signal(f"{{session}}/.signals/test.done", status="skipped")
```

**Warning**: Skipping stages reduces quality assurance.
