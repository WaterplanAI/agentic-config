# Getting Started

Setup and first use of agentic-config for AI-assisted development workflows.

## Prerequisites

- Claude Code CLI with plugin support (`claude plugin install` available) for Claude Code setup
- Pi CLI (`pi install` available) for pi package setup
- Git (for Claude marketplace access)

## Install for Claude Code

Add the marketplace, then install plugins:

```bash
claude plugin marketplace add WaterplanAI/agentic-config

claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
claude plugin install ac-safety@agentic-plugins
claude plugin install ac-audit@agentic-plugins
```

## Install for pi

The current primary pi install path uses the validated root umbrella package from a git ref.

### Team and automation install: pin a release tag

```bash
pi install "git:github.com/WaterplanAI/agentic-config@v0.2.6" -l
```

Use the equivalent SSH git source for the same repository and tag when needed.

For teams, prefer a committed `.pi/settings.json` pinned to the release tag so pi can auto-install the same reproducible package set on startup:

```json
{
  "packages": [
    "git:github.com/WaterplanAI/agentic-config@v0.2.6"
  ]
}
```

### Local testing and development: use a branch ref

```bash
pi install "git:github.com/WaterplanAI/agentic-config@main" -l
```

Use a feature branch name instead of `main` when testing unpublished pi changes.

### Package-root testing during development

The git root install exposes the full shipped pi surface. When you need to validate individual package roots during development, use local package paths such as:

```bash
pi install ./packages/pi-compat -l
pi install ./packages/pi-ac-meta -l
pi install ./packages/pi-ac-workflow -l
```

For bundled package roots such as `pi-all`, use the staged local testing flow from the [Pi Package Adoption Guide](../packages/README.md#local-package-testing-before-distribution).

Publishing the per-package npm surface remains future work. See the [Pi Package Adoption Guide](../packages/README.md) for the full install matrix.

## Enable Auto-Updates (Recommended)

> **Warning:** Auto-updates are disabled by default for third-party marketplaces.
> Without auto-updates, you must manually run `Update marketplace` to receive new
> plugin versions and skills.

1. Run `claude` and type `/plugins`
2. Navigate to **Marketplaces** tab
3. Select **agentic-plugins**
4. Select **Enable auto-update**

This keeps the marketplace and all installed plugins automatically in sync with new releases.

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

See [Plugin Catalog](plugin-catalog.md) for all skills across 7 plugins.

## Customization

### AGENTS.md + Symlinks

- `AGENTS.md` -- Primary file with standard guidelines (receives updates)
- `CLAUDE.md` -- Symlink to AGENTS.md (for Claude Code)
- `GEMINI.md` -- Symlink to AGENTS.md (for Gemini)

Add project-specific customizations directly to AGENTS.md.

## What Gets Installed

**Claude Code plugins (via `claude plugin install`):**
- `ac-workflow`, `ac-git`, `ac-qa`, `ac-tools`, `ac-meta`, `ac-safety`, `ac-audit`
- No symlinks -- plugins load from `~/.claude/plugins/cache/`

**Pi packages (via `pi install`):**
- `@agentic-config/pi-all` for the full shipped surface, or selective `@agentic-config/pi-*` packages
- Team rollout is typically versioned in committed `.pi/settings.json`

**Copied (project-customizable):**
- `AGENTS.md` -- Project-specific guidelines
- `CLAUDE.md`, `GEMINI.md` -- Symlinks to AGENTS.md

## Development Mode

For active development on agentic-config itself:

```bash
./dev.sh    # launches claude with all 7 --plugin-dir flags
```

## Troubleshooting

**Reinstall plugins:**
```bash
claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
claude plugin install ac-safety@agentic-plugins
claude plugin install ac-audit@agentic-plugins
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
- [Distribution Guide](distribution.md) -- Claude marketplace rollout plus pi git-tag distribution, dev branch installs, and future npm notes
- [Pi Package Adoption Guide](../packages/README.md) -- primary git-tag installs, branch-based dev installs, local package-root testing, and future npm distribution notes
- [Migration Guide v0.2.0](migration-v0.2.0.md) -- Migrate from v0.1.x symlinks
- [External Specs Storage](external-specs-storage.md) -- Configure external specs repository
