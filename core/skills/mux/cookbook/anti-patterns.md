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
- NEVER use bash polling loops (use monitor agent)

## Bash Violations (RUTHLESS ENFORCEMENT)

- NEVER run grep/find/cat yourself
- NEVER do "quick verification"
- NEVER inspect file content via bash
- NEVER rationalize exceptions
- NEVER run npx/npm/cdk/cargo/go directly

## Communication Violations

- NEVER accept inline content from agents (only "done")
- NEVER pass file content in prompts (pass paths)

## Blocking Violations (CRITICAL)

- NEVER use `TaskOutput()` - signals are the ONLY completion mechanism
- NEVER use `run_in_background=False` - ALWAYS `True`
- NEVER block on ANY agent (including monitor)
- NEVER wait for workers or monitor before proceeding
- NEVER use bash loops to wait

### TaskOutput is FORBIDDEN

`TaskOutput()` blocks until the agent completes. This defeats the entire architecture:

```python
# FATAL VIOLATION - blocks context, wastes tokens
monitor_result = TaskOutput(task_id=monitor_id, block=True)  # NEVER DO THIS

# CORRECT - continue immediately, verify via signals later
Task(..., run_in_background=True)  # Launch
# Continue to next phase immediately
uv run tools/verify.py "$SESSION_DIR" --action summary  # Check later
```

The monitor uses `poll-signals.py` internally. Orchestrator should NEVER block on monitor completion.

## Delegation Violations

- NEVER execute leaf tasks yourself
- NEVER skip sentinel review
- NEVER skip voice updates
- NEVER implement agent behavior inline
- NEVER run domain commands when skill exists

## Session Management Violations

- NEVER delete session directories
- NEVER run `rm -rf tmp/swarm/*`

## Consequence

Context pollution leads to session death. When context is full, your session dies.

**RULE: If you can describe the command, you can delegate it. NO EXCEPTIONS.**
