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

**Impact:** No session directory created. No enforcement marker (`mux-active`). Hooks do NOT block forbidden tools. Orchestrator can Read/Write/Edit files directly without denial. Silent compliance failure - no error, just wrong behavior.

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

## Anti-Pattern 4: Monitor Omission (CRITICAL)

**Violation:** Orchestrator launches a `Task()` for a stage worker but does not launch a companion monitor agent in the same message. Orchestrator then either polls for completion (blocked) or proceeds without verification (silent failure).

**Why it happens:** mux-ospec SKILL.md has zero mention of monitors at the top-level skill definition. Monitors are documented only in cookbooks, which the LLM may not read. Without explicit mandate, the LLM treats monitoring as optional.

**Impact:** Orchestrator either blocks (polling for agent completion) or proceeds blindly (no verification that stage succeeded). Blocking wastes context budget. Proceeding blindly causes cascading failures when downstream stages depend on missing artifacts.

**Correct behavior:** EVERY worker launch MUST be paired with a monitor in the SAME message. The monitor is a low-tier (haiku) background agent that polls for signal files and reports completion. Missing monitor = PROTOCOL VIOLATION.

**Example:**

WRONG:
```python
# WRONG - launches worker without monitor
Task(prompt="Invoke Skill(skill='spec', args='PLAN ...')",
     model="opus", run_in_background=True)
# Orchestrator now has no way to know when PLAN completes except polling (FORBIDDEN)
```

RIGHT:
```python
# CORRECT - worker + monitor in same message
# Worker
Task(prompt="""Invoke Skill(skill="spec", args="PLAN /path/to/spec.md ultrathink").
Signal: {session}/.signals/phase-1-plan.done
FINAL: Return EXACTLY: done""", model="opus", run_in_background=True)

# Monitor (SAME message, low-tier model)
Task(prompt=f"""Read agents/monitor.md. EXPECTED: 1. Use poll-signals.py to monitor {session}/.signals/phase-1-plan.done.
Report completion via signal: {session}/.signals/monitor-plan.done""",
     model="haiku", run_in_background=True)

# Checkpoint
# Stage worker launched (opus, background)
# Monitor launched (haiku, background)
# Continuing immediately to next stage
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
spec_path = "/Users/matias/projects/myapp/specs/2026/02/feature-auth/001-implement-jwt.md"
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

Task(prompt=f"""Monitor {session}/.signals/phase-1-plan.done completion.
FINAL: Return EXACTLY: done""", model="haiku", run_in_background=True)

# Wait for signal: phase-1-plan.done exists
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

**Correct behavior:** NEVER use `TaskOutput()`. ALL agent coordination happens via signal files. Orchestrator launches agents with `run_in_background=True` and continues immediately. Monitor agents watch for signal files and report completion.

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

Task(prompt=f"""Monitor {session}/.signals/phase-1-plan.done.
Use poll-signals.py. FINAL: Return EXACTLY: done""", model="haiku", run_in_background=True)

# Orchestrator continues immediately (context preserved)
# Verification happens later via signal files
# Check completion:
Bash(f"uv run .claude/skills/mux/tools/poll-signals.py {session}/.signals --expected phase-1-plan.done")
```

---

## Consequence

Context pollution leads to session death. When context is full, your session dies mid-workflow.

**RULE: If you can describe the work, you can delegate it. NO EXCEPTIONS.**

Orchestration = routing and verification, NOT execution.
