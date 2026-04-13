# O-Spec Phases via MUX


> Authoritative contract (wins on conflict):
> - full: CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
> - lean: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
> - leanest: CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
> - GATHER = RESEARCH; CONFIRM_SC is mandatory before PLAN
> - REVIEW/TEST/SENTINEL/SELF_VALIDATION are PASS-only gates
> - notify-first pacing; no polling loops; blocked/stuck defaults to user escalation
> - every stage must commit every changed repo and report `repo_scope`, `root_commit`, `spec_commit` (root first, spec second when both changed)


Source of truth: SKILL.md defines the canonical workflow. This cookbook details phase execution without overriding stage sequences or signal formats.

Execution guide for o_spec workflow stages through MUX orchestration.

## Phase Overview

MUX-OSPEC combines MUX parallel orchestration with o_spec stage-based workflow.

| MUX Phase | O-Spec Stages | Purpose |
|-----------|---------------|---------|
| Research | GATHER, CONSOLIDATE | Context collection (full mode only) |
| Success Criteria | SUCCESS_CRITERIA | Define explicit acceptance contract before planning |
| Alignment Gate | CONFIRM_SC | Mandatory user approval before PLAN (all modes) |
| Planning | PLAN | Strategy definition |
| Implementation | IMPLEMENT (per-phase) | Code generation |
| Validation | REVIEW, FIX, TEST | Quality assurance (PASS-only progression) |
| Finalization | DOCUMENT, SENTINEL / SELF_VALIDATION | Completion verification by modifier |

## Modifier Impact on Phases

### Full Mode (default)

Model tiers follow the authoritative mapping: `GATHER`/`IMPLEMENT`/`FIX`/`TEST`/`DOCUMENT` use medium-tier, while `CONSOLIDATE`/`SUCCESS_CRITERIA`/`PLAN`/`REVIEW`/`SENTINEL`/`SELF_VALIDATION` use high-tier (`CONFIRM_SC` is a user gate).

```
CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL
```

### Lean Mode

Skips research phases, SC extracted from spec file.

```
CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION
```

### Leanest Mode

Minimal phases, SC extracted from spec file.

```
CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION
```

## Phase 1: Research (Full Mode Only)

### GATHER Stage

Launch parallel researchers for spec context gathering.

```python
# Researchers (parallel)
for topic in research_topics:
    Task(
        prompt=f"""Invoke Skill(skill="spec", args="GATHER {spec_path} --topic {topic}").

OUTPUT: {{session}}/research/{topic}.md
SIGNAL: {{session}}/.signals/gather-{topic}.done

Return EXACTLY: done""",
        model="medium-tier",
        run_in_background=True
    )

```

### CONSOLIDATE Stage

Merge research outputs into unified context.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="CONSOLIDATE {spec_path}").

INPUT: {{session}}/research/*.md
OUTPUT: {{session}}/consolidated.md
SIGNAL: {{session}}/.signals/consolidate.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)
```

## Phase 2: Success Criteria Gate and Planning

### SUCCESS_CRITERIA Stage

Create or verify explicit success criteria content before user confirmation.

**Full mode**: delegate SUCCESS_CRITERIA from consolidated research.
**Lean/leanest modes**: verify explicit SUCCESS_CRITERIA already exists in the spec before CONFIRM_SC.

```python
source_file = "{session}/research/consolidated.md" if modifier == "full" else "{spec_path}"

Task(
    prompt=f"""Invoke Skill(skill="spec", args="SUCCESS_CRITERIA {spec_path}").

SOURCE: {source_file}
OUTPUT: {session}/success-criteria.md
SIGNAL: {session}/.signals/success-criteria.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)
```

### CONFIRM_SC Stage (All Modes)

MANDATORY gate before PLAN stage. User must review and approve SUCCESS_CRITERIA before any planning begins.

```python
AskUserQuestion(
    question="Review SUCCESS_CRITERIA. These define what success looks like for this spec.",
    options=[
        {"label": "Approve", "description": "SC accepted, proceed to PLAN"},
        {"label": "Refine", "description": "Adjust SC before proceeding"}
    ]
)

# If user selects Refine: loop with SC update delegation (max 3 iterations)
# If approved: proceed to PLAN stage
# Do not run PLAN without explicit CONFIRM_SC approval
```

### PLAN Stage

Generate implementation strategy with TDD approach.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").

INPUT: {session}/consolidated.md (if full mode)
OUTPUT: {session}/plan.md
SIGNAL: {session}/.signals/plan.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)
```

**Rationale**: SUCCESS_CRITERIA and CONFIRM_SC are the mandatory planning gate. Without explicit criteria and approval, planning cannot proceed.

## Phase 3: Implementation stage loop (PLAN -> IMPLEMENT -> REVIEW -> FIX)

Implementation executes per-phase from plan decomposition.

### Phase Decomposition Trigger

Complex specs trigger product-manager decomposition:

```python
# Trigger conditions
if spec_size > 50_000 or hlo_count > 5 or multi_stack:
    Task(
        prompt=f"""Invoke Skill(skill="product-manager", args="decompose {spec_path}").

OUTPUT: {{session}}/phases/phase-manifest.yml
SIGNAL: {{session}}/.signals/decomposition.done

Return EXACTLY: done""",
        model="high-tier",
        run_in_background=True
    )
```

### Per-Phase Implementation

Each phase follows IMPLEMENT -> REVIEW -> FIX cycle.

```python
for phase_num in range(1, total_phases + 1):
    # IMPLEMENT
    Task(
        prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} --phase {phase_num}").

OUTPUT: Implementation artifacts
SIGNAL: {{session}}/.signals/phase-{phase_num}-implement.done

Return EXACTLY: done""",
        model="medium-tier",
        run_in_background=True
    )

    # REVIEW (after implement signal)
    Task(
        prompt=f"""Invoke spec-reviewer for phase {phase_num}.

SPEC: {spec_path}
IMPLEMENTATION: phase-{phase_num} artifacts
CYCLE: 1

OUTPUT: {{session}}/reviews/phase-{phase_num}-review-1.md
SIGNAL: {{session}}/.signals/phase-{phase_num}-review-1.done

Return EXACTLY: done""",
        model="high-tier",
        run_in_background=True
    )
```

## Phase 4: Validation

### TEST Stage

Adaptive test execution based on detected framework.

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

## Phase 5: Finalization

### DOCUMENT Stage

Generate documentation artifacts.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="DOCUMENT {spec_path}").

OUTPUT: Documentation updates
SIGNAL: {{session}}/.signals/document.done

Return EXACTLY: done""",
    model="medium-tier",
    run_in_background=True
)
```

### SENTINEL Stage

Final quality gate and cross-cutting review.

```python
Task(
    prompt=f"""Read agents/sentinel.md.

SESSION: {{session}}
SPEC: {spec_path}
PILLARS: compliance, quality, coverage

OUTPUT: {{session}}/sentinel-review.md
SIGNAL: {{session}}/.signals/sentinel.done

Return EXACTLY: done""",
    model="high-tier",
    run_in_background=True
)
```

## Model Tier Assignments

| Stage | Tier | Rationale |
|-------|------|-----------|
| GATHER | medium-tier | research collection |
| CONSOLIDATE | high-tier | synthesis and prioritization |
| SUCCESS_CRITERIA | high-tier | explicit acceptance contract |
| CONFIRM_SC | user gate | explicit approval before planning |
| PLAN | high-tier | strategy and sequencing |
| IMPLEMENT | medium-tier | bounded execution |
| REVIEW | high-tier | strict quality judgment |
| FIX | medium-tier | targeted remediation |
| TEST | medium-tier | validation execution |
| DOCUMENT | medium-tier | doc alignment |
| SENTINEL / SELF_VALIDATION | high-tier | final gate |

## Signal Protocol

All phases signal completion via `.done` signal files (JSON content).

```json
{
  "$schema": "signal-v1.json",
  "phase": "implement",
  "phase_num": 2,
  "status": "completed",
  "timestamp": "2026-02-04T10:30:00Z",
  "duration_seconds": 342,
  "artifacts": ["path/to/output.md"],
  "sc_contributions": {"SC-007": "implemented"}
}
```

Signal creation:
```bash
uv run $MUX_TOOLS/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status success \
  --meta repo_scope="root+spec" --meta root_commit="abc1234" --meta spec_commit="def5678"
```

Required metadata:
- `repo_scope`: `spec-only` | `root-only` | `root+spec`
- `root_commit`: hash or `N/A`
- `spec_commit`: hash or `N/A`
