# Distribution Guide

Team and enterprise distribution of agentic-config for Claude Code plugins and pi packages.

Claude Code uses the marketplace flow below. Pi currently uses validated git-tag installs of the root umbrella package as the primary distribution path, with branch refs for development and local package-root installs for validation. Per-package npm distribution remains future work.

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

Pi package sources generally support npm, git, and local paths. For the current `agentic-config` monorepo package layout:
- git-tag installs of the validated root umbrella package are the primary team and automation path
- branch refs are the preferred repo-based path for local testing and development
- local package-root installs remain useful for focused package validation
- per-package npm distribution remains future work

For `@agentic-config/pi-ac-workflow`, open-source users should read the runtime ownership as:
- `pimux` = package-owned tmux control plane, including generic long-lived non-mux hierarchies
- `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap` = structured wrappers on top of `pimux`

See [pimux Workflow Topologies](pimux-workflow-topologies.md) for the practical hierarchy guide.

### Team and automation rollout: pinned git tag

Use the current public release tag when you want reproducible rollout from the repository itself:

```bash
pi install "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha" -l
```

Equivalent committed `.pi/settings.json` source:

```json
{
  "packages": [
    "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha"
  ]
}
```

Use the equivalent SSH git source for the same repository and tag when needed.

This path has been validated end to end against the root umbrella package layout, including representative skill and extension loading.

### Local testing and development: branch refs

Use a branch ref when you want repo-based rollout for local testing or development without cutting a new tag yet:

```bash
pi install "git:github.com/WaterplanAI/agentic-config@main" -l
```

Replace `main` with a feature branch name when testing unpublished pi changes.

### Local package-root installs for focused validation

Local-path installs remain primarily for local development and pre-distribution testing, not as the main repo-based distribution path for this monorepo.

Direct local-path installs are appropriate for standalone package roots such as:

```bash
pi install ./packages/pi-compat -l
pi install ./packages/pi-ac-meta -l
pi install ./packages/pi-ac-workflow -l
```

For bundled package roots such as `pi-all`, use the staged local testing flow from the [Pi Package Adoption Guide](../packages/README.md#local-package-testing-before-distribution).

### Future npm distribution

Publishing the per-package npm surface remains future work. When that distribution path is enabled, it will complement the git-based root install path rather than replace the validated repo-based rollout described above.

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
- [Pi Package Adoption Guide](../packages/README.md) -- npm installs, alternative git installs, committed `.pi/settings.json`, and local pre-distribution testing
- [Migration Guide v0.2.0](migration-v0.2.0.md) -- Migrate from v0.1.x symlinks
