# agentic-config

Project-agnostic, composable configuration system for AI-assisted development workflows.

## Quick Start

```bash
claude plugin marketplace add WaterplanAI/agentic-config
# For dev branch: `claude plugin marketplace add </path/to/dev/branch>` OR `./dev.sh`

claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
claude plugin install ac-safety@agentic-plugins
claude plugin install ac-audit@agentic-plugins
```

> **Note:** Auto-updates are disabled by default for third-party marketplaces.
> Enable them via `/plugins` > Marketplaces > agentic-plugins > Enable auto-update
> to stay in sync with new releases automatically.

See [Getting Started](docs/getting-started.md) for full setup.

## What is agentic-config?

A centralized configuration system with a Claude Code plugin architecture first in v0.2.0.

Future releases will extend the same plugin approach to additional tools (Cursor, Codex CLI, Gemini CLI, and Antigravity).

Core principles:

1. **Project-agnostic** -- Works in any codebase without modification
2. **Composable** -- Skills invoke other skills, creating compounding automation
3. **CC-native distribution** -- Install via `claude plugin install`, no symlinks

## Plugins

| Plugin | Focus | Skills |
|--------|-------|--------|
| `ac-workflow` | Spec workflow, MUX orchestration | 6 |
| `ac-git` | Git automation, PRs, releases | 7 |
| `ac-qa` | QA, E2E testing, browser automation | 7 |
| `ac-tools` | Utilities, integrations, bootstrap | 16 |
| `ac-meta` | Meta-prompting, self-improvement | 2 |
| `ac-safety` | Security guardrails (credential, write-scope, destructive-bash, supply-chain, playwright) | 1 |
| `ac-audit` | Tool audit logging (JSONL append-only log) | 1 |

## Documentation

- [Getting Started](docs/getting-started.md) -- Install, setup, first use
- [Plugin Catalog](docs/plugin-catalog.md) -- All 40 skills with composition patterns
- [Distribution Guide](docs/distribution.md) -- Team adoption and private marketplace
- [Migration Guide v0.2.0](docs/migration-v0.2.0.md) -- Migrate from v0.1.x
- [Uninstall Legacy (v0.1.x)](docs/migration-v0.2.0.md#step-1-remove-old-symlinks) -- Remove legacy symlink wiring
- [Full Documentation Index](docs/index.md)

## Permissions

MUX workflows (`ac-workflow` plugin) delegate to background agents via `Task(run_in_background=True)`. Background agents **cannot surface interactive permission prompts** -- any unapproved tool is auto-denied.

**Recommended:** Run Claude Code with `--dangerously-skip-permissions` for MUX workflows:

```bash
claude --dangerously-skip-permissions
```

Alternatively, pre-authorize specific tools via CLI:

```bash
claude --allowedTools "Skill Bash Read Write Edit Grep Glob"
```

All plugins in this repository are designed and tested with full tool permissions enabled.

## Contributing

See [Contributing Guidelines](.github/CONTRIBUTING.md).

## License

[MIT License](LICENSE)
