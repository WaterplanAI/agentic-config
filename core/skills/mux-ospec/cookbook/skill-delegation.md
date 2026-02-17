# Skill Delegation Routing for MUX-OSPEC

Source of truth: SKILL.md defines the canonical workflow. This cookbook details delegation routing patterns without overriding stage sequences or signal formats.

## The Rule

mux-ospec NEVER invokes skills directly. ALL spec stage execution is delegated via Task().

## Why Direct Invocation is "Context Suicide"

| Tool | Execution Context | Impact |
|------|-------------------|--------|
| `Skill()` | CURRENT agent (orchestrator) | Context DESTROYED |
| `Task()` | NEW subagent context | Context PRESERVED |

Skill() executes IN the calling agent's context. Running `/spec PLAN` in orchestrator loads the entire spec workflow into orchestrator memory. Running `/spec IMPLEMENT` in the same context overwrites PLAN context with IMPLEMENT context. Result: orchestrator dies before reaching TEST stage.

## The Delegation Contract

**Orchestrator responsibility:**
- Parse modifier and spec path
- Initialize MUX session
- Launch stage agents via Task()
- Verify signal completion (via task-notification + verify.py)
- Verify artifacts after each stage
- NEVER read spec files directly
- NEVER invoke Skill(spec) directly

**Stage agent responsibility:**
- Receive stage instructions via Task() prompt
- Invoke Skill(skill="spec", args="STAGE ...") as FIRST action
- Produce expected artifacts (commits, signals, output files)
- Return EXACTLY: "done" or "STAGE_FAILED"
- NEVER implement stage logic themselves

## Routing Table

| Stage | WRONG (direct) | RIGHT (delegated) |
|-------|---------------|-------------------|
| PLAN | `Skill(skill="spec", args="PLAN ...")` | `Task(prompt="Invoke Skill(skill='spec', args='PLAN ...')", ...)` |
| IMPLEMENT | `Skill(skill="spec", args="IMPLEMENT ...")` | `Task(prompt="Invoke Skill(skill='spec', args='IMPLEMENT ...')", ...)` |
| REVIEW | `Skill(skill="spec", args="REVIEW ...")` | `Task(prompt="Read agents/spec-reviewer.md. ...", ...)` |
| FIX | `Skill(skill="spec", args="FIX ...")` | `Task(prompt="Read agents/spec-fixer.md. ...", ...)` |
| TEST | `Skill(skill="spec", args="TEST ...")` | `Task(prompt="Read agents/spec-tester.md. ...", ...)` |
| DOCUMENT | `Skill(skill="spec", args="DOCUMENT ...")` | `Task(prompt="Invoke Skill(skill='spec', args='DOCUMENT ...')", ...)` |
| SENTINEL | Direct read/analysis | `Task(prompt="Read agents/sentinel.md. SESSION: ...", ...)` |

## WRONG vs RIGHT Examples

### Stage: PLAN

**WRONG (Context Suicide):**

```python
# Fatal: Runs in orchestrator context
# Loads entire spec workflow into orchestrator
# Orchestrator context consumed by PLAN execution
Skill(skill="spec", args="PLAN specs/2026/02/auth/001-system.md ultrathink")
```

**RIGHT (Context Preserved):**

```python
# Correct: Launches fresh agent with spec skill invocation
# Agent receives explicit instruction to invoke Skill(spec)
# Orchestrator context remains clean, receives task-notification on completion
Task(
    prompt="""Invoke Skill(skill="spec", args="PLAN specs/2026/02/auth/001-system.md ultrathink").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT plan yourself.
- Do NOT read source files before invoking the skill.
- Do NOT write to the spec file directly.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT implement as fallback.

Signal: tmp/mux/20260206-1430-auth/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

### Stage: IMPLEMENT

**WRONG (Context Suicide):**

```python
# Fatal: Runs in orchestrator context
# Loads implementation context into orchestrator
# Overwrites PLAN context if it existed
Skill(skill="spec", args="IMPLEMENT specs/2026/02/auth/001-system.md")
```

**RIGHT (Context Preserved):**

```python
# Correct: Fresh agent invokes Skill(spec) for implementation
Task(
    prompt="""Invoke Skill(skill="spec", args="IMPLEMENT specs/2026/02/auth/001-system.md ultrathink").

CONSTRAINTS:
- Your FIRST action is Skill(spec). Do NOT implement yourself.
- Do NOT read the spec file directly before invoking the skill.
- Do NOT edit source files without Skill(spec) guidance.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT code as fallback.

Signal: tmp/mux/20260206-1430-auth/.signals/phase-1-implement.done
FINAL: Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### Stage: REVIEW

**WRONG (Vague Delegation):**

```python
# Fatal: Agent may interpret "review" as manual code reading
# No explicit Skill() invocation instruction
# Agent likely reads files directly instead of using reviewer agent
Task(prompt="Review the implementation for phase 1", model="opus", run_in_background=True)
```

**WRONG (Direct Skill Invocation):**

```python
# Fatal: spec skill has no REVIEW stage
# Must use agents/spec-reviewer.md instead
Skill(skill="spec", args="REVIEW specs/2026/02/auth/001-system.md")
```

**RIGHT (Explicit Agent Reference):**

```python
# Correct: Agent reads spec-reviewer.md for review protocol
# Reviewer agent has specialized review logic
Task(
    prompt="""Read agents/spec-reviewer.md. SPEC: specs/2026/02/auth/001-system.md, PHASE: 1, CYCLE: 1

CONSTRAINTS:
- Follow reviewer protocol exactly (compliance check, quality check, grading matrix)
- Do NOT skip compliance validation
- Do NOT implement fixes yourself - return grade only
- Grade must be PASS, WARN, or FAIL

OUTPUT: tmp/mux/20260206-1430-auth/reviews/phase-1-review-1.md
SIGNAL: tmp/mux/20260206-1430-auth/.signals/phase-1-review-1.done
FINAL: Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

### Stage: FIX

**WRONG (Context Suicide):**

```python
# Fatal: spec skill has no FIX stage
# Orchestrator attempts to fix issues itself
Skill(skill="spec", args="FIX specs/2026/02/auth/001-system.md")
```

**WRONG (Helpful Trap):**

```python
# Fatal: Orchestrator reads review, attempts fix directly
# Violates delegation protocol
Read("tmp/mux/20260206-1430-auth/reviews/phase-1-review-1.md")
Edit("src/auth/login.py")  # Direct edit from orchestrator
```

**RIGHT (Explicit Fixer Agent):**

```python
# Correct: Delegate to spec-fixer agent
Task(
    prompt="""Read agents/spec-fixer.md. REVIEW: tmp/mux/20260206-1430-auth/reviews/phase-1-review-1.md

CONSTRAINTS:
- Read review file to identify issues
- Apply targeted fixes only (do NOT refactor unrelated code)
- Verify fixes pass type check and tests
- Commit with: spec(001): FIX phase-1 cycle-1

SIGNAL: tmp/mux/20260206-1430-auth/.signals/phase-1-fix-1.done
FINAL: Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### Stage: TEST

**WRONG (Direct Execution):**

```python
# Fatal: Orchestrator runs tests directly
# Violates bash whitelist (no test runners)
Bash("npm test")
```

**WRONG (Vague Delegation):**

```python
# Fatal: No explicit tester agent reference
# Agent may run tests without framework detection
Task(prompt="Run the tests", model="sonnet", run_in_background=True)
```

**RIGHT (Explicit Tester Agent):**

```python
# Correct: Delegate to spec-tester agent with framework detection
Task(
    prompt="""Read agents/spec-tester.md. SPEC: specs/2026/02/auth/001-system.md, SESSION: tmp/mux/20260206-1430-auth

CONSTRAINTS:
- Detect framework via detect-repo-type.py (pytest, jest, vitest, etc)
- Run appropriate test command for detected framework
- Capture test results in JSON format
- Do NOT implement missing tests yourself

OUTPUT: tmp/mux/20260206-1430-auth/tests/test-results.json
SIGNAL: tmp/mux/20260206-1430-auth/.signals/test.done
FINAL: Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### Stage: DOCUMENT

**WRONG (Context Suicide):**

```python
# Fatal: Runs in orchestrator context
# Loads documentation generation logic into orchestrator
Skill(skill="spec", args="DOCUMENT specs/2026/02/auth/001-system.md")
```

**RIGHT (Context Preserved):**

```python
# Correct: Fresh agent invokes Skill(spec) for documentation
Task(
    prompt="""Invoke Skill(skill="spec", args="DOCUMENT specs/2026/02/auth/001-system.md").

CONSTRAINTS:
- Your ONLY action is Skill(spec). Do NOT write docs yourself.
- Do NOT read source files to generate docs manually.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT write fallback docs.

Signal: tmp/mux/20260206-1430-auth/.signals/document.done
FINAL: Return EXACTLY: done""",
    model="sonnet",
    run_in_background=True
)
```

### Stage: SENTINEL

**WRONG (Direct Analysis):**

```python
# Fatal: Orchestrator reads session files directly
# Analyzes artifacts manually
Read("tmp/mux/20260206-1430-auth/plan.md")
Bash("git log --oneline -20")
Grep(pattern="SC-", path="specs/2026/02/auth/001-system.md")
```

**RIGHT (Sentinel Agent):**

```python
# Correct: Delegate to sentinel agent for final validation
Task(
    prompt="""Read agents/sentinel.md. SESSION: tmp/mux/20260206-1430-auth

CONSTRAINTS:
- Verify all SUCCESS_CRITERIA items from spec
- Check git log for expected commits (PLAN, IMPLEMENT, FIX, DOCUMENT)
- Validate test results
- Check type check passed
- Return PASS only if ALL criteria met

OUTPUT: tmp/mux/20260206-1430-auth/sentinel-review.md
SIGNAL: tmp/mux/20260206-1430-auth/.signals/sentinel.done
FINAL: Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)
```

## Delegation Template with Constraints

Standard template for all stage delegations:

```python
Task(
    prompt=f"""[Exact action instruction with Skill() call or agent reference]

CONSTRAINTS:
- [Primary constraint: what agent MUST do first]
- [Secondary constraints: what agent MUST NOT do]
- [Failure handling: what to do if primary action fails]

OUTPUT: [Expected artifact path or "Implementation artifacts"]
SIGNAL: {{session}}/.signals/[stage-name].done
FINAL: Return EXACTLY: done""",
    model="[opus|sonnet|haiku based on stage tier]",
    run_in_background=True
)
```

## Fatal Violation Examples

### Violation 1: Orchestrator Reads Spec File

```python
# FATAL: Orchestrator consuming spec content directly
# Should delegate to stage agent who invokes Skill(spec)
Read("specs/2026/02/auth/001-system.md")
```

**Impact:** Orchestrator context polluted with spec content. MUX session hooks should block this, but if orchestrator bypasses hooks, delegation protocol is violated.

### Violation 2: Orchestrator Implements Stage Logic

```python
# FATAL: Orchestrator planning without delegation
# Should launch Task() with Skill(spec) invocation
Read("specs/2026/02/auth/001-system.md")
Write("tmp/mux/20260206-1430-auth/plan.md", content="...")
Bash("git add tmp/mux/20260206-1430-auth/plan.md && git commit -m 'Add plan'")
```

**Impact:** No spec commit. Plan file in wrong location. Verification fails. Stage must be re-run.

### Violation 3: Vague Stage Prompt

```python
# FATAL: Agent may not invoke Skill(spec)
# Prompt allows interpretation
Task(prompt="Create a plan for the auth system", model="opus", run_in_background=True)
```

**Impact:** Agent writes plan manually without invoking /spec PLAN. Spec file remains empty. No spec commit. Verification fails.

### Violation 4: Stage Agent Does Not Invoke Skill

```python
# FATAL: Agent received delegation but bypassed Skill(spec)
# Agent prompt was clear but agent "helped" by planning manually
# Prompt: "Invoke Skill(skill='spec', args='PLAN ...')"
# Agent action: Read(spec), Write(plan), NO Skill() invocation
```

**Impact:** This is the "helpful trap." Agent rationalizes: "I can plan faster myself." Result: spec file empty, no commit, verification catches it, stage marked FAILED.

**Prevention:** Anti-bypass CONSTRAINTS in stage prompts:
- "Your ONLY action is Skill(spec). Do NOT plan yourself."
- "If Skill(spec) fails, return STAGE_FAILED - do NOT implement as fallback."

### Violation 5: Blocking on Agent Completion

```python
# FATAL: Orchestrator waits for agent to finish
# Should launch background and continue immediately
Task(
    prompt="...",
    model="opus",
    run_in_background=False  # WRONG: blocking
)
```

**Impact:** Orchestrator blocked. Cannot launch next stage. Violates MUX non-blocking principle.

### Violation 6: Polling Agent Output

```python
# FATAL: Orchestrator checking agent progress directly
# Should rely on signals only
Bash("tail -f tmp/mux/20260206-1430-auth/.signals/phase-1-plan.done")
Read("tmp/mux/20260206-1430-auth/plan.md")  # Before signal exists
```

**Impact:** Violates non-blocking principle. Orchestrator consumed waiting for agent. Signal protocol exists for this reason.

## Correct Delegation Flow

Complete example of PLAN stage with full compliance:

```python
# 1. Orchestrator receives mux-ospec invocation
# args: "lean specs/2026/02/auth/001-system.md"

# 2. Orchestrator initializes session
Bash("uv run .claude/skills/mux/tools/session.py 'mux-ospec-auth-system'")
# Result: tmp/mux/20260206-1430-auth/ created, hooks active

# 3. Orchestrator launches PLAN stage (background worker)
Task(
    prompt="""Invoke Skill(skill="spec", args="PLAN specs/2026/02/auth/001-system.md ultrathink").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT plan yourself.
- Do NOT read source files before invoking the skill.
- Do NOT write to the spec file directly.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT implement as fallback.

Signal: tmp/mux/20260206-1430-auth/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""",
    model="opus",
    run_in_background=True
)

# 4. Orchestrator prints checkpoint and continues immediately
"""
Stage: PLAN (Phase 1 of 3)
Checkpoint:
- Agent launched (opus, background)
- Expected signal: .signals/phase-1-plan.done
- Expected artifacts: spec commit, AI Section content
- Expected duration: 5-10 min
- Continuing immediately

Stage Progress:
- PLAN: IN_PROGRESS (agent running)
- IMPLEMENT: PENDING
- REVIEW: PENDING
- TEST: PENDING

Waiting for PLAN signal...
"""

# 5. PLAN agent receives Task() prompt, invokes Skill(spec)
# Skill(skill="spec", args="PLAN specs/2026/02/auth/001-system.md ultrathink")
# /spec PLAN executes: reads spec, generates plan, writes to AI Section, commits

# 6. PLAN agent signals completion
# Bash("uv run tools/signal.py tmp/mux/20260206-1430-auth/.signals/phase-1-plan.done --status success")

# 7. Runtime task-notification delivered to orchestrator

# 8. Orchestrator verifies PLAN artifacts
# - Check git log for spec commit: git log --oneline -5 | grep "spec([0-9]\+): PLAN"
# - Check spec file AI Section: sed -n '/^## AI Section/,/^## Human Section/p' | wc -l > 50

# 9. If verification passes, launch IMPLEMENT
# If verification fails, enter refinement flow
```

## Stage Agent Responsibilities

Stage agents that receive delegation MUST:

1. Invoke Skill(skill="spec", args="STAGE ...") as FIRST action (or read designated agent file for non-spec stages)
2. NOT read source files before skill invocation
3. NOT implement stage logic themselves
4. NOT write to spec file directly (Skill(spec) does this)
5. Return "STAGE_FAILED" if Skill(spec) fails (do NOT implement as fallback)
6. Signal completion after Skill() returns
7. Return EXACTLY: "done" as final output

Stage agents MUST NOT:

1. Read the spec file before invoking Skill(spec)
2. Implement planning/coding/testing logic themselves
3. Skip Skill() invocation to "help" or "be faster"
4. Continue working after Skill() fails (return STAGE_FAILED instead)
5. Write plans/code without Skill() guidance

## Orchestrator Responsibilities

Orchestrator MUST:

1. Initialize MUX session FIRST (before any delegation)
2. Launch workers via Task(run_in_background=True) with explicit Skill() instructions
3. Receive task-notifications from runtime on worker completion
4. Print checkpoints after every worker launch
5. Continue immediately after launch (do NOT block)
6. Verify artifacts after stage signals complete
7. Enter refinement flow if verification fails
8. NEVER read spec files directly
9. NEVER invoke Skill(spec) directly
10. NEVER run tests/builds directly

Orchestrator MUST NOT:

1. Read source files or spec files
2. Invoke any Skill() except Skill(skill="mux") during initialization
3. Block on agent completion (TaskOutput())
4. Poll agent output files
5. Implement stage logic itself
6. Skip verification after stage completion
