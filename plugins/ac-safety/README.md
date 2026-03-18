# ac-safety

Security guardrails -- credential protection, destructive command blocking, write scope enforcement, supply chain control, and browser restrictions.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-safety@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-safety@agentic-plugins --scope user
claude plugin install ac-safety@agentic-plugins --scope project
claude plugin install ac-safety@agentic-plugins --scope local
```

## Hooks

| Hook | Trigger | Default | Description |
|------|---------|---------|-------------|
| `credential-guardian` | PreToolUse (Read\|Grep\|Glob) | DENY | Blocks access to credential files (~/.aws, ~/.ssh, etc.) |
| `destructive-bash-guardian` | PreToolUse (Bash) | DENY | Blocks destructive commands (rm -rf, git push --force, etc.) |
| `write-scope-guardian` | PreToolUse (Write\|Edit\|NotebookEdit) | ASK | Restricts writes to allowed project paths |
| `supply-chain-guardian` | PreToolUse (Bash) | ASK | Blocks unapproved package installations |
| `playwright-guardian` | PreToolUse (mcp__playwright__*) | ASK | Restricts Playwright/MCP tool usage |

All hooks use **fail-close**: errors deny the operation.

## Skills

| Skill | Description |
|-------|-------------|
| `configure-safety` | Interactive safety.yaml customization |

## Configuration

Three-tier config resolution with deep-merge:

1. Project-level: `./safety.yaml` (highest priority)
2. User-level: `~/.claude/safety.yaml`
3. Plugin defaults: `config/safety.default.yaml` (lowest priority)

Category decisions use **most-restrictive-wins**: if project sets `ask` but user sets `deny`, the effective decision is `deny`. Security-critical lists (keys ending in `_prefixes`, `_allowlist`, `_files`, `_filenames`, `_extensions`, `_tools`) are **union-merged** -- higher-priority tiers add entries but cannot remove defaults. Other lists are replaced entirely by higher-priority tiers.

### Category decisions

Each guardian category supports three decisions: `deny`, `ask`, `allow`.

```yaml
# Example: safety.yaml
destructive_bash:
  categories:
    git-destructive: ask    # override default deny -> ask

supply_chain:
  categories:
    npx-packages: allow     # trust npx packages
  npx_allowlist:
    - "@playwright/mcp"
```

## Usage Examples

```
# Customize safety settings interactively
/configure-safety

# Override a category at project level
echo 'supply_chain:\n  categories:\n    pip-direct: allow' > safety.yaml
```

## License

MIT
