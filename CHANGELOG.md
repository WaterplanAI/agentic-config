# Changelog

All notable changes to agentic-config.

## [Unreleased]

### Added

- `--copy` flag for `setup-config.sh` to copy assets instead of symlinking (recommended for team repos)
- Copy mode auto-detection in `update-config.sh` with timestamped backup mechanism
- `install_mode` tracking in `.agentic-config.json` for installation mode persistence
- `.gitignore` pattern for copy-backup directories (`.agentic-config.copy-backup.*`)
- `/full-life-cycle-pr` command for orchestrating complete PR lifecycle (branch creation, spec workflow, squash/rebase, PR creation)
- `--skip-tag` option for `/milestone` to skip tag creation (default: false)

### Changed

- `/full-life-cycle-pr` now uses `--skip-tag` with `/milestone` by default

### Fixed

- Command injection vulnerability in `/full-life-cycle-pr` argument parsing (replaced `ARGS=($ARGUMENTS)` with safe IFS read)
- Arbitrary code execution risk in `/full-life-cycle-pr` .env sourcing (replaced `source .env` with grep/cut parsing)
- Missing branch name validation in `/full-life-cycle-pr` (added regex validation before git commands)
- Gemini `spec.toml` installation not respecting copy mode in `setup-config.sh` (now respects COPY_MODE)
- `.agent/workflows/spec.md` installation not respecting copy mode in `setup-config.sh` (now respects COPY_MODE)
- `get_install_mode()` non-jq fallback returning empty string instead of "symlink" default in `version-manager.sh`
- New commands installation not respecting `install_mode` during update in `update-config.sh` (now checks INSTALL_MODE)
- New skills installation not respecting `install_mode` during update in `update-config.sh` (now checks INSTALL_MODE)
- Missing backup verification before `rm -rf` in `update-config.sh` (now verifies backup exists before deleting)

## [0.1.6] - 2025-12-16

### Changed
- 'Squashed commits:' footer is now optional (default: disabled) in /squash_commit

## [0.1.5] - 2025-12-16

### Added
- Conventional Commits extended format for all commit-rewriting commands
- `/milestone` Phase 4B for standardized commit message generation
- `/squash`, `/squash_commit`, `/squash_and_rebase` now analyze git diff to generate structured messages
- `/release` merge commits use Conventional Commits format
- Git Commit Standards section in PROJECT_AGENTS.md

### Changed
- All squashed commits now include structured body (Added/Changed/Fixed/Removed sections)
- Commit messages can optionally include "Squashed commits:" footer with --with-squashed-commits flag (disabled by default)

## [0.1.4] - 2025-12-16

### Added
- `/o_spec` workflow modifiers: `full` (default), `normal`, `lean`, `leanest` for speed/quality tradeoffs
- `/o_spec` step skipping with `--skip=STEP1,STEP2` flag
- `/fork-terminal` command for opening new kitty terminal sessions with optional prime prompt
- `/agentic update nightly` option to rebuild all symlinks even when version matches
- `/milestone` Phase 0.7 and Phase 4.5 for PROJECT_AGENTS.md rules enforcement on release changes
- PROJECT_AGENTS.md symlink relative paths enforcement rule

### Fixed
- `/o_spec` missing YAML frontmatter (description, argument-hint, project-agnostic)

### Changed
- `/agentic update` now shows change summary table before options
- Renamed "Force update" to "Full Update" (less aggressive language)
- Added safe "Update" option for symlink-only updates when no template conflicts
- Improved safety messaging with explicit backup guarantees

## [0.1.3] - 2025-12-16

### Added
- `/worktree` command for creating git worktrees with asset symlinks and environment setup
- `/rebase` command for rebasing current branch onto target
- `/squash_and_rebase` command for squash + rebase in one operation
- `git-rewrite-history` skill for safe git history manipulation
- CHANGELOG.md handling in `/milestone` release workflow

### Fixed
- `git init` now checks if inside ANY git repo (including parent repos) before initializing
- Create `.installations.json` if missing before jq update (was causing setup to fail)
- `/worktree` now resolves `assets.source` relative to `.worktree.yml` location (not CWD)
- `/branch` creates spec dir relative to CWD (not repo root) and commits it
- `/worktree` spec dir no longer lost after worktree creation (requires committed state)
- `/worktree` commits setup changes at end to avoid unstaged files
- Backup existing skill directories before symlink replacement

### Changed
- Setup preserves pre-existing config content to `PROJECT_AGENTS.md`
- `/worktree` uses haiku agents for parallel environment setup
- Removed emojis from scripts and agent definitions for consistency

## [0.1.2] - 2025-12-16

### Added
- `/init` command for post-clone setup (creates symlinks + global install)
- `/branch` command for new branch with spec directory structure
- Quickstart section in README for new contributors

### Changed
- All commands/skills now installed by default (removed `--extras` flag)
- `/spec` removed from global install (project-specific only)
- Symlinks converted from absolute to relative paths (portable)
- Self-hosted repo detection in update script

### Fixed
- Symlinks now work after cloning to any directory

## [0.1.1] - 2025-12-15

### Added
- ts-bun template for Bun package manager
- `/adr` command for Architecture Decision Records
- PROJECT_AGENTS.md pattern (separates template from customizations)
- Auto-create `.gitignore` and `git init` during setup
- Orphan symlink cleanup on update

## [0.1.0] - 2025-11-25

### Added
- Centralized agentic configuration system
- Templates: TypeScript, Python (uv/poetry/pip), Rust, generic
- Hybrid symlink + copy distribution pattern
- Claude Code, Gemini CLI, Codex CLI, Antigravity integrations
- Spec workflow stages: CREATE, RESEARCH, PLAN, PLAN_REVIEW, IMPLEMENT, TEST, REVIEW, DOCUMENT, VALIDATE, FIX, AMEND
- Agent-powered management with 6 specialized agents
- `/agentic` commands: setup, migrate, update, status, validate, customize
- Natural language interface for all operations
- Project-agnostic commands and skills (/orc, /spawn, /squash, /pull_request, /gh_pr_review)
- Management scripts: setup, migrate, update
- Dynamic extras discovery and installation
