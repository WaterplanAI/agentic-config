# Bash Restrictions

Orchestrator Bash usage is LIMITED to these EXACT tools.

**Enforcement:** Skill-scoped hook (`mux-orchestrator-guard.py`) validates every Bash command against a whitelist. Non-whitelisted commands are HARD-BLOCKED (denied by hook before execution).

## Allowed Commands

| Command | Purpose |
|---------|---------|
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/session.py` | Create session directory |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py` | Check signal counts/status |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py` | Create signals (emergency) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/check-signals.py` | One-shot signal check (fallback) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py` | Bounded report access (TOC + Executive Summary) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/agents.py` | List/register agents |
| `mkdir -p` | Create directories |

## Explicit Blocklist (FATAL)

| Command | Violation |
|---------|-----------|
| `npx *` | Runtime execution |
| `npm *` | Package operations |
| `cdk *` | CDK commands |
| `git status` | Repository inspection |
| `git diff` | Content inspection |
| `git log` | History inspection |
| `git show` | Commit inspection |
| `grep` / `rg` | Content search |
| `find` | File search |
| `cat` / `head` / `tail` | File reading |
| `python *` | Script execution |
| `node *` | Script execution |
| `cargo *` / `go *` | Build commands |
| `make` / `gradle` / `mvn` | Build commands |

## Evidence of Violations (Real Examples)

```bash
# FATAL - orchestrator ran CDK directly
npx cdk synth SdcStack

# FATAL - orchestrator inspected git
git status --porcelain | head -30

# FATAL - orchestrator ran grep
grep -rn "pattern" --include="*.md"
```

## Correct Delegation

```python
# CDK validation -> agent with skill
Task(prompt="Invoke /build-validate skill.", model="sonnet", run_in_background=True)

# Git inspection -> sentinel
Task(prompt="Read ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/sentinel.md. Check git status.", model="sonnet", run_in_background=True)

# Pattern search -> auditor
Task(prompt="Read ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/auditor.md. Search for pattern.", model="sonnet", run_in_background=True)
```

## Hook Whitelist Patterns

The orchestrator hook (`mux-orchestrator-guard.py`) enforces these regex patterns:

```python
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",                          # Create directories
    r"^uv\s+run\s+.*tools/",                    # Any tools/ invocation
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/",  # MUX skill tools (explicit)
]
```

Any command not matching these patterns is DENIED by the hook before execution.

## Rationale

- Every bash command beyond tools/ pollutes context
- "Quick checks" become habit, eroding discipline
- If it's worth checking, it's worth delegating
- **When context is full, your session dies**
- Hook enforcement makes violations impossible, not just discouraged
