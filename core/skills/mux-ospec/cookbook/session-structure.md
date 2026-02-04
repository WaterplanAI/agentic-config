# Session Structure

Directory layout for mux-ospec workflow sessions.

## Structure

```
outputs/mux-ospec/{YYYY}/{MM}/{DD}/{session_id}/
  .signals/           # Completion markers
  research/           # GATHER outputs
    web-research.md
    codebase-audit.md
    pattern-analysis.md
    consolidated.md
  phases/
    phase-1/
      context-manifest.yml
      plan.md
    phase-2/
      context-manifest.yml
      plan.md
  reviews/            # REVIEW outputs
    phase-1-review-1.md
    phase-1-review-2.md
  tests/              # TEST outputs
    test-results.json
  workflow_state.yml  # Resume capability
```

## Session ID Format

```
HHMMSS-xxxxxxxx
```

- `HHMMSS` - Time of creation
- `xxxxxxxx` - Random 8-character suffix

## Directory Creation

```bash
uv run $MUX_TOOLS/session.py "mux-ospec-{topic}"
```

Returns: Full session path for use in subsequent commands.

## Signal Directory

All completion signals go to `.signals/`:

```
.signals/
  phase-1-plan.done
  phase-1-implement.done
  phase-1-review-1.done
  phase-1-fix-1.done
  phase-1-sentinel.done
  phase-2-plan.done
  ...
  test.done
  document.done
  final-sentinel.done
```

## Research Directory (Full Mode)

GATHER phase outputs:

| File | Content |
|------|---------|
| web-research.md | External best practices |
| codebase-audit.md | Existing patterns analysis |
| pattern-analysis.md | Test framework detection |
| consolidated.md | Merged findings + SC table |

## Phases Directory

Per-phase implementation context:

| File | Content |
|------|---------|
| context-manifest.yml | Phase scope, SC items, dependencies |
| plan.md | Implementation strategy |

## Reviews Directory

Review cycle outputs:

```
reviews/
  phase-{N}-review-{cycle}.md
```

Contains: Compliance review, quality review, grade, issues list.

## Tests Directory

Test execution results:

| File | Content |
|------|---------|
| test-results.json | Structured results |

## Workflow State

See: `cookbook/state-persistence.md`
