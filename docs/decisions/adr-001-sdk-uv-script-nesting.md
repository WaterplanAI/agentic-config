# ADR-001: SDK-as-UV-Script for Depth-N Agent Nesting

## Status

Accepted

## Date

2026-02-07

## Context

Claude Code agents using the built-in Team API are capped at depth-1: spawned agents lack the Task tool, preventing recursive sub-agent creation. Production workflows requiring depth-3+ nesting (discovery-driven research, hierarchical review, multi-stage orchestration where work shape is unknown at dispatch time) need an alternative spawning mechanism.

A 5-agent jury (3 high-tier, 2 medium-tier) evaluated 4 candidate approaches across 26 weighted criteria. The user's stated priorities, in rank order:

1. **Composability** (weight 1.00) -- reuse depth-0/1 patterns at depth-N unchanged
2. **Leader context preservation** (weight 0.95) -- structured, bounded results flowing up
3. **Agent specialization** (weight 0.90) -- deep per-depth specialization

The jury's winner (Approach A: Custom MCP Server, score 3.90) identified the right architectural qualities but required days of custom infrastructure. Post-jury analysis revealed an emergent hybrid -- Approach C' (SDK-as-UV-Script) -- that achieves A's composability without A's infrastructure cost, and C's integration without C's per-workflow boilerplate.

## Decision Drivers

Ranked by the user's stated priorities:

1. **Composability** -- Same invocation pattern at every depth; existing skills/tools work unmodified
2. **Context preservation** -- Structured, schema-validated results; bounded context window pressure
3. **Specialization** -- Per-depth agent configuration: tools, prompts, permissions, model tier
4. **Zero infrastructure** -- No separate server processes, health checks, or custom protocol maintenance
5. **Ecosystem alignment** -- Leverage existing uv-based tooling patterns already in the codebase

## Considered Options

### A: Custom MCP Server

Build a `spawn_agent` MCP tool as a standalone server process. Agents at any depth call the same tool to spawn sub-agents. Structured input (params) and output (results) via MCP protocol.

### B: `claude -p` from Bash

Shell out via Bash tool: `claude -p "prompt" --dangerously-skip-permissions`. Zero code required. Empirically confirmed working at depth-3 (~13s latency).

### C: Claude Code SDK (Direct)

Use `claude-agent-sdk` Python package to spawn sub-agents programmatically. Full tool access, structured returns, session management. Requires wrapper scripts per workflow pattern.

### D: Fan-out with Dependency Ordering

Flatten all work to depth-1 using the built-in Task tool with `blockedBy` dependency ordering. No nesting; leader pre-decomposes all work upfront.

### C': SDK-as-UV-Script (Emergent Hybrid)

PEP 723 single-file Python scripts with inline `claude-agent-sdk` dependency, executed via `uv run spawn.py args`. Combines A's universal composability (callable from Bash, skills, MCP, agents) with C's SDK integration (structured output, session management), while eliminating both approaches' main weaknesses (A's infrastructure, C's boilerplate).

## Decision

Adopt **Approach C' (SDK-as-UV-Script)** as the canonical pattern for depth-N agent nesting.

The key insight: a PEP 723 script with inline `claude-agent-sdk` dependency is simultaneously:

- A **Bash-callable tool** (composable from any context via `uv run script.py args`)
- A **full SDK client** (structured output, session management, tool access)
- A **self-contained executable** (no external config, no server process, no package.json)

This collapses the gap between Approach A (MCP) and Approach C (SDK). The `uv run` invocation is the universal calling convention -- identical at depth-0, depth-1, or depth-N.

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["claude-agent-sdk"]
# ///

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for msg in query(
        prompt="Execute assigned task",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Bash"],
            output_format={"type": "json_schema", "schema": result_schema}
        )
    ):
        ...  # Process structured result

asyncio.run(main())
```

**Invocation** (same at every depth): `uv run spawn.py --task "research X" --model medium-tier`

## Evaluation Summary

Jury scores (26 criteria, weighted 0.30-1.00, normalized to 5-point scale):

| Rank | Approach | Score | Composability | Context Pres. | Specialization | Integration | Infra Cost |
|------|----------|-------|---------------|---------------|----------------|-------------|------------|
| 1st | A: Custom MCP Server | 3.90 | 5/5 | 5/5 | 5/5 | 4/5 | 2/5 |
| 2nd | C: Claude Code SDK | 3.67 | 4/5 | 4/5 | 4/5 | 5/5 | 3/5 |
| 3rd | D: Fan-out Dependencies | 3.44 | 2/5 | 3/5 | 2/5 | 2/5 | 5/5 |
| 4th | B: `claude -p` Bash | 2.66 | 3/5 | 2/5 | 3/5 | 3/5 | 5/5 |
| -- | **C': SDK-as-UV-Script** | *Post-jury* | **5/5** | **5/5** | **4/5** | **5/5** | **5/5** |

C' was not scored by the jury (it emerged after deliberation). The projected scores reflect that C' inherits A's composability (universal callable pattern) and C's integration (SDK native), while eliminating A's infrastructure cost and C's per-workflow boilerplate.

### Top-3 Criteria Breakdown (Highest User Priority)

| Criterion | Weight | A (MCP) | B (Bash) | C (SDK) | D (Fan-out) |
|-----------|--------|---------|----------|---------|-------------|
| C1: Composability | 1.00 | 5 | 3 | 4 | 2 |
| C2: Leader Context | 0.95 | 5 | 2 | 4 | 3 |
| C3: Specialization | 0.90 | 5 | 3 | 4 | 2 |
| C4: Separation of Concerns | 0.85 | 5 | 3 | 4 | 4 |
| C5: Info Flow Direction | 0.80 | 5 | 2 | 4 | 3 |

### Failure Mode Highlights

| Criterion | Weight | A (MCP) | B (Bash) | C (SDK) | D (Fan-out) |
|-----------|--------|---------|----------|---------|-------------|
| C19: Resource Exhaustion | 0.45 | 3 | 1 | 3 | 5 |
| C25: Worst-Case Failure | 0.40 | 3 | 2 | 3 | 4 |
| C18: Orphaned Processes | 0.45 | 3 | 2 | 3 | 5 |
| C17: Observability | 0.50 | 4 | 2 | 3 | 5 |

## Consequences

### Positive

- **Universal composability**: `uv run script.py args` works identically from Bash, skills, MCP tools, agents, and slash commands at any depth
- **Zero infrastructure**: No MCP server to build, deploy, monitor, or version. Just Python files
- **Self-contained scripts**: PEP 723 inline dependencies eliminate external configuration (no package.json, node_modules, pyproject.toml)
- **Structured I/O**: SDK's `output_format` provides JSON schema validation; leader receives typed, parsed results
- **Ecosystem alignment**: Matches existing uv-based tool patterns already in the codebase (mux tools, gsuite tools)
- **Type safety**: Python type hints, pyright validation via `uvx --from pyright --with claude-agent-sdk pyright script.py`
- **Cost tracking**: SDK's `ResultMessage` provides `total_cost_usd`, `usage`, `duration_ms` per spawned agent

### Negative

- **SDK dependency**: Tight coupling to `claude-agent-sdk` API stability. Breaking changes in the SDK propagate to all spawn scripts
- **Python requirement**: Agents spawned via this pattern must use Python. Not usable from pure-shell or Node.js-only environments without adaptation
- **No built-in recursion limits**: Depth counter must be explicitly implemented per script. Developer discipline required
- **Cold start**: First `uv run` invocation incurs dependency resolution (~2-5s). Subsequent runs use cached environments
- **Process isolation model**: Each spawned agent is a separate OS process. No shared memory or in-process communication

### Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Orphaned processes**: Parent crash leaves child agents running | Medium | Implement PID tracking in session registry; add cleanup on session teardown; use process groups |
| **Resource exhaustion**: Recursive spawning without depth limit | High | Enforce `--max-depth N` parameter in spawn script; reject spawns beyond limit; circuit breaker pattern |
| **Cascading failures**: Depth-3 failure not propagated to depth-1 | Medium | Structured error returns via SDK; signal files (.fail) for async failure detection; timeout propagation |
| **SDK breaking changes**: API incompatibility on upgrade | Low | Pin SDK version in PEP 723 metadata (`claude-agent-sdk>=X.Y,<X+1`); use `[tool.uv] exclude-newer` for reproducibility |
| **Token multiplication**: Each depth level multiplies system prompt cost | Medium | Use minimal system prompts per depth; configure `system_prompt` to avoid full Claude Code preset at leaf agents |
| **Permission bypass**: SDK agents run outside Claude Code permission model | Medium | Implement custom permission checks in spawn script; restrict `allowed_tools` per agent config |

## Dissenting Opinions

### Strong Dissent: Pragmatist (medium-tier, Juror 3)

The Pragmatist's ranking was the **exact inverse** of the jury verdict: D (4.10) > B (3.85) > C (3.35) > A (2.65).

Core arguments:

1. Could not identify a compelling use case where depth-3 is strictly necessary vs depth-1 fan-out. The existing mux skill demonstrates 7-phase, 7-agent-type orchestration at depth-1
2. `claude -p` works TODAY at depth-3 in ~13s with zero code -- empirically confirmed during evaluation
3. MCP server requires days of development for unproven benefit
4. `--dangerously-skip-permissions` required for non-interactive `claude -p` bypasses all permission guardrails at depth-2+

Recommendation: Hybrid B+D -- use fan-out as default, fall back to `claude -p` for runtime-discovered subtasks.

**Majority response**: The user's stated priorities explicitly rank composability above implementation speed. The "decompose everything to depth-1" argument breaks down for dynamic, discovery-driven workflows where work shape is unknown at orchestration time. The `--dangerously-skip-permissions` concern actually strengthens the case for SDK-based approaches that can enforce their own permission model.

**Partial acceptance**: The jury accepted using `claude -p` for prototyping during implementation, and maintaining fan-out as default for pre-decomposable workflows.

### Moderate Dissent: Failure Analyst (medium-tier, Juror 4)

Argument: If failure resilience were the primary concern, Approach D would win. D scores 4-5 on nearly all resilience metrics. The catastrophic risks of deep nesting (resource exhaustion, cascading failures) make flattening fundamentally safer.

**Resolution**: The user explicitly prioritizes composability and specialization above resilience. C' can achieve adequate resilience through depth counters, circuit breakers, and process tracking -- mitigations that are implementable but not built-in.

## Implementation Notes

### Prototype Location

`core/tools/agentic/spawn.py` -- PEP 723 script implementing the spawn pattern.

### Usage Pattern

```bash
# From any agent at any depth:
uv run core/tools/agentic/spawn.py \
  --task "Research authentication patterns" \
  --tools "Read,Grep,Bash" \
  --model medium-tier \
  --max-depth 3 \
  --output /tmp/research-result.json
```

### Integration with Existing Infrastructure

- **Session management**: Works within existing mux session structure (`tmp/mux/YYYYMMDD-HHMM-topic/`)
- **Signal files**: Emits `.done`/`.fail` signals compatible with existing verify/poll infrastructure
- **Agent registry**: Registers spawned agents in session's `.agents/` directory
- **Trace propagation**: Accepts `--parent-trace` for distributed trace ID inheritance

### Fallback Strategy

- **Default**: Fan-out (Approach D) for pre-decomposable workflows
- **Prototyping**: `claude -p` (Approach B) for quick validation
- **Production nesting**: SDK-as-UV-Script (Approach C') for depth-2+ requirements
