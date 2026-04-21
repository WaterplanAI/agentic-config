# agentic-config

Project-agnostic, composable configuration system for AI-assisted development workflows.

## Quick Start

### Pi

Primary install from the current public release tag:

```bash
pi install "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha" -l
```

For teams and automation, prefer the tagged git ref in committed `.pi/settings.json` so the rollout stays reproducible.

For local testing or development, use a branch ref instead of a tag, for example:

```bash
pi install "git:github.com/WaterplanAI/agentic-config@main" -l
```

If you prefer SSH transport, use the equivalent SSH git source for the same repository and ref.

The current git root install exposes the full shipped pi surface. Individual package-root installs remain useful for local package development and validation. npm publication remains future work.

### Claude Code

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

See [Getting Started](docs/getting-started.md) for Claude Code and pi setup.

## Pi Packages

Pi is supported today through a validated root umbrella package installable from git refs, with local package-root installs for development and validation. Publishing the per-package npm surface remains future work.

For teams, prefer a committed `.pi/settings.json` pinned to a release tag. For local testing and development, use branch refs or direct local package paths as appropriate.

Inside `@agentic-config/pi-ac-workflow`, runtime ownership is deliberate: `pimux` is the package-owned tmux control plane, and `ac-workflow-mux`, `ac-workflow-mux-ospec`, and `ac-workflow-mux-roadmap` are structured wrappers on top of it. Generic long-lived tmux work stays on `pimux`; the shipped pi package no longer exposes a separate managed-agent surface.

Quick chooser:
- use `pimux` for a generic long-lived tmux worker, small team, or inspectable non-mux hierarchy
- use `ac-workflow-mux` for scout/planner/worker orchestration
- use `ac-workflow-mux-ospec` for one explicit spec-stage owner
- use `ac-workflow-mux-roadmap` for roadmap -> phase -> stage nesting

See [pimux Workflow Topologies](docs/pimux-workflow-topologies.md).

See the [Pi Package Adoption Guide](packages/README.md) for the primary git-tag install path, branch-based dev installs, local package-root testing, and future npm distribution notes.

## What is agentic-config?

A centralized configuration system with Claude Code plugins and a shipped pi package surface.

Future releases will extend the same plugin approach to additional tools (Cursor, Codex CLI, Gemini CLI, and Antigravity).

Core principles:

1. **Project-agnostic** -- Works in any codebase without modification
2. **Composable** -- Skills invoke other skills, creating compounding automation
3. **Native distribution surfaces** -- Claude via `claude plugin install`; pi via `pi install`

## Plugins

| Plugin | Focus | Skills |
|--------|-------|--------|
| `ac-workflow` | Spec workflow, pimux-backed orchestration | 6 |
| `ac-git` | Git automation, PRs, releases | 7 |
| `ac-qa` | QA, E2E testing, browser automation | 7 |
| `ac-tools` | Utilities, integrations, bootstrap | 17 |
| `ac-meta` | Meta-prompting, self-improvement | 2 |
| `ac-safety` | Security guardrails (credential, write-scope, destructive-bash, supply-chain, playwright) | 2 |
| `ac-audit` | Tool audit logging (JSONL append-only log) | 1 |

## Documentation

- [Getting Started](docs/getting-started.md) -- Install, setup, first use
- [Plugin Catalog](docs/plugin-catalog.md) -- All 42 skills with composition patterns
- [pimux Workflow Topologies](docs/pimux-workflow-topologies.md) -- `pimux`, mux, ospec, and roadmap hierarchy guide
- [Distribution Guide](docs/distribution.md) -- Claude marketplace rollout plus pi git-tag distribution, dev branch installs, and future npm notes
- [Pi Package Adoption Guide](packages/README.md) -- primary git-tag installs, branch-based dev installs, local package-root testing, and future npm distribution notes
- [Migration Guide v0.2.0](docs/migration-v0.2.0.md) -- Migrate from v0.1.x
- [Uninstall Legacy (v0.1.x)](docs/migration-v0.2.0.md#step-1-remove-old-symlinks) -- Remove legacy symlink wiring
- [Full Documentation Index](docs/index.md)

## Permissions

Claude Code MUX workflows (`ac-workflow` plugin) delegate to background agents via `Task(run_in_background=True)`. Background agents **cannot surface interactive permission prompts** -- any unapproved tool is auto-denied. In pi, the mux-family uses the package-owned `pimux` runtime instead; see [pimux Workflow Topologies](docs/pimux-workflow-topologies.md).

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

For local pre-distribution pi package testing, start with the [Pi Package Adoption Guide](packages/README.md#local-package-testing-before-distribution).

## License

[MIT License](LICENSE)
