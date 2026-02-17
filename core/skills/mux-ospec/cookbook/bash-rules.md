# Bash Restrictions

Orchestrator Bash usage is LIMITED to these EXACT tools.

## Allowed Commands

| Command | Purpose |
|---------|---------|
| `uv run .claude/skills/mux/tools/session.py` | Create session directory |
| `uv run .claude/skills/mux/tools/verify.py` | Check signal counts/status |
| `uv run .claude/skills/mux/tools/signal.py` | Create signals (emergency) |
| `uv run .claude/skills/mux/tools/check-signals.py` | One-shot signal count check |
| `uv run .claude/skills/mux/tools/agents.py` | List/register agents |
| `uv run $MUX_TOOLS/*.py` | Environment variable form |
| `mkdir -p` | Create directories |
| `ls` | List directories only |

## Explicit Blocklist (FATAL)

| Command | Violation |
|---------|-----------|
| `git status` | Repository inspection |
| `git diff` | Content inspection |
| `git log` | History inspection |
| `git show` | Commit inspection |
| `cat` / `head` / `tail` | File reading |
| `grep` / `rg` | Content search |
| `find` | File search |
| `python *` | Script execution |
| `node *` | Script execution |
| `pytest` / `npm test` | Test execution |
| `uv run tools/setup.py` | Project tools |
| `uv run pyright` | Type checking |
| `uv run ruff` | Linting |
| `/spec *` | Skill invocation via shebang |
| `source *` | Shell sourcing |

## Evidence of Violations (Real Examples)

```bash
# FATAL - orchestrator read spec directly
cat specs/2026/02/branch/001-feature.md

# FATAL - orchestrator ran tests
pytest tests/test_integration.py

# FATAL - orchestrator inspected git
git status --porcelain | head -30

# FATAL - orchestrator used grep
grep -rn "pattern" specs/ --include="*.md"

# FATAL - orchestrator invoked spec skill directly
/spec PLAN specs/2026/02/branch/001-feature.md
```

## Correct Delegation

```python
# Reading spec file -> delegate to stage agent
Task(prompt="""Invoke Skill(skill="spec", args="PLAN {spec_path}").
CONSTRAINTS: Do NOT read source files directly.""",
model="opus", run_in_background=True)

# Running tests -> delegate to tester agent
Task(prompt="Read agents/spec-tester.md. Detect framework and run tests.",
model="sonnet", run_in_background=True)

# Git inspection -> delegate to sentinel
Task(prompt="Read agents/sentinel.md. Check git status and verify commits.",
model="opus", run_in_background=True)

# Pattern search -> delegate to auditor
Task(prompt="Search for pattern X in codebase. Report findings.",
model="sonnet", run_in_background=True)
```

## Rationale

- Every bash command beyond `tools/*.py` pollutes context
- "Quick checks" become habit, eroding delegation discipline
- If it's worth checking, it's worth delegating to a specialist agent
- Direct file reading leads to orchestrator implementing instead of delegating
- When context is full, your session dies mid-workflow
- The orchestrator's job is coordination, not execution

## Why This Matters for mux-ospec

The o_spec workflow has a particularly dangerous failure mode: orchestrators reading spec files directly. When the orchestrator reads the spec:

1. Spec content (potentially 10K+ tokens) enters orchestrator context
2. Orchestrator sees what needs to be done
3. Orchestrator "helpfully" implements it directly instead of delegating to /spec IMPLEMENT
4. Spec file remains empty (no commit)
5. Workflow state is lost
6. No structured artifacts produced

The bash whitelist prevents this by making spec file reading impossible at the orchestrator level. All spec interaction MUST go through Task() delegation to spec stage agents.
