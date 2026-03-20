# ac-safety

Security guardrails plugin for Claude Code.

## Hooks

All hooks use fail-close: errors deny the operation.

- credential-guardian: blocks Read/Grep/Glob access to credential files
- destructive-bash-guardian: blocks destructive Bash commands by category
- write-scope-guardian: restricts Write/Edit to allowed paths
- supply-chain-guardian: blocks unapproved package installations
- playwright-guardian: restricts Playwright/MCP tool usage

Configuration: `safety.yaml` (project > `~/.claude/safety.yaml` > plugin defaults)
