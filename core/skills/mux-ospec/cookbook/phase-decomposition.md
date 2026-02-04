# Phase Decomposition

DAG-based phasing for complex spec workflows.

## Trigger Conditions

Phase decomposition activates when ANY condition is met:

| Condition | Threshold | Rationale |
|-----------|-----------|-----------|
| `--phased` flag | Present | Explicit request |
| Spec file size | > 50KB | Large specs need chunking |
| HLO count | > 5 objectives | Complex scope needs partitioning |

```python
# Trigger evaluation
if args.phased or spec_size > 50_000 or hlo_count > 5:
    invoke_decomposition()
```

## Product Manager Integration

Decomposition delegates to the product-manager skill.

```python
Task(
    prompt=f"""Invoke Skill(skill="product-manager", args="decompose {spec_path}").

Output: {{session}}/phases/phase-manifest.yml
Signal: {{session}}/.signals/decomposition.done

FINAL: Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

The product-manager skill:
1. Analyzes spec structure and HLO dependencies
2. Identifies natural work boundaries
3. Generates phase-manifest.yml with DAG structure
4. Assigns SC items to phases

## Phase Manifest Schema

```yaml
# phase-manifest.yml
version: "1.0"
spec_path: "/path/to/spec.md"
generated_at: "2026-02-04T10:00:00Z"
total_phases: 3

phases:
  - num: 1
    name: "Foundation"
    description: "Core infrastructure and base types"
    sc_items: ["SC-001", "SC-002"]
    dependencies: []  # No dependencies - starts immediately
    estimated_effort: "medium"
    stack: "backend"

  - num: 2
    name: "Core Logic"
    description: "Business logic implementation"
    sc_items: ["SC-003", "SC-004"]
    dependencies:
      - phase: 1
        type: "hard"  # Must complete before start
    estimated_effort: "high"
    stack: "backend"

  - num: 3
    name: "Integration Layer"
    description: "External integrations and API"
    sc_items: ["SC-005", "SC-006"]
    dependencies:
      - phase: 1
        type: "hard"
      - phase: 2
        type: "soft"  # Can start with partial completion
    estimated_effort: "medium"
    stack: "full"

bundles:
  - name: "frontend-components"
    phases: [2, 3]
    reason: "Share UI state management"
```

## DAG Dependency Resolution

### Dependency Types

| Type | Behavior | Use Case |
|------|----------|----------|
| `hard` | Wait for complete phase signal | Sequential work |
| `soft` | Wait for 80% SC completion | Parallel with handoff |
| `none` | No dependency | Independent work |

### Resolution Algorithm

```python
def resolve_execution_order(manifest):
    """Resolve DAG into execution waves."""
    phases = manifest["phases"]
    waves = []
    completed = set()

    while len(completed) < len(phases):
        # Find phases with satisfied dependencies
        ready = [
            p for p in phases
            if p["num"] not in completed
            and all_deps_satisfied(p, completed, phases)
        ]

        if not ready:
            raise CyclicDependencyError()

        waves.append([p["num"] for p in ready])
        completed.update(p["num"] for p in ready)

    return waves

def all_deps_satisfied(phase, completed, all_phases):
    """Check if phase dependencies are satisfied."""
    for dep in phase.get("dependencies", []):
        if dep["type"] == "hard":
            if dep["phase"] not in completed:
                return False
        elif dep["type"] == "soft":
            # Check 80% SC completion
            dep_phase = next(p for p in all_phases if p["num"] == dep["phase"])
            if not check_partial_completion(dep_phase, threshold=0.8):
                return False
    return True
```

### Execution Waves

Phases execute in waves based on dependency resolution.

```
Wave 1: [Phase 1]           # No dependencies
Wave 2: [Phase 2, Phase 3]  # Phase 1 complete, can parallelize
Wave 3: [Phase 4]           # Phases 2 & 3 complete
```

## Bundle Detection

Bundles group phases with soft dependencies for optimized execution.

### Bundle Criteria

| Criterion | Description |
|-----------|-------------|
| Shared stack | Same technology stack |
| Overlapping SC | SC items with cross-references |
| Integration points | Phases that interface heavily |

### Bundle Behavior

```yaml
bundles:
  - name: "api-layer"
    phases: [2, 3]
    reason: "Both implement REST endpoints"
    execution_hint: "co-locate"  # Run on same worker if possible
```

Bundled phases:
- Share context window when possible
- Signal completion as a group
- Can use soft dependencies internally

## Per-Phase Implementation

After decomposition, phases execute via PHASE_LOOP.

```python
# Load manifest
manifest = load_yaml(f"{session}/phases/phase-manifest.yml")
waves = resolve_execution_order(manifest)

for wave in waves:
    # Launch all phases in wave (parallel)
    for phase_num in wave:
        phase = get_phase(manifest, phase_num)

        Task(
            prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} --phase {phase_num}").

SC_SCOPE: {phase["sc_items"]}
STACK: {phase["stack"]}
SIGNAL: {{session}}/.signals/phase-{phase_num}-implement.done

FINAL: Return EXACTLY: done""",
            model="sonnet",
            run_in_background=True
        )

    # Monitor wave completion
    Task(
        prompt=f"""Read agents/monitor.md.

SESSION: {{session}}
EXPECTED: {len(wave)}
PATTERN: phase-*-implement.done

FINAL: Return EXACTLY: done""",
        model="haiku",
        run_in_background=True
    )
```

## Phase Signals

Each phase signals completion with SC tracking.

```json
{
  "$schema": "signal-v1.json",
  "phase": "implement",
  "phase_num": 2,
  "status": "completed",
  "timestamp": "2026-02-04T10:30:00Z",
  "duration_seconds": 342,
  "artifacts": [
    "src/api/endpoints.py",
    "tests/test_endpoints.py"
  ],
  "sc_contributions": {
    "SC-003": "implemented",
    "SC-004": "implemented"
  },
  "dependencies_satisfied": [1],
  "grade": "PASS"
}
```

## Error Handling

### Cyclic Dependencies

Detected during manifest validation.

```python
try:
    waves = resolve_execution_order(manifest)
except CyclicDependencyError as e:
    # Report to user, request manual intervention
    signal(
        f"{session}/.signals/decomposition.done",
        status="failed",
        error="cyclic_dependency",
        details=str(e)
    )
```

### Phase Failure

Failed phases block dependent phases.

```python
if phase_signal["status"] == "failed":
    # Mark dependent phases as blocked
    for dep_phase in get_dependents(manifest, phase_num):
        signal(
            f"{session}/.signals/phase-{dep_phase}-implement.done",
            status="blocked",
            reason=f"dependency phase-{phase_num} failed"
        )
```

## Multi-Stack Considerations

Phases can target different stacks.

| Stack | Model Tier | Context |
|-------|------------|---------|
| backend | medium | Server-side patterns |
| frontend | medium | UI/UX patterns |
| infra | medium | DevOps patterns |
| full | medium | Cross-cutting |

Stack-specific priming via `cookbook/stack-priming.md`.
