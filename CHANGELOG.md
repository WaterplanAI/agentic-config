# Changelog

All notable changes to agentic-config.

## [Unreleased]

### Added

- Path persistence library (`scripts/lib/path-persistence.sh`) for reliable AGENTIC_CONFIG_PATH persistence
  - `persist_agentic_path`: Writes installation path to multiple locations
  - `discover_agentic_path`: Priority-based discovery algorithm across all locations
  - `persist_to_dotpath`: Creates `~/.agents/.path` with absolute installation path
  - `persist_to_shell_profile`: Adds export to shell profiles with idempotency (bash/zsh)
  - `persist_to_xdg_config`: Creates XDG-compliant config at `~/.config/agentic/config`
  - Marker-based idempotency prevents duplicate shell profile entries
- Agentic root discovery library (`core/lib/agentic-root.sh`) for finding installation root
  - `get_agentic_root`: Walks up directory tree to find agentic-config installation
  - Looks for `VERSION` marker file and `core/` directory
  - Git repository root fallback when VERSION file exists there
  - Enables commands/skills to work from any nested directory or git worktree
- Config loader library (`core/lib/config-loader.sh`) for unified configuration loading
  - Priority order: Environment variables > `.env` > `.agentic-config.conf.yml`
  - `load_agentic_config`: Loads all config with priority resolution
  - `get_agentic_config`: Get specific value with priority lookup
- `.agentic-config.conf.yml` as YAML alternative to `.env` for project configuration
- Spec path resolver library (`core/lib/spec-resolver.sh`) for automatic external/local specs routing
  - `resolve_spec_path`: Automatically determines spec location based on configuration
  - `commit_spec_changes`: Routes commits to external or local repository based on spec path
  - No code changes needed when switching between external/local configurations
- External specs documentation (`docs/external-specs-storage.md`) with conditional loading pattern
- `/dry-run` skill for simulating command execution without file modifications
  - Sets dry_run flag in session state, executes commands with read-only constraint
  - Prevents all file writes except outputs/session/status.yml during simulation
  - Useful for testing workflows safely (e.g., `/dry-run /po_spec path/to/spec.md`)
- Pretooluse hook for hard enforcement of dry-run mode
  - Blocks Write, Edit, NotebookEdit tools when dry_run flag is enabled
  - Analyzes Bash commands to detect file-writing operations
  - Session status file (outputs/session/status.yml) exempt from blocking
  - Fail-open principle: allows operations on errors to prevent blocking legitimate work
  - Installed automatically during setup, migrate, and update workflows
- Source file validation in `/agentic update nightly` symlink rebuild
  - Validates source files exist before creating symlinks
  - Skips missing files with clear reporting to prevent broken symlinks
- `install.sh --nightly` flag to skip git reset and use local state (for development)
- `install.sh` positional argument for custom installation path (e.g., `bash -s -- /custom/path`)
- Config reconciliation function (`reconcile_config`) in version-manager.sh
  - Adds missing fields to `.agentic-config.json` without overwriting existing values
  - Ensures `install_mode`, `agentic_global_path`, and `auto_check` fields exist
  - Updates version and timestamp when changes are made
- `update-config.sh --nightly` flag for same-version updates
  - Reconciles config schema even when versions match
  - Rebuilds all symlinks (commands, skills, hooks)
  - Useful when new config fields added in development
- `install.sh` now reconciles self-hosted config after global install

### Changed

- `.agentic-config.json` schema now includes `agentic_global_path` field for project-local discovery
- Agentic root discovery (`core/lib/agentic-root.sh`) enhanced with 6-level priority algorithm:
  1. `$AGENTIC_CONFIG_PATH` environment variable (if set)
  2. `~/.agents/.path` file (simple text file)
  3. `~/.config/agentic/config` (XDG-compliant)
  4. `.agentic-config.json` in current project (`agentic_global_path` field)
  5. PWD traversal for `VERSION` + `core/` markers (backward compatibility)
  6. Default fallback: `$HOME/.agents/agentic-config`
- Installation scripts now persist `AGENTIC_CONFIG_PATH` to multiple locations for robust discovery
  - `install.sh` calls `persist_agentic_path` after successful installation
  - `scripts/install-global.sh` adds export to shell profiles with marker-based idempotency
  - Shell profile modification detects user's shell (bash/zsh) and adds export only once
- Agent workflows updated with path persistence:
  - `/agentic setup` now writes `agentic_global_path` to `.agentic-config.json`
  - `/agentic update` refreshes persistence locations during update
  - `/agentic migrate` sets up persistence during migration
- AGENTS.md simplified with conditional documentation pattern (detailed docs in `docs/`)
- `/branch` command now uses spec-resolver.sh for automatic path resolution
- All `/spec` stage files (CREATE, RESEARCH, PLAN, PLAN_REVIEW, IMPLEMENT, REVIEW, TEST, DOCUMENT) now use `commit_spec_changes` for spec commits
- Dry-run enforcement migrated from instruction-based to hook-based
  - Removed AGENTS.md dry-run verification section (replaced by pretooluse hook)
  - Hard enforcement at Claude Code tool level prevents accidental file modifications
- `/agentic update` nightly mode now requires explicit `nightly` argument
  - No longer auto-infers nightly mode based on version matching
  - Clear semantics: `/agentic update nightly` for symlink rebuild
- `/full-life-cycle-pr` and `/o_spec` session handling improved
  - No longer archives in-progress sessions when starting fresh
  - Prevents conflicts with parallel agents from `/orc`, `/spawn`, `/po_spec`
  - Sessions naturally become stale over time without destructive cleanup

### Fixed

- Removed redundant empty string check in spec-resolver.sh (line 204 unreachable due to `${VAR:-default}` handling empty strings)
- Fixed pattern match false-positive in spec-resolver.sh when `EXT_SPECS_LOCAL_PATH` is empty (guards against `*"//specs/"*` false matches)
- Added git reset on commit failure in spec-resolver.sh to unstage files after failed commits (prevents partial state)
- Standardized timestamp format in version-manager.sh to UTC ISO 8601 (`date -u +%Y-%m-%dT%H:%M:%SZ`) eliminating GNU/BSD date timezone inconsistencies
- **Critical**: Config file lookup now uses project root instead of global installation path
  - Added `get_project_root()` function to `agentic-root.sh` for proper project discovery
  - `config-loader.sh` now uses `get_project_root()` for `.env` and `.agentic-config.conf.yml`
  - `spec-resolver.sh` now uses `get_project_root()` for spec directory paths
  - `external-specs.sh` now uses `get_project_root()` for `.specs` directory
  - Previously: all projects using development repo as global install inherited its `.env` config
  - Now: each project correctly loads its own configuration files
- spec-resolver.sh pure bash depth calculation - replaced `tr`/`wc` with `${parent_dir//[!\/]/}` pattern for restricted shell compatibility
- external-specs.sh trap-based lock cleanup - added `trap '_release_lock "$lockdir"' EXIT` to prevent lock leaks on failure paths
- path-persistence.sh path validation - validates install path contains only safe characters `[a-zA-Z0-9_./-]+` before writing to shell profile (prevents shell injection)
- install.sh git clean flag - removed `-x` flag to preserve gitignored files (changed from `git clean -fdx` to `git clean -fd`)
- config-loader.sh unbalanced quote handling - removed contradictory stripping code that violated "leave as-is" comment
- update-config.sh relative symlinks in self-hosted mode - uses relative paths when target is repository root per PROJECT_AGENTS.md requirement
- Path resolution documentation in AGENTS.md and templates - clarified distinction between project root (`$PWD`) and global agentic installation (`$AGENTIC_CONFIG_PATH` or `~/.agents/agentic-config`)
  - Replaced confusing traversal pattern with explicit AGENTIC_GLOBAL pattern across 20 files
  - Updated all spec stage agents (CREATE, PLAN, RESEARCH, PLAN_REVIEW, IMPLEMENT, REVIEW, DOCUMENT, TEST) to use AGENTIC_GLOBAL
  - Updated command files (branch, o_spec, po_spec) to use AGENTIC_GLOBAL
  - Updated docs/external-specs-storage.md to document new pattern
  - CRITICAL note added: `core/` does NOT exist at project root (only specific commands are symlinked)
- IMPLEMENT spec stage now enforces `spec(NNN): IMPLEMENT - <title>` format on ALL commits (was missing on first commit)
- Hook execution in non-Python projects - added `--no-project` flag to all `uv run` hook commands
  - Fixed in `.claude/settings.json`, `scripts/setup-config.sh`, `.claude/commands/init.md`, `scripts/update-config.sh`
  - Prevents "project not found" errors when hooks run in directories without `pyproject.toml`
- Hook path resolution when Claude changes working directory
  - Hook command now uses absolute paths instead of relative paths
  - `dry-run-guard.py` accepts project root as CLI argument
  - Prevents "No such file or directory" errors when CWD differs from project root
  - Updated in `setup-config.sh`, `update-config.sh`, `init.md`, and hook script

## [0.1.14] - 2025-12-26

### Added

- `install.sh` - curl-installable script for single-command global installation
  - Clones/updates repo to `~/.agents/agentic-config` (configurable via `AGENTIC_CONFIG_DIR`)
  - Pre-flight checks for git and OS compatibility (macOS/Linux)
  - Colored terminal output with clear next steps after installation
  - Handles both fresh installs and updates gracefully
  - `--dry-run` flag for preview mode (no changes made)
- `chore` GitHub label (#a2eeef) for maintenance and housekeeping tasks (#15)
- `--with-squashed-commits` flag for `/milestone` to opt-in include squashed commit references (#14)
- `.gitignore` patterns to prevent tracking invalid nested symlinks in `core/`
- `cleanup_invalid_nested_symlinks()` function in `update-config.sh` for automatic cleanup
- Pre-cleanup step in `/init` command to remove invalid symlinks before creating new ones
- `validate_symlink_target()` function in `setup-config.sh` to prevent creating symlinks inside source directories

### Changed

- Default install location from `~/projects/agentic-config` to `~/.agents/agentic-config` (hidden directory, standard for user configs)
- README Quickstart section now uses curl install pattern as primary installation method
- `/init` command simplified to post-clone symlink repair only (no longer runs global install)
- `setup-config.sh` and `update-config.sh` no longer install `agentic-*` commands (now globally installed via `install.sh`)
- `/full-life-cycle-pr` now uses `/po_spec` instead of `/o_spec` for phased orchestration (#13)
- `/milestone` now excludes squashed commit references by default (use `--with-squashed-commits` to include) (#14)
- README quickstart step 4 now includes explicit `claude` command before `/agentic setup`

### Fixed

- UUID generation parse errors in shell commands across 6 files - replaced `tr '[:upper:]' '[:lower:]'` with POSIX-safe `tr 'A-Z' 'a-z'` (#11)
- CLI validation for `--type-checker` and `--linter` flags in `setup-config.sh` - now rejects invalid values (#7)
- Command injection risk in `setup-config.sh` - replaced `eval "$detected"` with safe grep/cut parsing (#7)
- Pipe character escaping in `template-processor.sh` sed pattern (#7)
- Invalid self-referential symlinks being created inside `core/agents/` and `core/skills/` directories

## [0.1.13] - 2025-12-26

### Added

- `/po_spec` command for phased spec orchestration (multi-phase feature decomposition with DAG execution)
- `product-manager` skill for decomposing large features into concrete development phases
- `--auto` flag for `/milestone` to skip all confirmation gates (autonomous execution)
- Workflow state persistence for `/full-life-cycle-pr`, `/o_spec`, and `/po_spec` commands
  - Session-based state tracking in `outputs/orc/{YYYY}/{MM}/{DD}/{HHMMSS}-{UUID}/workflow_state.yml`
  - Automatic resume detection for interrupted workflows
  - AI-interpreted state updates with current step/stage tracking
  - Orchestrator behavioral constraints to enforce delegation pattern

### Changed

- `/full-life-cycle-pr` now passes `--auto` to `/milestone` for fully autonomous execution after initial confirmation
- Single confirmation gate design: user confirms once at start, then workflow runs to completion
- `/full-life-cycle-pr` now creates session directories and maintains workflow state for resume capability
- `/o_spec` now maintains workflow state with per-stage tracking across all modifiers (full/normal/lean/leanest)

### Fixed

- `/fork-terminal` security vulnerability: prevents dangerous execution in system directories
  - PATH argument now optional with safe default `/tmp/claude/<uuid>`
  - Validates PATH before execution to reject root (/) and system directories (/bin, /usr, /etc, /System, /sbin, /Library)
  - Automatically creates isolated temporary directory with UUID when PATH not provided
  - Clear error messages on invalid paths with safe invocation examples in SAFETY section

## [0.1.12] - 2025-12-18

### Fixed

- Renamed `low-priority` label to `priority: low` for consistency
- `py-uv` alias now correctly maps to `python-uv` template in setup script (fixes #8)
- Added `bun` alias for `ts-bun` template for consistency
- Synced usage docs and error message to show same type format

## [0.1.11] - 2025-12-17

### Added

- `.github/CONTRIBUTING.md` with label documentation and contribution guidelines
- GitHub labels: `priority: critical`, `priority: high`, `priority: low`, `blocked`, `needs-triage`, `complex`
- `LICENSE` file (MIT)

## [0.1.10] - 2025-12-17

### Added

- `--type-checker` and `--linter` CLI flags for `setup-config.sh` to specify Python tooling variants
- Autodetection of existing Python tooling from pyproject.toml, setup.cfg, and requirements*.txt
- `detect_python_tooling()` function in `scripts/lib/detect-project-type.sh` for tooling detection
- `{{VAR}}` placeholder substitution support in `scripts/lib/template-processor.sh`
- `scripts/test-python-tooling-variants.sh` test suite (17 tests) for variant validation

### Changed

- python-pip template default tooling from mypy+pylint to pyright+ruff (aligns with python-uv and python-poetry)
- `templates/python-pip/AGENTS.md.template` now uses variable placeholders for configurable tooling

## [0.1.9] - 2025-12-17

### Fixed

- 5 symlinks converted from absolute to relative paths for portability (.gemini/commands/spec, .gemini/commands/spec.toml, agents, .codex/prompts/spec.md, .agent/workflows/spec.md)

### Changed

- PROJECT_AGENTS.md now documents exceptions for git commit author identity and functional emojis in specific agent files

## [0.1.8] - 2025-12-17

### Fixed

- New agentic-*.md agents now installed for copy mode users during update (previously only existing agents were updated)
- SPEC_ARG with spaces now handled correctly in `/full-life-cycle-pr` (quoted strings parsed properly)
- Version tracking now always updates when copy mode replaces assets (previously could skip if template changes pending)
- Backup verification for agents/ now validates file count (not just directory existence) to catch partial backups
- Invalid INSTALL_MODE values now rejected with clear error message during update
- Documentation inconsistency in `/milestone` (removed `--no-tag` alias, only `--skip-tag` supported)
- Dry-run output in `setup-config.sh` now shows copy mode indicator

## [0.1.7] - 2025-12-17

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
