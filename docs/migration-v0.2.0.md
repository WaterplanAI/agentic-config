# Migration Guide: v0.1.x to v0.2.0

## Overview

v0.2.0 is a **breaking release** that replaces symlink-based installation with CC-native plugin distribution.

### What Changed

| Aspect | v0.1.x | v0.2.0 |
|--------|--------|--------|
| Installation | `setup-config.sh` creates symlinks | `claude plugin install` |
| Plugin loading | `.claude/skills/` symlinks to `plugins/` | CC auto-discovers from plugin cache |
| Update | `update-config.sh` recreates symlinks | `claude plugin install` (reinstall) |
| Plugin names | `agentic-*` (6 plugins) | `ac-*` (5 plugins) |
| Asset types | Commands + Skills | Skills only |
| Hook wiring | Manual `settings.json` | Auto-registered from plugin declarations (`hooks/hooks.json` and skill frontmatter `hooks`) |

### Plugin Name Mapping

| v0.1.x | v0.2.0 | Notes |
|--------|--------|-------|
| `agentic` | (redistributed) | Assets split across `ac-tools`, `ac-git`, `ac-meta` |
| `agentic-spec` | `ac-workflow` | Merged with `agentic-mux` |
| `agentic-mux` | `ac-workflow` | Merged with `agentic-spec` |
| `agentic-git` | `ac-git` | Renamed |
| `agentic-review` | `ac-qa` | Renamed |
| `agentic-tools` | `ac-tools` | Renamed |
| -- | `ac-meta` | New (skill-writer, hook-writer from `agentic`) |

## Prerequisites

- Claude Code CLI with plugin support (`claude plugin install` available)
- Git access to the agentic-config repository (for marketplace)

## Migration Steps

### Step 1: Remove Old Symlinks

v0.1.x created symlinks in `.claude/skills/`, `.claude/commands/`, and `.claude/agents/`. Remove symlinked entries (but preserve any real files you created manually):

```bash
# Check what exists (identify symlinks vs real files)
find .claude/skills -type l 2>/dev/null
find .claude/commands -type l 2>/dev/null
find .claude/agents -type l 2>/dev/null

# Remove symlinks only (preserves real files)
find .claude/skills -type l -delete 2>/dev/null
find .claude/commands -type l -delete 2>/dev/null
find .claude/agents -type l -delete 2>/dev/null

# Clean up empty directories
rmdir .claude/skills .claude/commands .claude/agents 2>/dev/null
```

### Step 2: Add the Marketplace

From a local clone (development or testing):

```bash
claude plugin marketplace add ./path/to/agentic-config
```

From a GitHub repository (production):

```bash
claude plugin marketplace add <owner>/agentic-config
```

### Step 3: Install Plugins

Install all 5 plugins (or only the ones you need). Run these commands in a **separate terminal**, not inside a Claude Code session:

```bash
claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-git@agentic-plugins
claude plugin install ac-qa@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-meta@agentic-plugins
```

### Step 4: Verify Installation

```bash
# List installed plugins
claude plugin list

# Verify key skills are available
# Start Claude and test: /spec, /mux, /pull-request, /gsuite
```

### Alternative: Local Development with --plugin-dir

For active development on agentic-config itself, use `--plugin-dir` to load plugins directly from source (no install needed):

```bash
# Use the dev.sh convenience script
./dev.sh

# Or manually specify plugin directories
claude \
  --plugin-dir ./plugins/ac-workflow \
  --plugin-dir ./plugins/ac-git \
  --plugin-dir ./plugins/ac-qa \
  --plugin-dir ./plugins/ac-tools \
  --plugin-dir ./plugins/ac-meta
```

This reads plugin source directly -- changes are picked up on restart without reinstalling.

### Step 5: Update Project Configuration

If your `AGENTS.md` references old paths, update them:

| Old Reference | New Reference |
|---------------|---------------|
| `.claude/skills/<name>` | Skill is auto-discovered from plugin |
| `.claude/commands/<name>` | Use skill name directly (e.g., `/pull-request`) |
| `../../plugins/agentic-*` | Not needed -- plugins load from cache |
| `setup-config.sh` | `/improve-agents-md` |
| `update-config.sh` | `/improve-agents-md` |

### Step 6: Team Distribution (Optional)

For team-wide adoption, commit a `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "agentic-plugins": {
      "source": {
        "source": "github",
        "repo": "<owner>/agentic-config"
      }
    }
  },
  "enabledPlugins": {
    "ac-workflow@agentic-plugins": true,
    "ac-git@agentic-plugins": true,
    "ac-qa@agentic-plugins": true,
    "ac-tools@agentic-plugins": true,
    "ac-meta@agentic-plugins": true
  }
}
```

Team members are auto-prompted to install when they trust the project.

## Fallback

If you need to stay on the symlink-based workflow, pin v0.1.19:

```bash
# Clone specific version
git clone --branch v0.1.19 <repo-url> ~/.agents/agentic-config

# Or if already cloned, checkout the tag
cd ~/.agents/agentic-config
git checkout v0.1.19
```

v0.1.19 is the last release with symlink-based installation. It will not receive further updates.

## Troubleshooting

### Plugin install fails with "marketplace not found"

```bash
# Add the marketplace first
claude plugin marketplace add <owner>/agentic-config
```

### Old skills still appearing after migration

```bash
# Remove leftover symlinks
find .claude/skills -type l -delete 2>/dev/null
find .claude/commands -type l -delete 2>/dev/null
```

### `/spec` or `/mux` not working

Verify `ac-workflow` is installed:

```bash
claude plugin list | grep ac-workflow
# If missing:
claude plugin install ac-workflow@agentic-plugins
```

### Hooks not firing

Hooks are auto-registered from plugin declarations. Depending on the plugin, hooks can be declared in `hooks/hooks.json` (plugin-level) or `hooks` frontmatter in `SKILL.md` (skill-scoped). If hooks are not firing:

```bash
# Reinstall plugins that declare hooks
claude plugin install ac-workflow@agentic-plugins
claude plugin install ac-tools@agentic-plugins
claude plugin install ac-git@agentic-plugins
```

### Custom AGENTS.md content lost

v0.2.0 never overwrites custom sections in `AGENTS.md` without `--force`. If content was accidentally lost, restore from git:

```bash
git checkout HEAD -- AGENTS.md
```

## Removed Assets

These commands/skills were removed in v0.2.0. Use the listed alternatives:

| Removed | Alternative |
|---------|-------------|
| `/orc` | `/mux` |
| `/spawn` | Platform-native subagents (Agent tool / team workflows) |
| `/squash`, `/rebase`, `/squash_and_rebase`, `/squash_commit` | `/git-safe` |
| `/fork-terminal` | (removed, no replacement) |
| `/full-life-cycle-pr` | Compose: `/spec PLAN` + `/spec IMPLEMENT` + `/pull-request` |
| `command-writer` | `skill-writer` |
| `agent-orchestrator-manager` | `mux` |
| `git-rewrite-history` | `git-safe` |
| `/agentic-setup`, `/agentic-migrate` | `/improve-agents-md` |
| `/agentic-update` | `/improve-agents-md` |
| `/agentic-status`, `/agentic-validate` | `/improve-agents-md` |
