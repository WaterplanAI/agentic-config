# Distribution Guide

Team and enterprise distribution of agentic-config for Claude Code plugins and pi packages.

Claude Code uses the marketplace flow below. Pi uses published packages and committed `.pi/settings.json`.

## Claude Code Marketplace Distribution

### Prerequisites

Add the marketplace (required for Claude Code distribution methods):

```bash
claude plugin marketplace add <owner>/agentic-config
```

## Tier 1: Global (Personal)

Individual developer installs plugins to their user-level configuration. No repository footprint.

```bash
claude plugin install ac-workflow@agentic-plugins --scope user
claude plugin install ac-git@agentic-plugins --scope user
claude plugin install ac-tools@agentic-plugins --scope user
```

**Effect:** Plugin is available in all projects for this user only.

**Settings location:** `~/.claude/settings.json`

**Use when:**
- Exploring plugins personally before recommending to team
- Using plugins not relevant to the whole team
- Working across many repositories with consistent personal tooling

## Tier 2: Team-Recommended (Full Set)

Team commits `.claude/settings.json` with marketplace reference and enabled plugins. All team members are auto-prompted to install when they trust the project.

Add to your project `.claude/settings.json`:

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
    "ac-meta@agentic-plugins": true,
    "ac-safety@agentic-plugins": true,
    "ac-audit@agentic-plugins": true
  }
}
```

**Merge with existing hooks:** If your `.claude/settings.json` already has a `hooks` section, merge the keys. Do not replace the entire file.

**Use when:**
- Standardizing team workflows
- Onboarding new team members with zero friction

## Tier 3: Selective (Per-Team-Need)

Enable only specific plugins based on team role or project needs. Use the same `.claude/settings.json` pattern but include only the plugins you need in `enabledPlugins`.

**Use when:**
- Different sub-teams need different plugin sets
- Minimizing plugin surface area for focused workflows
- Compliance requirements limit which plugins are allowed

## Config Collision Prevention

Personal and team plugins coexist without conflict:

- **Team plugins** (project `.claude/settings.json`) apply to all team members
- **Personal plugins** (user `~/.claude/settings.json`) apply only to the individual
- Both are additive -- no overrides in either direction
- Different team members can have different personal plugin sets with zero collision

## Auto-Prompt Behavior

When `enabledPlugins` references a plugin from `extraKnownMarketplaces`:

1. Team member opens the project in Claude Code
2. Claude Code detects the marketplace reference and enabled plugins
3. If the plugin is not installed locally, the user is prompted to install it
4. User accepts -- plugin is installed and available immediately
5. User declines -- no change, they can install later manually

One `.claude/settings.json` commit replaces per-member setup instructions.

## Pi Package Distribution

Pi package sources generally support npm, git, and local paths. For the current `agentic-config` monorepo package layout, the recommended distribution path is npm-published packages plus a committed `.pi/settings.json` for team rollout.

### Team-Recommended: Committed `.pi/settings.json`

Install the full shipped surface with the one-shot package:

```json
{
  "packages": [
    "npm:@agentic-config/pi-all@0.2.6"
  ]
}
```

This is the preferred team path because pi can auto-install missing packages on startup and keep the package list versioned with the project.

Use selective package entries when you want a smaller rollout surface:

```json
{
  "packages": [
    "npm:@agentic-config/pi-ac-git@0.2.6",
    "npm:@agentic-config/pi-ac-tools@0.2.6",
    "npm:@agentic-config/pi-ac-workflow@0.2.6"
  ]
}
```

### Manual Installs

One-shot install:

```bash
pi install npm:@agentic-config/pi-all@0.2.6
```

Selective installs:

```bash
pi install npm:@agentic-config/pi-ac-git@0.2.6
pi install npm:@agentic-config/pi-ac-tools@0.2.6
pi install npm:@agentic-config/pi-ac-workflow@0.2.6
```

Use `pi install -l` when you want pi to write directly to the project-local `.pi/settings.json` instead of your global settings.

### Local-Path Installs for Pre-Distribution Testing

Local-path installs remain valid for local pre-distribution testing, but they are not the primary team rollout path for this monorepo. Use the exact staged/local commands in the [Pi Package Adoption Guide](../packages/README.md#local-package-testing-before-distribution) when validating unpublished packages locally.

For the full current package surface and install matrix, see the [Pi Package Adoption Guide](../packages/README.md).

---

## Claude Code Private Marketplace (Enterprise)

Run a private marketplace from a private GitHub repository.

### Prerequisites

- Private GitHub repository containing `.claude-plugin/marketplace.json`
- `GITHUB_TOKEN` with `repo` scope (for private repo access)

### Setup

1. Fork or create private repository:

```bash
gh repo fork <owner>/agentic-config --org <your-org> --private
```

2. Configure GitHub token:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

3. Add the private marketplace:

```bash
claude plugin marketplace add <your-org>/agentic-config
```

4. Install plugins:

```bash
claude plugin install ac-workflow@agentic-plugins
```

Team members use the same `.claude/settings.json` pattern (Tier 2/3) but with `<your-org>` as the repo owner. All team members need `GITHUB_TOKEN` set.

### Strict Marketplace Mode

For compliance-restricted environments:

```json
{
  "strictKnownMarketplaces": {
    "agentic-plugins": {
      "source": {
        "source": "github",
        "repo": "<your-org>/agentic-config"
      }
    }
  }
}
```

With `strictKnownMarketplaces`:
- Only listed marketplaces are allowed
- Users cannot add additional third-party marketplaces
- Enforced at the project level via `.claude/settings.json`

### Customization

Enterprise teams can customize their fork:

1. **Add internal plugins**: Create new plugin directories under `plugins/`
2. **Remove unused plugins**: Delete plugin directories and update `marketplace.json`
3. **Modify existing plugins**: Adjust skills for internal workflows
4. **Pin versions**: Lock plugin versions in `plugin.json` to control rollout

All customizations are isolated to the private fork.

## See Also

- [Getting Started](getting-started.md) -- Claude Code and pi setup
- [Pi Package Adoption Guide](../packages/README.md) -- npm installs, committed `.pi/settings.json`, and local pre-distribution testing
- [Migration Guide v0.2.0](migration-v0.2.0.md) -- Migrate from v0.1.x symlinks
