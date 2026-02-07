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

### GATHER (full only)

Delegate MUX research for spec context:

```python
# LAUNCH AGENT: GATHER research
Task(prompt="""You are a MUX research orchestrator.
TASK: Research for {spec_context}.
SUBJECTS: [Web research, Codebase audit, Pattern analysis]
CONSOLIDATE TO: {session}/research/consolidated.md

CONSTRAINTS:
- Your ONLY action is orchestrating research via Task() delegation.
- Do NOT read source files yourself.
- Do NOT write the consolidated output yourself - delegate to agents.
- If research fails, return "STAGE_FAILED" - do NOT fabricate results.

Signal: {session}/.signals/gather.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
```

### CONFIRM SC (full only)

```python
AskUserQuestion(question="Review SUCCESS_CRITERIA at {session}/research/consolidated.md. Approve?")
```

### PHASE_LOOP (PLAN -> IMPLEMENT -> REVIEW -> FIX)

For each phase N, delegate these stages:

```python
# PLAN
# Execute ONLY as first stage of phase N
Task(prompt="""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT plan yourself.
- Do NOT read source files before invoking the skill.
- Do NOT write to the spec file directly.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT implement as fallback.

Signal: {session}/.signals/phase-{N}-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# IMPLEMENT
# Execute ONLY when phase-{N}-plan.done signal exists
Task(prompt="""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} ultrathink").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT implement yourself.
- Do NOT read the spec to "understand" it before invoking the skill.
- Do NOT edit source files directly.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT code as fallback.

Signal: {session}/.signals/phase-{N}-implement.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)

# REVIEW (per cycle)
# Execute ONLY when phase-{N}-implement.done signal exists
Task(prompt="""Read agents/spec-reviewer.md. SPEC: {spec_path}, PHASE: {N}, CYCLE: {cycle}
Grade: PASS|WARN|FAIL.

CONSTRAINTS:
- Your ONLY action is following agents/spec-reviewer.md instructions.
- Do NOT invent your own review criteria.
- Do NOT fix issues yourself - only report them.
- If review cannot proceed, return "STAGE_FAILED" - do NOT skip review.

Signal: {session}/.signals/phase-{N}-review-{cycle}.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# FIX (if WARN/FAIL)
# Execute ONLY when review grade is WARN or FAIL
Task(prompt="""Read agents/spec-fixer.md. REVIEW: {session}/reviews/phase-{N}-review-{cycle}.md

CONSTRAINTS:
- Your ONLY action is following agents/spec-fixer.md instructions.
- Do NOT invent fixes outside the review findings.
- Do NOT skip the spec-fixer agent and fix directly.
- If fix fails, return "STAGE_FAILED" - do NOT ignore the review.

Signal: {session}/.signals/phase-{N}-fix-{cycle}.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)
```

### TEST

```python
# Execute ONLY when PHASE_LOOP is complete
Task(prompt="""Read agents/spec-tester.md. SPEC: {spec_path}, SESSION: {session}
Detect framework via detect-repo-type.py.

CONSTRAINTS:
- Your ONLY action is following agents/spec-tester.md instructions.
- Do NOT write tests yourself outside the agent protocol.
- Do NOT skip test execution.
- If testing fails, return "STAGE_FAILED" - do NOT mark as passed.

Signal: {session}/.signals/test.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)
```

### DOCUMENT (full/lean)

```python
# Execute ONLY when test.done signal exists
Task(prompt="""Invoke Skill(skill="spec", args="DOCUMENT {spec_path}").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT write docs yourself.
- Do NOT read source files to "summarize" them.
- Do NOT create documentation outside the skill.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT write docs as fallback.

Signal: {session}/.signals/document.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)
```

### SENTINEL (full) / SELF-VALIDATION (lean/leanest)

```python
# Execute ONLY as final stage
Task(prompt="""Read agents/sentinel.md. SESSION: {session}. Verify all SC items PASS.

CONSTRAINTS:
- Your ONLY action is following agents/sentinel.md instructions.
- Do NOT validate by reading files yourself.
- Do NOT approve incomplete work.
- If validation fails, return "STAGE_FAILED" - do NOT override the sentinel.

Signal: {session}/.signals/sentinel.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
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

### 2. Stage Agents Must Actually Invoke Skill(spec)

**What failed:** PLAN agent received spec path and wrote its own plan without invoking Skill(skill="spec"). Spec file empty. No commit.

**Rule:** Stage prompts include anti-bypass CONSTRAINTS. Verify artifacts after stage return.

### 3. "done" Return Without Artifacts

**What failed:** Agent returned "done" without producing commits, signals, or output files. Git log unchanged.

**Rule:** Verify artifacts exist after every stage return. Missing signal = STAGE_FAILED.

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
    When gather.done signal arrives -> proceed

  CONFIRM SC:
    MUX MODE | Action: AskUserQuestion | Target: SC approval | Rationale: gate before implementation
    Wait for user confirmation

PHASE_LOOP (for each phase N):
  PLAN:
    MUX MODE | Action: Task (PLAN + monitor) | Target: Phase {N} PLAN | Rationale: next stage
    Launch PLAN agent (opus, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When phase-{N}-plan.done arrives:
      IF signal missing -> STAGE_FAILED, launch NEW agent
      IF present -> proceed to IMPLEMENT

  IMPLEMENT:
    MUX MODE | Action: Task (IMPLEMENT + monitor) | Target: Phase {N} IMPLEMENT | Rationale: plan done
    Launch IMPLEMENT agent (sonnet, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When phase-{N}-implement.done arrives -> proceed to REVIEW

  REVIEW (cycle loop):
    MUX MODE | Action: Task (REVIEW + monitor) | Target: Phase {N} REVIEW cycle {C} | Rationale: impl done
    Launch REVIEW agent (opus, bg) + monitor (haiku, bg) in SAME message
    Print checkpoint
    Continue immediately
    When phase-{N}-review-{C}.done arrives:
      IF PASS -> proceed to TEST (or next phase)
      IF WARN/FAIL + cycle < max:
        Launch FIX agent (sonnet, bg) + monitor in SAME message
        When fix done -> launch NEW REVIEW agent (fresh context)
      IF WARN/FAIL + cycle >= max -> proceed with warning

TEST:
  MUX MODE | Action: Task (TEST + monitor) | Target: test execution | Rationale: review passed
  Launch TEST agent (sonnet, bg) + monitor (haiku, bg) in SAME message
  Print checkpoint
  Continue immediately
  When test.done arrives:
    IF PASS -> proceed
    IF FAIL -> STAGE_FAILED, escalate

IF modifier != "leanest":
  DOCUMENT:
    MUX MODE | Action: Task (DOCUMENT + monitor) | Target: documentation | Rationale: tests passed
    Launch DOCUMENT agent (sonnet, bg) + monitor (haiku, bg) in SAME message

SENTINEL (full) / SELF-VALIDATION (lean/leanest):
  MUX MODE | Action: Task (SENTINEL + monitor) | Target: final validation | Rationale: all stages done
  Launch SENTINEL agent (opus, bg) + monitor (haiku, bg) in SAME message
  When sentinel.done arrives -> WORKFLOW COMPLETE

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
> Skill(skill="spec", args="PLAN ...")                <-- VIOLATION: direct Skill() invocation
55s of churning, massive context consumed, no delegation, no signals, context died before IMPLEMENT.
```

## Example 2: PLAN Stage Launch

```
(GATHER complete, SC confirmed)

MUX MODE | Action: Task (PLAN + monitor) | Target: Phase 1 PLAN | Rationale: GATHER done, SC approved

> Task(opus, bg) - PLAN agent with Skill(spec) delegation
> Task(haiku, bg) - Monitor for phase-1-plan.done

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
(agent notification: PLAN complete)

STAGE_PLAN_COMPLETE - Spec file populated with implementation plan.

Stage Results:
- Signal: {session}/.signals/phase-1-plan.done
- Commits: a1b2c3d
- Duration: ~4min
- Key output: 3 HLOs, 8 MLOs, TDD approach

MUX MODE | Action: Task (IMPLEMENT + monitor) | Target: Phase 1 IMPLEMENT | Rationale: PLAN done

> Task(sonnet, bg) - IMPLEMENT agent with Skill(spec) delegation
> Task(haiku, bg) - Monitor for phase-1-implement.done

Checkpoint:
- Worker launched (sonnet, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

Workflow Progress:
- GATHER: COMPLETE
- PLAN: COMPLETE
- IMPLEMENT: IN_PROGRESS
- REVIEW: PENDING
- TEST: PENDING
- DOCUMENT: PENDING
- SENTINEL: PENDING

Waiting for notifications.
```

## Example 4: Review Cycle with Fix

```
(REVIEW cycle 1 returns WARN)

REVIEW cycle 1 grade: WARN

Review Results:
- Compliance: WARN (2 minor gaps - edge case handling, error messages)
- Quality: PASS (0 issues)
- Action: FIX + re-review (cycle 1/3)

MUX MODE | Action: Task (FIX + monitor) | Target: Phase 1 FIX cycle 1 | Rationale: review WARN

> Task(sonnet, bg) - FIX agent with spec-fixer.md
> Task(haiku, bg) - Monitor for phase-1-fix-1.done

Checkpoint:
- Worker launched (sonnet, background)
- Monitor in same message (haiku, 10min timeout)
- Continuing immediately

(fix completes)

MUX MODE | Action: Task (REVIEW + monitor) | Target: Phase 1 REVIEW cycle 2 | Rationale: fix applied

> NEW Task(opus, bg) - FRESH review agent (never resume old one)
> Task(haiku, bg) - Monitor

(REVIEW cycle 2 returns PASS -> proceed to TEST)
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
