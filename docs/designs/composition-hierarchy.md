# Agentic Tool Composition Hierarchy

Design document for the layered composition pattern that builds from the atomic
`spawn.py` primitive into progressively higher-order agentic tools.

## Table of Contents

1. [Overview](#1-overview)
2. [Layer Architecture](#2-layer-architecture)
3. [Layer Contracts](#3-layer-contracts)
4. [System Prompt Architecture](#4-system-prompt-architecture)
5. [Inter-Layer Communication Protocol](#5-inter-layer-communication-protocol)
6. [Depth Budget Model](#6-depth-budget-model)
7. [Refinement and Escalation](#7-refinement-and-escalation)
8. [Verification (Sentinel) Loop](#8-verification-sentinel-loop)
9. [Session Lifecycle](#9-session-lifecycle)
10. [File Conventions](#10-file-conventions)

---

## 1. Overview

### Core Principle

Every agentic workflow decomposes into a hierarchy of composable tools,
each implemented as a PEP 723 Python script callable via `uv run`:

```
Layer 0: Primitive      spawn.py              (SDK wrapper, atomic)
Layer 1: Executor       <name>.py             (spawn.py + fixed system prompt)
Layer 2: Orchestrator   <name>-orchestrator   (sequences executors per-stage)
Layer 3: Coordinator    <name>-coordinator    (sequences orchestrators per-phase)
Layer 4: Campaign       <name>-campaign       (phases + verification loops)
```

### Invariant

The universal calling convention is `uv run <tool>.py ARGS`. This is identical
at depth-0, depth-1, or depth-N. Every layer calls the layer directly below it
via `subprocess.run`. No layer ever skips a layer.

### Two Composition Modes

| Mode | Layers 2-4 are... | Depth cost | When to use |
|------|--------------------|------------|-------------|
| **Tool composition** | Pure Python scripts. No LLM. | Zero (only spawn.py consumes depth) | Deterministic stage/phase sequences |
| **Agent composition** | LLM agents (via spawn.py + Bash-only tools) | Each layer consumes 1 depth unit | Dynamic decisions, runtime-discovered work |

**Recommendation**: Start with agent composition (faster to build, more flexible).
Optimize to tool composition when stage sequences become deterministic.

---

## 2. Layer Architecture

### Layer Definitions

| Layer | Name | Responsibility | Delegates To |
|-------|------|----------------|-------------|
| **0** | **Primitive** | Execute a single agent session. Owns SDK invocation, depth tracking, output formatting, environment inheritance. | Nothing (leaf node). |
| **1** | **Executor** | Bind a fixed system prompt + argument vocabulary to spawn.py. One executor = one specialized task type. | Layer 0 via `subprocess.run`. |
| **2** | **Orchestrator** | Sequence multiple executor calls. Owns stage ordering, inter-stage data flow, per-stage success/failure gating. | Layer 1 executors via `subprocess.run`. |
| **3** | **Coordinator** | Compose multiple orchestrators into a multi-phase operation. Owns phase ordering, cross-orchestrator dependencies, phase-level rollback. | Layer 2 orchestrators via `subprocess.run`. |
| **4** | **Campaign** | Drive multi-phase operations with verification loops, human checkpoints, and convergence criteria. Owns outermost retry/abort logic. | Layer 3 coordinators via `subprocess.run`. |

### Coordinator vs Executor: Formal Distinction

| Property | Executor (Layer 1) | Coordinator (Layer 2+) |
|----------|-------------------|----------------------|
| Calls spawn.py directly | YES | NO (tool mode) or YES via Bash (agent mode) |
| Calls other `.py` tools | NO | YES (lower-layer tools only) |
| Has a system prompt file | YES (owns one) | NO (tool mode) or YES (agent mode) |
| Reads/writes source files | NO (spawned agent does) | NEVER |
| Runs tests | NO (spawned agent may) | NEVER |
| Makes sequencing decisions | NO (single invocation) | YES (stage/phase ordering) |
| Has retry logic | NO (fire-and-forget) | YES (per-stage/per-phase) |
| Parses lower-layer output | N/A | YES (reads stdout JSON, exit codes) |

**The critical rule**: If a `.py` file contains `from claude_agent_sdk import`
or `--system-prompt`, it is Layer 0 or Layer 1. If it calls `uv run <tool>.py`
in a loop with branching logic, it is Layer 2+.

**Anti-pattern**: An "orchestrator" that wraps spawn.py with a system prompt is
NOT an orchestrator -- it is just another executor. A true Layer 2 orchestrator
calls `executor.py STAGE_A`, then `executor.py STAGE_B`, then
`executor.py STAGE_C` sequentially.

### Model Tier Allocation

| Layer | Default Tier | Rationale |
|-------|-------------|-----------|
| **0** | `medium-tier` | Generic default; overridden by caller. |
| **1** | Task-dependent | Research/analysis = `medium-tier`. Implementation = `high-tier`. Validation = `low-tier`. |
| **2+** (tool mode) | N/A | Pure Python. Zero tokens consumed. Passes tier config DOWN to executors. |
| **2+** (agent mode) | `high-tier` | Makes sequencing/routing decisions requiring strong reasoning. |

**Key insight**: In tool composition mode, only Layers 0-1 consume model tokens.
Layers 2-4 configure which tier each executor uses but consume zero tokens themselves.

**Exception**: If a Layer 2+ tool needs LLM reasoning (e.g., "should I retry this
failed stage?"), it spawns a dedicated Layer 1 executor for that single decision.
It does NOT embed SDK calls directly.

---

## 3. Layer Contracts

### Layer 0 to Layer 1 (Primitive to Executor)

**What Layer 1 sends:**
```bash
uv run spawn.py \
  --prompt <constructed-prompt> \
  --system-prompt <resolved-path.md> \
  --model <tier-or-raw-id> \
  --output-format text|json \
  --max-depth <N> \
  [--current-depth <D>] \
  [--cwd <path>] \
  [--allowed-tools <comma-list>]
```

**What Layer 0 returns:**

| Signal | Channel | Format |
|--------|---------|--------|
| Exit code | `returncode` | `0`=success, `1`=failure, `2`=depth exceeded |
| Output | `stdout` | `KEY=value` (text) or JSON object |
| Errors | `stderr` | JSON `{"status":"error","error":{"code":"...","message":"..."}}` |

**Promises**: Layer 1 always provides `--prompt` and `--system-prompt`. Never
modifies `AGENTIC_SPAWN_DEPTH` directly (spawn.py owns depth tracking).

### Layer 1 to Layer 2 (Executor to Orchestrator)

**What Layer 2 sends:**
```bash
uv run <executor>.py <POSITIONAL_ARGS> \
  [--model <tier>] \
  [--max-depth <N>] \
  [--output-format json] \
  [--cwd <path>]
```

**What Layer 1 returns:**

| Signal | Channel | Format |
|--------|---------|--------|
| Exit code | `returncode` | Passthrough from spawn.py: `0`, `1`, `2` |
| Output | `stdout` | Passthrough from spawn.py (text or JSON) |
| Errors | `stderr` | Passthrough from spawn.py |

**Promises**: Layer 2 passes `--output-format json` for machine-readable parsing.
Respects exit codes -- never retries on exit code `2` (depth exceeded).
Layer 1 provides deterministic argument vocabulary.

### Layer 2 to Layer 3 (Orchestrator to Coordinator)

**What Layer 2 returns:**

| Signal | Channel | Format |
|--------|---------|--------|
| Exit code | `returncode` | `0`=all stages passed, `1`=failure, `2`=depth exceeded, `12`=partial |
| Stage manifest | `stdout` | JSON array of per-stage results |
| Progress | `stderr` | Human-readable stage progress (optional) |

**Stage manifest format:**
```json
{
  "orchestrator": "<name>",
  "stages": [
    {"name": "STAGE_A", "status": "success", "exit_code": 0, "artifact": "<path>"},
    {"name": "STAGE_B", "status": "failure", "exit_code": 1, "error": "<reason>"}
  ],
  "summary": {"total": 3, "passed": 2, "failed": 1, "exit_code": 12}
}
```

### Layer 3 to Layer 4 (Coordinator to Campaign)

Same structural pattern. Phase reports replace stage manifests:

```json
{
  "phase": "phase-01",
  "status": "complete",
  "exit_code": 0,
  "orchestrators": [
    {"name": "<orchestrator>", "manifest": "<path>", "exit_code": 0}
  ],
  "artifacts": ["<path-1>", "<path-2>"],
  "sentinel_grade": "PASS"
}
```

---

## 4. System Prompt Architecture

### File Convention

```
core/prompts/
  executors/<name>.md           # Layer 1 system prompts
  orchestrators/<name>.md       # Layer 2 system prompts (agent mode only)
  coordinators/<name>.md        # Layer 3 system prompts (agent mode only)
  campaigns/<name>.md           # Layer 4 system prompts (agent mode only)
```

Existing convention preserved: skills with `SKILL.md` files continue to use
those. Command definitions at `core/commands/claude/<name>.md` continue unchanged.
The `core/prompts/` tree is for prompts consumed by `core/tools/agentic/` tools.

### Prompt Composition Rule

The system prompt defines WHO the agent is and HOW it operates.
The prompt defines WHAT to do. They must not overlap.

| Layer | System Prompt (WHO/HOW) | Prompt (WHAT) |
|-------|-------------------------|---------------|
| Executor | Role, tools, output format, constraints | Specific task: action + target + args |
| Orchestrator | Role, stage sequence, routing rules | Workflow: modifier + target |
| Coordinator | Role, phase graph, dependency rules | Phase specification or range |
| Campaign | Role, verification loop, session lifecycle | Campaign plan: phases + config |

**Anti-patterns:**
- Prompt contains role definition ("You are a...") -- belongs in system prompt
- System prompt contains specific file paths -- come from the prompt
- Orchestrator prompt contains stage logic -- system prompt owns stage sequences

### Template: Executor (Layer 1)

```markdown
# <Executor Name>

## Role
You are a <ROLE>. You execute a single task and produce concrete artifacts.

## Input
Prompt format: `/<command> <ACTION> <target> [extra-args]`

## Execution Protocol
1. VALIDATE inputs exist
2. EXECUTE the task using available tools
3. PRODUCE artifacts (files, commits)
4. VERIFY artifacts created correctly
5. RETURN status

## Output
EXACTLY one of:
- `STAGE_<ACTION>_COMPLETE` -- success
- `STAGE_FAILED: <reason>` -- failure

## Constraints
- Never modify files outside declared scope
- Never return success without verifiable artifacts
- On failure: no partial artifacts, exit code 1
```

### Template: Orchestrator (Layer 2)

```markdown
# <Orchestrator Name>

## Role
You are a STAGE SEQUENCER. You call executor tools and route on exit codes.
You NEVER execute work directly.

## The One Rule
Before ANY action: "Am I calling an executor or doing work myself?"
- Calling executor (uv run <tool>.py) = PROCEED
- Doing work directly = STOP

## Stage Sequence
| Modifier | Stages |
|----------|--------|
| `full`   | A -> B -> C -> D |
| `lean`   | B -> C -> D |

## Per-Stage Protocol
1. CALL: `uv run <executor>.py <STAGE> <target> --output-format json`
2. CHECK exit code (0=proceed, 1=retry once, 2=abort)
3. ROUTE to next stage or handle failure

## Failure Handling
- Exit 1: Retry once. If retry fails, abort.
- Exit 2: Abort immediately (depth exceeded).
- Timeout (10min): Kill, retry once.

## Constraints
- NEVER use Read, Write, Edit, Grep, Glob
- ALL work happens inside executors
```

### Template: Coordinator (Layer 3)

```markdown
# <Coordinator Name>

## Role
You are a PHASE COORDINATOR. You call orchestrators and track phase dependencies.
You NEVER execute stages or read source files.

## Phase Sequence
| Phase | Orchestrator | Depends On |
|-------|-------------|------------|
| 1 | <orch-a>.py | none |
| 2 | <orch-b>.py | Phase 1 |

## Per-Phase Protocol
1. VERIFY dependencies met (prior phases completed)
2. CALL: `uv run <orchestrator>.py <modifier> <target> --output-format json`
3. CHECK result
4. CHECKPOINT progress
5. ROUTE: next phase, retry, or escalate

## Escalation
- Orchestrator fails after retry: write refinement doc, exit 10
- Human input required: write escalation doc, exit 3

## Constraints
- NEVER call executors directly (only orchestrators)
- NEVER read/write source files
- Checkpoint after EVERY phase transition
```

### Template: Campaign (Layer 4)

```markdown
# <Campaign Name>

## Role
You are a CAMPAIGN CONTROLLER. You coordinate phases via coordinators,
run verification loops, and handle human escalation.

## Campaign Flow
For each phase:
1. CALL coordinator
2. RUN verification (sentinel loop)
3. If PASS: checkpoint, next phase
4. If FAIL: remediate (max 2 cycles), then escalate

## Session Lifecycle
- INIT: set up session directory
- PHASE_N: execute via coordinator
- VERIFY: sentinel loop
- CHECKPOINT: save state for resume
- COMPLETE: cleanup, final report

## Constraints
- NEVER call orchestrators or executors directly
- NEVER skip verification between phases
- Session directory is single source of truth
```

### Cross-Layer Invariants

1. **Return protocol**: Status line only. All work product in files.
2. **Failure propagation**: Failures bubble up. No layer swallows errors.
3. **Layer isolation**: Each layer calls only the layer directly below.
4. **Idempotent retry**: Re-running with same inputs produces same result or succeeds.
5. **Session as state**: All state in session directory. No in-memory state survives process boundaries.
6. **Exit codes**: 0=success, 1=failure, 2=depth-exceeded, 3=human-input-required.

---

## 5. Inter-Layer Communication Protocol

### Exit Code Semantics

| Code | Name | Meaning | Origin |
|------|------|---------|--------|
| 0 | `SUCCESS` | Completed successfully | All layers |
| 1 | `FAILURE` | Unrecoverable at this layer | All layers |
| 2 | `DEPTH_EXCEEDED` | Spawn depth limit reached | Layer 0 |
| 3 | `HUMAN_INPUT` | Cannot resolve autonomously | Layers 2-4 |
| 10 | `NEEDS_REFINEMENT` | Work produced but quality gate failed | Layers 1-3 |
| 11 | `NEEDS_ESCALATION` | Requires parent intervention | Layers 1-3 |
| 12 | `PARTIAL_SUCCESS` | Some stages/phases passed, others failed | Layers 2-4 |
| 20 | `INTERRUPTED` | Cancelled by user (KeyboardInterrupt) | All layers |
| 21 | `TIMEOUT` | Subprocess timeout exceeded | All layers |

### Exit Code Propagation

| Child Exit | Orchestrator (L2) | Coordinator (L3) | Campaign (L4) |
|------------|-------------------|-------------------|----------------|
| 0 | Absorb, next stage | Absorb, next phase | Absorb, verify |
| 1 | Retry once, then re-raise | Retry once, then re-raise | Log, escalate |
| 2 | Always re-raise | Always re-raise | Always re-raise |
| 10 | Re-raise to coordinator | Absorb, re-invoke child with resolution | Log, retry once |
| 11 | Re-raise | Re-raise | Present to human |
| 12 | Absorb, retry failed stages | Absorb, retry failed phases | Log partial results |
| 20 | Always re-raise, cleanup | Always re-raise, cleanup | Always re-raise |

**Invariant**: Exit code 2 (DEPTH_EXCEEDED) is NEVER absorbed by any layer.

### Signal File Protocol

**Path convention:**
```
<session-dir>/.signals/<layer>-<name>.<status>
```

| Component | Values |
|-----------|--------|
| `<layer>` | `exec`, `orch`, `coord`, `sentinel`, `monitor` |
| `<name>` | Descriptive slug (e.g., `research`, `phase-01`, `quality-gate`) |
| `<status>` | `.done`, `.fail`, `.refine` |

**Signal file format (YAML):**
```yaml
path: <artifact-path>
size: <bytes>
status: success|fail|needs-refinement
created_at: <ISO-8601>
completed_at: <ISO-8601>
trace_id: <hex-16>
layer: <layer-name>
name: <signal-name>
elapsed_seconds: <float>
version: 1
```

**Atomic write protocol**: Write to temp file `.<name>.tmp.<pid>`, then
`os.replace()` to target. Prevents partial reads.

### Observability Module

All layers import observability utilities from `lib/observability.py`, which provides:

**P1 - Streaming Subprocess I/O:**
```python
run_streaming(cmd, *, timeout, label, env=None) -> tuple[int, str]
```
Replaces `subprocess.run(capture_output=True)` with Popen-based streaming that forwards stderr line-by-line while capturing stdout for manifest parsing.

**P2 - Signal Activation:**
```python
signal_completion(session_dir, layer, name, status, artifact_path=None,
                 trace_id=None, elapsed_seconds=None) -> Path | None
```
Write atomic completion signals after every subprocess/agent execution. All layers (L0-L4) call this on both success and failure paths.

**P3 - Trace ID Propagation:**
```python
get_trace_id() -> str | None
propagate_trace_id(session_dir=None) -> str
build_child_env_with_trace(current_depth, trace_id=None) -> dict[str, str]
```
Introduces `AGENTIC_TRACE_ID` environment variable propagated through all subprocess boundaries for cross-layer correlation.

**P4 - Timer Instrumentation:**
```python
class Timer:  # context manager
    elapsed_ms() -> int
    elapsed_seconds() -> float
    running_elapsed_ms() -> int
```
Wrap every subprocess invocation and agent execution to track elapsed time.

**P5 - Structured Progress Events:**
```python
emit_event(layer, stage, status, *, elapsed_ms=None, detail=None) -> None
```
Emits JSON-lines on stderr with timestamp, trace ID, layer, depth, and elapsed time.

**P6 - Live Report File:**
```python
write_live_report(session_dir, layer, stage, status, *,
                 elapsed_seconds=None, detail=None) -> None
```
Appends to persistent `.live-report` file in session directories for `tail -f` monitoring.

**P7 - Consolidated Execution Report:**
```python
write_consolidated_report(session_dir) -> Path
```
Generates human-readable `execution-report.md` from signals, live-report, and manifests at campaign/coordinator completion.

---

## 6. Depth Budget Model

### How Depth Works

`AGENTIC_SPAWN_DEPTH` is incremented ONLY by spawn.py on each invocation.
The effective depth equals the number of transitive spawn.py calls in the
call chain.

**In tool composition mode** (pure Python orchestrators):
```
Campaign       depth 0  (pure Python, no spawn)
  Coordinator  depth 0  (pure Python, no spawn)
    Orchestr.  depth 0  (pure Python, no spawn)
      Executor depth 0  (subprocess to spawn.py)
        spawn  depth 1  (increments AGENTIC_SPAWN_DEPTH)
          agent work    (may call more executors -> depth 2+)
```

A full 5-layer stack with tool composition: **depth = 1** for linear chains.
Depth grows only when spawned agents invoke additional executors.

**In agent composition mode** (LLM-driven orchestrators):
```
Campaign     → spawn.py (depth 1)
  Coord.     → spawn.py (depth 2)
    Orch.    → spawn.py (depth 3)
      Exec.  → spawn.py (depth 4)
        agent work      (depth 5+)
```

Each LLM-driven layer consumes 1 depth unit.

### Minimum Depth Requirements

| Stack | Tool Mode | Agent Mode |
|-------|-----------|------------|
| Executor only | 2 | 2 |
| Orchestrator + Executor | 2 | 3 |
| Coord + Orch + Exec | 2 | 4 |
| Campaign + Coord + Orch + Exec | 2 | 5 |
| Campaign + Sentinel loop | 3 | 6 |

### Recommended Defaults

| Use Case | `--max-depth` |
|----------|---------------|
| Single-stage task | 2 |
| Multi-stage workflow | 3 |
| Workflow with sub-spawning agents | 5 |
| Full campaign (agent mode) | 7 |

### Depth Propagation

Each layer passes `--max-depth` unchanged to the layer below. Only spawn.py
increments the actual depth counter. Max-depth is a global budget shared
across all transitive spawn.py calls.

```python
# Layer 2 passes max-depth through unchanged
cmd = ["uv", "run", str(executor_path), stage, spec_path,
       "--max-depth", str(args.max_depth), "--output-format", "json"]
```

### Depth Exhaustion

| Remaining | Behavior |
|-----------|----------|
| >= 2 | Normal. Can spawn children that can self-heal. |
| 1 | Can spawn ONE child. Child cannot self-heal. Log warning. |
| 0 | Cannot spawn. Return exit 2 immediately. |

**Mid-orchestration exhaustion options:**
1. **Compress**: Execute remaining stages in a single spawn (if semantically valid)
2. **Abort**: Return exit 2 with partial results
3. **Escalate**: Return exit 11 asking parent to allocate more depth

---

## 7. Refinement and Escalation

### Three-Tier Escalation

```
Tier 1: Self-Heal     (layer-local retry with error diagnostics)
Tier 2: Parent Refine  (escalate to parent with refinement document)
Tier 3: Human Escalate (present to human for resolution)
```

### Tier 1: Self-Heal

- Executor detects recoverable failure (type errors, lint failures)
- Retries with augmented prompt containing error diagnostics
- Max `SELF_HEAL_MAX=2` attempts
- Each retry consumes 1 depth unit
- If depth insufficient for retry, skip to Tier 2

**Retry prompt augmentation:**
```
Previous attempt failed with:
{error_diagnostics}

Fix the following issues:
{issue_list}
```

### Tier 2: Escalate to Parent Layer

**Trigger**: Self-heal exhausted or issue outside child's capability.

**Protocol:**
1. Child exits with code 10 (NEEDS_REFINEMENT) or 11 (NEEDS_ESCALATION)
2. Child writes refinement doc to `<session-dir>/refinements/<layer>-<name>.md`
3. Child creates `.refine` signal file
4. Parent reads refinement doc (via bounded summary, not full content)
5. Parent either resolves (code 10) or propagates (code 11)

**Refinement document format:**
```markdown
# Refinement Request

## Summary
One-line description.

## Context
- Stage: <stage-name>
- Artifact: <path>
- Attempt: N of N (self-heal exhausted)

## Issue
Detailed description.

## Diagnostics
- Error 1: ...
- Error 2: ...

## Suggested Resolution
What parent/human could do to unblock.
```

**Resolution flow back:**
1. Parent writes resolution to `<session-dir>/resolutions/<layer>-<name>.md`
2. Parent re-invokes child with `--extra-context <resolution-path>`
3. Child reads resolution as additional context

### Tier 3: Human Escalation

- Exit code 11 reaches campaign layer
- Campaign collects unresolved refinement docs
- Presents consolidated escalation to human
- Human provides resolution
- Campaign writes resolution and re-invokes failing phase

---

## 8. Verification (Sentinel) Loop

### Trigger Conditions

1. After every phase completion (mandatory)
2. After refinement re-runs (mandatory)
3. On explicit request from coordinator or campaign

### Pipeline

```
Writer(s)     -> produce test specifications from completed work
Executor      -> run verification (tests, type checks, lint)
Auditor       -> cross-reference results against specifications
Consolidator  -> produce prioritized fix list
[Loop]        -> Diagnose -> Fix -> Retest (max 3 cycles)
```

### Stage I/O

**Writer -> Executor:**
- Input: Completed artifact paths (from signal `path` fields)
- Output: `<session-dir>/sentinel/test-spec.md`

**Executor -> Auditor:**
- Input: Test spec + artifacts under test
- Output: `<session-dir>/sentinel/verification-results.json`
```json
{
  "checks": [
    {"name": "typecheck", "tool": "pyright", "passed": false, "errors": 3},
    {"name": "lint", "tool": "ruff", "passed": true, "errors": 0},
    {"name": "tests", "tool": "test-runner", "passed": true, "errors": 0}
  ],
  "overall": "FAIL",
  "blocking_count": 3
}
```

**Auditor -> Consolidator:**
- Cross-references verification failures against spec requirements
- Output: `<session-dir>/sentinel/audit-report.md`
- Grade: `PASS` | `WARN` | `FAIL`

**Consolidator -> Fix List:**
- Output: `<session-dir>/sentinel/fix-list.json`
```json
{
  "fixes": [
    {"id": 1, "severity": "blocking", "file": "src/module.py", "issue": "...", "suggested_fix": "..."},
    {"id": 2, "severity": "warning", "file": "src/util.py", "issue": "...", "suggested_fix": "..."}
  ]
}
```

### Loop Termination

| Condition | Action |
|-----------|--------|
| All checks pass (PASS) | Exit loop, return 0 |
| Max cycles (3), blocking issues | Exit loop, return 10 (NEEDS_REFINEMENT) |
| Max cycles, only warnings | Exit loop, return 0 (warnings logged) |
| Depth budget exhausted | Exit loop, return 2 |
| No improvement after 2 consecutive cycles | Escalate |

### Artifact Location

```
<session-dir>/sentinel/
  cycle-1/
    test-spec.md
    verification-results.json
    audit-report.md
    fix-list.json
  cycle-2/
    ...
  grade.txt              # Final: PASS|WARN|FAIL
  summary.json           # Cycle count, blocking count
```

---

## 9. Session Lifecycle

### State Machine

```
INIT -> PHASE_N -> VERIFY -> CHECKPOINT -> [PHASE_N+1 | COMPLETE]
                     |
                     v
                 REFINEMENT -> PHASE_N (retry)
```

### Session Directory Structure

```
<base-dir>/<YYYYMMDD-HHMM-topic>/
  .trace                         # Trace ID (16 hex chars)
  .session-state                 # Current state (YAML)
  .live-report                   # Append-only progress log (JSON-lines)
  manifest.json                  # Session manifest
  execution-report.md            # Consolidated execution report

  phases/
    phase-01-<name>/
      manifest.json              # Stage manifest
      report.json                # Phase report
      artifacts/

  sentinel/
    cycle-1/
    grade.txt
    summary.json

  refinements/                   # Refinement request docs
  resolutions/                   # Resolution docs

  checkpoints/
    cp-<timestamp>.json          # Serialized state for resume

  .signals/                      # Flat namespace, layer-prefixed
```

### Session State

```yaml
state: PHASE_N
current_phase: 2
total_phases: 5
started_at: 2026-02-07T10:00:00Z
last_checkpoint: checkpoints/cp-20260207T1005.json
depth_used: 2
depth_max: 7
```

### Checkpoint Format

```json
{
  "checkpoint_version": 1,
  "created_at": "<ISO-8601>",
  "session_dir": "<path>",
  "trace_id": "<hex-16>",
  "completed_phases": [
    {"name": "phase-01", "exit_code": 0, "sentinel_grade": "PASS"}
  ],
  "pending_phases": ["phase-02", "phase-03"],
  "depth_used": 2,
  "depth_max": 7,
  "environment": {"AGENTIC_SPAWN_DEPTH": "2"}
}
```

### Resume Protocol

1. Read latest checkpoint (sorted by timestamp)
2. Validate checkpoint version
3. Restore session state
4. Set `AGENTIC_SPAWN_DEPTH` from checkpoint
5. Verify completed phase artifacts exist
6. If any artifact missing, mark that phase pending
7. Continue from first pending phase

---

## 10. File Conventions

### Tool Files

```
core/tools/agentic/
  spawn.py                          # Layer 0: Primitive (singleton)
  <name>.py                         # Layer 1: Executor
  <name>-orchestrator.py            # Layer 2: Orchestrator
  <name>-coordinator.py             # Layer 3: Coordinator
  <name>-campaign.py                # Layer 4: Campaign
```

### System Prompt Files

| Layer | Location |
|-------|----------|
| Executor (command) | `core/commands/claude/<name>.md` |
| Executor (skill) | `core/skills/<name>/SKILL.md` |
| Executor (agent) | `core/agents/<name>.md` |
| Orchestrator+ | `core/prompts/<layer>/<name>.md` |

### Config Files (Layer 2+)

```
core/tools/agentic/config/
  <orchestrator>.json              # Stage definitions
  <coordinator>.json               # Phase definitions
```

**Stage config schema:**
```json
{
  "stages": [
    {
      "name": "research",
      "executor": "spec.py",
      "args": ["RESEARCH"],
      "model": "medium-tier",
      "retry": 1,
      "required": true
    }
  ]
}
```

### Naming Convention

| Layer | Pattern | Example |
|-------|---------|---------|
| Layer 1 | `<workflow>.py` | `spec.py`, `researcher.py` |
| Layer 2 | `o<workflow>.py` | `ospec.py`, `oresearch.py` |
| Layer 3 | `coordinator.py` | `coordinator.py` |
| Layer 4 | `campaign.py` | `campaign.py` |

---

## Appendix: Implementation Status

### Layer Tools

| Layer | Pattern | Implementation | Status |
|-------|---------|---------------|--------|
| **0** | Primitive | `core/tools/agentic/spawn.py` | Done |
| **1** | Executor (spec) | `core/tools/agentic/spec.py` | Done |
| **1** | Executor (researcher) | `core/tools/agentic/researcher.py` | Done |
| **2** | Orchestrator (ospec) | `core/tools/agentic/ospec.py` | Done |
| **2** | Orchestrator (oresearch) | `core/tools/agentic/oresearch.py` | Done |
| **3** | Coordinator | `core/tools/agentic/coordinator.py` | Done |
| **4** | Campaign | `core/tools/agentic/campaign.py` | Done |

### Supporting Infrastructure

| Component | Implementation | Status |
|-----------|---------------|--------|
| Shared library | `core/tools/agentic/lib/__init__.py` | Done |
| Observability module | `core/tools/agentic/lib/observability.py` | Done |
| Stage config (ospec) | `core/tools/agentic/config/ospec.json` | Done |
| Research config | `core/tools/agentic/config/oresearch.json` | Done |
| Phase config (example) | `core/tools/agentic/config/coordinator-example.json` | Done |
| Executor prompts | `core/prompts/executors/researcher-{market,ux,tech,consolidator}.md` | Done |
| Orchestrator prompt | `core/prompts/orchestrators/ospec.md` | Done |
| Coordinator prompt | `core/prompts/coordinators/coordinator.md` | Done |
| Campaign prompts | `core/prompts/campaigns/{campaign,refinement-evaluator,roadmap-writer,evaluator}.md` | Done |
| Signal protocol | `core/skills/mux/tools/signal.py` | Pre-existing |
| Signal polling | `core/skills/mux/tools/poll-signals.py` | Pre-existing |
| Session lifecycle | `core/skills/mux/tools/session.py` | Pre-existing |

The composition hierarchy generalizes these existing implementations into
reusable patterns for any agentic workflow.
