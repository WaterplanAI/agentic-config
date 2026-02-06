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

### 1. Orchestrator Must Not Read Source Files

**What failed:** Orchestrator read spec file directly, consumed 15K tokens, then attempted to implement without delegating. Spec file remained empty. No PLAN commit.

**Rule:** Session init activates hooks. Hooks block direct file access. Delegate ALL reading via Task().

### 2. Stage Agents Must Actually Invoke Skill(spec)

**What failed:** PLAN agent received spec path and wrote its own plan without invoking Skill(skill="spec"). Spec file empty. No commit.

**Rule:** Stage prompts include anti-bypass CONSTRAINTS. Verify artifacts after stage return.

### 3. "done" Return Without Artifacts

**What failed:** Agent returned "done" without producing commits, signals, or output files. Git log unchanged.

**Rule:** Verify artifacts exist after every stage return. Missing signal = STAGE_FAILED.

### 4. Direct Skill() Invocation Killed Orchestrator

**What failed:** Orchestrator called Skill(skill="spec", args="PLAN ...") directly. Entire spec workflow loaded into orchestrator context. Context died before IMPLEMENT.

**Rule:** NEVER invoke Skill() directly. Always delegate: Task(prompt="Invoke Skill(...)").

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
