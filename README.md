# Agentic Configuration System

Centralized, versioned configuration for AI-assisted development workflows. Single source of truth for agentic tools (Claude Code, Antigravity, Codex CLI, Gemini CLI).

## Quickstart (New Contributors)

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

That's it! All `/agentic` commands are now available globally.

---

## Quick Start

### With Agent-Powered Interface

After installation, use these commands in any project:

```bash
cd ~/projects/my-project

# Natural language
"Setup agentic-config in this project"

# Or slash commands
/agentic setup        # Setup new project
/agentic migrate      # Migrate existing installation
/agentic update       # Update to latest version
/agentic status       # Show all installations
```

### Manual Script Execution

```bash
# Setup new project
~/.agents/agentic-config/scripts/setup-config.sh ~/projects/my-project

# Migrate existing manual installation
~/.agents/agentic-config/scripts/migrate-existing.sh ~/projects/my-project

# Update to latest version
~/.agents/agentic-config/scripts/update-config.sh ~/projects/my-project
```

### Custom Install Location

Override default install path (`~/.agents/agentic-config`):
```bash
AGENTIC_CONFIG_DIR=~/custom/path curl -sL https://raw.githubusercontent.com/MatiasComercio/agentic-config/main/install.sh | bash
```

**Available commands after install:**
- `/agentic` - Router for all actions
- `/agentic-setup` - Direct setup command
- `/agentic-migrate` - Direct migrate command
- `/agentic-update` - Direct update command
- `/agentic-status` - Direct status command

## What Gets Installed

**Symlinked (instant updates from central repo):**
- `agents/` - Core workflow definitions (RESEARCH, PLAN, IMPLEMENT, etc.)
- `.agent/workflows/spec.md` - Antigravity workflow integration
- `.claude/commands/spec.md` - Claude Code command integration
- `.claude/hooks/pretooluse/dry-run-guard.py` - Dry-run mode enforcement hook
- `.gemini/commands/spec.toml` - Gemini CLI command integration
- `.codex/prompts/spec.md` - Codex CLI prompt (uses proper codex command file)

**Copied (project-customizable):**
- `.agent/config.yml` - Antigravity configuration (permissions, directories)
- `AGENTS.md` - Project-specific guidelines and conventions

**Local symlinks:**
- `CLAUDE.md` → `AGENTS.md`
- `GEMINI.md` → `AGENTS.md`

## Supported Project Types

| Type | Package Manager | Type Checker | Linter |
|------|----------------|--------------|--------|
| **typescript** | pnpm | tsc | eslint |
| **ts-bun** | bun | tsc | eslint |
| **python-poetry** | poetry | pyright | ruff |
| **python-uv** | uv | pyright | ruff |
| **python-pip** | pip | mypy | pylint |
| **rust** | cargo | cargo check | clippy |
| **generic** | custom | custom | custom |

Project type is auto-detected (via lockfiles/config files) or can be specified with `--type` flag.

## Architecture

### Hybrid Symlink + Copy Pattern

**Why symlinks for workflows?**
- Universal across projects
- Instant updates when central repo changes
- Zero duplication
- Version-controlled improvements benefit all projects

**Why copies for configs?**
- Project-specific customization needed
- Different tooling per language
- Security settings may vary
- Custom instructions per project

### Directory Structure

```
~/.agents/agentic-config/
├── core/                   # Universal files (symlinked)
│   ├── agents/
│   │   ├── spec-command.md
│   │   └── spec/          # RESEARCH, PLAN, IMPLEMENT, etc.
│   └── commands/          # AI tool integrations
│       ├── claude/
│       └── gemini/
├── templates/             # Project-specific configs (copied)
│   ├── typescript/
│   ├── python-poetry/
│   ├── python-uv/
│   ├── python-pip/
│   ├── rust/
│   └── generic/
├── scripts/               # Management tools
│   ├── setup-config.sh
│   ├── migrate-existing.sh
│   ├── update-config.sh
│   ├── install-global.sh  # User-level installation
│   └── lib/               # Utilities
└── docs/                  # Documentation
```

## Usage

### New Project Setup

```bash
cd ~/projects/my-new-app
~/.agents/agentic-config/scripts/setup-config.sh .

# With explicit type
~/.agents/agentic-config/scripts/setup-config.sh --type python-poetry .

# Dry run to preview
~/.agents/agentic-config/scripts/setup-config.sh --dry-run .
```

### Migrate Existing Installation

For projects with manual agentic configuration:

```bash
cd ~/projects/existing-app
~/.agents/agentic-config/scripts/migrate-existing.sh .
```

Creates backup, preserves customizations, converts to centralized pattern.

### Update to Latest Version

```bash
cd ~/projects/my-app
~/.agents/agentic-config/scripts/update-config.sh .

# Force update templates without prompting
~/.agents/agentic-config/scripts/update-config.sh --force .
```

### What Gets Installed (Commands & Skills)

All commands and skills are installed by default:

**Commands:**
- `/init` - Initialize/repair symlinks after clone (bootstrap command)
- `/adr` - Architecture Decision Records with auto-numbering
- `/orc` - Orchestrate multi-agent tasks
- `/spawn` - Spawn subagents with specific models
- `/squash` - Squash commits intelligently
- `/pull_request` - Create GitHub PRs with comprehensive descriptions
- `/gh_pr_review` - Review GitHub PRs with multi-agent orchestration

**Skills:**
- `agent-orchestrator-manager` - Multi-agent delegation workflows
- `single-file-uv-scripter` - Self-contained Python scripts with UV
- `command-writer` - Create custom slash commands
- `skill-writer` - Author Claude Code skills
- `git-find-fork` - Find true merge-base/fork-point

**New in v1.1.1:**
- Auto-creates `.gitignore` with sensible defaults
- Auto-runs `git init` if not inside any git repository (including parent repos)
- Cleans up orphaned symlinks on update

### /init Command (Bootstrap)

The `/init` command repairs symlinks in the **agentic-config repository itself** after cloning.

**When to use:**
- After cloning agentic-config manually (not via install.sh)
- If symlinks are broken or missing
- After pulling changes that add new commands/skills

**What it does:**
```
.claude/commands/*.md                   → ../../core/commands/claude/*.md          (relative symlinks)
.claude/skills/*                        → ../../core/skills/*                       (relative symlinks)
.claude/agents/*.md                     → ../../core/agents/*.md                    (relative symlinks)
.claude/hooks/pretooluse/dry-run-guard.py → ../../../core/hooks/pretooluse/dry-run-guard.py (relative symlinks)
.claude/settings.json                   → hook registration (created/merged)
```

**Usage:**
```bash
cd ~/.agents/agentic-config
/init
```

**Note:** For global install (global commands), use the curl install pattern instead.

**Note:** `/init` is a real file (not a symlink) so it's available even when other symlinks are broken.

### Customization

#### File Behavior by Type

**Symlinked files (automatic updates):**
- `agents/`, `.claude/commands/`, `.gemini/commands/`, `.codex/prompts/`, `.agent/workflows/`
- Update instantly when central repo changes
- **No customization possible** - use them as-is

**Copied files (customizable):**
- `AGENTS.md` - Project-specific guidelines (customize freely)
- `.agent/config.yml` - Rarely needs changes (use template defaults when possible)

#### AGENTS.md: Safe Customization with PROJECT_AGENTS.md

**New in v1.1.1:** Separation of template from project customizations

- `AGENTS.md` - Template with standard guidelines (receives updates)
- `PROJECT_AGENTS.md` - Project-specific overrides (never touched by updates)

**How it works:**
```markdown
# AGENTS.md (template)
## Core Principles
- Verify over assume
- Failures first
- DO NOT OVERCOMPLICATE

## Project-Specific Instructions
READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE
```

**PROJECT_AGENTS.md** (your customizations):
```markdown
# Project-Specific Guidelines

## API Structure
- REST endpoints in src/api/
- GraphQL resolvers in src/graphql/
- Authentication via JWT in middleware/

## Testing Strategy
- Unit tests colocated with implementation
- Integration tests in tests/integration/
- E2E tests use Playwright
```

**Migration:**
- Run `update-config.sh --force` to auto-migrate existing customizations
- Content below "CUSTOMIZE BELOW THIS LINE" moves to PROJECT_AGENTS.md
- AGENTS.md replaced with latest template

**Benefits:**
- Clean updates without merge conflicts
- Explicit separation of concerns
- PROJECT_AGENTS.md always takes precedence

#### .agent/config.yml: Minimal Customization

Rarely needs changes (same structure works for most projects). If you do customize:

**When updates available:**
```bash
update-config.sh ~/projects/my-app
# Shows: 📄 .agent/config.yml has updates
# Suggests: diff current-file template-file
```

**Three options:**
1. **Review + manual merge** - View diff, selectively apply changes
2. **Force update** - `update-config.sh --force` (overwrites customizations)
3. **Keep current** - Ignore update (miss template improvements)

#### Recommended Workflow

**Initial setup:**
```bash
~/.agents/agentic-config/scripts/setup-config.sh ~/projects/my-app
cd ~/projects/my-app
# Edit AGENTS.md below "CUSTOMIZE BELOW THIS LINE"
# Add project architecture, conventions, specific rules
```

**On central repo updates:**
```bash
# 1. Symlinked files auto-update - nothing to do ✓

# 2. Check copied files for template improvements
~/.agents/agentic-config/scripts/update-config.sh ~/projects/my-app

# 3. Review diffs shown, decide on manual merge or --force
# 4. Test: run /spec on small task to verify
```

**Best practices:**
- Keep `.agent/config.yml` customizations minimal (prefer defaults)
- Put all project-specific content below the marker in `AGENTS.md`
- Never edit symlinked files (changes lost on next update)
- Test workflows after updates

**Disable auto-check (manual updates only):**
```bash
jq '.auto_check = false' .agentic-config.json > tmp && mv tmp .agentic-config.json
```

## Agent-Powered Management

Natural language interface for all agentic-config operations using specialized Claude Code agents.

### Available Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/agentic setup [path]` | Setup new project | Auto-detect type, guide installation |
| `/agentic migrate [path]` | Migrate manual installation | Preserve customizations, create backup |
| `/agentic update [path]` | Update to latest version | Show diffs, guide merge |
| `/agentic status` | Query all installations | Health dashboard, version tracking |
| `/agentic validate [path]` | Diagnose issues | Check integrity, offer auto-fix |
| `/agentic customize` | Customization guide | Safe zones, examples, validation |

**Path default:** Current directory if not specified

### Natural Language

Agents respond to conversational requests:
- "Setup agentic-config in this project" → setup agent
- "Update to latest version" → update agent
- "Show all my installations" → status agent
- "Validate this installation" → validate agent
- "Help me customize AGENTS.md" → customize agent

### Example Workflow

```bash
cd ~/projects/new-app

# Natural language request
"Setup agentic-config for this TypeScript project"

# Agent interaction:
# - Detects TypeScript via package.json
# - Explains what will be installed
# - Asks: "Proceed with setup? [Y/n/dry-run]"
# - Executes installation
# - Guides customization
# - Validates setup
```

### Key Features

- **Interactive:** Asks questions, explains before executing
- **Safe:** Dry-run mode, creates backups, validates after changes
- **Intelligent:** Auto-detects project type, identifies customizations
- **Helpful:** Shows diffs, guides merges, provides rollback instructions

See [Agent Guide](docs/agents/AGENTIC_AGENT.md) for detailed documentation.

## Version Management

### Tracking

Each installation creates `.agentic-config.json`:

```json
{
  "version": "1.0.0",
  "installed_at": "2025-11-24T10:30:00Z",
  "project_type": "typescript",
  "auto_check": true
}
```

Central registry at `~/.agents/agentic-config/.installations.json` tracks all installations.

### Updates

**Opt-in per project:**
- `auto_check: true` - Notifies on version mismatch (default)
- `auto_check: false` - Manual updates only

**Update strategy:**
- Symlinked files: automatic (next use)
- Copied files: manual review via `update-config.sh`

## Workflows

### /spec Command

Structured development workflow with AI assistance:

```bash
# Stage 1: Research
/spec RESEARCH specs/2025/11/001-feature.md

# Stage 2: Plan
/spec PLAN specs/2025/11/001-feature.md

# Stage 3: Implement
/spec IMPLEMENT specs/2025/11/001-feature.md
```

**Available stages:**
- `RESEARCH` - Analyze codebase, record findings
- `PLAN` - Design changes, create diffs
- `IMPLEMENT` - Apply changes, run validation
- `REVIEW` - Code review workflow
- `VALIDATE` - Integrity checks
- `FIX` - Bug fix workflow
- `AMEND` - Amendment workflow

See `core/agents/spec/*.md` for stage definitions.

### External Specs Storage

Specification files can be stored in a separate external repository to reduce clutter in the main repository while maintaining version control.

**Configuration:**

Create a `.env` file in the repository root (based on `.env.example`):
```bash
EXT_SPECS_REPO_URL=git@github.com:user/specs.git  # Git repository URL (SSH or HTTPS)
EXT_SPECS_LOCAL_PATH=.specs                       # Local directory path (default: .specs)
```

**Automatic Path Resolution:**

The spec workflow automatically detects external vs local configuration:

- When `EXT_SPECS_REPO_URL` is set:
  - Specs stored in `.specs/specs/`
  - Commits pushed to external repository

- When `EXT_SPECS_REPO_URL` is NOT set:
  - Specs stored in `specs/`
  - Commits pushed to main repository

**No code changes needed** when switching between external and local configurations. The spec-resolver library (`core/lib/spec-resolver.sh`) handles all path resolution and commit routing automatically.

**Available Functions:**

For manual operations, source the wrapper script:
```bash
source scripts/external-specs.sh

# Initialize/update external repository
ext_specs_init

# Commit and push changes
ext_specs_commit "commit message"

# Get absolute path to external specs directory
ext_specs_path
```

**Integrated Commands:**
- `/branch` - Creates spec directories using resolved paths
- All `/spec` stages - Automatically commit to appropriate repository

See `AGENTS.md` for detailed spec resolver documentation.

## Troubleshooting

### Broken Symlinks

**In agentic-config repo itself:**
```bash
cd ~/.agents/agentic-config
/init   # Regenerates all symlinks
```

**In other projects:**
```bash
cd ~/projects/my-app

# Verify symlinks
ls -la agents
ls -la .claude/commands/

# Re-run setup with --force
~/.agents/agentic-config/scripts/setup-config.sh --force .
```

### Version Mismatch

```bash
# Check current version
cat ~/projects/my-app/.agentic-config.json

# Update to latest
~/.agents/agentic-config/scripts/update-config.sh ~/projects/my-app
```

### Template Conflicts

```bash
# View diff between current and template
diff ~/projects/my-app/AGENTS.md \
     ~/.agents/agentic-config/templates/typescript/AGENTS.md.template

# Manually merge or force update
~/.agents/agentic-config/scripts/update-config.sh --force ~/projects/my-app
```

## Development

### Adding New Template

1. Create directory: `templates/new-language/`
2. Add `.agent/config.yml.template`
3. Add `AGENTS.md.template`
4. Update `detect-project-type.sh` detection logic
5. Test with `setup-config.sh --type new-language`

### Updating Workflows

Edit files in `core/agents/spec/*.md`. All projects using symlinks get updates automatically.

### Version Bumps

```bash
# Update VERSION file
echo "1.1.0" > ~/.agents/agentic-config/VERSION

# Document in CHANGELOG.md
# Push to remote
# Projects will detect update on next check
```

## Contributing

1. Test changes in isolated project first
2. Update CHANGELOG.md
3. Bump VERSION (semver)
4. Commit and push
5. Notify installations via update script

## License

Private - Internal use only
