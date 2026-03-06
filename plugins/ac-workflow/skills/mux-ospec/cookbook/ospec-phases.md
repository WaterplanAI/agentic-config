# O-Spec Phases via MUX

Source of truth: SKILL.md defines the canonical workflow. This cookbook details phase execution without overriding stage sequences or signal formats.

Execution guide for o_spec workflow stages through MUX orchestration.

## Phase Overview

MUX-OSPEC combines MUX parallel orchestration with o_spec stage-based workflow.

| MUX Phase | O-Spec Stages | Purpose |
|-----------|---------------|---------|
| Research | GATHER, CONSOLIDATE | Context collection (full mode only) |
| Alignment | CONFIRM SC | Success criteria validation (all modes) |
| Planning | PLAN | Strategy definition |
| Implementation | IMPLEMENT (per-phase) | Code generation |
| Validation | REVIEW, FIX, TEST | Quality assurance |
| Finalization | DOCUMENT, SENTINEL | Completion verification |

## Modifier Impact on Phases

### Full Mode (default)

All phases execute with high-tier models for quality stages.

```
GATHER -> CONSOLIDATE -> [CONFIRM SC] -> [PHASE_LOOP] -> TEST -> DOCUMENT -> SENTINEL
```

### Lean Mode

Skips research phases, SC extracted from spec file.

```
CONFIRM SC -> [PHASE_LOOP] -> TEST -> DOCUMENT -> SELF-VALIDATION
```

### Leanest Mode

Minimal phases, SC extracted from spec file.

```
CONFIRM SC -> [PHASE_LOOP] -> TEST -> SELF-VALIDATION
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
        model="opus",
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
    model="opus",
    run_in_background=True
)
```

## Phase 2: Planning

### PLAN Stage

Generate implementation strategy with TDD approach.

```python
Task(
    prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").

INPUT: {{session}}/consolidated.md (if exists)
OUTPUT: {{session}}/plan.md
SIGNAL: {{session}}/.signals/plan.done

Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

### CONFIRM SC Stage (All Modes)

MANDATORY gate before PLAN stage. User must review and approve Success Criteria before any planning begins.

**Full mode**: SC extracted from consolidated research output.
**Lean/leanest modes**: SC extracted directly from spec file Human Section.

```python
# 1. Delegate SC extraction
source_file = "{session}/research/consolidated.md" if modifier == "full" else "{spec_path}"

Task(
    prompt=f"""Read {source_file}.

Extract and return ONLY the SUCCESS_CRITERIA section.

Return the criteria in structured format with:
- Item ID (SC-XXX)
- Description
- Acceptance criteria

Return EXACTLY the criteria text, no commentary.""",
    model="haiku",
    subagent_type="Explore",
    run_in_background=True
)

# 2. Present to user for approval
AskUserQuestion(
    question="Review SUCCESS_CRITERIA. These define what success looks like for this spec.",
    options=[
        {"label": "Approve", "description": "SC accepted, proceed to PLAN"},
        {"label": "Refine", "description": "Adjust SC before proceeding"}
    ]
)

# 3. If user selects Refine: loop with SC update delegation (max 3 iterations)
# 4. If approved: proceed to PLAN stage
```

**Rationale**: SC is the most fundamental unit of work. Without clear success criteria, planning cannot be properly aligned to user expectations. This gate ensures alignment before any implementation strategy is defined.

## Phase 3: Implementation (PHASE_LOOP)

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
        model="opus",
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
        model="sonnet",
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
        model="opus",
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
    model="sonnet",
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
    model="sonnet",
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
    model="opus",
    run_in_background=True
)
```

## Model Tier Assignments

| Stage | Tier | Model | Rationale |
|-------|------|-------|-----------|
| GATHER | high | opus | Research requires deep understanding |
| CONSOLIDATE | high | opus | Synthesis requires judgment |
| PLAN | high | opus | Strategic decisions, TDD strategy |
| CONFIRM SC | high | opus | Validation requires experience |
| IMPLEMENT | medium | sonnet | Well-defined scope |
| REVIEW | high | opus | Quality assessment |
| FIX | medium | sonnet | Targeted changes |
| TEST | medium | sonnet | Execution-focused |
| DOCUMENT | medium | sonnet | Template-based |
| SENTINEL | high | opus | Cross-cutting coordination |

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
uv run $MUX_TOOLS/signal.py "$SIGNAL_PATH" --path "$OUTPUT_PATH" --status success
```
