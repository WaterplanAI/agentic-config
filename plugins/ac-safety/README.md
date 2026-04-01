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
| `harden-supply-chain-sec` | Harden supply chain security: configure minimum release age, detect frozen-lockfile patterns, apply dependency policies across package managers |

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

# Harden supply chain security (dry-run preview first)
/harden-supply-chain-sec

# Harden with guided mode (interactive prompts at each step)
/harden-supply-chain-sec --guided

# Harden with post-config hardening (dependency policies, security agents)
/harden-supply-chain-sec --harden

# Override a category at project level
echo 'supply_chain:\n  categories:\n    pip-direct: allow' > safety.yaml
```

## Verified Behavior

Global minimum release age configuration has been empirically verified on macOS (2026-04-01):

| Manager | Version | Global config | Verification method | Result |
|---------|---------|---------------|---------------------|--------|
| uv | 0.9.21 | `~/.config/uv/uv.toml` | `uvx ruff@latest` resolved 0.15.7 (skipped 0.15.8, 6d old); PEP 723 inline override and global fallback confirmed | Pass |
| Bun | 1.3.3 | `~/.bunfig.toml` | `bun install --dry-run` blocked npm@11.12.1 (5d old) with explicit age gate error | Pass |
| npm | 11.12.0 | `~/.nvm/.../etc/npmrc` | `npm config get before --global` returns dynamic `now - 7d` timestamp; shifts with wall clock | Pass |
| pnpm | 10.19.0 | `~/Library/Preferences/pnpm/rc` | `pnpm config get minimum-release-age` returns 10080 | Pass |
| Yarn | 4.13.0 | `~/.yarnrc.yml` | `npmMinimalAgeGate` read and enforced from home `.yarnrc.yml` | Pass |

Details in `skills/harden-supply-chain-sec/SKILL.md` Section 17.

## License

MIT
