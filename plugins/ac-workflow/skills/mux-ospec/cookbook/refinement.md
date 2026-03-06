# Refinement

Refinement loop protocol for collecting user feedback and resolving ambiguity before implementation.

## When Refinement Triggers

| Trigger | Context | Gate |
|---------|---------|------|
| User explicitly requests refinement | Any mode | After PLAN |
| CONFIRM SC loop rejects SC | All modes | Before PLAN (mandatory gate) |
| Stage returns NEEDS_REFINEMENT | Any mode | Current stage |
| Orchestrator detects unresolved decisions in plan | Any mode | After PLAN |

### Detection Heuristics

Plan contains unresolved decisions when:
- Plan summary includes "TBD", "to be decided", "open question"
- Multiple mutually exclusive approaches listed without selection
- Dependencies on user input not yet provided
- Success criteria reference undefined behavior

## Refinement Loop Protocol

### Core Rules

1. Orchestrator uses `AskUserQuestion()` to present refinement questions
2. Questions MUST be specific, actionable, with concrete options
3. Max 3 refinement iterations per gate
4. After refinement: delegate updates to FRESH Task() agent (never reuse context-burned agents)

### Loop Structure

```python
MAX_REFINEMENT = 3

for iteration in range(1, MAX_REFINEMENT + 1):
    # 1. Extract plan summary (never read directly)
    Task(
        prompt=f"""Read the plan report at {plan_report_path}.
Return ONLY: unresolved decisions, open questions, and ambiguities.
Format each as a numbered item with context.

IMPORTANT: Path is RELATIVE to project root. Do NOT prepend '/'.

Return EXACTLY: the extracted items or "NO_UNRESOLVED" if none found.""",
        subagent_type="Explore",
        model="haiku",
        run_in_background=True
    )

    # 2. If no unresolved items, exit loop
    if result == "NO_UNRESOLVED":
        break

    # 3. Present refinement questions to user
    AskUserQuestion(
        question=f"""Plan refinement (iteration {iteration}/{MAX_REFINEMENT}):

{structured_refinement_request}

Approve plan as-is or provide refinement direction?""",
        options=[
            {"label": "Approve", "description": "Plan accepted, proceed to IMPLEMENT"},
            {"label": "Refine", "description": "Provide direction for plan updates"}
        ]
    )

    # 4. If approved, exit loop
    if response == "Approve":
        break

    # 5. Delegate plan update to FRESH agent
    Task(
        prompt=f"""Update the plan in {spec_path} based on user feedback:

FEEDBACK: {user_refinement_direction}

Your FIRST and MANDATORY action:
Skill(skill="spec", args="PLAN {spec_path}")

Apply user feedback during planning. Do NOT read files before invoking Skill.
If Skill fails: RETURN "STAGE_FAILED"

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/phase-{N}-plan-refine-{iteration}.done --status success --meta commit="$(git rev-parse --short HEAD)"
RETURN: "PLAN_REFINED"
""",
        subagent_type="general-purpose",
        model="opus",
        run_in_background=True
    )

    # 6. Verify signal, loop to re-extract summary
```

## Structured Refinement Request Format

When presenting refinement questions, use this format:

```markdown
## Refinement Request: {Title}

### What Needs Refinement
[Specific ambiguity or decision point]

### Context
[Relevant findings from research/audit phases]

### Options
1. [Option A] -- [trade-off]
2. [Option B] -- [trade-off]

### Suggested Default
[Recommended option with rationale]

### Impact on Spec
[Which spec sections would change]
```

### Example

```markdown
## Refinement Request: Authentication Strategy

### What Needs Refinement
Plan references both JWT and session-based auth without selecting one.

### Context
Codebase audit found existing session middleware in src/middleware/session.ts.
Spec SC-003 requires "stateless authentication for API endpoints".

### Options
1. JWT only -- Stateless, matches SC-003, requires new token infrastructure
2. Hybrid (JWT for API, sessions for web) -- Reuses existing middleware, higher complexity
3. Session-based only -- Minimal change, but violates SC-003 stateless requirement

### Suggested Default
Option 1 (JWT only). SC-003 explicitly requires stateless auth. Existing session middleware
can remain for non-API routes without conflict.

### Impact on Spec
- Plan Section: Authentication approach (currently ambiguous)
- Implementation: Token generation, validation middleware, refresh flow
- Test Evidence: Auth integration tests scope changes
```

## PLAN Refinement Gate

After PLAN stage completes, orchestrator MAY enter refinement before IMPLEMENT.

### Trigger Conditions

- User requested refinement (explicit flag or instruction)
- Plan contains unresolved decisions (detected via summary extraction)

### Flow

```
PLAN complete
    |
    v
Extract plan summary via Task(haiku/explore)
    |
    v
Unresolved decisions? ----NO----> Proceed to IMPLEMENT
    |
   YES
    |
    v
Present refinement questions via AskUserQuestion()
    |
    v
User approves? ----YES----> Proceed to IMPLEMENT
    |
   NO (provides direction)
    |
    v
Delegate plan update to FRESH Task(opus)
    |
    v
Loop (max 3 iterations)
```

### Summary Extraction Prompt

```python
Task(
    prompt=f"""Read the plan section of {spec_path} using:
uv run {MUX_TOOLS}/extract-summary.py {plan_report_path}

Return ONLY:
1. Unresolved decisions (items marked TBD or with multiple options)
2. Open questions (dependencies on user input)
3. Ambiguities (underspecified behavior)

Format each as:
- DECISION: [description] | Options: [A, B, C] | Default: [suggested]

If nothing unresolved, return: NO_UNRESOLVED

IMPORTANT: Path is RELATIVE to project root. Do NOT prepend '/'.""",
    subagent_type="Explore",
    model="haiku",
    run_in_background=True
)
```

## Integration with MUX Protocol

Refinement uses ONLY allowed MUX actions:

| Action | Purpose |
|--------|---------|
| `AskUserQuestion()` | Present refinement questions to user |
| `Task()` | Delegate plan updates and summary extraction |
| `uv run extract-summary.py` | Read plan summaries (via delegated Task) |

### Prohibited During Refinement

- NEVER read spec or plan files directly
- NEVER interpret plan content in the orchestrator
- NEVER conduct research to inform refinement decisions (delegate instead)

## Signal Protocol

Refinement iterations produce distinct signals:

```
{session}/.signals/
  phase-{N}-plan.done              # Original PLAN completion
  phase-{N}-plan-refine-1.done     # Refinement iteration 1
  phase-{N}-plan-refine-2.done     # Refinement iteration 2
  phase-{N}-plan-refine-3.done     # Refinement iteration 3 (max)
```

## CONFIRM SC Refinement (All Modes)

The CONFIRM SC loop is a MANDATORY refinement gate for success criteria that applies BEFORE PLAN in ALL workflow modifiers (full, lean, leanest):

```python
# Already in SKILL.md - max 3 iterations
AskUserQuestion(question="Review SUCCESS_CRITERIA. Approve or refine?",
    options=[
        {"label": "Approve", "description": "SC accepted, proceed to PLAN"},
        {"label": "Refine", "description": "Adjust SC before proceeding"}
    ])
# If REFINE: delegate SC update, re-present
```

**Full mode**: SC extracted from consolidated research output.
**Lean/leanest modes**: SC extracted directly from spec file.

The PLAN refinement gate is a SEPARATE gate that applies after PLAN completes.

## Anti-Patterns

### Skipping Refinement

WRONG:
```python
# Plan has TBD items but orchestrator proceeds anyway
# "Saving time" by skipping refinement
# Result: IMPLEMENT agent makes arbitrary decisions, review catches them, wastes cycles
```

RIGHT:
```python
# Detect TBD items -> enter refinement gate -> resolve before IMPLEMENT
# Investment: ~2 minutes of user interaction
# Savings: Avoids 1-3 review-fix cycles (10-30 minutes each)
```

### Conducting Research Directly

WRONG:
```python
# Orchestrator reads codebase to inform refinement options
Read("src/auth/middleware.ts")  # VIOLATION: direct file reading
```

RIGHT:
```python
# Delegate research to Task agent, receive structured summary
Task(prompt="Analyze auth patterns in codebase. Return: current approach, dependencies, migration cost.",
     model="haiku", run_in_background=True)
```

### Vague Questions

WRONG:
```python
AskUserQuestion(question="Is the plan okay?")
# No options, no context, no suggested default
# User cannot make informed decision
```

RIGHT:
```python
AskUserQuestion(question="""Plan refinement:

## Refinement Request: Database Migration Strategy

### What Needs Refinement
Plan does not specify migration approach for schema changes.

### Options
1. Alembic auto-generate -- Fast, may miss edge cases
2. Manual migration scripts -- Full control, more effort
3. Schema-first with Alembic review -- Balanced approach

### Suggested Default
Option 3. Auto-generate as starting point, manual review before apply.

Approve plan or select/describe preferred approach?""")
```

### Reusing Context-Burned Agents

WRONG:
```python
# Same agent that produced the plan also applies refinement
# Agent carries stale plan context, may repeat same decisions
```

RIGHT:
```python
# FRESH agent for every refinement update
# Clean context = clean execution
Task(prompt="Apply refinement...", model="opus", run_in_background=True)
```
