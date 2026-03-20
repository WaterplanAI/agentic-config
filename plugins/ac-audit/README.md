# ac-audit

Tool audit logging -- JSONL audit trail and real-time systemMessage display for Claude Code.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-audit@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-audit@agentic-plugins --scope user
claude plugin install ac-audit@agentic-plugins --scope project
claude plugin install ac-audit@agentic-plugins --scope local
```

## Hooks

| Hook | Trigger | Description |
|------|---------|-------------|
| `tool-audit` | PreToolUse (*) | Logs all tool invocations to JSONL, displays configured tools via systemMessage |

Fail-close: errors deny the operation.

## Configuration

Three-tier config resolution: project `audit.yaml` > `~/.claude/audit.yaml` > plugin defaults. Higher-priority tiers override lower ones.

```yaml
# Example: audit.yaml
log_dir: "/var/log/claude-audit"
log_permissions: 384  # 0o600
max_words: 50
display_tools:
  - "Bash"
  - "Write"
```

## Usage

No manual invocation needed. Hooks fire automatically on all tool calls when the plugin is installed.

## License

MIT
