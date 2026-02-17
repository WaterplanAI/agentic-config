# Anti-Patterns

## Anti-Pattern 1: Context Suicide (FATAL - NO RECOVERY)

**Violation:** Orchestrator calls `Skill(skill="spec", args="PLAN ...")` directly instead of wrapping in `Task()`. This loads the entire spec workflow into the orchestrator's context, consuming massive token budget and killing the orchestrator before subsequent stages complete.

**Why it happens:** The frontmatter includes `Skill` in `allowed-tools`, signaling to the LLM that direct invocation is permitted. The SKILL.md contains Python code blocks showing `Skill()` calls that look like immediate execution instructions. The LLM sees an allowed tool plus an instruction to use it and executes directly.

**Impact:** Orchestrator context dies mid-workflow. PLAN may complete, but IMPLEMENT never launches. Session state corruption. Zero recovery path - must restart from scratch.

**Correct behavior:** ALL spec stage invocations MUST be wrapped in `Task()` delegation. The orchestrator NEVER invokes `Skill(skill="spec")` directly.

**Example:**

WRONG:
```python
# FATAL - loads entire spec workflow into orchestrator context
Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink")
```

RIGHT:
```python
# Correct - delegates to background agent with isolated context
Task(prompt="""Invoke Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink").

CONSTRAINTS:
- Your ONLY action is invoking Skill(spec). Do NOT plan yourself.
- Do NOT read source files before invoking the skill.
- If Skill(spec) fails, return "STAGE_FAILED" - do NOT implement as fallback.

Signal: {session}/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
```

---

## Anti-Pattern 2: Spec File Reading (CRITICAL)

**Violation:** Orchestrator uses `Read(spec_path)` or `Bash("cat spec.md")` to "understand" the spec before delegating to stage agents.

**Why it happens:** The FORBIDDEN section does not explicitly list `Read`, `Write`, `Edit`, `Grep`, `Glob`. The LLM's default helpful behavior is to understand context before acting. Without an explicit prohibition, "quickly checking the spec file to understand requirements" seems reasonable and efficient.

**Impact:** Context pollution (15K+ tokens consumed by spec content). Orchestrator becomes spec-aware and attempts to implement directly instead of delegating. Spec stages never actually run. No commits, no artifacts, no signal files.

**Correct behavior:** Orchestrator NEVER reads spec files, source files, or any content files. The orchestrator's job is delegation routing, not content processing. All file reading happens within delegated agents.

**Example:**

WRONG:
```python
# WRONG - reads spec directly, pollutes context
spec_content = Read("/path/to/spec.md")
# Orchestrator now "understands" requirements and attempts to implement
Task(prompt=f"Implement this: {spec_content}")  # Context death imminent
```

RIGHT:
```python
# CORRECT - passes spec path to agent, agent reads in isolation
Task(prompt="""Invoke Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink").
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
```

---

## Anti-Pattern 3: Session Skip (CRITICAL)

**Violation:** Orchestrator jumps directly to stage delegation without calling `session.py` first. Enforcement hooks never activate, allowing forbidden tool usage.

**Why it happens:** The current SKILL.md buries session init in a numbered list under "IMMEDIATE ACTION REQUIRED". The urgency framing ("IMMEDIATELY invoke tools") encourages the LLM to skip setup steps and jump to the "real work" (stage delegation).

**Impact:** No session directory created. No observability marker (`mux-active`). Session tracking unavailable. While skill-scoped hooks still enforce tool restrictions (they activate on skill load, not marker presence), the session directory structure required for file-based communication is missing.

**Correct behavior:** Session initialization MUST be the absolute first action. No exceptions. All subsequent tool calls depend on session existence and hook activation.

**Example:**

WRONG:
```python
# WRONG - skips session init, jumps to stage
Task(prompt="Invoke Skill(skill='spec', args='PLAN ...')", ...)  # No session, no enforcement
```

RIGHT:
```python
# CORRECT - session init first, then stages
# Step 1: MANDATORY FIRST ACTION
Bash("uv run .claude/skills/mux/tools/session.py 'mux-ospec-feature-auth'")
# Output: Session created at tmp/swarm/20260206-1430-mux-ospec-feature-auth
# Enforcement marker created, hooks now active

# Step 2: Launch stage (now protected by hooks)
Task(prompt="""Invoke Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink").
Signal: tmp/swarm/20260206-1430-mux-ospec-feature-auth/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
```

---

## Anti-Pattern 5: Helpful Implementation (FATAL)

**Violation:** When a delegated stage agent returns "done" but artifacts are missing (no commit, empty spec, no signal), the orchestrator "helps" by implementing the stage logic directly instead of re-delegating or failing.

**Why it happens:** LLMs have a strong default to be helpful. When an agent returns "done" but verification shows missing artifacts, the orchestrator's instinct is to fix it rather than report failure. mux-ospec stage prompts lack anti-bypass language that prohibits this fallback behavior.

**Impact:** Orchestrator context consumed by implementation details. Direct file editing, test running, build execution - all violations of delegation protocol. Session state corruption. Orchestrator dies before completing workflow.

**Correct behavior:** If a stage agent fails or produces incomplete artifacts, the orchestrator MUST either re-delegate to a new agent OR return "STAGE_FAILED" and halt. The orchestrator NEVER implements stage logic itself, even as fallback.

**Example:**

WRONG:
```python
# Agent returns "done" but git log shows no PLAN commit
# WRONG - orchestrator "helps" by planning directly
plan_content = Read("/path/to/spec.md")  # Context pollution
Write("/path/to/spec.md", ai_section_content)  # Direct execution
Bash("git add spec.md && git commit -m 'spec(001): PLAN ...'")  # Protocol violation
```

RIGHT:
```python
# Agent returns "done" but git log shows no PLAN commit
# CORRECT - orchestrator detects failure and re-delegates or halts
Bash("git log --oneline -1")  # Output: Previous commit, not PLAN commit
# Verification failed

# Option A: Re-delegate to new agent
Task(prompt="""RECOVERY: Previous PLAN agent returned 'done' but produced no commit.
Invoke Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink").
Verify commit exists before returning done.
FINAL: Return EXACTLY: done or STAGE_FAILED""", model="opus", run_in_background=True)

# Option B: Halt and report
AskUserQuestion(question="PLAN stage failed silently (no commit). Re-attempt or abort?")
```

---

## Anti-Pattern 6: Variable Substitution (CRITICAL)

**Violation:** Orchestrator sends a Task prompt with unresolved template variables (`{spec_path}`, `{session}`, `{N}`, `{cycle}`). Sub-agent receives malformed instructions like "Invoke Skill(skill='spec', args='PLAN {spec_path} ultrathink')" and fails silently because it has no value for `{spec_path}`.

**Why it happens:** SKILL.md contains Python code blocks with f-string-style variables in template examples. The LLM treats these as templates but may fail to substitute variables correctly, especially for computed values like `{N}` (phase number) and `{cycle}` (review cycle number) which have no clear source.

**Impact:** Sub-agents receive malformed prompts. They either fail with errors (best case) or hallucinate values (worst case - may read wrong files or create wrong signals). Silent cascade failures across all stages.

**Correct behavior:** ALL template variables MUST be resolved before Task() invocation. Use actual f-strings in Python or explicit variable substitution. Verify prompt content before delegation.

**Example:**

WRONG:
```python
# WRONG - unresolved template variables sent to agent
Task(prompt="""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").
Signal: {session}/.signals/phase-{N}-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
# Agent receives literal string "{spec_path}", has no value to substitute
```

RIGHT:
```python
# CORRECT - all variables resolved before Task() invocation
spec_path = "/Users/jane/projects/myapp/specs/2026/02/feature-auth/001-implement-jwt.md"
session = "tmp/swarm/20260206-1430-mux-ospec-feature-auth"
phase_num = 1

Task(prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").
Signal: {session}/.signals/phase-{phase_num}-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)
# Agent receives fully resolved prompt with actual paths
```

---

## Anti-Pattern 7: Code Block Execution (CRITICAL)

**Violation:** Orchestrator sees multiple Python code blocks in SKILL.md labeled "EXECUTE THIS TOOL CALL" and executes ALL of them immediately in sequence, regardless of workflow phase or stage dependencies.

**Why it happens:** SKILL.md headers say "EXECUTE THIS TOOL CALL" above every stage template. The LLM reads all sections and sees multiple "EXECUTE" instructions. Without clear sequential gating ("execute ONLY when previous stage signal exists"), the LLM interprets this as "execute all blocks now".

**Impact:** All stages launch simultaneously. IMPLEMENT agent starts before PLAN completes. TEST runs before implementation. DOCUMENT writes before tests pass. Resource exhaustion, race conditions, missing dependencies, cascading failures.

**Correct behavior:** Stage templates are CONDITIONAL. Orchestrator launches ONE stage at a time, waits for signal file verification, then launches next stage. Templates are execution instructions ONLY when their preconditions are met.

**Example:**

WRONG:
```python
# WRONG - launches all stages at once
Task(prompt="PLAN...", model="opus", run_in_background=True)  # Phase 1 PLAN
Task(prompt="IMPLEMENT...", model="sonnet", run_in_background=True)  # Phase 1 IMPLEMENT (no PLAN artifact!)
Task(prompt="REVIEW...", model="opus", run_in_background=True)  # Phase 1 REVIEW (no IMPLEMENT artifact!)
Task(prompt="TEST...", model="sonnet", run_in_background=True)  # TEST (no implementation!)
Task(prompt="DOCUMENT...", model="sonnet", run_in_background=True)  # DOCUMENT (nothing to document!)
# All 5 agents running in parallel with unmet dependencies
```

RIGHT:
```python
# CORRECT - sequential phased execution with signal verification
# Phase 1: PLAN
Task(prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").
Signal: {session}/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# Wait for task-notification from runtime
# Then verify signal: phase-1-plan.done exists
# Verify artifact: git log shows PLAN commit

# Phase 1: IMPLEMENT (only after PLAN signal verified)
Task(prompt=f"""Invoke Skill(skill="spec", args="IMPLEMENT {spec_path} ultrathink").
Signal: {session}/.signals/phase-1-implement.done
FINAL: Return EXACTLY: done""", model="sonnet", run_in_background=True)

# ... continue sequentially
```

---

## Anti-Pattern 8: TaskOutput Blocking (CRITICAL)

**Violation:** Orchestrator uses `TaskOutput(task_id=..., block=True)` to wait for agent completion instead of signal-based monitoring. This blocks the orchestrator context, consuming tokens while waiting.

**Why it happens:** `TaskOutput()` appears to be a clean way to retrieve agent results. Without explicit prohibition in FORBIDDEN section, the LLM may use it as a synchronous coordination mechanism.

**Impact:** Orchestrator context blocked during agent execution. Token budget consumed by waiting. Defeats background execution architecture. If agent is long-running (30+ seconds), orchestrator may timeout or context-die while blocked.

**Correct behavior:** NEVER use `TaskOutput()`. ALL agent coordination happens via signal files. Orchestrator launches agents with `run_in_background=True` and continues immediately. Runtime task-notification signals completion. Orchestrator runs verify.py as safety check.

**Example:**

WRONG:
```python
# WRONG - blocks orchestrator until PLAN agent completes
plan_task_id = Task(prompt="PLAN...", model="opus", run_in_background=True)
plan_result = TaskOutput(task_id=plan_task_id, block=True)  # BLOCKING - context frozen
# Orchestrator context consumed for entire PLAN duration (30-60 seconds)
# Token budget wasted on waiting
```

RIGHT:
```python
# CORRECT - fire-and-forget with signal-based verification
Task(prompt=f"""Invoke Skill(skill="spec", args="PLAN {spec_path} ultrathink").
Signal: {session}/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# Orchestrator continues immediately (context preserved)
# Runtime delivers task-notification when worker completes
# Safety check:
# Bash(f"uv run .claude/skills/mux/tools/verify.py {session}/.signals --action summary")
```

---

## Anti-Pattern 9: Absolute Path Misresolution (CRITICAL)

**Violation:** Signal reader agent interprets `tmp/mux/20260209-1430-topic/.signals/phase-1-plan.done` as `/tmp/mux/20260209-1430-topic/.signals/phase-1-plan.done` (absolute path under system `/tmp/`). The signal file is not found, and the orchestrator falls back to trusting the task-notification return value directly instead of verifying via the signal file.

**Why it happens:** `session.py` returns `SESSION_DIR=tmp/mux/...` (relative path). When the signal reader agent (haiku/explore) receives a prompt like "Read the signal file at tmp/mux/.../phase-1-plan.done", low-tier models "correct" the path by prepending `/` because `/tmp/` is a well-known system directory. The prompt contains no guidance about path interpretation.

**Impact:** Signal file not found at `/tmp/mux/...`. Signal reader returns error or empty data. Orchestrator falls back to trusting the agent's return value ("STAGE_PLAN_COMPLETE") without signal verification. This defeats the entire signal-based verification architecture. Failures go undetected.

**Correct behavior:** All signal reader prompts MUST include explicit guidance that paths are RELATIVE to project root. The `tmp/` prefix is a project-local directory, NOT `/tmp/`.

**Example:**

WRONG:
```python
# WRONG - no path guidance, haiku interprets tmp/ as /tmp/
Task(
    prompt=f"""Read the signal file at {signal_path}.
Return ONLY this structured routing data...""",
    subagent_type="Explore",
    model="haiku",
    run_in_background=True
)
# Agent reads /tmp/mux/20260209-1430-topic/.signals/phase-1-plan.done -> FILE NOT FOUND
```

RIGHT:
```python
# CORRECT - explicit path guidance prevents misresolution
Task(
    prompt=f"""Read the signal file at {signal_path}.

IMPORTANT: This path is RELATIVE to the project root. Use it exactly as given.
Do NOT prepend '/' or convert to an absolute path. 'tmp/' is a project-local directory, NOT '/tmp/'.

Return ONLY this structured routing data...""",
    subagent_type="Explore",
    model="haiku",
    run_in_background=True
)
# Agent reads tmp/mux/20260209-1430-topic/.signals/phase-1-plan.done -> FOUND
```

---

## Anti-Pattern 10: Same-File Parallel Implementation (FATAL)

**Violation:** Orchestrator decomposes IMPLEMENT into parallel waves (P0/P1) and launches multiple agents that edit the SAME source file simultaneously. Example: 2 agents adding subcommands to `drive.py` + 2 agents adding subcommands to `docs.py`, all in the same wave.

**Why it happens:** The orchestrator correctly identifies independent logical units (reply, resolve, edit, find) and optimizes for throughput by parallelizing them. It may even detect the file overlap ("Conflict risk: 2 agents editing drive.py") but lacks a hard rule to stop, so it proceeds with a plan to "merge/reconcile after."

**Impact:** Both agents read the same file state, make independent edits, and the second write clobbers the first. Work is lost. No merge strategy exists — agents write entire files, not patches. The orchestrator must re-run lost work, wasting time and tokens.

**Correct behavior:** Before launching ANY parallel batch of implementation agents, identify the target files each agent will EDIT. If ANY file appears in more than one agent's scope, those agents MUST be serialized into separate sequential waves. Only agents with ZERO file overlap may run in the same wave.

**Example:**

WRONG:
```python
# P0: 4 agents, 2 pairs editing same files
Task(prompt="Add reply subcommand to drive.py ...", run_in_background=True)
Task(prompt="Add resolve subcommand to drive.py ...", run_in_background=True)  # CLOBBER
Task(prompt="Add edit subcommand to docs.py ...", run_in_background=True)
Task(prompt="Add find subcommand to docs.py ...", run_in_background=True)     # CLOBBER
# Orchestrator notes "will need merge/reconciliation" -- TOO LATE
```

RIGHT:
```python
# Wave 1: one agent per file (zero overlap)
Task(prompt="Add reply subcommand to drive.py ...", run_in_background=True)
Task(prompt="Add edit subcommand to docs.py ...", run_in_background=True)
# Wait for wave 1 completion

# Wave 2: remaining work on same files (builds on wave 1 output)
Task(prompt="Add resolve subcommand to drive.py ...", run_in_background=True)
Task(prompt="Add find subcommand to docs.py ...", run_in_background=True)
```

---

## Anti-Pattern 11: SC Gate Skip in Full Mode (CRITICAL)

**Violation:** In `full` mode, orchestrator jumps from GATHER directly to PLAN, skipping both CONSOLIDATE and CONFIRM SC stages. User has to manually intervene to prevent unreviewed work.

**Why it happens:** The Checkpoint Pattern (Workflow Progress tracker) did not list CONSOLIDATE or CONFIRM_SC as tracked stages. The orchestrator printed `GATHER: COMPLETE` followed by `PLAN: PENDING`, and the visual absence of intermediate stages caused the LLM to route directly from GATHER to PLAN. The execution loop pseudocode had the correct sequence, but the templates (which the LLM references more frequently) reinforced the wrong pattern.

**Impact:** Success criteria never reviewed by user. PLAN proceeds on potentially wrong assumptions. User alignment lost. Work may need to be redone after user reviews SC post-implementation.

**Correct behavior:** After GATHER completes in `full` mode:
1. Launch CONSOLIDATE agent (synthesize research)
2. After CONSOLIDATE signal: extract SC and present to user via AskUserQuestion
3. After user APPROVES SC: proceed to PLAN
4. All three steps are MANDATORY and tracked in Workflow Progress

**Example:**

WRONG:
```
GATHER: COMPLETE
(orchestrator routes directly to PLAN)
PLAN: IN_PROGRESS
```

RIGHT:
```
GATHER: COMPLETE
CONSOLIDATE: IN_PROGRESS
(wait for consolidate signal)
CONSOLIDATE: COMPLETE
CONFIRM SC: IN_PROGRESS
(present SC to user, wait for approval)
CONFIRM SC: APPROVED
PLAN: IN_PROGRESS
```

---

## Consequence

Context pollution leads to session death. When context is full, your session dies mid-workflow.

**RULE: If you can describe the work, you can delegate it. NO EXCEPTIONS.**

Orchestration = routing and verification, NOT execution.
