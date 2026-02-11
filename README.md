# agentic-config

Project-agnostic, composable configuration system for AI-assisted development workflows.

## Quick Start

Install with a single command:

```bash
curl -sL https://raw.githubusercontent.com/MatiasComercio/agentic-config/main/install.sh | bash

# Preview mode (no changes):
curl -sL https://raw.githubusercontent.com/MatiasComercio/agentic-config/main/install.sh | bash -s -- --dry-run
```

Then in any project:
```bash
claude
/agentic setup
```

## What is agentic-config?

A centralized configuration system for AI-assisted development tools (Claude Code, Antigravity, Codex CLI, Gemini CLI) with three core principles:

1. **Project-agnostic** - Commands and skills work in any codebase without modification
2. **Composable** - Commands invoke other commands, creating compounding automation
3. **Flexible installation** - Works at repo root, subdirectory, or with external specs storage

### Core Value: Composability

Commands build upon each other to create powerful workflows:

```
/full-life-cycle-pr           Complete PR from idea to submission
        |
        +---> /po_spec        Phased orchestrator (DAG-aware parallelization)
                |
                +---> /o_spec E2E orchestrator (8-stage workflow)
                        |
                        +---> /spec Single stage execution
```

**Example:** `/full-life-cycle-pr feat/oauth "Add OAuth2"` creates a branch, decomposes the feature into phases, implements each phase through 8 stages, squashes commits, and creates a PR - all with a single confirmation.

See [Commands & Skills Index](docs/index.md) for the complete catalog and detailed composition patterns.

## What Gets Installed

**Symlinked (instant updates):**
- `agents/` - Core workflow definitions
- `.claude/commands/` - Claude Code commands
- `.claude/skills/` - Claude Code skills
- `.gemini/commands/` - Gemini CLI integration
- `.codex/prompts/` - Codex CLI integration

**Copied (project-customizable):**
- `AGENTS.md` - Project-specific guidelines
- `PROJECT_AGENTS.md` - Project overrides (never touched by updates)

## Core Commands

| Command | Description |
|---------|-------------|
| `/agentic setup` | Setup new project |
| `/agentic update` | Update to latest version |
| `/spec STAGE path` | Execute single workflow stage |
| `/o_spec path` | Run full 8-stage workflow |
| `/full-life-cycle-pr branch "desc"` | Complete PR workflow |

See [Commands & Skills Index](docs/index.md) for all 33 commands and 10 skills.

## Customization

### AGENTS.md Pattern

- `AGENTS.md` - Template with standard guidelines (receives updates)
- `PROJECT_AGENTS.md` - Your customizations (never touched by updates)

Updates merge cleanly without conflicts.

### Supported Project Types

| Type | Package Manager | Type Checker | Linter |
|------|----------------|--------------|--------|
| typescript | pnpm | tsc | eslint |
| ts-bun | bun | tsc | eslint |
| python-poetry | poetry | pyright | ruff |
| python-uv | uv | pyright | ruff |
| rust | cargo | cargo check | clippy |
| generic | custom | custom | custom |

Project type is auto-detected or specified with `--type` flag.

## Documentation

- [Commands & Skills Index](docs/index.md) - Complete catalog with composition examples
- [External Specs Storage](docs/external-specs-storage.md) - Configure external specs repository
- [Agent Management Guide](docs/agents/AGENTIC_AGENT.md) - Detailed agent usage
- [Playwright CLI Setup](docs/playwright-cli-setup.md) - E2E browser testing

## Troubleshooting

**Broken symlinks:**
```bash
# In agentic-config repo
/init

# In other projects
~/.agents/agentic-config/scripts/setup-config.sh --force .
```

**Version mismatch:**
```bash
~/.agents/agentic-config/scripts/update-config.sh .
```

## Contributing

See [Contributing Guidelines](.github/CONTRIBUTING.md) for development workflow.

## License

[MIT License](LICENSE)
