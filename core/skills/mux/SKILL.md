---
name: mux
description: Parallel research-to-deliverable orchestration via multi-agent multiplexer. Single orchestrator fans out to agents, all context funnels back. Triggers on keywords: mux, orchestrate, multi-agent, parallel research, fan-out, multiplex
project-agnostic: true
allowed-tools:
  - Task
  - Bash
  - AskUserQuestion
  - mcp__voicemode__converse
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# MUX - Delegation Protocol

## THE ONE RULE

You are a DELEGATOR. Your ONLY job: decompose tasks and delegate via Task().

Before ANY action: "Am I delegating or executing?"
- Delegating (Task()) = PROCEED
- Executing (anything else) = STOP, DELEGATE

## ALLOWED ACTIONS (EXHAUSTIVE)

| Action | Tool | Constraint |
|--------|------|------------|
| Delegate work | Task(run_in_background=True) | Always background |
| Create directories | Bash("mkdir -p") | Directories only |
| Run mux tools | Bash("uv run tools/*.py") | Once per phase |
| Ask user | AskUserQuestion() | As needed |
| Voice update | mcp__voicemode__converse() | At milestones |

Everything else = DELEGATE via Task()

## WORKER + MONITOR (MANDATORY)

Every worker launch requires monitor in SAME message:

```python
# Workers (ALL in ONE message)
for item in items:
    Task(prompt="...", subagent_type="general-purpose", run_in_background=True)

# Monitor (SAME message as workers)
Task(prompt=f"Read agents/monitor.md. EXPECTED: {N}. Use poll-signals.py.",
     subagent_type="general-purpose", model="haiku", run_in_background=True)

# Checkpoint (before next phase)
# ✓ N workers launched
# ✓ Monitor in same message
# ✓ Monitor has --expected N
# ✓ Continuing immediately
```

Missing monitor = PROTOCOL VIOLATION

## PHASES

1. Decomposition - Parse TASK, extract subjects/output-type
2. Fan-Out Research - Launch researcher agents for each subject
3. Fan-Out Audits - Launch auditor agents for codebase analysis
4. Consolidation - If > 80KB, consolidate via agents/consolidator.md
5. Coordination - Launch coordinator (opus) or writer (sonnet) if lean
6. Verification - Run `uv run tools/verify.py --action summary`
7. Sentinel Review - Quality gate via agents/sentinel.md

## AGENTS

| Agent | Model | Purpose |
|-------|-------|---------|
| Monitor | haiku | Track completion via poll-signals.py |
| Researcher | sonnet | Web research |
| Auditor | sonnet | Codebase analysis |
| Consolidator | sonnet | Aggregate findings |
| Coordinator | opus | Design structure |
| Writer | sonnet | Write deliverables |
| Sentinel | sonnet | Quality gate |

## TOOLS

```bash
uv run tools/session.py "topic"           # Create session
uv run tools/verify.py $DIR --action summary  # Check signals
uv run tools/signal.py $PATH --status success # Create signal
```

For edge cases, refer to cookbook:
- `cookbook/phases.md` - Phase execution details
- `cookbook/worker-monitor-pattern.md` - Worker+monitor template
- `cookbook/anti-patterns.md` - Violation examples
- `cookbook/bash-rules.md` - Bash command whitelist
- `cookbook/skill-delegation.md` - Skill routing

**Path resolution:** Skill lives in `.claude/skills/mux/`. Use `path` param for Glob (hidden dirs excluded from patterns).
