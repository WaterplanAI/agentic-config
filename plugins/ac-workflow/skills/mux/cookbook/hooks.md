# Hooks Architecture

Skill-scoped hook enforcement for MUX orchestration.

## Overview

MUX uses skill-scoped hooks defined in skill frontmatter. These hooks run only while the skill is active, which separates orchestrator restrictions from subagent permissions.

## How Skill-Scoped Hooks Work

Hooks in skill frontmatter are scoped to the lifecycle of that skill and are automatically cleaned up when the skill finishes.

This means:
- Hooks in `skills/mux/SKILL.md` only fire for the MUX orchestrator
- Hooks in `skills/mux-subagent/SKILL.md` only fire for subagents that load `mux-subagent`
- No cross-contamination between orchestrator and subagent enforcement

### Why This Solves Orchestrator vs Subagent Discrimination

Global hooks fire for all processes and require extra discrimination logic. Skill-scoped hooks are inherently contextual: the orchestrator and subagents load different skills, so each gets the correct guard automatically.

## Hook Embedding in Skill Frontmatter

Hooks are defined in YAML frontmatter with the same schema as `settings.json` hooks:

```yaml
---
name: skill-name
hooks:
  PreToolUse:
    - matcher: "ToolName|OtherTool"
      hooks:
        - type: command
          command: "uv run --no-project --script ${CLAUDE_PLUGIN_ROOT}/skills/<skill>/hooks/<guard>.py"
---
```

Hook commands receive JSON on stdin (`tool_name`, `tool_input`) and must emit a valid Claude hook payload with `hookSpecificOutput.permissionDecision`.

## MUX Orchestrator Hook (`mux-orchestrator-guard.py`)

Defined in `${CLAUDE_PLUGIN_ROOT}/skills/mux/SKILL.md`.

### Enforcement Rules

| Tool | Decision | Notes |
|------|----------|-------|
| Read | Allowlisted | Otherwise deny |
| Write/Edit/NotebookEdit | Deny | Delegate via Task |
| Grep/Glob | Allowlisted | Otherwise deny |
| WebSearch/WebFetch | Deny | Delegate to researcher |
| TaskOutput | Deny | Use signal protocol |
| Skill | Allowlisted | Allow direct `Skill(skill="mux-ospec")`; deny all other direct Skill calls |
| Bash | Whitelist | `mkdir -p`, `uv run ...tools/...` |
| Task | Validate | `run_in_background=True` required |
| AskUserQuestion, voicemode, TaskCreate/Update/List, SendMessage | Allow | Explicit allow list |
| Unknown tools | askFirst | Safety fallback |

The `mux-ospec` exception is intentionally narrow: it exists for mux-roadmap phase execution. All other direct `Skill()` calls remain blocked and must be delegated via `Task(run_in_background=True)`.

### Read Allowlist Patterns

The orchestrator guard allows reads only for MUX-critical paths:
- `${CLAUDE_PLUGIN_ROOT}/skills/mux/...`
- `${CLAUDE_PLUGIN_ROOT}/skills/mux-subagent/...`
- Runtime-resolved `.../skills/mux/...` and `.../skills/mux-subagent/...`
- Plugin cache paths `.../plugins/cache/<id>/skills/mux...`
- Signal directories (`.signals`, `tmp/mux/.../.signals/...`)

### Grep/Glob Allowlist Patterns

The orchestrator may search only:
- Skill directories (`${CLAUDE_PLUGIN_ROOT}/skills`, runtime `.../skills/...`, cache variants)
- `.claude/hooks/...`

### Bash Whitelist Patterns

```python
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",
    r"^uv\s+run\s+.*tools/",
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/",
]
```

## MUX Subagent Hook (`mux-subagent-guard.py`)

Defined in `${CLAUDE_PLUGIN_ROOT}/skills/mux-subagent/SKILL.md`.

### Enforcement Rules

| Tool | Decision | Reason |
|------|----------|--------|
| TaskOutput | Deny | Subagents must signal completion via files |
| Everything else (including Skill) | Allow | Subagents need broad execution capability |

## Hook Resolution Order

All matching hooks run in this order:
1. Managed policy settings
2. User settings (`~/.claude/settings.json`)
3. Project settings (`.claude/settings.json`)
4. Local project settings (`.claude/settings.local.json`)
5. Plugin hooks (when enabled)
6. Skill/agent frontmatter hooks (when active)

Skill hooks add enforcement; they do not replace other matching hooks.

## Interaction with Other Production Hooks

Skill-scoped MUX hooks operate alongside plugin-level hooks such as:
- `dry-run-guard.py`
- `git-commit-guard.py`
- `gsuite-public-asset-guard.py`

All matching hooks still run.

## Failure Mode

Both MUX hook scripts are fail-closed: if hook evaluation errors, they emit `deny`.
