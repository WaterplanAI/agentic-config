# Stage Patterns


> Authoritative contract (wins on conflict):
> - full: CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
> - lean: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
> - leanest: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
> - GATHER = RESEARCH; CONFIRM_SC is mandatory before PLAN
> - REVIEW/TEST/SENTINEL/SELF_VALIDATION are PASS-only gates
> - notify-first pacing; no polling loops; blocked/stuck defaults to user escalation
> - every stage must commit every changed repo and report `repo_scope`, `root_commit`, `spec_commit` (root first, spec second when both changed)


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
    model="high-tier",
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
    model="high-tier",
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
        model="high-tier",
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
    model="high-tier",
    run_in_background=True
)
```

**TDD Strategy**: Plan includes test-first approach.

### SUCCESS_CRITERIA Stage (Full Mode)

Materialize explicit acceptance criteria before confirmation.

```python
Task(
    prompt=f"""Invoke Skill(skill=\"spec\", args=\"SUCCESS_CRITERIA {spec_path}\").

OUTPUT: {{session}}/plan/success-criteria.md
SIGNAL: {{session}}/.signals/success-criteria.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)
```

### CONFIRM_SC Stage (All Modes)

Get user approval before PLAN.

```python
AskUserQuestion(
    question="Approve SUCCESS_CRITERIA before PLAN?",
    options=[
        {"label": "Approve", "description": "Proceed to PLAN"},
        {"label": "Refine", "description": "Update criteria first"},
    ],
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
    model="medium-tier",
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
    model="medium-tier",
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
    model="high-tier",
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
    model="medium-tier",
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
    model="medium-tier",
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
    model="medium-tier",
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
        model="high-tier",
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
            model="medium-tier",
            run_in_background=True
        )
```

## Parallel Stage Execution

Independent stages execute in parallel.

### Research Parallelism

```python
# Multiple researchers (parallel)
Task(prompt="Research architecture...", model="high-tier", run_in_background=True)
Task(prompt="Research integrations...", model="high-tier", run_in_background=True)
Task(prompt="Research edge-cases...", model="high-tier", run_in_background=True)

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

Each stage commits every changed repo and reports repo-scoped evidence.

```yaml
repo_scope: spec-only | root-only | root+spec
root_commit: <hash|N/A>
spec_commit: <hash|N/A>
```

Ordering rule when both repos changed: root commit first, spec commit second.

## Stage Bypass Policy

Primary stages are mandatory for the selected modifier contract and must not be bypassed at runtime.

- `full` executes every listed stage in order.
- `lean` and `leanest` follow their explicit reduced sequences.
- `REVIEW`, `TEST`, `SENTINEL`, and `SELF_VALIDATION` remain PASS-only gates.
