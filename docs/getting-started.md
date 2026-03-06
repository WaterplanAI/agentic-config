# Getting Started

Setup and first use of agentic-config for AI-assisted development workflows.

## Prerequisites

- Claude Code CLI with plugin support (`claude plugin install` available)
- Git (for marketplace access)

## Install

Add the marketplace, then install plugins:

```bash
claude plugin marketplace add WaterplanAI/agentic-config

claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
```

## Setup a Project

In any project directory:

```bash
claude
/improve-agents-md setup
```

The `improve-agents-md` skill (part of `ac-tools`) generates and manages AGENTS.md (CLAUDE.md):

1. Auto-detects project type (TypeScript, Python, Rust, etc.)
2. Renders AGENTS.md template with tooling values from `tooling.yml`
3. Injects extras (e.g., PEP 723 for Python types)

### Supported Project Types

| Type | Package Manager | Type Checker | Linter |
|------|----------------|--------------|--------|
| typescript | pnpm | tsc | eslint |
| ts-bun | bun | tsc | eslint |
| python-poetry | poetry | pyright | ruff |
| python-uv | uv | pyright | ruff |
| python-pip | pip | pyright | ruff |
| rust | cargo | cargo check | clippy |
| generic | custom | custom | custom |

Project type is auto-detected or specified with `--type` flag.

## Update

```bash
claude
/improve-agents-md update
```

Regenerates AGENTS.md with latest template.

## Validate

```bash
claude
/improve-agents-md validate
```

Checks AGENTS.md is up-to-date with current template and validates project type detection.

## Core Commands

| Command | Description |
|---------|-------------|
| `/improve-agents-md setup` | Generate AGENTS.md for new project |
| `/improve-agents-md update` | Regenerate AGENTS.md with latest template |
| `/improve-agents-md validate` | Check AGENTS.md is current |
| `/spec STAGE path` | Execute single workflow stage |
| `/mux "prompt"` | Parallel research-to-deliverable orchestration |

See [Plugin Catalog](plugin-catalog.md) for all skills across 5 plugins.

## Customization

### AGENTS.md + Symlinks

- `AGENTS.md` -- Primary file with standard guidelines (receives updates)
- `CLAUDE.md` -- Symlink to AGENTS.md (for Claude Code)
- `GEMINI.md` -- Symlink to AGENTS.md (for Gemini)

Add project-specific customizations directly to AGENTS.md.

## What Gets Installed

**Plugins (via `claude plugin install`):**
- `ac-workflow`, `ac-git`, `ac-qa`, `ac-tools`, `ac-meta`
- No symlinks -- plugins load from `~/.claude/plugins/cache/`

**Copied (project-customizable):**
- `AGENTS.md` -- Project-specific guidelines
- `CLAUDE.md`, `GEMINI.md` -- Symlinks to AGENTS.md

## Development Mode

For active development on agentic-config itself:

```bash
./dev.sh    # launches claude with all 5 --plugin-dir flags
```

## Troubleshooting

**Reinstall plugins:**
```bash
claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
```

**Skill not responding:**
- Use explicit slash command: `/improve-agents-md setup`
- Check plugin is installed: `claude plugin list`
- Reinstall if missing: `claude plugin install ac-tools@agentic-plugins`

**Plugin not found:**
```bash
claude plugin marketplace add WaterplanAI/agentic-config
```

**Uninstall legacy v0.1.x wiring:**
```bash
./uninstall.sh --project --dry-run   # preview project symlink removal
./uninstall.sh --global --dry-run    # preview global wiring removal
```
See [Migration Guide](migration-v0.2.0.md#step-1-remove-old-symlinks) for details.

**Version mismatch:**
```bash
claude
/improve-agents-md update
```

## See Also

- [Plugin Catalog](plugin-catalog.md) -- All skills by plugin
- [Distribution Guide](distribution.md) -- Team adoption tiers and private marketplace
- [Migration Guide v0.2.0](migration-v0.2.0.md) -- Migrate from v0.1.x symlinks
- [External Specs Storage](external-specs-storage.md) -- Configure external specs repository
