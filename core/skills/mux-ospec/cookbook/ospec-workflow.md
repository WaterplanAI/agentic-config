# O-Spec Workflow

Stage sequences, model assignments, and execution patterns for o_spec modifiers.

## Stage Sequences by Modifier

### Full Mode (default)

Complete workflow with research and validation.

```
GATHER -> CONSOLIDATE -> [CONFIRM SC] -> [PHASE_LOOP] -> TEST -> DOCUMENT -> SENTINEL -> SELF-VALIDATION
```

| Stage | Tier | Purpose |
|-------|------|---------|
| GATHER | high | Parallel research collection |
| CONSOLIDATE | high | Research synthesis |
| CONFIRM SC | user | SUCCESS_CRITERIA validation |
| PHASE_LOOP | varies | Per-phase implementation cycle |
| TEST | medium | Adaptive test execution |
| DOCUMENT | medium | Documentation artifacts |
| SENTINEL | high | Cross-cutting final review |
| SELF-VALIDATION | medium | Orchestrator self-check |

### Lean Mode

Skips research, assumes context is sufficient.

```
[PHASE_LOOP] -> TEST -> DOCUMENT -> SELF-VALIDATION
```

| Stage | Tier | Purpose |
|-------|------|---------|
| PHASE_LOOP | varies | Per-phase implementation cycle |
| TEST | medium | Adaptive test execution |
| DOCUMENT | medium | Documentation artifacts |
| SELF-VALIDATION | medium | Orchestrator self-check |

### Leanest Mode

Minimal workflow for well-defined specs.

```
[PHASE_LOOP] -> TEST -> SELF-VALIDATION
```

| Stage | Tier | Purpose |
|-------|------|---------|
| PHASE_LOOP | medium/low | Per-phase implementation cycle |
| TEST | low | Adaptive test execution |
| SELF-VALIDATION | low | Orchestrator self-check |

## PHASE_LOOP Structure

Per-phase cycle with TDD enforcement.

```
PLAN (with TDD Contribution) -> IMPLEMENT -> REVIEW -> SENTINEL
```

### Per-Phase Execution

```python
for phase_num in phases:
    # PLAN with TDD strategy
    Task(
        prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} --phase {phase_num} ultrathink").

Include TDD approach:
- Test files to create/modify
- Test cases per SC-XXX
- Assertion patterns

OUTPUT: {{session}}/phases/{phase_num}/plan.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-plan.done

Return EXACTLY: done""",
        model="opus",
        run_in_background=True
    )

    # IMPLEMENT (includes writing tests first per TDD)
    Task(
        prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} --phase {phase_num}").

TDD enforcement:
1. Write failing tests first
2. Implement to pass tests
3. Refactor if needed

OUTPUT: Implementation artifacts
SIGNAL: {{session}}/.signals/phase-{phase_num}-implement.done

Return EXACTLY: done""",
        model="sonnet",
        run_in_background=True
    )

    # REVIEW (N-cycle loop)
    # See review-cycles.md for loop details

    # Per-phase SENTINEL (optional, --phased flag)
    Task(
        prompt=f"""Read agents/sentinel.md.

SESSION: {{session}}
PHASE: {phase_num}
SCOPE: phase-only

OUTPUT: {{session}}/phases/{phase_num}/sentinel.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-sentinel.done

Return EXACTLY: done""",
        model="opus",
        run_in_background=True
    )
```

## Model Tier Assignments

### Full Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| GATHER | high | Deep understanding required |
| CONSOLIDATE | high | Synthesis requires judgment |
| CONFIRM SC | user | Human validation |
| PLAN | high | Strategic decisions, TDD strategy |
| IMPLEMENT | medium | Well-defined scope |
| REVIEW | high | Quality assessment |
| FIX | medium | Targeted changes |
| TEST | medium | Execution-focused |
| DOCUMENT | medium | Template-based |
| SENTINEL | high | Cross-cutting coordination |
| Monitor | low | Simple polling |

### Lean Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| PLAN | high | Strategic decisions |
| IMPLEMENT | medium | Well-defined scope |
| REVIEW | high | Quality assessment |
| FIX | medium | Targeted changes |
| TEST | medium | Execution-focused |
| DOCUMENT | medium | Template-based |
| SELF-VALIDATION | medium | Basic check |

### Leanest Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| PLAN | medium | Quick planning |
| IMPLEMENT | medium | Well-defined scope |
| REVIEW | medium | Lightweight review |
| FIX | low | Simple fixes |
| TEST | low | Basic validation |
| SELF-VALIDATION | low | Minimal check |

## Skip Patterns by Modifier

### Full Mode Skips

None by default. Optional via `--skip` flag.

### Lean Mode Skips

| Skipped | Reason |
|---------|--------|
| GATHER | Context assumed sufficient |
| CONSOLIDATE | No research to synthesize |
| CONFIRM SC | Spec already validated |
| SENTINEL | Replaced by SELF-VALIDATION |

### Leanest Mode Skips

| Skipped | Reason |
|---------|--------|
| GATHER | Context assumed sufficient |
| CONSOLIDATE | No research to synthesize |
| CONFIRM SC | Spec already validated |
| DOCUMENT | Documentation deferred |
| SENTINEL | Replaced by SELF-VALIDATION |

## SUCCESS_CRITERIA Derivation

Each stage contributes to SUCCESS_CRITERIA completion.

### PLAN Stage

```yaml
# Extract SC items from spec
success_criteria:
  - id: SC-001
    text: "Feature X works"
    phase: 1
    tdd_tests: ["test_feature_x_basic", "test_feature_x_edge"]
  - id: SC-002
    text: "API endpoint returns 200"
    phase: 2
    tdd_tests: ["test_api_returns_200"]
```

### IMPLEMENT Stage

```yaml
# Track SC contributions per implementation
sc_contributions:
  SC-001:
    status: implemented
    files: ["src/feature_x.py", "tests/test_feature_x.py"]
    tests_passing: true
  SC-002:
    status: partial
    files: ["src/api.py"]
    tests_passing: false
    remaining: "error handling"
```

### SENTINEL Stage

```yaml
# Final SC validation
sc_validation:
  SC-001: PASS
  SC-002: PASS
  SC-003: FAIL  # Triggers additional FIX cycle
```

## Interaction Mode Handling

### Voice Mode (default when available)

```python
# Phase transitions trigger voice updates
if voice_available:
    mcp__voicemode__converse(
        message=f"Phase {phase_num} {stage} completed. Grade: {grade}.",
        wait_for_response=False
    )
```

### Non-Voice Mode

```python
# Silent execution, results in session output
# User checks signals/outputs manually
```

### User Confirmation Points

| Stage | Confirmation | Modifier |
|-------|--------------|----------|
| CONFIRM SC | Required | full only |
| COMMIT | Configurable | all |
| FIX (final cycle) | Optional | all |

## MUX Phase Integration

| MUX Phase | O-Spec Stages | Integration |
|-----------|---------------|-------------|
| Research | GATHER, CONSOLIDATE | Parallel researcher delegation |
| Planning | PLAN, CONFIRM_SC | Strategic preparation |
| Execution | IMPLEMENT (phased) | Per-phase Task() delegation |
| Validation | REVIEW, FIX, TEST | N-cycle quality loops |
| Finalization | DOCUMENT, SENTINEL | Completion verification |

## TDD Enforcement

### Per-Phase TDD

1. PLAN includes test specifications
2. IMPLEMENT writes tests first
3. REVIEW validates test coverage
4. FIX maintains test compliance

### Test-First Sequence

```python
# Within IMPLEMENT stage
# 1. Write failing test
git_add("tests/test_feature.py")
# 2. Implement feature
git_add("src/feature.py")
# 3. Verify tests pass
run_tests()
# 4. Refactor if needed
```

### Coverage Tracking

```yaml
# Per-phase coverage in signal metadata
coverage:
  statements: 85
  branches: 78
  sc_coverage:
    SC-001: 100
    SC-002: 90
```
