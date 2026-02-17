# Anti-Patterns

## Context Suicide (FATAL - NO RECOVERY)

- **Calling `Skill()` directly from orchestrator** - executes IN your context
- Running `npx`, `npm`, `cdk`, `cargo`, `go`, `make` commands directly
- Running `git status`, `git diff`, `git log` for inspection
- Running any build/test/lint command directly
- Running `grep`, `cat`, `head`, `tail` for content inspection
- Rationalizing "just this once" or "quick check"
- Claiming "it's faster if I do it"

## Skill Invocation Violations (CONTEXT DEATH)

- `Skill(skill="spec", ...)` from orchestrator - FATAL
- `Skill(skill="commit")` from orchestrator - FATAL
- ANY direct Skill() call from orchestrator - FATAL
- Vague Task() prompts like "run /spec" without explicit `Skill()` invocation

## Tool Violations (STRICTLY BLOCKED)

- NEVER use Read/Write/Edit yourself
- NEVER read worker output files (context pollution)
- NEVER write reports yourself (delegate to writer)
- NEVER edit deliverables (delegate to writer)
- NEVER use bash polling loops (wait for task-notification, then verify.py)

## Bash Violations (RUTHLESS ENFORCEMENT)

- NEVER run grep/find/cat yourself
- NEVER do "quick verification"
- NEVER inspect file content via bash
- NEVER rationalize exceptions
- NEVER run npx/npm/cdk/cargo/go directly

## Communication Violations

- NEVER accept inline content from agents (only "0")
- NEVER pass file content in prompts (pass paths)

## Blocking Violations (CRITICAL)

- NEVER use `TaskOutput()` - signals are the ONLY completion mechanism
- NEVER use `run_in_background=False` - ALWAYS `True`
- NEVER block on ANY agent
- NEVER wait for workers before proceeding
- NEVER use bash loops to wait
- NEVER poll .signals/ in a loop (use one-shot check-signals.py as fallback)

### TaskOutput is FORBIDDEN

`TaskOutput()` blocks until the agent completes. This defeats the entire architecture:

```python
# FATAL VIOLATION - blocks context, wastes tokens
result = TaskOutput(task_id=worker_id, block=True)  # NEVER DO THIS

# CORRECT - continue immediately, verify after task-notification
Task(..., run_in_background=True)  # Launch
# Continue to next phase immediately
# After receiving task-notifications:
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action summary  # One-shot check
```

Orchestrator should NEVER block. Wait for runtime task-notifications, then run verify.py once.

## Delegation Violations

- NEVER execute leaf tasks yourself
- NEVER skip sentinel review
- NEVER skip voice updates
- NEVER implement agent behavior inline
- NEVER run domain commands when skill exists
- NEVER drop explicit skill references from user's task

### Dropped Skill Reference (CRITICAL - USER TOOLING LOST)

When the user explicitly names ANY skill (e.g., "Use /my-skill", "run /browser"), the orchestrator MUST forward that as a mandatory `Skill()` invocation in the subagent prompt. Dropping it forces the subagent to improvise without the user's specialized tooling.

```python
# User said: "Use /my-skill run-test with key: abc123"

# FATAL VIOLATION - generic description, skill reference dropped
Task(prompt="Reproduce the error via local test using key abc123 ...", ...)
# Subagent has NO IDEA about /my-skill, improvises badly

# CORRECT - explicit skill forwarding
Task(prompt="""MANDATORY: Invoke Skill(skill="my-skill", args="run-test key: abc123").
This skill invocation is NON-NEGOTIABLE. The user explicitly requested it.
DO NOT attempt the task without this skill.
...""", ...)
```

## Session Management Violations

- NEVER delete session directories
- NEVER run `rm -rf tmp/swarm/*`

## Phase Execution Violations

- NEVER launch all phases simultaneously
- NEVER skip interactive gates at decision points
- NEVER proceed after sentinel failure without user input
- NEVER consolidate without checking threshold first
- NEVER launch parallel agents that EDIT the same source file

### All-At-Once Launch (CRITICAL BUG)

```python
# FATAL VIOLATION - launches all phases together
Task(prompt="Research...", run_in_background=True)
Task(prompt="Audit...", run_in_background=True)
Task(prompt="Consolidate...", run_in_background=True)
Task(prompt="Write...", run_in_background=True)

# CORRECT - phased execution with announcements
# Phase 1: Research
Task(prompt="Research...", run_in_background=True)
voice("Research phase launched")

# Phase 2: Audit (after research task-notifications received)
Task(prompt="Audit...", run_in_background=True)
voice("Audit phase launched")
# ... etc
```

### Same-File Parallel Implementation (FATAL - WRITE CONFLICT)

```python
# FATAL VIOLATION - 2 agents editing drive.py simultaneously
Task(prompt="Add reply to drive.py", run_in_background=True)
Task(prompt="Add resolve to drive.py", run_in_background=True)  # CLOBBER

# CORRECT - sequential waves, one agent per file per wave
Task(prompt="Add reply to drive.py", run_in_background=True)
# After completion:
Task(prompt="Add resolve to drive.py", run_in_background=True)
```

- Launching parallel agents that EDIT the same source file
- Detecting file overlap ("conflict risk") but proceeding anyway
- Planning "merge/reconciliation after" instead of preventing conflict
- Rationalizing "they edit different functions in the same file"

**HARD RULE:** Before ANY parallel launch, check target file overlap. If ANY file appears in >1 agent scope, SERIALIZE into separate waves.

## Consequence

Context pollution leads to session death. When context is full, your session dies.

**RULE: If you can describe the command, you can delegate it. NO EXCEPTIONS.**

## Hook-Enforced Violations (HARD-BLOCKED)

These violations are blocked by skill-scoped hooks and cannot be bypassed:

- Orchestrator using Read to access report files (BLOCKED by mux-orchestrator-guard.py)
- Orchestrator using Grep/Glob to search output directories (BLOCKED by hook)
- Orchestrator running non-whitelisted Bash commands (BLOCKED by hook)
- Orchestrator loading other skills via Skill() during MUX (BLOCKED by hook -- context suicide)
- Subagent using TaskOutput (BLOCKED by mux-subagent-guard.py)
- Subagent loading additional skills after mux-subagent (BLOCKED by hook)

## Return Protocol Violations (CRITICAL)

Old protocol used "done" (4 chars). New protocol uses "0" (1 char).

- "done" = VIOLATION (old protocol, replaced by "0")
- Any text with "0" embedded = VIOLATION (e.g., "Status: 0")
- Summary + "0" = VIOLATION (e.g., "Research complete.\n\n0")
- "0" + explanation = VIOLATION (e.g., "0\nWrote file to...")
- Return > 1 character = VIOLATION

## Subagent Protocol Violations

- Subagent returning verbose text instead of `0` (context pollution)
- Subagent skipping signal file creation (orchestrator detects via verify.py, work re-launched)
- Subagent skipping mux-subagent skill loading (loses hook enforcement + protocol knowledge)

---

## Plan Mode Bypass -- Rationalizing Direct Research

**Severity:** CRITICAL (undetectable by hooks)

**Scenario:**
1. User invokes MUX skill (e.g., `/mux-ospec`)
2. Plan mode is active in Claude Code session
3. Plan mode blocks Bash (non-readonly) -- session.py cannot run
4. Orchestrator thinks: "I can't run session.py, but I CAN read files to prepare"
5. Orchestrator reads 15+ files directly, launches Plan agents, burns entire context window
6. User eventually notices: "WHY ARE YOU NOT FOLLOWING THE MUX PROTOCOL?"

**Why it's undetectable:**
- Hooks block tool calls, but plan mode operates ABOVE the tool invocation layer
- When plan mode is active, the hook may not fire for certain tools or the orchestrator may use read-only tools that are allowed in plan mode
- The rationalization chain feels logical: "I need context to ask good refinement questions"

**The rationalization chain:**
```
Plan mode blocks Bash
-> "I can't run session.py yet"
-> "But I CAN read files (readonly)"
-> "I need to understand the codebase for refinement questions"
-> "This is actually helpful preparation"
-> [Reads 15 files, launches Plan agent, burns 100k+ tokens]
-> Protocol completely violated
```

**Correct behavior:**
1. Detect plan mode is active
2. STOP immediately
3. Tell user: "MUX requires Bash. Plan mode blocks Bash. Please exit plan mode."
4. Take ZERO actions until plan mode is exited
5. Once exited: run session.py as MANDATORY FIRST ACTION

**Key insight:** The MUX orchestrator NEVER reads files, regardless of circumstances. If Bash is blocked for any reason, the answer is ALWAYS "tell the user and wait" -- never "work around it by reading directly."
