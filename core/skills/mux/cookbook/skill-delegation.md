# Skill Delegation

**NEVER invoke Skill() directly from orchestrator. ALWAYS delegate via Task().**

## Why

| Tool | Execution Context | Impact |
|------|-------------------|--------|
| `Skill()` | CURRENT agent (orchestrator) | Context DESTROYED |
| `Task()` | NEW subagent context | Context PRESERVED |

Skill() executes IN the calling agent's context. Running `/spec PLAN` in orchestrator = orchestrator death.

## Routing Table

| Pattern | WRONG (Context Suicide) | RIGHT (Context Preserved) |
|---------|-------------------------|---------------------------|
| `/spec PLAN` | `Skill(skill="spec", args="PLAN ...")` | `Task(prompt="Invoke Skill(skill='spec', args='PLAN ...')")` |
| `/spec IMPLEMENT` | `Skill(skill="spec", args="IMPLEMENT ...")` | `Task(prompt="Invoke Skill(skill='spec', args='IMPLEMENT ...')")` |
| `/commit` | `Skill(skill="commit")` | `Task(prompt="Invoke Skill(skill='commit')")` |
| `/review-pr` | `Skill(skill="review-pr", ...)` | `Task(prompt="Invoke Skill(skill='review-pr', ...)")` |
| Any skill | Direct `Skill()` call | `Task()` instructing subagent |

## Delegation Template

```python
Task(
    prompt="""Invoke the /spec skill for Phase 1 PLAN.

Use: Skill(skill="spec", args="PLAN 002-phase-001 THINK HARD")

OUTPUT: {output_path}
SIGNAL: {signal_path}
Return exactly: 0""",
    subagent_type="general-purpose",
    model="opus",
    run_in_background=True
)
```

## Fatal Violations

```python
# FATAL - runs in orchestrator context
Skill(skill="spec", args="PLAN 002-phase-001")

# FATAL - vague prompt, may not invoke Skill()
Task(prompt="Execute /spec PLAN for phase-001")

# FATAL - describing workflow instead of tool
Task(prompt="Run the spec planning stage")
```

## Correct Patterns

```python
# Explicit Skill() instruction
Task(
    prompt="Invoke Skill(skill='spec', args='PLAN 002-phase-001'). Return: 0",
    model="opus",
    run_in_background=True
)

# Domain skill via delegation
Task(
    prompt="Invoke Skill(skill='build-validate'). Report success/failure. Return: 0",
    model="sonnet",
    run_in_background=True
)

# Git inspection (no skill needed)
Task(
    prompt="Read .claude/skills/mux/agents/sentinel.md. Check git status. SIGNAL: {signal}",
    model="sonnet",
    run_in_background=True
)
```

## mux-subagent Skill Delegation

Every MUX subagent MUST load the `mux-subagent` skill as its FIRST action. This is a special case of skill delegation where the subagent invokes a skill IN its own context (not delegated via Task).

### Why mux-subagent is Different

Unlike other skills that would pollute orchestrator context, `mux-subagent` is designed to run in the subagent's context. It:
1. Activates subagent-specific hooks (blocks TaskOutput, blocks additional Skill loads)
2. Provides the file-based communication protocol
3. Enforces the `0` return convention
4. Documents signal file creation requirements

### Delegation Pattern

Every Task() prompt from orchestrator MUST include:

```
MANDATORY FIRST ACTION: Before ANY other action, load the MUX subagent protocol:
Skill(skill="mux-subagent")
This is NON-NEGOTIABLE. If you skip this, your work will be rejected.
```

### Inline Protocol Preamble (Fallback)

If Skill() is unavailable to a subagent, the inline preamble in the Task prompt provides critical rules as fallback:

```
MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)
```

### What mux-subagent Hooks Block

After loading `mux-subagent`, the subagent's hooks block:
- **TaskOutput** -- must use signal files
- **Skill** -- no additional skills after mux-subagent (all tools already available)
