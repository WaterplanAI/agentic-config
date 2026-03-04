# Distribution Guide

Team and enterprise distribution of agentic-config plugins.

## Prerequisites

Add the marketplace (required for all distribution methods):

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
    "ac-meta@agentic-plugins": true
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

---

## Private Marketplace (Enterprise)

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

- [Getting Started](getting-started.md) -- Setup and first use
- [Migration Guide v0.2.0](migration-v0.2.0.md) -- Migrate from v0.1.x symlinks
