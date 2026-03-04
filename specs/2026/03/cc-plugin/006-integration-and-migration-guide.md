# 006 - Integration and Migration Guide

## Human Section

### Goal
Wire `ac-bootstrap` into plugin manifests/documentation, replace ALL references to symlink creation with CC-native plugin commands, and write a migration guide for v0.1.x -> v0.2.0.

### Constraints
- Zero references to symlink wiring in docs (excluding CHANGELOG, RESUME, historical docs, tmp/)
- Migration guide must provide step-by-step instructions with fallback option
- All 6 README files (root + 5 plugins) must reflect CC-native architecture
- All content must be project-agnostic and anonymized

---

## AI Section

### Scope

**Steps covered**: Addendum A7-A10 (redesigned for CC-native)
**Input:** `ac-bootstrap` skill complete from Phase 5, CC-native wiring verified from Phase 4
**Output:** Fully integrated docs, migration guide, all references updated to CC-native

### Tasks

1. **Register `ac-bootstrap` in plugin manifest**:
   - Update `plugins/ac-tools/.claude-plugin/plugin.json` to include `ac-bootstrap` in skill inventory
   - Verify skill count incremented (15 base + 1 = 16 skills in ac-tools, or current count + 1)
   - Validate JSON after edit

2. **Replace ALL references to symlink creation/management**:
   - Search all files under `plugins/`, `.claude/`, `docs/`, root for symlink references:
     - `ln -s`, `symlink`, `.claude/skills/` symlink paths, `../../plugins/ac-*` relative symlink targets
   - Replace symlink instructions with `claude plugin install` commands
   - Remove any remaining symlink-related utility scripts/functions
   - Update setup/update docs to use CC-native installation
   - Verify: `grep -r "ln -s\|symlink" plugins/ .claude/ docs/` returns zero matches (excluding CHANGELOG, RESUME, tmp/, test fixtures)

3. **Write migration guide: v0.1.x (symlinks) -> v0.2.0 (CC-native)**:
   - Create `docs/migration-v0.2.0.md`
   - Content structure:
     - Overview of breaking changes
     - Prerequisites (Claude CLI version requirement)
     - Step 1: Remove old symlinks (`rm -rf .claude/skills .claude/commands .claude/agents` where symlinks)
     - Step 2: Install plugins via `claude plugin install` for each of the 5 `ac-*` plugins
     - Step 3: Verify installation (`claude --print-plugins` or equivalent)
     - Step 4: Update `CLAUDE.md` / `PROJECT_AGENTS.md` if referencing old paths
     - Fallback: pin `v0.1.19` for symlink-based workflow
     - Troubleshooting section for common migration issues

4. **Update README with CC-native installation instructions**:
   - `README.md` (root):
     - Installation section: `claude plugin install` for each plugin
     - Development section: `claude --plugin-dir` or dev convenience script
     - Architecture overview: 5 `ac-*` plugins, skills-first, CC-native distribution
     - Plugin table with name, description, skill count
   - `plugins/ac-workflow/README.md`: skill list (mux, mux-ospec, mux-subagent, product-manager, spec, mux-roadmap), description
   - `plugins/ac-git/README.md`: skill list (git-find-fork, git-safe, gh-assets-branch-mgmt, pull-request, release, branch, worktree), description, hooks
   - `plugins/ac-qa/README.md`: skill list (e2e-review, e2e-template, gh-pr-review, test-e2e, playwright-cli, browser, prepare-app), description
   - `plugins/ac-tools/README.md`: skill list (gsuite, human-agentic-design, had, cpc, dr, dry-run, single-file-uv-scripter, ac-issue, adr, milestone, setup-voice-mode, video-query, agentic-export, agentic-import, agentic-share, ac-bootstrap), description, hooks
   - `plugins/ac-meta/README.md`: skill list (skill-writer, hook-writer), description

5. **Update remaining documentation**:
   - `docs/adoption-tiers.md`: updated plugin names and install method (if exists)
   - `docs/private-marketplace.md`: updated plugin names (if exists)
   - Any ADR files referencing old plugin names or symlink wiring
   - Verify no stale references remain in any doc under `docs/`

### Acceptance Criteria

- `ac-bootstrap` appears in `ac-tools` plugin manifest (`plugin.json`)
- Zero references to symlink wiring in docs (excluding CHANGELOG, RESUME, historical docs, tmp/)
- Migration guide exists at `docs/migration-v0.2.0.md` with step-by-step instructions and fallback
- README uses `claude plugin install` for installation, `claude --plugin-dir` for development
- All 6 README files (root + 5 plugins) reflect CC-native architecture with accurate skill lists
- Skills-first bootstrap guidance is consistent across updated docs
- No PII violations (pre-commit hook passes)

### Depends On

Phase 5 (005-bootstrap-capability-migration) -- skill must exist before integration and reference migration.

---

## Implement

### TODO

- Task 1: Register `ac-bootstrap` in ac-tools plugin.json -- Status: Done
- Task 2: Rewrite docs/agents/AGENTIC_AGENT.md for CC-native -- Status: Done
- Task 3: Update docs/index.md for CC-native -- Status: Done
- Task 4: Update docs/playwright-cli-setup.md -- Status: Done
- Task 5: Create docs/migration-v0.2.0.md -- Status: Done
- Task 6: Update root README.md -- Status: Done
- Task 7: Expand plugins/ac-meta/README.md -- Status: Done
- Task 8: Verify remaining docs need no changes -- Status: Done
- Task 9: Validate zero symlink wiring refs in docs -- Status: Done
- Task 10: Commit -- Status: Done

Commit: 7c823b3

---

## Plan

### Files

- `plugins/ac-tools/.claude-plugin/plugin.json` (L1-12)
  - Add `skills` array with all 16 skills including `ac-bootstrap`
- `docs/agents/AGENTIC_AGENT.md` (L1-284)
  - Rewrite for CC-native: remove symlink references, replace legacy script refs with `ac-bootstrap` skill, update agent descriptions
- `docs/index.md` (L1-362)
  - Update Commands Catalog and Skills Catalog for CC-native: remove deleted assets, update names, add missing skills
- `docs/playwright-cli-setup.md` (L33)
  - Remove `.claude/skills/playwright-cli/` reference, replace with CC-native plugin reference
- `docs/migration-v0.2.0.md` (NEW)
  - Migration guide: v0.1.x symlinks to v0.2.0 CC-native
- `README.md` (L1-148)
  - Update skill counts (ac-tools 15->16), fix stale command references, update docs index
- `plugins/ac-meta/README.md` (L1-7)
  - Expand to full README format matching other plugin READMEs

### Plan Tasks

#### Task 1 -- Register `ac-bootstrap` in ac-tools plugin.json

Tools: editor

Add a `skills` array to `plugins/ac-tools/.claude-plugin/plugin.json` listing all 16 skills. Currently the file has no explicit skill inventory.

Diff:
````diff
--- a/plugins/ac-tools/.claude-plugin/plugin.json
+++ b/plugins/ac-tools/.claude-plugin/plugin.json
@@
 {
   "name": "ac-tools",
   "description": "Utilities - integrations, dry-run, prototyping, asset management",
   "version": "1.0.0",
   "author": {
     "name": "Agentic Config Contributors"
   },
   "homepage": "https://github.com/example-org/agentic-config",
   "repository": "https://github.com/example-org/agentic-config",
   "license": "MIT",
-  "keywords": ["tools", "gsuite", "dry-run", "adr", "milestone", "video"]
+  "keywords": ["tools", "gsuite", "dry-run", "adr", "milestone", "video", "bootstrap"],
+  "skills": [
+    "ac-bootstrap",
+    "ac-issue",
+    "adr",
+    "agentic-export",
+    "agentic-import",
+    "agentic-share",
+    "cpc",
+    "dr",
+    "dry-run",
+    "gsuite",
+    "had",
+    "human-agentic-design",
+    "milestone",
+    "setup-voice-mode",
+    "single-file-uv-scripter",
+    "video-query"
+  ]
 }
````

Verification:
- `python3 -c "import json; json.load(open('plugins/ac-tools/.claude-plugin/plugin.json'))"` exits 0
- `python3 -c "import json; d=json.load(open('plugins/ac-tools/.claude-plugin/plugin.json')); assert len(d['skills'])==16, f'Expected 16, got {len(d[\"skills\"])}'; assert 'ac-bootstrap' in d['skills']"`

#### Task 2 -- Rewrite docs/agents/AGENTIC_AGENT.md for CC-native

Tools: editor (full file replacement)

This file is heavily outdated: references `setup-config.sh`, `update-config.sh`, `migrate-existing.sh`, symlink integrity checks, broken symlink troubleshooting, and legacy agent names. Replace the ENTIRE file content with a CC-native version.

The file currently references 6 agents (agentic-setup, agentic-migrate, agentic-update, agentic-status, agentic-validate, agentic-customize) which were REMOVED in Phase 1. Replace with `ac-bootstrap` skill documentation.

Write the following complete file to `docs/agents/AGENTIC_AGENT.md`:

````diff
--- a/docs/agents/AGENTIC_AGENT.md
+++ b/docs/agents/AGENTIC_AGENT.md
@@ FULL FILE REPLACEMENT @@
+# Agentic-Config Management Guide
+
+Guide for managing agentic-config installations using Claude Code plugins and the `ac-bootstrap` skill.
+
+## Overview
+
+agentic-config is managed through CC-native plugins installed via `claude plugin install`. The `ac-bootstrap` skill (part of `ac-tools`) handles project setup, updates, and validation.
+
+## Available Commands
+
+| Command | Description | Example Usage |
+|---------|-------------|---------------|
+| `/ac-bootstrap setup` | Setup new project | `/ac-bootstrap setup` |
+| `/ac-bootstrap update` | Update to latest version | `/ac-bootstrap update` |
+| `/ac-bootstrap validate` | Check installation integrity | `/ac-bootstrap validate` |
+| `/agentic setup` | Alias for ac-bootstrap setup | `/agentic setup` |
+| `/agentic update` | Alias for ac-bootstrap update | `/agentic update` |
+
+## Natural Language Usage
+
+The `ac-bootstrap` skill responds to conversational requests:
+
+```
+"Setup agentic-config in this project"
+"Update to latest version"
+"Validate this installation"
+```
+
+Claude automatically invokes the `ac-bootstrap` skill based on intent.
+
+## Workflows
+
+### Setup
+
+1. Detects project type (TypeScript, Python, Rust, etc.)
+2. Confirms setup parameters
+3. Installs plugins via `claude plugin install`
+4. Renders project-type templates (`CLAUDE.md`, `PROJECT_AGENTS.md`)
+5. Validates installation
+
+### Update
+
+1. Compares current vs latest version
+2. Shows CHANGELOG for changes
+3. Reinstalls/upgrades plugins via CC-native mechanism
+4. Preserves `PROJECT_AGENTS.md` customizations
+5. Validates post-update
+
+### Validate
+
+1. Checks plugin installation status
+2. Validates config files and templates
+3. Reports diagnostic results
+4. Offers remediation for common issues
+
+## Example Workflows
+
+### New Project Setup
+
+```bash
+cd ~/projects/new-app
+
+# Natural language
+"Setup agentic-config for this TypeScript project"
+
+# Or slash command
+/agentic setup
+
+# Skill will:
+# - Detect TypeScript via package.json
+# - Ask confirmation
+# - Install plugins via claude plugin install
+# - Render templates
+# - Validate installation
+```
+
+### Update
+
+```bash
+cd ~/projects/my-app
+
+/agentic update
+
+# Skill shows:
+# Current: v0.1.x -> Latest: v0.2.0
+# CHANGELOG highlights
+# Files needing review
+# Options: force update, manual merge, or skip
+```
+
+### Troubleshooting
+
+```bash
+# Plugin not working after upgrade
+
+/ac-bootstrap validate
+
+# Skill diagnoses:
+# - Checks plugin installation status
+# - Validates config files
+# - Tests skill availability
+# - Offers reinstall if needed
+```
+
+## Customization Safety
+
+### PROJECT_AGENTS.md
+
+```markdown
+# Project-Specific Guidelines
+
+## Your Custom Content
+<!-- Never touched by updates -->
+
+### Architecture
+...your project notes...
+```
+
+**Update safety:**
+- `CLAUDE.md`: Template section may change with updates
+- `PROJECT_AGENTS.md`: **Never touched** by setup or update flows
+- Update flow only shows diffs for template sections
+
+### Plugin Installation
+
+**Installed via `claude plugin install` (auto-update):**
+- All skills, hooks, agents from `ac-*` plugins
+- Plugins load from `~/.claude/plugins/cache/`
+
+**Copied (customizable):**
+- `CLAUDE.md` - Project-specific guidelines
+- `PROJECT_AGENTS.md` - Your customizations (never touched by updates)
+
+## Troubleshooting
+
+### Skill Not Responding
+
+**Issue:** Skill does not activate on natural language request
+
+**Fix:**
+- Use explicit slash command: `/ac-bootstrap setup`
+- Check plugin is installed: `claude plugin list`
+- Reinstall if missing: `claude plugin install ac-tools@agentic-plugins`
+
+### Permission Denied
+
+**Issue:** Bootstrap tools fail with permission errors
+
+**Fix:**
+- Ensure Claude Code has write access to project directory
+- Run `claude plugin install ac-tools@agentic-plugins --scope user` for user-level install
+
+### Plugin Not Found
+
+**Issue:** `claude plugin install` cannot find the plugin
+
+**Fix:**
+```bash
+# Add the marketplace first
+claude plugin marketplace add <owner>/agentic-config
+
+# Then install
+claude plugin install ac-tools@agentic-plugins
+```
+
+## Advanced Usage
+
+### Batch Operations
+
+```bash
+# Validate current installation
+/ac-bootstrap validate
+
+# Force reinstall all plugins
+/ac-bootstrap setup --force
+```
+
+### Flags
+
+| Flag | Description |
+|------|-------------|
+| `--dry-run` | Preview changes without modifying files |
+| `--force` | Force reinstall/overwrite |
+| `--type <type>` | Specify project type (typescript, python-uv, etc.) |
+| `--copy` | Copy templates instead of rendering |
+
+## See Also
+
+- [Main README](../../README.md) - Full documentation
+- [CHANGELOG](../../CHANGELOG.md) - Version history
+- [Migration Guide](../migration-v0.2.0.md) - Migrate from v0.1.x symlinks to v0.2.0 CC-native
````

Verification:
- File no longer contains `setup-config.sh`, `update-config.sh`, `migrate-existing.sh`, `symlink integrity`, `broken symlink`, `agentic-setup`, `agentic-migrate`, `agentic-validate`, `agentic-customize`
- `grep -c "symlink" docs/agents/AGENTIC_AGENT.md` returns 0

#### Task 3 -- Update docs/index.md for CC-native

Tools: editor

The index.md has several stale references:
- Commands that no longer exist: `/orc`, `/spawn`, `/squash`, `/squash_commit`, `/squash_and_rebase`, `/rebase`, `/fork-terminal`, `/full-life-cycle-pr`, `/agentic-setup`, `/agentic-migrate`, `/agentic-update`, `/agentic-status`
- Skills that no longer exist: `agent-orchestrator-manager`, `command-writer`, `git-rewrite-history`
- Missing skills: `ac-bootstrap`, `branch`, `worktree`, `pull-request`, `release`, `git-safe`, `e2e-review`, `e2e-template`, `gh-pr-review`, `test-e2e`, `browser`, `prepare-app`, `ac-issue`, `adr`, `milestone`, `setup-voice-mode`, `video-query`, `agentic-export`, `agentic-import`, `agentic-share`, `spec`, `mux-roadmap`
- Symlink reference in `/worktree` description

Replace the Commands Catalog and Skills Catalog sections. Keep composition hierarchy, workflow diagrams, and related docs sections as-is.

Diff (replace from `## Commands Catalog` through `## Workflow Diagrams`):
````diff
--- a/docs/index.md
+++ b/docs/index.md
@@ Replace section: ## Commands Catalog through end of ## Skills Catalog (before ## Workflow Diagrams) @@
-## Commands Catalog
-
-### Agentic Management
-
-| Command | Description |
-|---------|-------------|
-| `/agentic` | Main dispatcher (setup, migrate, update, status, validate, customize) |
-| `/agentic-setup` | Setup agentic-config in current or specified directory |
-| `/agentic-migrate` | Migrate existing manual agentic installation to centralized system |
-| `/agentic-update` | Update agentic-config to latest version |
-| `/agentic-status` | Show status of all agentic-config installations |
-| `/agentic-export` | Export project asset to agentic-config repository |
-| `/agentic-import` | Import external asset into agentic-config repository |
-
-### Spec Workflow
-
-| Command | Description |
-|---------|-------------|
-| `/spec` | Execute single stage (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT) |
-| `/o_spec` | E2E spec orchestrator with modifiers (full/normal/lean/leanest) |
-| `/po_spec` | Phased orchestrator - decomposes large features into DAG phases |
-| `/branch` | Create new branch with spec directory structure |
-
-### Git & Versioning
-
-| Command | Description |
-|---------|-------------|
-| `/squash` | Squash all commits since base into single commit with Conventional Commits |
-| `/squash_commit` | Generate standardized Conventional Commit message for squashed commits |
-| `/squash_and_rebase` | Squash all commits into one, then rebase onto target branch |
-| `/rebase` | Rebase current branch onto target branch |
-| `/milestone` | Validate backlog completion, then squash+tag or identify gaps |
-| `/release` | Full release workflow - milestone, rebase, push, merge to main |
-
-### Pull Requests & Reviews
-
-| Command | Description |
-|---------|-------------|
-| `/full-life-cycle-pr` | Orchestrate complete PR lifecycle from branch creation to submission |
-| `/pull_request` | Create comprehensive GitHub Pull Request with auth validation |
-| `/gh_pr_review` | Review GitHub PR with multi-agent orchestration |
-| `/ac-issue` | Report issues to agentic-config repository via GitHub CLI |
-
-### Orchestration
-
-| Command | Description |
-|---------|-------------|
-| `/orc` | Orchestrate task accomplishment using multi-agent delegation |
-| `/spawn` | Spawn a subagent with specified model and task |
-| `/mux-roadmap` | Multi-track roadmap orchestration with cross-session state management |
-
-### E2E Testing
-
-| Command | Description |
-|---------|-------------|
-| `/browser` | Open browser at URL for E2E testing via playwright-cli |
-| `/browser` | Open browser at URL for E2E testing via playwright-cli |
-| `/test_e2e` | Execute E2E test from definition file |
-| `/e2e_review` | Review spec implementation with E2E visual browser validation |
-| `/prepare_app` | Start development server for E2E testing |
-| `/e2e-template` | Template for E2E test definitions |
-| `/video_query` | Query video using Gemini API (native video upload) |
-
-### Utilities
-
-| Command | Description |
-|---------|-------------|
-| `/adr` | Document architecture decisions with auto-numbering |
-| `/fork-terminal` | Open new kitty terminal session with optional command |
-| `/worktree` | Create new git worktree with symlinked/copied assets |
-
----
-
-## Skills Catalog
-
-### Workflow & Planning
-
-| Skill | Description |
-|-------|-------------|
-| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |
-| `agent-orchestrator-manager` | Orchestrates multi-agent workflows via /spawn, parallelizes independent work |
-| `mux` | Parallel research-to-deliverable orchestration via multi-agent multiplexer |
-| `mux-ospec` | Orchestrated spec workflow combining MUX delegation with stage-based execution |
-| `mux-subagent` | Protocol compliance skill for MUX subagents with file-based communication |
-
-### Code Generation
-
-| Skill | Description |
-|-------|-------------|
-| `command-writer` | Expert assistant for creating Claude Code custom slash commands |
-| `skill-writer` | Expert assistant for authoring Claude Code skills |
-| `hook-writer` | Expert assistant for authoring Claude Code hooks with correct JSON schemas |
-| `single-file-uv-scripter` | Creates self-contained Python scripts with inline PEP 723 metadata |
-
-### Design & Prototyping
-
-| Skill | Description |
-|-------|-------------|
-| `human-agentic-design` | Generates interactive HTML prototypes optimized for dual human+agent interaction |
-| `had` | Alias for human-agentic-design |
-
-### Git Utilities
-
-| Skill | Description |
-|-------|-------------|
-| `git-find-fork` | Finds true merge-base/fork-point, detects history rewrites from rebases |
-| `git-rewrite-history` | Rewrites git history safely with dry-run-first workflow |
-| `gh-assets-branch-mgmt` | Manages GitHub assets branch for persistent image hosting in PRs |
-
-### Browser & E2E Testing
-
-| Skill | Description |
-|-------|-------------|
-| `playwright-cli` | Token-efficient browser automation via CLI commands (replaces Playwright MCP) |
-
-### Browser & E2E Testing
-
-| Skill | Description |
-|-------|-------------|
-| `playwright-cli` | Token-efficient browser automation via CLI commands (replaces Playwright MCP) |
-
-### Testing & Safety
-
-| Skill | Description |
-|-------|-------------|
-| `dry-run` | Simulates command execution without file modifications |
-| `dr` | Alias for dry-run |
-
-### Integrations
-
-| Skill | Description |
-|-------|-------------|
-| `gsuite` | Google Suite integration for Sheets, Docs, Slides, Gmail, Calendar, Tasks with multi-account support |
-
-### Utilities
-
-| Skill | Description |
-|-------|-------------|
-| `cpc` | Copy text to clipboard via pbcopy (macOS) |
+## Skills Catalog
+
+All assets are skills (no commands). Organized by plugin.
+
+### ac-workflow (6 skills)
+
+| Skill | Description |
+|-------|-------------|
+| `spec` | Core specification workflow engine with stage agents (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT) |
+| `mux` | Parallel research-to-deliverable orchestration via multi-agent multiplexer |
+| `mux-ospec` | Orchestrated spec execution with phase decomposition |
+| `mux-roadmap` | Multi-track roadmap orchestration with cross-session continuity |
+| `mux-subagent` | MUX subagent protocol for delegated execution |
+| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |
+
+### ac-git (7 skills)
+
+| Skill | Description |
+|-------|-------------|
+| `branch` | Create new branch with spec directory structure |
+| `git-find-fork` | Finds true merge-base/fork-point, detects history rewrites from rebases |
+| `git-safe` | Safe git history manipulation with guardrails (squash, rebase) |
+| `gh-assets-branch-mgmt` | Manages GitHub assets branch for persistent image hosting in PRs |
+| `pull-request` | Create comprehensive GitHub Pull Requests |
+| `release` | Full release workflow (milestone, squash, tag, push, merge) |
+| `worktree` | Create git worktrees with assets and environment setup |
+
+### ac-qa (7 skills)
+
+| Skill | Description |
+|-------|-------------|
+| `browser` | Open browser for E2E testing via Playwright |
+| `e2e-review` | Visual spec implementation validation with Playwright |
+| `e2e-template` | Template for creating E2E test definitions |
+| `gh-pr-review` | Review GitHub PRs with multi-agent orchestration |
+| `playwright-cli` | Token-efficient browser automation via CLI commands |
+| `prepare-app` | Start development server for E2E testing |
+| `test-e2e` | Execute E2E test definitions with Playwright |
+
+### ac-tools (16 skills)
+
+| Skill | Description |
+|-------|-------------|
+| `ac-bootstrap` | Bootstrap and manage agentic-config installations (setup, update, validate) |
+| `ac-issue` | Report issues to agentic-config repository via GitHub CLI |
+| `adr` | Document architecture decisions with auto-numbering |
+| `agentic-export` | Export project assets to agentic-config repository |
+| `agentic-import` | Import external assets into agentic-config repository |
+| `agentic-share` | Shared core logic for asset import/export |
+| `cpc` | Clipboard-powered code exchange |
+| `dr` | Alias for dry-run |
+| `dry-run` | Simulate command execution without file modifications |
+| `gsuite` | Google Suite integration (Sheets, Docs, Slides, Drive, Gmail, Calendar, Tasks) |
+| `had` | Alias for human-agentic-design |
+| `human-agentic-design` | Interactive HTML prototype generator |
+| `milestone` | Validate backlog and generate milestone/release notes |
+| `setup-voice-mode` | Configure voice mode for conversational interaction |
+| `single-file-uv-scripter` | Create self-contained Python scripts with PEP 723 inline deps |
+| `video-query` | Query video content using Gemini API |
+
+### ac-meta (2 skills)
+
+| Skill | Description |
+|-------|-------------|
+| `skill-writer` | Expert assistant for authoring Claude Code skills |
+| `hook-writer` | Expert assistant for authoring Claude Code hooks |
````

Verification:
- No references to `command-writer`, `agent-orchestrator-manager`, `git-rewrite-history`, `orc`, `spawn`, `fork-terminal`, `/squash`, `/rebase`
- No `## Commands Catalog` section header
- `grep -c "symlink" docs/index.md` returns 0
- Total skill count: 6 + 7 + 7 + 16 + 2 = 38 (correct for current state)

#### Task 4 -- Update docs/playwright-cli-setup.md

Tools: editor

Remove reference to `.claude/skills/playwright-cli/` (L33). Replace with CC-native plugin reference.

Diff:
````diff
--- a/docs/playwright-cli-setup.md
+++ b/docs/playwright-cli-setup.md
@@
 ### 3. Install Skills (for Claude Code)

 If using agentic-config, skills are installed automatically during `/agentic setup`.

 For manual installation:
 ```bash
-playwright-cli install --skills
+claude plugin install ac-qa@agentic-plugins
 ```

-This generates `.claude/skills/playwright-cli/` with the skill definition and reference docs.
+This installs the `ac-qa` plugin which includes the `playwright-cli` skill.
````

Verification:
- `grep ".claude/skills/" docs/playwright-cli-setup.md` returns no matches

#### Task 5 -- Create docs/migration-v0.2.0.md

Tools: editor (new file)

Create the migration guide as a new file.

Write the following complete file to `docs/migration-v0.2.0.md`:

````diff
--- /dev/null
+++ b/docs/migration-v0.2.0.md
@@ NEW FILE @@
+# Migration Guide: v0.1.x to v0.2.0
+
+## Overview
+
+v0.2.0 is a **breaking release** that replaces symlink-based installation with CC-native plugin distribution.
+
+### What Changed
+
+| Aspect | v0.1.x | v0.2.0 |
+|--------|--------|--------|
+| Installation | `setup-config.sh` creates symlinks | `claude plugin install` |
+| Plugin loading | `.claude/skills/` symlinks to `plugins/` | CC auto-discovers from plugin cache |
+| Update | `update-config.sh` recreates symlinks | `claude plugin install` (reinstall) |
+| Plugin names | `agentic-*` (6 plugins) | `ac-*` (5 plugins) |
+| Asset types | Commands + Skills | Skills only |
+| Hook wiring | Manual `settings.json` | Auto-registered via `hooks.json` per plugin |
+
+### Plugin Name Mapping
+
+| v0.1.x | v0.2.0 | Notes |
+|--------|--------|-------|
+| `agentic` | (redistributed) | Assets split across `ac-tools`, `ac-git`, `ac-meta` |
+| `agentic-spec` | `ac-workflow` | Merged with `agentic-mux` |
+| `agentic-mux` | `ac-workflow` | Merged with `agentic-spec` |
+| `agentic-git` | `ac-git` | Renamed |
+| `agentic-review` | `ac-qa` | Renamed |
+| `agentic-tools` | `ac-tools` | Renamed |
+| -- | `ac-meta` | New (skill-writer, hook-writer from `agentic`) |
+
+## Prerequisites
+
+- Claude Code CLI with plugin support (`claude plugin install` available)
+- Git access to the agentic-config repository (for marketplace)
+
+## Migration Steps
+
+### Step 1: Remove Old Symlinks
+
+v0.1.x created symlinks in `.claude/skills/`, `.claude/commands/`, and `.claude/agents/`. Remove symlinked entries (but preserve any real files you created manually):
+
+```bash
+# Check what exists (identify symlinks vs real files)
+find .claude/skills -type l 2>/dev/null
+find .claude/commands -type l 2>/dev/null
+find .claude/agents -type l 2>/dev/null
+
+# Remove symlinks only (preserves real files)
+find .claude/skills -type l -delete 2>/dev/null
+find .claude/commands -type l -delete 2>/dev/null
+find .claude/agents -type l -delete 2>/dev/null
+
+# Clean up empty directories
+rmdir .claude/skills .claude/commands .claude/agents 2>/dev/null
+```
+
+### Step 2: Add the Marketplace
+
+```bash
+claude plugin marketplace add <owner>/agentic-config
+```
+
+### Step 3: Install Plugins
+
+Install all 5 plugins (or only the ones you need):
+
+```bash
+claude plugin install ac-workflow@agentic-plugins
+claude plugin install ac-git@agentic-plugins
+claude plugin install ac-qa@agentic-plugins
+claude plugin install ac-tools@agentic-plugins
+claude plugin install ac-meta@agentic-plugins
+```
+
+### Step 4: Verify Installation
+
+```bash
+# List installed plugins
+claude plugin list
+
+# Verify key skills are available
+# Start Claude and test: /spec, /mux, /pull-request, /gsuite
+```
+
+### Step 5: Update Project Configuration
+
+If your `CLAUDE.md` or `PROJECT_AGENTS.md` references old paths, update them:
+
+| Old Reference | New Reference |
+|---------------|---------------|
+| `.claude/skills/<name>` | Skill is auto-discovered from plugin |
+| `.claude/commands/<name>` | Use skill name directly (e.g., `/pull-request`) |
+| `../../plugins/agentic-*` | Not needed -- plugins load from cache |
+| `setup-config.sh` | `/ac-bootstrap setup` |
+| `update-config.sh` | `/ac-bootstrap update` |
+
+### Step 6: Team Distribution (Optional)
+
+For team-wide adoption, commit a `.claude/settings.json`:
+
+```json
+{
+  "extraKnownMarketplaces": {
+    "agentic-plugins": {
+      "source": {
+        "source": "github",
+        "repo": "<owner>/agentic-config"
+      }
+    }
+  },
+  "enabledPlugins": {
+    "ac-workflow@agentic-plugins": true,
+    "ac-git@agentic-plugins": true,
+    "ac-qa@agentic-plugins": true,
+    "ac-tools@agentic-plugins": true,
+    "ac-meta@agentic-plugins": true
+  }
+}
+```
+
+Team members are auto-prompted to install when they trust the project.
+
+## Fallback
+
+If you need to stay on the symlink-based workflow, pin v0.1.19:
+
+```bash
+# Clone specific version
+git clone --branch v0.1.19 <repo-url> ~/.agents/agentic-config
+
+# Or if already cloned, checkout the tag
+cd ~/.agents/agentic-config
+git checkout v0.1.19
+```
+
+v0.1.19 is the last release with symlink-based installation. It will not receive further updates.
+
+## Troubleshooting
+
+### Plugin install fails with "marketplace not found"
+
+```bash
+# Add the marketplace first
+claude plugin marketplace add <owner>/agentic-config
+```
+
+### Old skills still appearing after migration
+
+```bash
+# Remove leftover symlinks
+find .claude/skills -type l -delete 2>/dev/null
+find .claude/commands -type l -delete 2>/dev/null
+```
+
+### `/spec` or `/mux` not working
+
+Verify `ac-workflow` is installed:
+
+```bash
+claude plugin list | grep ac-workflow
+# If missing:
+claude plugin install ac-workflow@agentic-plugins
+```
+
+### Hooks not firing
+
+Hooks are auto-registered from each plugin's `hooks/hooks.json`. If hooks are not firing:
+
+```bash
+# Reinstall the plugin with hooks
+claude plugin install ac-tools@agentic-plugins
+claude plugin install ac-git@agentic-plugins
+```
+
+### Custom PROJECT_AGENTS.md lost
+
+v0.2.0 never overwrites `PROJECT_AGENTS.md`. If it was accidentally deleted, restore from git:
+
+```bash
+git checkout HEAD -- PROJECT_AGENTS.md
+```
+
+## Removed Assets
+
+These commands/skills were removed in v0.2.0. Use the listed alternatives:
+
+| Removed | Alternative |
+|---------|-------------|
+| `/orc` | `/mux` |
+| `/spawn` | `Task()` built-in |
+| `/squash`, `/rebase`, `/squash_and_rebase`, `/squash_commit` | `/git-safe` |
+| `/fork-terminal` | (removed, no replacement) |
+| `/full-life-cycle-pr` | (removed) |
+| `command-writer` | `skill-writer` |
+| `agent-orchestrator-manager` | `mux` |
+| `git-rewrite-history` | `git-safe` |
+| `/agentic-setup`, `/agentic-migrate` | `/ac-bootstrap setup` |
+| `/agentic-update` | `/ac-bootstrap update` |
+| `/agentic-status`, `/agentic-validate` | `/ac-bootstrap validate` |
````

Verification:
- File exists at `docs/migration-v0.2.0.md`
- Contains "Step 1", "Step 2", "Step 3", "Step 4", "Fallback", "Troubleshooting"
- Contains `claude plugin install` commands
- Contains pin `v0.1.19` fallback

#### Task 6 -- Update root README.md

Tools: editor

Three changes needed:
1. Update `ac-tools` skill count from 16 to 16 (already correct, but verify ac-bootstrap is mentioned in description)
2. Fix stale "33 commands and 19 skills" reference -- now 38 skills, 0 commands
3. Add migration guide to documentation links

Diff 1 -- Fix stale skill/command count:
````diff
--- a/README.md
+++ b/README.md
@@
-See [Commands & Skills Index](docs/index.md) for all 33 commands and 19 skills.
+See [Skills Catalog](docs/index.md) for all 38 skills across 5 plugins.
````

Diff 2 -- Add migration guide to documentation links:
````diff
--- a/README.md
+++ b/README.md
@@
 ## Documentation

 - [Commands & Skills Index](docs/index.md) - Complete catalog with composition examples
 - [Plugin Adoption Tiers](docs/adoption-tiers.md) - Team distribution: global, team-recommended, selective
 - [Private Marketplace Setup](docs/private-marketplace.md) - Enterprise private marketplace with GITHUB_TOKEN
 - [External Specs Storage](docs/external-specs-storage.md) - Configure external specs repository
 - [Agent Management Guide](docs/agents/AGENTIC_AGENT.md) - Detailed agent usage
 - [Playwright CLI Setup](docs/playwright-cli-setup.md) - E2E browser testing
+- [Migration Guide v0.2.0](docs/migration-v0.2.0.md) - Migrate from v0.1.x symlinks to v0.2.0 CC-native
````

Verification:
- `grep "33 commands" README.md` returns no matches
- `grep "migration-v0.2.0" README.md` returns a match

#### Task 7 -- Expand ac-meta README.md

Tools: editor (full file replacement)

Currently a minimal 7-line README. Expand to match the format of other plugin READMEs.

Write the following complete file to `plugins/ac-meta/README.md`:

````diff
--- a/plugins/ac-meta/README.md
+++ b/plugins/ac-meta/README.md
@@ FULL FILE REPLACEMENT @@
+# ac-meta
+
+Meta-prompting and self-improvement -- generate new skills and hooks following conventions.
+
+## Installation
+
+### From marketplace
+
+```bash
+claude plugin marketplace add <owner>/agentic-config
+claude plugin install ac-meta@agentic-plugins
+```
+
+### Scopes
+
+```bash
+claude plugin install ac-meta@agentic-plugins --scope user
+claude plugin install ac-meta@agentic-plugins --scope project
+claude plugin install ac-meta@agentic-plugins --scope local
+```
+
+## Skills
+
+| Skill | Description |
+|-------|-------------|
+| `skill-writer` | Expert assistant for authoring Claude Code skills with correct SKILL.md structure |
+| `hook-writer` | Expert assistant for authoring Claude Code hooks with correct JSON schemas |
+
+## Usage Examples
+
+```
+# Create a new skill
+/skill-writer my-new-skill "Automates X workflow"
+
+# Create a new hook
+/hook-writer pre-commit-lint "Lint staged files before commit"
+```
+
+## License
+
+MIT
````

Verification:
- File contains "## Installation", "## Skills", "## Usage Examples"
- Lists both `skill-writer` and `hook-writer`

#### Task 8 -- Verify remaining docs need no changes

Tools: shell (read-only verification)

Check that `docs/adoption-tiers.md`, `docs/private-marketplace.md`, `docs/decisions/adr-001-sdk-uv-script-nesting.md` have no stale references.

Commands:
- `grep -n "agentic-spec\|agentic-git\|agentic-review\|agentic-tools\|agentic-mux\|plugins/agentic/\|setup-config\.sh\|update-config\.sh\|\.claude/skills/" docs/adoption-tiers.md docs/private-marketplace.md docs/decisions/adr-001-sdk-uv-script-nesting.md`

Expected: Zero matches. These files already use CC-native references (`ac-*` names, `claude plugin install`). ADR-001 is a historical architecture decision record and does not reference plugin names or symlinks.

If any matches found, apply targeted replacements (not expected based on current file contents).

#### Task 9 -- Validate zero symlink wiring refs in docs

Tools: shell

Run the acceptance criteria validation:

```bash
# Symlink wiring references (excluding acceptable contexts)
grep -rn "ln -s" docs/ plugins/ README.md --include="*.md" --include="*.json" | grep -v "CHANGELOG\|RESUME\|tmp/\|worktree\|\.env\|/etc/localtime"

# Legacy script references in docs
grep -rn "setup-config\.sh\|update-config\.sh\|migrate-existing\.sh\|install-global\.sh" docs/

# Old plugin names in docs (non-historical)
grep -rn "agentic-spec\|agentic-git\|agentic-review\|agentic-tools\|agentic-mux" docs/ | grep -v "migration-v0.2.0"
```

Expected: All three commands return zero matches.

Note: Symlink references in `plugins/ac-git/skills/worktree/SKILL.md` are acceptable -- the worktree skill legitimately creates symlinks for worktree assets. References in `plugins/ac-tools/skills/ac-bootstrap/tools/*.py` are acceptable -- they handle legacy migration detection. References in `plugins/ac-tools/skills/milestone/SKILL.md` are acceptable -- milestone checks for symlink requirements in project rules. The `gsuite/tools/*.py` `/etc/localtime` symlink reference is an OS-level pattern, not installation wiring.

#### Task 10 -- Commit

Tools: git

Commands:
```bash
# Source spec resolver
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

# Stage specific files
git add \
  plugins/ac-tools/.claude-plugin/plugin.json \
  docs/agents/AGENTIC_AGENT.md \
  docs/index.md \
  docs/playwright-cli-setup.md \
  docs/migration-v0.2.0.md \
  README.md \
  plugins/ac-meta/README.md \
  specs/2026/03/cc-plugin/006-integration-and-migration-guide.md

# Commit
commit_spec_changes "specs/2026/03/cc-plugin/006-integration-and-migration-guide.md" "PLAN" "006" "integration-and-migration-guide"
```

### Validate

- L6 "Wire `ac-bootstrap` into plugin manifests": Task 1 adds `ac-bootstrap` to `ac-tools/plugin.json` with `skills` array (L89-90)
- L6 "replace ALL references to symlink creation": Tasks 2-4 rewrite AGENTIC_AGENT.md, index.md, playwright-cli-setup.md; Task 9 validates zero remaining refs (L9, L31-37)
- L6 "write a migration guide for v0.1.x -> v0.2.0": Task 5 creates `docs/migration-v0.2.0.md` with full step-by-step guide (L39-49)
- L9 "Zero references to symlink wiring in docs": Task 9 validates via grep (L9)
- L10 "Migration guide must provide step-by-step instructions with fallback option": Task 5 includes Steps 1-6, Fallback section pinning v0.1.19 (L10)
- L11 "All 6 README files (root + 5 plugins) must reflect CC-native architecture": Task 6 updates root README, Task 7 expands ac-meta README; ac-workflow/ac-git/ac-qa/ac-tools READMEs already complete from Phase 4 (L11)
- L12 "All content must be project-agnostic and anonymized": All new content uses `<owner>`, `example.com`, generic names (L12)
- L71 "`ac-bootstrap` appears in `ac-tools` plugin manifest": Task 1 (L71)
- L73 "Migration guide exists at `docs/migration-v0.2.0.md`": Task 5 (L73)
- L74 "README uses `claude plugin install`": Already present in root README from Phase 4; verified in Task 6 (L74)
- L75 "All 6 README files reflect CC-native architecture": Tasks 6-7 + existing READMEs (L75)
- L76 "Skills-first bootstrap guidance is consistent": Task 2 rewrites AGENTIC_AGENT.md to reference `ac-bootstrap` skill (L76)
- L77 "No PII violations": All content uses anonymized placeholders (L77)

### FEEDBACK

- [ ] FEEDBACK: `docs/index.md:1` title "Commands & Skills Index" is stale -- should be "Skills Catalog" since all commands were converted to skills in Phase 2-3. Same for subtitle at `docs/index.md:3`.
- [ ] FEEDBACK: `README.md:46` and `README.md:119` link text says "Commands & Skills Index" -- should match updated catalog title ("Skills Catalog").
- [ ] FEEDBACK: `docs/index.md:5-165` Composition Pattern section references removed commands (`/full-life-cycle-pr`, `/o_spec`, `/po_spec`, `/pull_request`). Plan intentionally kept as-is, but these are stale and may confuse users.
- [ ] FEEDBACK: `docs/index.md:236-276` Workflow Diagrams section references the same removed commands. Same rationale -- intentionally kept but stale.

---

## Review

### Task-by-Task Compliance

**Task 1 -- Register `ac-bootstrap` in ac-tools plugin.json**: MET
- `plugins/ac-tools/.claude-plugin/plugin.json` contains `skills` array with 16 entries, `ac-bootstrap` present (L13)
- JSON validates cleanly; `bootstrap` keyword added to keywords array (L11)

**Task 2 -- Rewrite docs/agents/AGENTIC_AGENT.md for CC-native**: MET
- Full file replacement performed (commit: 247 lines changed)
- Zero symlink references (`grep -c "symlink"` = 0)
- Zero legacy script references (`setup-config.sh`, `update-config.sh`, `migrate-existing.sh` absent)
- Zero legacy agent names (`agentic-setup`, `agentic-migrate`, etc. absent)
- Content references `ac-bootstrap` skill with workflows, troubleshooting, and flags table

**Task 3 -- Update docs/index.md for CC-native**: MET
- Commands Catalog section removed; Skills Catalog reorganized by plugin
- Skill counts match disk: ac-workflow=6, ac-git=7, ac-qa=7, ac-tools=16, ac-meta=2 (total 38)
- No references to `command-writer`, `agent-orchestrator-manager`, `git-rewrite-history`, `/orc`, `/spawn`, `/fork-terminal`, `/squash`, `/rebase`
- Composition hierarchy and workflow diagrams kept as-is per plan

**Task 4 -- Update docs/playwright-cli-setup.md**: MET
- `playwright-cli install --skills` replaced with `claude plugin install ac-qa@agentic-plugins` (L30)
- `.claude/skills/playwright-cli/` reference removed (L33 replaced)
- Zero `.claude/skills/` references remain

**Task 5 -- Create docs/migration-v0.2.0.md**: MET
- File exists at `docs/migration-v0.2.0.md` (198 lines)
- Contains: What Changed table, Plugin Name Mapping, Steps 1-6, Fallback (pin v0.1.19), Troubleshooting (5 scenarios), Removed Assets table
- All content uses `<owner>`, `<repo-url>` placeholders -- anonymized

**Task 6 -- Update root README.md**: MET
- "33 commands and 19 skills" replaced with "38 skills across 5 plugins" (L68)
- Migration guide link added to Documentation section (L125)

**Task 7 -- Expand ac-meta README.md**: MET
- Expanded from 7-line stub to full README with Installation, Scopes, Skills table, Usage Examples, License

**Task 8 -- Verify remaining docs need no changes**: MET
- `docs/adoption-tiers.md`, `docs/private-marketplace.md`, `docs/decisions/adr-001-sdk-uv-script-nesting.md` contain zero stale references

**Task 9 -- Validate zero symlink wiring refs in docs**: MET
- `grep -rn "ln -s" docs/ plugins/ README.md` (excluding CHANGELOG, RESUME, tmp/, worktree, /etc/localtime, migration guide): zero matches
- `grep -rn "setup-config.sh|update-config.sh|migrate-existing.sh|install-global.sh" docs/`: matches only in `docs/migration-v0.2.0.md` (acceptable -- migration comparison context)
- `grep -rn "agentic-spec|agentic-git|agentic-review|agentic-tools|agentic-mux" docs/` excluding migration guide: zero matches

**Task 10 -- Commit**: MET
- Commit `7c823b3`: 7 files changed, 375 insertions, 291 deletions

### Test Coverage

- No unit/e2e tests applicable -- this phase is documentation-only (docs, READMEs, JSON manifest, migration guide)
- Validation is grep-based acceptance criteria (Task 9), all passing

### Deviations

1. `docs/index.md` title (L1) remains "# Commands & Skills Index" and subtitle (L3) says "commands and skills" -- stale since there are no commands anymore. Root README L46 and L119 also reference "Commands & Skills Index". This is NOT in the plan's diff scope (plan only replaced the catalog sections). Does NOT affect achieving spec goal -- the title is cosmetic and the migration guide + Skills Catalog are the primary deliverables. Future cleanup recommended.

2. `docs/index.md` Composition Pattern (L5-164) and Workflow Diagrams (L236-276) reference removed commands (`/full-life-cycle-pr`, `/pull_request`, `/o_spec`, `/po_spec`). Plan explicitly states "Keep composition hierarchy, workflow diagrams, and related docs sections as-is." Does NOT affect spec goal -- these serve as conceptual architecture documentation.

### Goal Achieved?

**Yes.** All 7 acceptance criteria are met: `ac-bootstrap` registered in manifest, zero symlink wiring refs in docs, migration guide with step-by-step + fallback exists, READMEs reflect CC-native, skills-first bootstrap guidance is consistent, no PII violations. The two deviations (stale index.md title, kept composition sections) are cosmetic/intentional per plan and do not affect the spec goal.

### Next Steps

- Phase 7: Validation Expansion + E2E Testing (remove symlink tests, add CC-native plugin validation, E2E `claude plugin install` round-trip, `marketplace.json` validation)

---

## Test Evidence & Outputs

### Commands Run

```bash
uv run pytest tests/ -v --tb=short
uv run ruff check plugins/ac-tools/skills/ plugins/ac-tools/.claude-plugin/
uv run ruff check plugins/ac-meta/
```

### Results

- Unit tests: 52 passed, 0 failed, 0 skipped
- Lint (Phase 006 files): PASS -- 0 errors, 0 warnings
- Lint (full repo): 31 pre-existing warnings in `_archive/` and `core/` files -- none in Phase 006 files

### Pass/Fail Status

PASS

### Fixes Applied

None -- all tests passed on first run.

### Fix-Rerun Cycles

---

## Updated Doc

Phase 006 was documentation-only. All documentation was updated in IMPLEMENT.

### Files Updated

- `plugins/ac-tools/.claude-plugin/plugin.json` -- added `skills` array (16 entries including `ac-bootstrap`)
- `docs/agents/AGENTIC_AGENT.md` -- full rewrite for CC-native; removed all legacy script and symlink refs; replaced with `ac-bootstrap` skill workflows
- `docs/index.md` -- Commands Catalog removed; Skills Catalog reorganized by plugin (38 skills across 5 plugins)
- `docs/playwright-cli-setup.md` -- replaced `.claude/skills/playwright-cli/` reference with `claude plugin install ac-qa@agentic-plugins`
- `docs/migration-v0.2.0.md` -- new migration guide: v0.1.x symlinks to v0.2.0 CC-native (Steps 1-6, Fallback, Troubleshooting, Removed Assets)
- `README.md` -- updated skill/command count; added migration guide link
- `plugins/ac-meta/README.md` -- expanded from 7-line stub to full README

### Changes Made

- DOCUMENT stage: no additional project documentation required; implementation deliverables were documentation files themselves
- Spec `## Updated Doc` section appended

0
