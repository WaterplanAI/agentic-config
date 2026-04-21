# O-Spec Workflow


> Authoritative contract (wins on conflict):
> - full: CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
> - lean: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
> - leanest: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
> - GATHER = RESEARCH; CONFIRM_SC is mandatory before PLAN
> - REVIEW/TEST/SENTINEL/SELF_VALIDATION are PASS-only gates
> - notify-first pacing; no polling loops; blocked/stuck defaults to user escalation
> - every stage must commit every changed repo and report `repo_scope`, `root_commit`, `spec_commit` (root first, spec second when both changed)


Source of truth: SKILL.md defines the canonical workflow. This cookbook expands on execution details but does NOT override stage sequences or signal formats.

Stage sequences, model assignments, and execution patterns for o_spec modifiers.

## Stage Sequences by Modifier

### Full Mode (default)

Complete workflow with research and validation.

```
CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
```

| Stage | Tier | Purpose |
|-------|------|---------|
| GATHER | medium-tier | Parallel research collection (`GATHER = RESEARCH`) |
| CONSOLIDATE | high-tier | Research synthesis |
| SUCCESS_CRITERIA | high-tier | Explicit acceptance contract |
| CONFIRM_SC | user gate | Mandatory approval before `PLAN` |
| PLAN | high-tier | Strategy and phase sequencing |
| IMPLEMENT | medium-tier | Bounded implementation |
| REVIEW | high-tier | PASS-only quality gate |
| FIX | medium-tier | Targeted remediation |
| TEST | medium-tier | PASS-only validation gate |
| DOCUMENT | medium-tier | Documentation artifacts |
| SENTINEL | high-tier | Final PASS-only gate |

### Lean Mode

Skips research, assumes spec is already validated.

```
CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
```

| Stage | Tier | Purpose |
|-------|------|---------|
| CONFIRM_SC | user gate | SUCCESS_CRITERIA validation from spec file |
| PLAN | high-tier | Strategy and sequencing |
| IMPLEMENT | medium-tier | Bounded implementation |
| REVIEW | high-tier | PASS-only quality gate |
| FIX | medium-tier | Targeted remediation |
| TEST | medium-tier | PASS-only validation gate |
| DOCUMENT | medium-tier | Documentation artifacts |
| SELF_VALIDATION | high-tier | Final PASS-only gate for lean mode |

### Leanest Mode

Minimal workflow for well-defined specs.

```
CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
```

| Stage | Tier | Purpose |
|-------|------|---------|
| CONFIRM_SC | user gate | SUCCESS_CRITERIA validation from spec file |
| PLAN | high-tier | Strategy and sequencing |
| IMPLEMENT | medium-tier | Bounded implementation |
| REVIEW | high-tier | PASS-only quality gate |
| FIX | medium-tier | Targeted remediation |
| TEST | medium-tier | PASS-only validation gate |
| SELF_VALIDATION | high-tier | Final PASS-only gate for leanest mode |

## Explicit implementation stages and REVIEW/FIX loop

Implementation remains explicit (`PLAN -> IMPLEMENT -> REVIEW -> FIX`) and loops only between `REVIEW` and `FIX` until `PASS` or user escalation.

```
PLAN -> IMPLEMENT -> REVIEW -> FIX (on WARN/FAIL) -> REVIEW ...
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
        model="high-tier",
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
        model="medium-tier",
        run_in_background=True
    )

    # REVIEW (N-cycle loop)
    # See review-cycles.md for loop details

    # SENTINEL is the final full-mode gate (single run after DOCUMENT), not a per-phase optional stage.
    # Use REVIEW/FIX within each phase; reserve SENTINEL for workflow completion verification.
```

## Model Tier Assignments

### Full Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| CREATE | high-tier | Strategic decisions, template application, path resolution |
| GATHER | medium-tier | Research collection and extraction |
| CONSOLIDATE | high-tier | Synthesis and prioritization |
| SUCCESS_CRITERIA | high-tier | Acceptance-contract framing |
| CONFIRM_SC | user gate | Human approval |
| PLAN | high-tier | Strategy and TDD planning |
| IMPLEMENT | medium-tier | Bounded execution |
| REVIEW | high-tier | Strict quality judgment |
| FIX | medium-tier | Targeted remediation |
| TEST | medium-tier | Validation execution |
| DOCUMENT | medium-tier | Documentation alignment |
| SENTINEL | high-tier | Final cross-cutting gate |

### Lean Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| CREATE | high-tier | Strategic decisions, template application, path resolution |
| PLAN | high-tier | Strategy and decomposition |
| IMPLEMENT | medium-tier | Well-defined scope |
| REVIEW | high-tier | Quality assessment |
| FIX | medium-tier | Targeted changes |
| TEST | medium-tier | Validation execution |
| DOCUMENT | medium-tier | Template-based output |
| SELF_VALIDATION | high-tier | Final PASS-only gate |

### Leanest Mode

| Stage | Tier | Rationale |
|-------|------|-----------|
| CREATE | high-tier | Strategic decisions, template application, path resolution |
| PLAN | high-tier | Quick but explicit planning |
| IMPLEMENT | medium-tier | Well-defined scope |
| REVIEW | high-tier | Lightweight but strict review gate |
| FIX | medium-tier | Simple targeted fixes |
| TEST | medium-tier | Basic validation execution |
| SELF_VALIDATION | high-tier | Final PASS-only gate |

## Modifier-defined stage deltas (fixed contract)

Primary stages are **not** runtime-bypassable. Required gates must execute for the selected modifier.

### Full Mode

No omitted primary stages; execute the full sequence exactly as defined.

### Lean Mode

| Not Included | Reason |
|--------------|--------|
| GATHER | Context assumed sufficient |
| CONSOLIDATE | No research to synthesize |
| SENTINEL | Replaced by SELF_VALIDATION |

### Leanest Mode

| Not Included | Reason |
|--------------|--------|
| GATHER | Context assumed sufficient |
| CONSOLIDATE | No research to synthesize |
| DOCUMENT | Documentation deferred |
| SENTINEL | Replaced by SELF_VALIDATION |

## Repo-scoped commit evidence (mandatory)

Every stage that changes files must report:

```yaml
repo_scope: spec-only | root-only | root+spec
root_commit: <hash|N/A>
spec_commit: <hash|N/A>
```

If both repos changed, commit root first and spec second.

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
| CONFIRM_SC | Required | all modifiers |
| COMMIT | Mandatory repo-scoped evidence (`repo_scope`, `root_commit`, `spec_commit`) | all |
| FIX (final cycle) | Optional | all |

## MUX Phase Integration

| MUX Phase | O-Spec Stages | Integration |
|-----------|---------------|-------------|
| Setup | CREATE (optional) | Spec creation via /spec CREATE delegation |
| Research | GATHER, CONSOLIDATE | Parallel researcher delegation |
| Planning | SUCCESS_CRITERIA, CONFIRM_SC, PLAN | Strategic preparation |
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
