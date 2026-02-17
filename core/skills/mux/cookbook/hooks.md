# Hooks Architecture

Skill-scoped hook enforcement for MUX orchestration.

## Overview

MUX uses skill-scoped hooks -- hooks defined in skill frontmatter that ONLY fire when the skill is active. This cleanly separates orchestrator restrictions from subagent permissions.

## How Skill-Scoped Hooks Work

Hooks defined in skill/agent frontmatter are scoped to the component's lifecycle and only run when that component is active. They are automatically cleaned up when the component finishes.

This means:
- Hooks in `mux.md` ONLY fire for the MUX orchestrator
- Hooks in `mux-subagent.md` ONLY fire for subagents that load the skill
- No cross-contamination between orchestrator and subagent hooks
- Hooks are automatically cleaned up when the component finishes

### How This Solves Orchestrator-vs-Subagent Discrimination

Previous versions (v1-v3) used global hooks in `settings.json` with PID-scoped marker files. This had a FATAL flaw: global hooks fire for ALL processes (orchestrator AND subagents). There was no mechanism to distinguish orchestrator from subagent in hook context.

Skill-scoped hooks solve this completely: each component defines its own hooks, scoped to its own lifecycle. The orchestrator loads `mux.md` (with orchestrator hooks), subagents load `mux-subagent.md` (with subagent hooks). No discrimination logic needed -- the hooks are inherently scoped.

## Hook Embedding in Skill Frontmatter

Hooks are defined in the YAML frontmatter of skill files using the `hooks:` key. The syntax is identical to `settings.json` hooks:

```yaml
---
name: skill-name
hooks:
  PreToolUse:
    - matcher: "ToolName|OtherTool"
      hooks:
        - type: command
          command: "path/to/hook-script.py"
---
```

The `matcher` field is a regex matching tool names. The `command` runs on stdin (receives JSON with `tool_name` and `tool_input`) and outputs JSON with a `permissionDecision` (`allow`, `deny`, or `askFirst`).

## MUX Orchestrator Hooks (mux.md)

Defined in `core/skills/mux/SKILL.md` frontmatter. Uses external script: `mux-orchestrator-guard.py`.

### Hook Execution Flow

```
Orchestrator loads mux.md
  -> frontmatter hooks ACTIVATE
  -> PreToolUse intercepts ALL tool calls
  -> Hook script evaluates tool + parameters
  -> ALLOW / DENY / askFirst decision
  -> Hooks CLEANED UP when skill finishes
```

### Enforcement Rules

| Tool | Decision | Reason |
|------|----------|--------|
| Read | DENY (with allowlist) | Use extract-summary.py |
| Write/Edit/NotebookEdit | DENY | Delegate via Task |
| Grep/Glob | DENY (with allowlist) | Delegate via Task |
| WebSearch/WebFetch | DENY | Delegate to researcher |
| TaskOutput | DENY | Use signals |
| Skill | DENY | Context suicide |
| Bash | Whitelist | mkdir -p, uv run tools/* |
| Task | Validate | run_in_background=True required |

### Read Allowlist

Orchestrator MAY read:
- `.claude/skills/mux/*` -- skill files, agents, cookbooks
- `.claude/skills/mux-subagent.md` -- subagent skill
- `/signals/` -- signal metadata
- `tmp/mux/.*/signals/` -- session signal directories

### Grep/Glob Allowlist

Orchestrator MAY search:
- `.claude/skills/` -- skill discovery
- `.claude/hooks/` -- hook discovery

### Bash Whitelist

```python
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",                          # Create directories
    r"^uv\s+run\s+.*tools/",                    # Any tools/ invocation
    r"^uv\s+run\s+\.claude/skills/mux/tools/",  # MUX skill tools
]
```

## MUX Subagent Hooks (mux-subagent.md)

Defined in `core/skills/mux-subagent/SKILL.md` frontmatter. Uses external script: `mux-subagent-guard.py`.

Subagents have their OWN restrictions enforced via the `mux-subagent` skill hooks. They are NOT exempt from MUX restrictions -- they have DIFFERENT restrictions appropriate to their role.

### Enforcement Rules

| Tool | Decision | Reason |
|------|----------|--------|
| TaskOutput | DENY | Use signal files |
| Skill | DENY | No additional skills after mux-subagent |
| Everything else | ALLOW | Subagents need full tool access |

### Why Subagents Block TaskOutput and Skill

- **TaskOutput**: Defeats the async architecture. Subagents must use file-based signals.
- **Skill**: After loading `mux-subagent`, subagents have everything they need. Additional skills would pollute their context.

## Hook Resolution Order

All matching hooks run, in this order:
1. Managed policy settings (enterprise-wide)
2. User settings (`~/.claude/settings.json`)
3. Project settings (`.claude/settings.json`)
4. Local project settings (`.claude/settings.local.json`)
5. Plugin hooks (when enabled)
6. **Skill/agent frontmatter hooks** (when active)

Skill hooks ADD to existing hooks; they do not replace them.

## Interaction with Production Hooks

Existing production hooks in `settings.json` continue to function independently:
- `dry-run-guard.py` -- blocks writes during dry-run
- `git-commit-guard.py` -- blocks --no-verify
- `gsuite-public-asset-guard.py` -- blocks public asset creation

MUX skill hooks add to these; they do not replace them. All matching hooks run in parallel.

## Hard vs Soft Enforcement

| Constraint | Type | Mechanism |
|------------|------|-----------|
| Read blocked (orchestrator) | HARD | mux.md skill hook |
| Write/Edit blocked (orchestrator) | HARD | mux.md skill hook |
| Grep/Glob blocked (orchestrator) | HARD | mux.md skill hook |
| TaskOutput blocked (both) | HARD | mux.md + mux-subagent.md hooks |
| Bash whitelist (orchestrator) | HARD | mux.md skill hook |
| Task run_in_background (orchestrator) | HARD | mux.md skill hook |
| Skill blocked (both) | HARD | mux.md + mux-subagent.md hooks |
| Subagent return `0` | SOFT | mux-subagent skill + agent definitions |
| Signal creation | SOFT | mux-subagent skill + verify.py detection |
| Output file format | SOFT | Agent definitions + sentinel review |

## Hook Scripts

| Script | Location | Scope |
|--------|----------|-------|
| `mux-orchestrator-guard.py` | `core/hooks/pretooluse/` | Orchestrator only (via mux.md frontmatter) |
| `mux-subagent-guard.py` | `core/hooks/pretooluse/` | Subagents only (via mux-subagent.md frontmatter) |

Both scripts are fail-closed: any error in the hook results in DENY (not ALLOW).
