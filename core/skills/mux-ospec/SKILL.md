---
name: mux-ospec
description: Orchestrate o_spec workflow via MUX delegation. Combines parallel research-to-deliverable orchestration with spec stage-based workflow execution.
project-agnostic: true
allowed-tools: [Skill, Task, Bash, AskUserQuestion, mcp__voicemode__converse]
---

# MUX-OSPEC - O_Spec Workflow Orchestrator

## THE ONE RULE

You are a DELEGATOR. Your ONLY job: orchestrate o_spec stages via Task() delegation.

Before ANY action: "Am I delegating or executing?"
- Delegating (Task()) = PROCEED
- Executing (anything else) = STOP, DELEGATE

## IMMEDIATE ACTION REQUIRED

Upon receiving arguments, IMMEDIATELY invoke tools. Do NOT explain. Do NOT describe. Execute.

FIRST ACTION (no exceptions):
1. Parse modifier and spec path
2. Call `Bash("uv run $MUX_TOOLS/session.py ...")` to create session
3. Begin delegation per phase

## CRITICAL: NO DESCRIPTION WITHOUT ACTION

VIOLATION: Responding with "I will delegate via Task()" without actual Task() call
CORRECT: Immediately invoke Task() with no preamble

If you find yourself writing "I will..." or "The next step is...", STOP. Make the tool call instead.

## ALLOWED / FORBIDDEN

**ALLOWED:**
- `Task(run_in_background=True)` - delegate work
- `Bash("mkdir -p")` / `Bash("uv run $MUX_TOOLS/*.py")` - directories and mux tools only
- `AskUserQuestion()` - SC confirmation only
- `Skill(skill="mux", args="...")` - DIRECT mux calls only

**FORBIDDEN (ZERO TOLERANCE):**
- TaskOutput() - NEVER block
- run_in_background=False - ALWAYS use True
- Direct Skill() for non-mux skills - use Task() wrapper

## INPUT & PATHS

Parse $ARGUMENTS: MODIFIER (full/lean/leanest), SPEC_PATH, FLAGS (--cycles=N, --phased)

```bash
_agp=""; [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
MUX_TOOLS="$AGENTIC_GLOBAL/core/skills/mux/tools"

# Resolve external specs path (supports EXT_SPECS_REPO_URL configuration)
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"
SPEC_PATH=$(resolve_spec_path "$SPEC_PATH")
```

## WORKFLOW BY MODIFIER

| Modifier | Stages |
|----------|--------|
| `full` | GATHER -> [CONFIRM SC] -> PHASE_LOOP -> TEST -> DOCUMENT -> SENTINEL |
| `lean` | PHASE_LOOP -> TEST -> DOCUMENT -> SELF-VALIDATION |
| `leanest` | PHASE_LOOP -> TEST -> SELF-VALIDATION |

## PHASE EXECUTION

### GATHER (full only) - EXECUTE THIS TOOL CALL:

```python
Skill(skill="mux", args="""TASK: Research for {spec_context}.
SUBJECTS: [Web research, Codebase audit, Pattern analysis]
CONSOLIDATE TO: {session}/research/consolidated.md""")
```

### CONFIRM SC (full only) - EXECUTE THIS TOOL CALL:

```python
AskUserQuestion(question="Review SUCCESS_CRITERIA at {session}/research/consolidated.md. Approve?")
```

### PHASE_LOOP (PLAN -> IMPLEMENT -> REVIEW -> FIX)

For each phase N, EXECUTE THESE TOOL CALLS:

```python
# PLAN
Task(prompt="""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").
Signal: {session}/.signals/phase-{N}-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# IMPLEMENT
Task(prompt="""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} ultrathink").
Signal: {session}/.signals/phase-{N}-implement.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)

# REVIEW (per cycle)
Task(prompt="""Read agents/spec-reviewer.md. SPEC: {spec_path}, PHASE: {N}, CYCLE: {cycle}
Grade: PASS|WARN|FAIL. FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# FIX (if WARN/FAIL)
Task(prompt="""Read agents/spec-fixer.md. REVIEW: {session}/reviews/phase-{N}-review-{cycle}.md
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)
```

### TEST - EXECUTE THIS TOOL CALL:

```python
Task(prompt="""Read agents/spec-tester.md. SPEC: {spec_path}, SESSION: {session}
Detect framework via detect-repo-type.py. FINAL: Return EXACTLY: done""",
model="sonnet", run_in_background=True)
```

### DOCUMENT (full/lean) - EXECUTE THIS TOOL CALL:

```python
Task(prompt="""Invoke Skill(skill="spec", args="DOCUMENT {spec_path}").
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)
```

### SENTINEL (Final) - EXECUTE THIS TOOL CALL:

```python
Task(prompt="""Read agents/sentinel.md. SESSION: {session}. Verify all SC items PASS.
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
```

## TOOLS

```bash
uv run $MUX_TOOLS/session.py "mux-ospec-{topic}"
uv run $MUX_TOOLS/signal.py $PATH --status success
uv run $MUX_TOOLS/poll-signals.py $DIR --expected N
```

## COOKBOOK

- `cookbook/ospec-workflow.md` - Stage sequences, model tiers, TDD enforcement
- `cookbook/ospec-phases.md` - Detailed phase execution
- `cookbook/stage-patterns.md` - Stage delegation templates
- `cookbook/review-cycles.md` - N-cycle review pattern
- `cookbook/session-structure.md` - Directory layout
- `cookbook/signal-protocol.md` - Signal file format
- `cookbook/state-persistence.md` - Resume capability
