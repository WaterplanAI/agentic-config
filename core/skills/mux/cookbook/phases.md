# Phase Execution

Detailed phase-by-phase execution guide for MUX orchestration.

## Phase 0: Confirmation

CONFIRM to user (voice and text by default) that you are starting the mux process using the `mux` skill explicitly.

Voice example:
```python
mcp__voicemode__converse(
    message="Starting mux for {topic}",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

## Phase 1: Decomposition

Parse TASK from the arguments provided. DO NOT gather additional context yourself.

Extract from TASK text:
- `LEAN_MODE`: true if "lean" keyword present
- `RESEARCH_SUBJECTS`: Products/systems mentioned in TASK
- `OUTPUT_TYPE`: roadmap | spec | analysis | learnings (infer from TASK)

### Context Gathering Pattern

**CRITICAL:** If you need more context to decompose the task:
1. DO NOT use Read/Grep/WebFetch yourself
2. DO launch an auditor agent to gather context
3. Wait for auditor signal, then proceed with decomposition

```python
# If context needed, delegate to auditor FIRST
Task(
    prompt="""Read .claude/skills/mux/agents/auditor.md for protocol.

TASK: Gather context for task decomposition
- Analyze relevant codebase areas
- Fetch any referenced URLs/issues
OUTPUT: {session_dir}/audit/task-context.md
SIGNAL: {session_dir}/.signals/000-context.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
    subagent_type="general-purpose",
    model="sonnet",
    run_in_background=True
)
```

Voice update:
```python
mcp__voicemode__converse(
    message=f"Starting mux for {topic}",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

## Parallelization Safety (ALL Fan-Out Phases)

**Before launching ANY parallel batch, validate file overlap:**

- Research/audit agents: SAFE to parallelize (each writes to its OWN output file)
- Implementation/writer agents: Check target files FIRST
- If ANY source file appears in >1 agent's scope: SERIALIZE into separate waves

This rule applies to Phase 2, Phase 3, Phase 5, and any custom fan-out.

## Phase 2: Fan-Out Research

Launch ALL workers in ONE message for parallelism (safe: each writes to independent output file).

```python
# Workers (ALL launched here)
for subject in subjects:
    Task(
        prompt=f"""Read .claude/skills/mux/agents/researcher.md for protocol.

TASK: Research {subject}
OUTPUT: {session_dir}/research/{subject.lower().replace(' ', '-')}.md
SIGNAL: {session_dir}/.signals/research-{subject.lower().replace(' ', '-')}.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
        subagent_type="general-purpose",
        model="sonnet",
        run_in_background=True
    )

# Checkpoint
# ✓ {len(subjects)} workers launched
# ✓ Continuing immediately -- runtime notifies on each completion
# ✓ After {len(subjects)} notifications: run verify.py once, then proceed

voice(f"{len(subjects)} research workers launched")
```

## Phase 3: Fan-Out Audits

Same pattern as Phase 2, using `.claude/skills/mux/agents/auditor.md`.

```python
# Workers
for audit_task in audit_tasks:
    Task(
        prompt=f"""Read .claude/skills/mux/agents/auditor.md for protocol.

TASK: {audit_task}
OUTPUT: {audit_output_path}
SIGNAL: {audit_signal_path}

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
        subagent_type="general-purpose",
        model="sonnet",
        run_in_background=True
    )
```

## Phase 2-3: Completion Tracking

Orchestrator continues IMMEDIATELY after launching workers - never waits.

Runtime task-notification delivers per-worker completion signals. After receiving
all N notifications, orchestrator runs verify.py once as safety check:

```bash
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

If fewer than N notifications arrive within timeout, use one-shot fallback:
```bash
uv run .claude/skills/mux/tools/check-signals.py "$SESSION_DIR" --expected N
```

## Phase 4: Consolidation

Only if total size exceeds 80KB.

```bash
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action total-size
```

If > 80KB, launch consolidator:

```python
Task(
    prompt=f"""Read .claude/skills/mux/agents/consolidator.md for protocol.

TASK: Consolidate findings from research and audits
SESSION: {session_dir}
OUTPUT: {session_dir}/consolidated.md
SIGNAL: {session_dir}/.signals/consolidation.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
    subagent_type="general-purpose",
    model="sonnet",
    run_in_background=True
)
```

## Phase 5: Coordination

### Standard Mode

Launch coordinator (opus) who delegates to writers.

```python
Task(
    prompt=f"""Read .claude/skills/mux/agents/coordinator.md for protocol.

TASK: Design deliverable structure and delegate to writers
SESSION: {session_dir}
OUTPUT: {session_dir}/coordination.md
SIGNAL: {session_dir}/.signals/coordination.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
    subagent_type="general-purpose",
    model="opus",
    run_in_background=True
)
```

### Lean Mode

Launch single writer (sonnet) directly.

```python
Task(
    prompt=f"""Read .claude/skills/mux/agents/writer.md for protocol.

TASK: Write {deliverable_name}
SESSION: {session_dir}
OUTPUT: {session_dir}/deliverables/{deliverable_name}.md
SIGNAL: {session_dir}/.signals/writer.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
    subagent_type="general-purpose",
    model="sonnet",
    run_in_background=True
)
```

## Phase 6: Verification

```bash
uv run .claude/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

Output shows:
- Signals completed
- Output files created
- Total size
- Missing signals (if any)

## Phase 6.5: Sentinel Review

MANDATORY quality gate.

```python
Task(
    prompt=f"""Read .claude/skills/mux/agents/sentinel.md for protocol.

TASK: Review session quality against pillars
SESSION: {session_dir}
PILLARS: {quality_pillars}
OUTPUT: {session_dir}/sentinel-review.md
SIGNAL: {session_dir}/.signals/sentinel.done

MUX SUBAGENT PROTOCOL:
- Invoke Skill(skill="mux-subagent") as FIRST action
- Write ALL output to files (never in response)
- Create signal before returning
- Final response MUST be EXACTLY: 0 (one character, nothing else)

FINAL: Return EXACTLY: 0""",
    subagent_type="general-purpose",
    model="sonnet",
    run_in_background=True
)
```

If FAIL: Use AskUserQuestion to let user decide:
```python
AskUserQuestion(
    questions=[{
        "question": "Sentinel review found gaps. How to proceed?",
        "header": "Quality Gate",
        "options": [
            {"label": "Proceed anyway", "description": "Accept current quality and continue"},
            {"label": "Address gaps", "description": "Re-run affected phases to fix issues"},
            {"label": "Abort", "description": "Stop session without delivering"}
        ],
        "multiSelect": False
    }]
)
```

## Interactive Gates (Critical Decision Points)

Use AskUserQuestion ONLY at these points:
1. **Sentinel failure** - proceed/address/abort
2. **Consolidation decision** - when output > 80KB
3. **Error recovery** - timeout/failure handling

Normal phase transitions: voice announcement + auto-proceed.

## Error Recovery Patterns

| Error Type | Recovery Action |
|------------|----------------|
| Agent timeout | Check partial signal, relaunch with tighter scope |
| Notification timeout | Run check-signals.py, relaunch missing workers |
| Coordinator context limit | Run consolidation first, retry |

## Voice Protocol Timing

Update at:
- Phase start (confirmation)
- Milestones (workers launched)
- Completion (sentinel review done)
- Errors (recovery actions)

```python
mcp__voicemode__converse(
    message="{update}",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```
