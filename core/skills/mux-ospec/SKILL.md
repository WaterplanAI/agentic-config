---
name: mux-ospec
description: Orchestrate o_spec workflow via MUX delegation. Combines parallel research-to-deliverable orchestration with spec stage-based workflow execution.
project-agnostic: true
allowed-tools: [Task, Bash, AskUserQuestion, mcp__voicemode__converse]
---

# MUX-OSPEC - O_Spec Workflow Orchestrator

## MANDATORY FIRST ACTION (NO EXCEPTIONS)

**BEFORE ANY OTHER TOOL CALL**, you MUST run:

```bash
uv run .claude/skills/mux/tools/session.py "mux-ospec-{topic}"
```

This creates the session AND activates MUX enforcement hooks.
**If you skip this, hooks will block all subsequent tool calls.**

---

## PREAMBLE RITUAL (BEFORE EVERY TOOL CALL)

**BEFORE EVERY TOOL CALL**, output this EXACTLY:

```
MUX MODE | Action: [Task|mkdir|uv run tools] | Target: ___ | Rationale: ___
```

If you cannot complete this sentence with an allowed action, **STOP AND DELEGATE**.

**VIOLATIONS:**
- Using Glob/Grep/Read/Edit/Write = BLOCKED BY HOOK
- Skipping preamble = PROTOCOL VIOLATION
- Any action not in ALLOWED ACTIONS table = DELEGATE

---

## THE ONE RULE

You are a DELEGATOR. Your ONLY job: orchestrate o_spec stages via Task() delegation.

Before ANY action: "Am I delegating or executing?"
- Delegating (Task()) = PROCEED
- Executing (anything else) = STOP, DELEGATE

**You NEVER interpret stage results.** When a stage agent completes:
- Delegate reading signal/output to Task(haiku/explore)
- Receive ONLY routing data: status, grade, commit hash
- Route to next stage based on returned routing data
- NEVER read signal files, review reports, or stage outputs yourself

## CRITICAL: NO DESCRIPTION WITHOUT ACTION

VIOLATION: Responding with "I will delegate via Task()" without actual Task() call
CORRECT: Immediately invoke Task() with no preamble

If you find yourself writing "I will..." or "The next step is...", STOP. Make the tool call instead.

## ALLOWED ACTIONS (EXHAUSTIVE)

| Action | Tool | Constraint |
|--------|------|------------|
| Delegate work | Task(run_in_background=True) | Always background |
| Create directories | Bash("mkdir -p") | Directories only |
| List directories | Bash("ls") | Directories only |
| Run mux tools | Bash("uv run tools/*.py") | Session init, signals, polls |
| Ask user | AskUserQuestion() | SC confirmation, gates |
| Voice update | mcp__voicemode__converse() | At milestones |

Everything else = DELEGATE via Task()

## FORBIDDEN (ZERO TOLERANCE)

- **Direct execution** - NEVER use Read/Write/Edit/Grep/Glob/WebFetch/WebSearch yourself
- **Skill()** - NEVER invoke skills directly. Delegate: `Task(prompt="Invoke Skill(skill='spec', ...)")`
- **TaskOutput()** - NEVER block on agent completion
- **run_in_background=False** - ALWAYS use True
- **Blocking on agents** - Continue immediately after launch, use signals for completion
- **Polling agent output** - NEVER use Read/Bash/tail to check agent progress files
- **Interpreting stage results** - NEVER read signal files, review reports, test outputs, or stage artifacts yourself. Delegate reading to Task(haiku/explore) and receive ONLY routing data

## WORKER + MONITOR (MANDATORY)

Every Task() launch requires a monitor in the SAME message:

```python
# Stage worker
Task(prompt="...", model="opus", run_in_background=True)

# Monitor (SAME message)
Task(prompt=f"Read agents/monitor.md. EXPECTED: 1. Use poll-signals.py.",
     model="haiku", run_in_background=True)

# Checkpoint
# Stage worker launched (opus, background)
# Monitor in same message (haiku)
# Continuing immediately
```

Missing monitor = PROTOCOL VIOLATION

---

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
| `full` | GATHER -> CONSOLIDATE -> [CONFIRM SC] -> PHASE_LOOP -> TEST -> DOCUMENT -> SENTINEL |
| `lean` | PHASE_LOOP -> TEST -> DOCUMENT -> SELF-VALIDATION |
| `leanest` | PHASE_LOOP -> TEST -> SELF-VALIDATION |

## PHASE EXECUTION

Each stage = one Task() subagent whose FIRST and MANDATORY action is `/spec <STAGE>`.
mux-ospec knows NOTHING about how stages work internally. It only knows the ORDER.

### GATHER (full only)

MUX parallel research - NOT a /spec stage. Uses MUX fan-out pattern.

```python
Task(prompt="""You are a MUX research orchestrator for: {spec_context}

YOUR FIRST AND ONLY ACTION: Orchestrate research via parallel Task() delegation.
Subjects: [Web research, Codebase audit, Pattern analysis]
Consolidate to: {session}/research/consolidated.md

DO NOT read source files yourself. DO NOT write consolidated output yourself.
If research fails, RETURN "STAGE_FAILED".

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/gather.done --status success
RETURN: "STAGE_GATHER_COMPLETE"
""", subagent_type="general-purpose", model="opus", run_in_background=True)
```

### CONFIRM SC (full only)

Refinement loop - present SC to user, iterate if needed:

```python
# 1. Delegate reading SC summary
Task(prompt="Read {session}/research/consolidated.md. Return ONLY the SUCCESS_CRITERIA section.",
     subagent_type="Explore", model="haiku", run_in_background=True)

# 2. Present to user
AskUserQuestion(question="Review SUCCESS_CRITERIA. Approve or refine?",
    options=[
        {"label": "Approve", "description": "SC accepted, proceed to PLAN"},
        {"label": "Refine", "description": "Adjust SC before proceeding"}
    ])

# 3. If REFINE: delegate SC update, re-present
# Loop until approved or max 3 iterations
```

### PHASE_LOOP (PLAN -> IMPLEMENT -> REVIEW -> FIX)

For each phase N, delegate ONE stage at a time. Each stage agent's FIRST action = `/spec <STAGE>`.

#### PLAN

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="PLAN {spec_path}")

DO NOT read files, write code, or do anything before invoking this Skill.
DO NOT plan as a fallback if the Skill fails.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. git log --oneline -5 | grep -i "spec.*PLAN" (commit must exist)
2. Spec file has >50 lines in AI Section

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/phase-{N}-plan.done --status success --meta commit="$(git rev-parse --short HEAD)"
RETURN: "STAGE_PLAN_COMPLETE"
""", subagent_type="general-purpose", model="opus", run_in_background=True)
```

#### IMPLEMENT

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="IMPLEMENT {spec_path}")

DO NOT read the spec to "understand" it first. DO NOT write code yourself.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. git log --oneline -10 | grep -E "(feat|fix|refactor)\\(" (commit must exist)
2. Type check passes: {type_check_cmd}
3. No test regressions: {test_cmd}

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/phase-{N}-implement.done --status success --meta commit="$(git rev-parse --short HEAD)"
RETURN: "STAGE_IMPLEMENT_COMPLETE"
""", subagent_type="general-purpose", model="sonnet", run_in_background=True)
```

#### REVIEW

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="REVIEW {spec_path}")

ENHANCEMENT: Also read agents/spec-reviewer.md at {AGENTIC_GLOBAL}/core/skills/mux-ospec/agents/spec-reviewer.md for additional review criteria beyond /spec defaults.

DO NOT invent your own review criteria. DO NOT fix issues (only report them).
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. Review report exists with explicit grade: PASS, WARN, or FAIL

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/phase-{N}-review-{cycle}.done --status success --meta grade="{PASS|WARN|FAIL}"
RETURN: "STAGE_REVIEW_COMPLETE grade={PASS|WARN|FAIL}"
""", subagent_type="general-purpose", model="opus", run_in_background=True)
```

#### FIX

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="FIX {spec_path}")

ENHANCEMENT: Also read agents/spec-fixer.md at {AGENTIC_GLOBAL}/core/skills/mux-ospec/agents/spec-fixer.md for context-preserving fix protocol.
REVIEW REPORT: {session}/reviews/phase-{N}-review-{cycle}.md

DO NOT invent fixes outside the review findings. DO NOT delete working code.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. git log --oneline -5 | grep -i "fix" (commit must exist)
2. Type check passes: {type_check_cmd}

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/phase-{N}-fix-{cycle}.done --status success --meta commit="$(git rev-parse --short HEAD)"
RETURN: "STAGE_FIX_COMPLETE"
""", subagent_type="general-purpose", model="sonnet", run_in_background=True)
```

### TEST

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="TEST {spec_path}")

ENHANCEMENT: Also read agents/spec-tester.md at {AGENTIC_GLOBAL}/core/skills/mux-ospec/agents/spec-tester.md for adaptive test execution and framework detection.

DO NOT write tests yourself. DO NOT skip execution. DO NOT fabricate results.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. Tests actually ran (check output for pass/fail counts)

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/test.done --status success --meta grade="{PASS|FAIL}",tests_run={N},tests_passed={N}
RETURN: "STAGE_TEST_COMPLETE grade={PASS|FAIL}"
""", subagent_type="general-purpose", model="sonnet", run_in_background=True)
```

### DOCUMENT (full/lean)

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="DOCUMENT {spec_path}")

DO NOT read source files to summarize them. DO NOT write docs yourself.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. git log --oneline -5 | grep -i "spec.*DOCUMENT" (commit must exist)

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/document.done --status success --meta commit="$(git rev-parse --short HEAD)"
RETURN: "STAGE_DOCUMENT_COMPLETE"
""", subagent_type="general-purpose", model="sonnet", run_in_background=True)
```

### SENTINEL (full) / SELF-VALIDATION (lean/leanest)

```python
Task(prompt="""THINK VERY HARD; TAKE YOUR TIME.

Your FIRST and MANDATORY action:
Skill(skill="spec", args="SENTINEL {spec_path}")

ENHANCEMENT: Also read agents/sentinel.md at {AGENTIC_GLOBAL}/core/skills/mux-ospec/agents/sentinel.md for cross-phase coordination review criteria.

DO NOT approve incomplete work. DO NOT override the grade.
If Skill fails: RETURN "STAGE_FAILED"

After Skill completes, verify:
1. All SC items explicitly graded
2. Overall grade is explicit: PASS, WARN, or FAIL

Signal: uv run {MUX_TOOLS}/signal.py {session}/.signals/sentinel.done --status success --meta grade="{PASS|WARN|FAIL}"
RETURN: "STAGE_SENTINEL_COMPLETE grade={PASS|WARN|FAIL}"
""", subagent_type="general-purpose", model="opus", run_in_background=True)
```

## TOOLS

```bash
uv run $MUX_TOOLS/session.py "mux-ospec-{topic}"
uv run $MUX_TOOLS/signal.py $PATH --status success
uv run $MUX_TOOLS/poll-signals.py $DIR --expected N
```

## LESSONS LEARNED (HARDCODED - NEVER VIOLATE)

### 1. Orchestrator Must Not Read Spec Files

**What failed:** Orchestrator read the spec file directly, ran git commands, listed directories, searched patterns. Consumed 55s and massive context before any delegation happened. No work done. Spec file remained empty. No PLAN commit. No IMPLEMENT commit.

**Rule:** RUN session.py FIRST. Session init activates hooks that BLOCK Read/Grep/Glob. Delegate ALL spec reading to stage agents. Orchestrator receives ONLY signal notifications and stage completion status. If you find yourself reading ANY file, you are VIOLATING this rule.

### 2. Stage Agents Must Invoke /spec as FIRST Action

**What failed:** PLAN agent received spec path and wrote its own plan without invoking `/spec PLAN`. Spec file empty. No commit. Agent "helped" by doing the work itself.

**Rule:** Every stage agent's FIRST and MANDATORY action = `Skill(skill="spec", args="<STAGE> <spec_path>")`. No reading, no writing, no thinking before invoking /spec. The Skill IS the work.

### 3. Stage Agent Returns Without Artifacts

**What failed:** Agent returned "STAGE_PLAN_COMPLETE" without producing commits, signals, or output files. Git log unchanged. Agent claimed success falsely.

**Rule:** Orchestrator delegates signal reading after every return. Signal must contain status + metadata (commit hash, grade). Missing signal or missing metadata = STAGE_FAILED. Delegate verification to signal reader, never trust agent return value alone.

### 4. Direct Skill() Invocation Killed Orchestrator

**What failed:** Orchestrator called Skill(skill="spec", args="PLAN ...") directly. Entire spec workflow loaded into orchestrator context. Context died before IMPLEMENT.

**Rule:** NEVER invoke Skill() directly. Always delegate: Task(prompt="Invoke Skill(...)").

### 5. Always Launch NEW Stage Agent After Failure

**What failed:** Attempting to resume a stage agent after STAGE_FAILED polluted context from the failed attempt. Agent carried stale state and repeated the same error.

**Rule:** After any STAGE_FAILED or review cycle fix, always launch a FRESH stage agent. Never resume a failed one. Fresh context = clean execution.

### 6. Monitor Timeouts Are Normal

**What happened:** Monitors timed out at 5-10min while stage workers were still active. This is expected behavior for complex PLAN/IMPLEMENT stages that may run 100+ tool calls.

**Rule:** When monitor times out, check worker status (`tail -5 <output-file>`). If worker still active, relaunch monitor with same/longer timeout. Do NOT treat timeout as failure. Do NOT abort the stage.

### 7. Stale Monitor Notifications Are Normal

**What happened:** After relaunching monitors, old monitors eventually completed with stale signals. These notifications arrived after the stage was already processed by the new monitor.

**Rule:** When a monitor notification arrives, verify it matches the CURRENT stage. If stale (stage already completed or moved to next), ignore and continue. Do NOT re-process completed stages.

### 8. Orchestrator Must Not Interpret Stage Results

**What failed:** Orchestrator read signal files and review reports directly to determine routing (PASS/WARN/FAIL). This consumed context with review details the orchestrator doesn't need, and violated the delegation principle.

**Rule:** After EVERY stage notification, delegate reading the signal file to Task(haiku/explore). Receive ONLY structured routing data: status, grade, commit, error. Route based on routing data. NEVER read signal files, review reports, test outputs, or any stage artifacts yourself.

## ERROR RECOVERY

| Scenario | Action |
|----------|--------|
| Stage agent timeout | Monitor times out, check worker status via tail, relaunch monitor |
| Worker truly stuck | Mark stage STAGE_FAILED, launch NEW stage agent |
| Skill(spec) internal failure | Stage agent returns STAGE_FAILED with error details |
| Type check fails 3x | STAGE_FAILED with error details, escalate to user |
| Tests fail 3x | STAGE_FAILED with failure analysis, escalate to user |
| Context exhaustion | Stage agent dies mid-work. Relaunch from last signal checkpoint |
| Review cycle WARN after max cycles | Proceed to TEST with warning. Log gaps |
| Stale monitor notification | Ignore - verify against current stage state |
| Signal file missing after "done" | Treat as STAGE_FAILED, relaunch fresh agent |

## SESSION CLEANUP

When mux-ospec work is complete, deactivate enforcement:

```bash
uv run .claude/skills/mux/tools/deactivate.py
```

This removes the mux-active marker and restores normal operation.

## COOKBOOK

- `cookbook/ospec-workflow.md` - Stage sequences, model tiers, TDD enforcement
- `cookbook/ospec-phases.md` - Detailed phase execution
- `cookbook/stage-patterns.md` - Stage delegation templates
- `cookbook/review-cycles.md` - N-cycle review pattern
- `cookbook/session-structure.md` - Directory layout
- `cookbook/signal-protocol.md` - Signal file format
- `cookbook/state-persistence.md` - Resume capability
- `cookbook/anti-patterns.md` - Violation examples with WRONG/RIGHT patterns
- `cookbook/skill-delegation.md` - Skill routing table
- `cookbook/bash-rules.md` - Bash command whitelist
- `cookbook/error-recovery.md` - Error handling and retry patterns
- `cookbook/phase-decomposition.md` - DAG-based phase decomposition
- `cookbook/stack-priming.md` - Stack-specific context injection
- `cookbook/test-commands.md` - Framework-specific test commands

---

## ENFORCEMENT SUMMARY

| Layer | What Happens |
|-------|--------------|
| **Session Init** | MUST run session.py FIRST - creates enforcement marker |
| **Forbidden Tools** | Read/Write/Edit/Grep/Glob/WebSearch -> **BLOCKED** |
| **Bash Whitelist** | Only `mkdir -p`, `ls`, `uv run tools/*` allowed |
| **User Approval** | ALL tool calls require confirmation (askFirst) |
| **Fail-Closed** | Hook errors -> BLOCK (not allow) |
| **Skill() Direct** | FORBIDDEN - delegate via Task() wrapping Skill() |

---

## SIGNAL READER PROMPT TEMPLATE

After EVERY stage notification, delegate reading the signal to get routing data.
**The orchestrator NEVER reads signal files directly.**

```python
Task(
    prompt=f"""Read the signal file at {signal_path}.
Return ONLY this structured routing data, nothing else:

status: <success|failed>
grade: <PASS|WARN|FAIL|N/A>
commit: <hash|N/A>
error: <description|none>
metadata: <key=value pairs from signal>

Do NOT summarize, interpret, or add commentary. Raw routing data only.""",
    subagent_type="Explore",
    model="haiku",
    run_in_background=True
)
```

## EXECUTION LOOP

```
1. Parse $ARGUMENTS -> MODIFIER, SPEC_PATH, FLAGS
2. Run session.py (MANDATORY FIRST)
3. mkdir -p {session}/.signals

IF modifier == "full":
  GATHER:
    MUX MODE | Action: Task (gather + monitor) | Target: research | Rationale: parallel research
    Launch gather agent (opus, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When notification arrives:
      Delegate signal reading to Task(haiku/explore): read gather.done
      IF status=success -> proceed to CONFIRM SC
      IF status=failed -> STAGE_FAILED, escalate to user

  CONFIRM SC:
    MUX MODE | Action: AskUserQuestion | Target: SC approval | Rationale: gate before implementation
    Wait for user confirmation

PHASE_LOOP (for each phase N):
  PLAN:
    MUX MODE | Action: Task (PLAN + monitor) | Target: Phase {N} PLAN | Rationale: next stage
    Launch PLAN agent (opus, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When notification arrives:
      Delegate signal reading to Task(haiku/explore): read phase-{N}-plan.done
      IF status=success -> proceed to IMPLEMENT
      IF status=failed -> launch NEW PLAN agent (fresh context)

  IMPLEMENT:
    MUX MODE | Action: Task (IMPLEMENT + monitor) | Target: Phase {N} IMPLEMENT | Rationale: plan done
    Launch IMPLEMENT agent (sonnet, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When notification arrives:
      Delegate signal reading to Task(haiku/explore): read phase-{N}-implement.done
      IF status=success -> proceed to REVIEW
      IF status=failed -> launch NEW IMPLEMENT agent (fresh context)

  REVIEW (cycle loop):
    MUX MODE | Action: Task (REVIEW + monitor) | Target: Phase {N} REVIEW cycle {C} | Rationale: impl done
    Launch REVIEW agent (opus, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When notification arrives:
      Delegate signal reading to Task(haiku/explore): read phase-{N}-review-{C}.done
      Parse grade from returned routing data
      IF grade=PASS -> proceed to TEST (or next phase)
      IF grade=WARN/FAIL + cycle < max:
        Launch FIX agent (sonnet, bg) + monitor in SAME message
        When fix notification arrives:
          Delegate signal reading to Task(haiku/explore): read phase-{N}-fix-{C}.done
          Launch NEW REVIEW agent (fresh context, cycle C+1)
      IF grade=WARN/FAIL + cycle >= max -> proceed with warning

TEST:
  MUX MODE | Action: Task (TEST + monitor) | Target: test execution | Rationale: review passed
  Launch TEST agent (sonnet, bg) + monitor (haiku, bg) in SAME message
  Print checkpoint
  Continue immediately
  When notification arrives:
    Delegate signal reading to Task(haiku/explore): read test.done
    IF grade=PASS -> proceed
    IF grade=FAIL -> STAGE_FAILED, escalate to user

IF modifier != "leanest":
  DOCUMENT:
    MUX MODE | Action: Task (DOCUMENT + monitor) | Target: documentation | Rationale: tests passed
    Launch DOCUMENT agent (sonnet, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When notification arrives:
      Delegate signal reading to Task(haiku/explore): read document.done
      IF status=success -> proceed
      IF status=failed -> escalate

SENTINEL (full) / SELF-VALIDATION (lean/leanest):
  MUX MODE | Action: Task (SENTINEL + monitor) | Target: final validation | Rationale: all stages done
  Launch SENTINEL agent (opus, bg) + monitor (haiku, bg) in SAME message
  When notification arrives:
    Delegate signal reading to Task(haiku/explore): read sentinel.done
    IF grade=PASS -> WORKFLOW COMPLETE
    IF grade=WARN -> WORKFLOW COMPLETE with warnings
    IF grade=FAIL -> escalate to user

CLEANUP:
  uv run deactivate.py
  Print final report
```

## MONITOR PROMPT TEMPLATE

Always launched in the SAME message as the stage worker:

```python
Task(
    prompt=f"""Read agents/monitor.md for protocol.

SESSION: {session}
EXPECTED: {expected_signal_count}
SIGNAL_DIR: {session}/.signals

Use subscribe.py (push; fallback to polling with 10min timeout).

FINAL: Return EXACTLY: done""",
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True
)
```

## CHECKPOINT PATTERN (after EVERY launch)

```
MUX MODE | Status: {STAGE} agent launched + monitor active | Continuing immediately

{STAGE} stage for Phase {N} launched.

Checkpoint:
- Worker launched ({model}, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

Workflow Progress:
- GATHER: {COMPLETE|SKIPPED}
- PLAN: {COMPLETE|IN_PROGRESS|PENDING}
- IMPLEMENT: {COMPLETE|IN_PROGRESS|PENDING}
- REVIEW: {COMPLETE|IN_PROGRESS cycle {C}/{max}|PENDING}
- TEST: {COMPLETE|IN_PROGRESS|PENDING}
- DOCUMENT: {COMPLETE|IN_PROGRESS|PENDING|SKIPPED}
- SENTINEL: {COMPLETE|IN_PROGRESS|PENDING}

Waiting for notifications.
```

---

# Report

## Progress Updates (MANDATORY)

### After EVERY Stage Completion

```
STAGE_{STAGE}_COMPLETE - {description}.

Stage Results:
- Signal: {signal_path}
- Commits: {hash} (if applicable)
- Duration: ~{N}min
- Key output: {brief summary}

Workflow Progress:
- GATHER: {state}
- PLAN: {state}
- IMPLEMENT: {state}
- REVIEW: {state} (cycle {C}/{max})
- TEST: {state}
- DOCUMENT: {state}
- SENTINEL: {state}
```

### After Review Cycle

```
REVIEW cycle {C} grade: {PASS|WARN|FAIL}

Review Results:
- Compliance: {grade} ({N} gaps)
- Quality: {grade} ({N} issues)
- Action: {EARLY EXIT to TEST | FIX + re-review | PROCEED with warning}

Workflow Progress:
- REVIEW: cycle {C}/{max} - {grade}
```

### After WORKFLOW COMPLETE

```
WORKFLOW COMPLETE.

Final Status:
- GATHER: {COMPLETE|SKIPPED}
- PLAN: COMPLETE (commit: {hash})
- IMPLEMENT: COMPLETE (commit: {hash})
- REVIEW: COMPLETE ({C} cycles, final grade: {grade})
- TEST: COMPLETE ({N} passing, {M} new)
- DOCUMENT: {COMPLETE|SKIPPED}
- SENTINEL: COMPLETE (grade: {grade})

Spec: {SPEC_PATH}
Session: {session}
Branch: {branch}
```

Then deactivate MUX session:
```bash
uv run .claude/skills/mux/tools/deactivate.py
```

---

# Examples

## Example 1: Full Workflow Start

**Invocation:**
```
/mux-ospec full specs/2026/02/feat/001-feature.md
```

**Correct flow (what SHOULD happen):**
```
MUX MODE | Action: uv run session.py | Target: session init | Rationale: mandatory first action

> Bash("uv run .claude/skills/mux/tools/session.py 'mux-ospec-feature'")

MUX MODE | Action: Bash mkdir | Target: session dirs | Rationale: prepare signal directory

> Bash("mkdir -p {session}/.signals")

MUX MODE | Action: Task (GATHER + monitor) | Target: research | Rationale: full modifier requires GATHER

> Task(opus, bg) - GATHER research orchestrator
> Task(haiku, bg) - Monitor for gather.done signal

Checkpoint:
- Worker launched (opus, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

Workflow Progress:
- GATHER: IN_PROGRESS
- PLAN: PENDING
- IMPLEMENT: PENDING
- REVIEW: PENDING
- TEST: PENDING
- DOCUMENT: PENDING
- SENTINEL: PENDING

Waiting for notifications.
```

**WRONG flow (what the failing session did):**
```
> Read(specs/2026/02/feat/001-feature.md)           <-- VIOLATION: reading spec yourself
> Bash("git branch --show-current")                   <-- VIOLATION: no session init
> Grep("function.*handler", path="src/")              <-- VIOLATION: searching codebase yourself
> Read(src/handler.ts)                                <-- VIOLATION: reading source files
> Skill(skill="spec", args="PLAN ...")                <-- VIOLATION: direct Skill() (must delegate via Task)
55s of churning, massive context consumed, no delegation, no signals, context died before IMPLEMENT.
```

**ALSO WRONG (bloated stage prompt):**
```
> Task(prompt="You are executing PLAN... ABSOLUTE CONSTRAINTS... 40 lines of instructions...")
                                                       <-- VIOLATION: stage prompt contains implementation knowledge
                                                       <-- Stage agent should ONLY invoke /spec PLAN, nothing else
```

## Example 2: PLAN Stage Launch (thin wrapper)

```
(GATHER complete, SC approved)

MUX MODE | Action: Task (PLAN + monitor) | Target: Phase 1 PLAN | Rationale: SC approved

> Task(opus, bg) - prompt: "THINK VERY HARD; TAKE YOUR TIME.
>   Your FIRST and MANDATORY action: Skill(skill='spec', args='PLAN specs/.../001-feature.md')
>   DO NOT read files first. If Skill fails: RETURN STAGE_FAILED.
>   After Skill: verify commit + spec content. Signal + RETURN STAGE_PLAN_COMPLETE"
> Task(haiku, bg) - Monitor

Checkpoint:
- Worker launched (opus, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

Workflow Progress:
- GATHER: COMPLETE
- PLAN: IN_PROGRESS
- IMPLEMENT: PENDING
- REVIEW: PENDING
- TEST: PENDING
- DOCUMENT: PENDING
- SENTINEL: PENDING

Waiting for notifications.
```

## Example 3: Stage Completion + Next Stage

```
(agent notification: PLAN complete - returned "STAGE_PLAN_COMPLETE")

MUX MODE | Action: Task (signal reader) | Target: read PLAN signal | Rationale: get routing data

> Task(haiku/explore) - "Read {session}/.signals/phase-1-plan.done. Return routing data only."

(haiku returns: status=success, commit=a1b2c3d)

STAGE_PLAN_COMPLETE confirmed. Launching IMPLEMENT.

MUX MODE | Action: Task (IMPLEMENT + monitor) | Target: Phase 1 IMPLEMENT | Rationale: PLAN confirmed

> Task(sonnet, bg) - prompt: "THINK VERY HARD; TAKE YOUR TIME.
>   Your FIRST and MANDATORY action: Skill(skill='spec', args='IMPLEMENT specs/.../001-feature.md')
>   DO NOT read spec first. If Skill fails: RETURN STAGE_FAILED.
>   After Skill: verify commit + type check + tests. Signal + RETURN STAGE_IMPLEMENT_COMPLETE"
> Task(haiku, bg) - Monitor

Checkpoint:
- Worker launched (sonnet, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

Workflow Progress:
- GATHER: COMPLETE
- PLAN: COMPLETE (commit: a1b2c3d)
- IMPLEMENT: IN_PROGRESS
- REVIEW: PENDING
- TEST: PENDING
- DOCUMENT: PENDING
- SENTINEL: PENDING

Waiting for notifications.
```

## Example 4: Review Cycle with Fix (refinement loop)

```
(REVIEW cycle 1 - agent returned "STAGE_REVIEW_COMPLETE grade=WARN")

MUX MODE | Action: Task (signal reader) | Target: read REVIEW signal | Rationale: get routing data

> Task(haiku/explore) returns: status=success, grade=WARN

REVIEW grade=WARN. Cycle 1/3. Launching FIX.

MUX MODE | Action: Task (FIX + monitor) | Target: Phase 1 FIX cycle 1 | Rationale: grade=WARN

> Task(sonnet, bg) - prompt: "THINK VERY HARD; TAKE YOUR TIME.
>   Your FIRST and MANDATORY action: Skill(skill='spec', args='FIX specs/.../001-feature.md')
>   ENHANCEMENT: Also read agents/spec-fixer.md for fix protocol.
>   REVIEW REPORT: {session}/reviews/phase-1-review-1.md
>   If Skill fails: RETURN STAGE_FAILED. Signal + RETURN STAGE_FIX_COMPLETE"
> Task(haiku, bg) - Monitor

(FIX returns "STAGE_FIX_COMPLETE")

MUX MODE | Action: Task (signal reader) | Target: read FIX signal | Rationale: confirm fix

> Task(haiku/explore) returns: status=success, commit=b2c3d4e

MUX MODE | Action: Task (REVIEW + monitor) | Target: Phase 1 REVIEW cycle 2 | Rationale: fix confirmed

> NEW Task(opus, bg) - FRESH review agent (Skill(spec, REVIEW))
> Task(haiku, bg) - Monitor

(REVIEW cycle 2 returns "STAGE_REVIEW_COMPLETE grade=PASS")

> Task(haiku/explore) returns: status=success, grade=PASS

Grade=PASS -> proceed to TEST
```

## Example 5: Monitor Timeout + Relaunch

```
(agent notification: monitor timed out)

Monitor timed out, but worker still active (85 tools, 110K tokens). Relaunching.

MUX MODE | Action: Task (monitor relaunch) | Target: IMPLEMENT monitor retry | Rationale: worker still active

> Task(haiku, bg) - new monitor with 10min timeout

Worker deep in implementation. Monitor watching. Waiting.
```

## Example 6: STAGE_FAILED + Relaunch

```
(IMPLEMENT agent returns STAGE_FAILED)

IMPLEMENT STAGE_FAILED - Skill(spec) invocation failed. Error: spec file not found.

MUX MODE | Action: AskUserQuestion | Target: user decision | Rationale: STAGE_FAILED requires escalation

> AskUserQuestion: "IMPLEMENT failed: spec file not found at {path}. Options: 1) Fix path and retry, 2) Abort workflow"

(user provides corrected path)

MUX MODE | Action: Task (IMPLEMENT + monitor) | Target: Phase 1 IMPLEMENT retry | Rationale: user corrected path

> NEW Task(sonnet, bg) - FRESH implement agent (never resume failed one)
> Task(haiku, bg) - Monitor

Checkpoint:
- Worker launched (sonnet, background) - FRESH agent
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately
```

## Example 7: Full Workflow Completion

```
WORKFLOW COMPLETE.

Final Status:
- GATHER: COMPLETE
- PLAN: COMPLETE (commit: a1b2c3d)
- IMPLEMENT: COMPLETE (commit: e4f5g6h)
- REVIEW: COMPLETE (2 cycles, final grade: PASS)
- TEST: COMPLETE (47 passing, +12 new)
- DOCUMENT: COMPLETE (commit: i7j8k9l)
- SENTINEL: COMPLETE (grade: PASS)

Spec: specs/2026/02/feat/001-feature.md
Session: tmp/mux/20260207-1430-feature/
Branch: feat/001-feature

MUX MODE | Action: uv run deactivate.py | Target: cleanup | Rationale: workflow complete

> Bash("uv run .claude/skills/mux/tools/deactivate.py")
```

---

# BEGIN

Parse `$ARGUMENTS` now.

**Your FIRST action MUST be:** `Bash("uv run .claude/skills/mux/tools/session.py 'mux-ospec-{topic}'")`

Do NOT read any files first. Do NOT run git commands. Do NOT analyze anything. Do NOT read the spec. Run session.py FIRST, then follow the EXECUTION LOOP above.
