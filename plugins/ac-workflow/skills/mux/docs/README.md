# Mux Skill

Parallel research-to-deliverable orchestration via multi-agent multiplexer.

## Table of Contents

- [Overview](#overview)
- [When to Use](#when-to-use)
- [Core Architecture](#core-architecture)
  - [Agent Hierarchy](#agent-hierarchy)
  - [Model Tier Strategy](#model-tier-strategy)
- [Core Patterns](#core-patterns)
  - [File-Based Communication](#file-based-communication)
  - [Signal Protocol](#signal-protocol)
  - [Completion Tracking](#completion-tracking)
  - [Output Format Protocol](#output-format-protocol)
  - [Async Constraints](#async-constraints)
- [Session Directory Structure](#session-directory-structure)
- [Tools Reference](#tools-reference)
- [Execution Modes](#execution-modes)
  - [Standard Mode](#standard-mode)
  - [Lean Mode](#lean-mode)
- [Anti-Patterns](#anti-patterns)
- [Design Decisions](#design-decisions)

## Overview

Mux is a multi-agent orchestration skill that decomposes complex research-to-deliverable tasks into parallel streams of specialized agents. The orchestrator NEVER executes leaf tasks itself; it ONLY decomposes, delegates, tracks, verifies, and reports.

**Key Characteristics**:
- Six specialized agents with strict role separation
- File-based signal protocol for structured result metadata
- Mandatory async pattern for non-blocking execution
- Runtime task-notification for completion tracking
- Three-tier model strategy optimizes cost vs quality

**Target Audience**: Both human developers (understanding architecture) and AI agents (self-reference during execution).

## When to Use

Use mux for tasks that require:

1. **Parallel Research**: Gathering external knowledge on multiple subjects simultaneously
2. **Codebase Analysis**: Auditing existing code against requirements or pillars
3. **Complex Deliverables**: Creating multi-component specs, roadmaps, or analyses
4. **Research-to-Implementation**: Synthesizing external knowledge into actionable plans
5. **Quality-Critical Work**: Deliverables requiring review gates and validation

**Do NOT use for**:
- Simple single-file edits (use direct agent delegation)
- Tasks without research/analysis phase
- Synchronous user interactions requiring immediate response
- Tasks under 5KB output (overhead exceeds benefit)

## Core Architecture

### Agent Hierarchy

Six specialized agents operate in a clear hierarchy:

| Agent | Model Tier | Subagent Type | Primary Role |
|-------|------------|---------------|--------------|
| Researcher | sonnet (medium) | general-purpose | Web research and synthesis |
| Auditor | sonnet (medium) | general-purpose | Codebase gap analysis |
| Consolidator | sonnet (medium) | general-purpose | Aggregate findings |
| Coordinator | opus (high) | general-purpose | Design structure, delegate writing |
| Writer | sonnet (medium) | general-purpose | Write deliverable components |
| Sentinel | sonnet (medium) | general-purpose | Phase review, quality gate |

**Role Details**:

**Researcher** (External Knowledge):
- Gathers information via WebSearch
- Synthesizes findings into structured markdown (3-5KB)
- Outputs include TOC + Executive Summary format

**Auditor** (Internal Knowledge):
- Analyzes codebase using Glob/Grep/Read tools
- Identifies gaps between current state and requirements
- Produces audit reports (3-5KB) with actionable findings

**Consolidator** (Aggregation):
- Reduces 80KB+ of research/audit outputs to manageable size
- Extracts relevant findings with citations to source files
- Produces 5-8KB consolidated summary for coordinator input

**Coordinator** (Structure Design):
- High-tier reasoning to design optimal deliverable structure
- Decides: single file vs index+components, DAG dependencies, size targets
- Delegates all writing to worker agents (never writes itself)

**Writer** (Component Creation):
- Creates specific deliverable components per coordinator instructions
- Validates size targets (trim if over target+2KB)
- Enforces TOC + Executive Summary format

**Sentinel** (Quality Assurance):
- Ruthless review to catch gaps before user sees deliverable
- Audits signals, reads deliverables, assesses quality
- Proposes actions with CRITICAL/HIGH/MEDIUM/LOW priority
- Advisory only (orchestrator decides whether to act)

### Model Tier Strategy

| Tier | Model | Cost | Use Cases |
|------|-------|------|-----------|
| Low | haiku | $ | (Reserved for future lightweight tasks) |
| Medium | sonnet | $$ | Researcher, Auditor, Writer, Consolidator, Sentinel |
| High | opus | $$$ | Coordinator (structure design requires reasoning) |

**Rationale**:
- **Sonnet for Workers**: Balance of capability and cost, parallel execution multiplies cost
- **Opus for Coordinator**: ONE critical decision (structure design) vs MANY execution tasks
- **Sonnet for Sentinel**: Quality review follows checklist, volume makes opus prohibitive

**Cost Example** (5 research + 1 consolidation + 1 coordination + 5 writing):
- All opus: ~$5.00
- Tiered: ~$0.50 (10x savings)
- All haiku: ~$0.05 (unusable quality)

## Core Patterns

### File-Based Communication

**Principle**: Agents communicate via file PATHS, NEVER inline content.

**Good**:
```python
Task(prompt="Read {input_path}. Write to {output_path}. Signal: {signal_path}")
```

**Bad**:
```python
Task(prompt="Here is the research: [10KB content]. Write deliverable.")
```

**Why**:
- Prevents prompt bloat and context pollution
- Enables lazy evaluation (agent only reads if needed)
- Natural batching (multiple paths in one prompt)
- Audit trail (all paths in signal files)

### Signal Protocol

**Purpose**: Structured result metadata for worker outputs.

**Format** (~50 bytes):
```
path: tmp/mux/.../research/001-topic.md
size: 4523
status: success
```

**Extensions**:
- `.done` = success
- `.fail` = failure (includes error field)

**Creation**:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
    --path "$OUTPUT_PATH" \
    --status success
```

**Why This Exists**:
- Workers write signal files as structured metadata about their outputs
- Signal files persist as audit trail
- Parallel-friendly (no serialization needed)
- Orchestrator reads them AFTER receiving task-notification

### Completion Tracking

**Primary Mechanism**: Runtime task-notification delivers per-worker completion signals.

**Batch-Completion Counting Pattern**:
```python
# 1. Launch workers in background
for item in items:
    Task(
        prompt=f"...",
        run_in_background=True
    )

# 2. Orchestrator continues immediately - NO waiting
voice(f"{len(items)} workers launched")

# 3. Runtime delivers N task-notifications (one per worker)
# 4. After receiving all N notifications, run verify.py once
Bash(f"uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py {session_dir} --action summary")
```

**Fallback**: If fewer than N notifications arrive within timeout, use one-shot checker:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/check-signals.py {session_dir} --expected {N}
```

**Voice Updates**:
- Voice announcements at phase milestones (not per-worker)
- User hears: "5 research workers launched", "Research phase complete"
- Keeps orchestrator context clean while providing async feedback

### Output Format Protocol

**Mandatory Structure** (every agent output file):

```markdown
# {Title}

## Table of Contents
- [Executive Summary](#executive-summary)
- [Section 1](#section-1)

## Executive Summary

**Purpose**: {1 sentence}
**Key Findings**:
- Finding 1
- Finding 2

**Next Steps**:
- Action 1

---

## Section 1
{Detailed content}
```

**Why This Structure**:
1. **Table of Contents**: Navigation without reading full file
2. **Executive Summary**: Enables bounded extraction via extract-summary.py
3. **Horizontal rule (---)**: Marks boundary between summary and detail
4. **Consistent sections**: Predictable structure for downstream processing

**Enforcement**: Sentinel validates format compliance and flags violations with WARN grade.

**Size Targets**:

| Document Type | Target | Maximum |
|---------------|--------|---------|
| Research | 3-5KB | 8KB |
| Audit | 3-5KB | 8KB |
| Consolidated | 5-8KB | 15KB |
| Component | 3-8KB | target + 2KB |
| Index | 2-3KB | 5KB |

### Async Constraints

**Mandatory Pattern** (no exceptions):

**ALL Task() calls**:
```python
Task(
    prompt="...",
    model="sonnet",
    run_in_background=True  # MANDATORY - never omit
)
```

**Why These Constraints Exist**:
- Blocking on workers makes orchestrator unresponsive during long-running tasks
- User cannot query status during execution
- Multiple phases cannot overlap
- Voice updates provide async notification instead

**Violations** (blocked by code):
- `run_in_background=False` or omitted
- Any synchronous waiting loop

## Session Directory Structure

**Standard Layout**:
```
tmp/mux/
  {YYYYMMDD-HHMM-topic}/          # Session root
    research/                      # Phase 2 outputs
      001-subject-focus.md
      002-subject-focus.md
    audits/                        # Phase 3 outputs
      001-audit-focus.md
      002-audit-focus.md
    consolidated/                  # Phase 4 output
      consolidated-summary.md
    deliverable/                   # Phase 5 outputs
      index.md
      components/
        001-component.md
        002-component.md
    .signals/                      # Completion signals
      001-research.done
      002-research.done
      001-audit.done
      consolidated.done
      001-component.done
      002-component.done
```

**Session ID Format**: `{YYYYMMDD-HHMM-topic}`

Example: `20260130-0854-mux-readme`

**Why This Format**:
- Lexicographic sorting = chronological order
- Timestamp ensures uniqueness (no collision risk)
- Topic slug provides human-readable context
- Compatible with ls/find/grep for discovery

**Creation**:
```bash
eval "$(uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/session.py 'topic-slug')"
# SESSION_DIR is now set to tmp/mux/{timestamp}-topic-slug
```

**Persistence**: Session directories are NEVER deleted.

**Why**:
- Audit trail for debugging
- Research reuse across sessions
- Quality analysis over time
- User can manually clean up when disk space matters
- Disk cost: ~100KB per session (mostly signal files)

## Tools Reference

All Python tools use PEP 723 inline dependencies and run via `uv run`.

### session.py - Session Creation

**Purpose**: Create standard directory structure.

**Usage**:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/session.py "topic-slug"
# Output: SESSION_DIR=tmp/mux/20260130-0854-topic-slug
```

**What It Creates**:
- `{timestamp}-{topic}/research/`
- `{timestamp}-{topic}/audits/`
- `{timestamp}-{topic}/consolidated/`
- `{timestamp}-{topic}/.signals/`

**Why PEP 723**: Zero setup, self-contained dependencies, fast execution via uv caching.

### signal.py - Signal Creation

**Purpose**: Create completion signals for verification.

**Usage**:
```bash
# Auto-calculate size from file
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
    --path "$OUTPUT_PATH" \
    --status success

# With explicit size
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SESSION_DIR/.signals/001-name.done" \
    --path "$OUTPUT_PATH" \
    --size 4523 \
    --status success

# Failure signal
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py "$SESSION_DIR/.signals/001-name.fail" \
    --path "$OUTPUT_PATH" \
    --status fail \
    --error "API timeout"
```

**Why Tool Exists**: Enables signal creation via Bash for agents that lack Write tool access.

### verify.py - Signal Verification

**Purpose**: Zero-context verification of completion status.

**Actions**:
```bash
# Count completed workers
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action count

# List failures with errors
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action failures

# Get all output paths
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action paths

# Get individual sizes
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action sizes

# Get total output size (for consolidation decision)
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action total-size

# Combined summary
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action summary
```

**Critical Use Case** (consolidation decision):
```bash
total=$(uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py "$SESSION_DIR" --action total-size)
if [ "$total" -gt 81920 ]; then
    # Launch consolidator
fi
```

### extract-summary.py - Bounded Extraction

**Purpose**: Extract TOC + Executive Summary with hard byte cap.

**Usage**:
```bash
# Default 1KB cap
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py research/001-topic.md

# Custom cap
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py research/001-topic.md --max-bytes 2048
```

**What Gets Extracted**:
1. Title (# heading)
2. Table of Contents
3. Executive Summary
4. Everything up to first `---` separator

**Typical Output**: 500-800 bytes
**Hard Cap**: 1024 bytes (configurable)

**Why This Exists**: Coordinator needs to assess research quality without reading full 5KB files. Bounded extraction prevents context bloat.

**Fallback Strategy**:
1. Extract up to `---` separator (preferred)
2. Extract up to next `##` heading after Executive Summary
3. Extract first 40 lines (emergency fallback)

## Execution Modes

### Standard Mode

Full parallel mux with all phases:

**Phase 1: Decomposition**
- Parse task to extract research subjects, focus areas, output type, pillars
- Determine if lean mode requested

**Phase 2: Fan-Out Research** (if research subjects)
- Launch researcher agents in parallel (1 per subject × focus combination)
- Each produces 3-5KB markdown with external knowledge

**Phase 3: Fan-Out Audits** (if codebase context)
- Launch auditor agents in parallel (1 per focus area)
- Each produces 3-5KB audit report with gap analysis

**Phase 2-3 Completion Tracking**:
```python
# Launch workers in background
for subject in subjects:
    Task(..., run_in_background=True)

# Orchestrator continues immediately - runtime notifies on completion
voice(f"{len(subjects)} workers launched")

# After receiving all N task-notifications, run verify.py once
```

**Phase 4: Consolidation** (if total > 80KB)
- Single consolidator agent reads all research/audit outputs
- Produces 5-8KB consolidated summary with citations

**Phase 5: Coordination**
- Coordinator (opus) designs deliverable structure
- Delegates components to writer agents (parallel batches)
- Writers produce components per coordinator instructions

**Phase 6: Verification**
- Use verify tool to check completion status
- Report to user: "{N} files created"

### Lean Mode

Simplified execution for straightforward tasks.

**Detection**: Keyword "lean" in task description.

**Core Principle**: Simplified EXECUTION, not simplified DELEGATION. Even in lean mode, orchestrator never self-executes.

**What Changes**:

| Aspect | Standard Mode | Lean Mode |
|--------|---------------|-----------|
| Phase 2-3 research | Full parallel mux | Skip or 1 agent |
| Phase 4 consolidation | If >80KB | Skip |
| Phase 5 coordinator | Opus + workers | Single sonnet worker |
| Agent count | 5-10+ | 1-2 |

**What Does NOT Change**:
- Orchestrator still delegates ALL file operations
- Workers still create signal files
- Workers still return only "done"
- Output protocol still enforced
- Session directory still created
- Verification still via signals

**Lean Flow Example**:
```
TASK: "lean - fix extract-summary.py to include TOC"

1. Decompose: single file edit, no research needed
2. Skip Phase 2-3-4
3. Launch ONE writer agent:
   Task(
       prompt="Read ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/writer.md. Fix {file}. OUTPUT: {path}. SIGNAL: {signal}",
       model="sonnet",
       run_in_background=True
   )
4. Verify via signal file when complete
5. Report to user
```

**Critical**: Even for trivial one-line fixes, NEVER do it yourself. Delegate to writer agent.

## Anti-Patterns

**Tool Violations**:
- NEVER use Read/Write/Edit in orchestrator (delegate to agents)
- NEVER use bash polling loops for completion (wait for task-notification, then verify.py)

**Communication Violations**:
- NEVER accept inline content from agents (only "done")
- NEVER pass file content in prompts (pass paths)

**Blocking Violations** (CRITICAL):
- NEVER use `run_in_background=False` or omit it (ALWAYS `True`)
- NEVER wait synchronously for any agent
- NEVER poll signal files in a loop (wait for task-notification)

**Session Management Violations**:
- NEVER delete session directories (keep for debugging/audit)
- NEVER run `rm -rf tmp/mux/*` or similar cleanup commands

**Return Protocol Violations**:
- Agent returning file paths (should be in signal file, not return)
- Agent returning content summaries
- Agent returning key findings
- Agent returning anything except "done"

## Design Decisions

### Why File-Based Signals Instead of Return Values

**Problem**: Agent return values pollute orchestrator context.

**Solution**: Signal files with metadata only (~50 bytes).

**Benefits**:
- Zero-context verification
- Audit trail (signals persist)
- Parallel-friendly (no serialization needed)
- Failure isolation (one .fail signal doesn't block others)

### Why Mandatory Output Format

**Problem**: Without structure, parent agents must read entire files to understand content.

**Solution**: TOC + Executive Summary at top enables:
1. Bounded extraction via extract-summary.py (500-800 bytes vs 5KB)
2. Sentinel can assess quality without full read
3. Coordinator can size-estimate without reading details
4. Consolidator can cite sources with line ranges

**Enforcement**: Sentinel validates format compliance and grades WARN if violated.

### Why Session Directories Persist

**Problem**: Deleting sessions removes audit trail and debugging context.

**Solution**: Keep all session directories indefinitely.

**Benefits**:
- Debugging failed runs
- Reusing research across sessions
- Quality analysis over time
- User can manually clean up when disk space matters

**Disk Cost**: ~100KB per session (mostly signal files, not content).

### Why Sentinel is Advisory Only

**Problem**: Blocking quality gate could halt progress on minor issues.

**Solution**: Sentinel proposes actions with CRITICAL/HIGH/MEDIUM/LOW priority. Orchestrator decides whether to act.

**Rationale**:
- Iterative improvement vs perfection paralysis
- User can override sentinel recommendations
- Sentinel learns from patterns (institutional knowledge)
- CRITICAL gaps can still be escalated via voice alerts

### Why Coordinator Uses Opus

**Problem**: Structure design is complex (DAG dependencies, size estimation, split decisions).

**Example Decision**:
- Should deliverable be single file or index + components?
- Which components can be written in parallel?
- What size target for each component?
- Which research findings map to which sections?

**Solution**: Use opus for ONE critical decision vs sonnet for MANY execution tasks.

**Cost Justification**: 1 opus call ($0.10) vs 5 sonnet writers ($0.25). Quality of structure design determines entire deliverable quality.

### Why PEP 723 for Tools

**Problem**: Traditional Python scripts require dependencies in pyproject.toml or virtual env management.

**Solution**: PEP 723 inline metadata enables `uv run script.py` without project setup.

**Example**:
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
```

**Benefits**:
- Zero setup (uv creates ephemeral venv)
- Self-contained (dependencies in script)
- Fast execution (uv caches)
- Portable (works across projects)
