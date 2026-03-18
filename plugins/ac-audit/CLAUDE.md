# ac-audit

Tool audit logging plugin for Claude Code.

## Hooks

- tool-audit: logs all tool invocations to JSONL, displays Bash commands via systemMessage

Configuration: `audit.yaml` (project > `~/.claude/audit.yaml` > plugin defaults)
Fail-close: errors deny the operation.
