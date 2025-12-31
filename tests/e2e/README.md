# E2E Test Suite

Comprehensive end-to-end tests for agentic-config installation and lifecycle management.

## Quick Start

Run all tests:
```bash
./tests/e2e/run_all.sh
```

Run individual test suite:
```bash
./tests/e2e/test_install.sh
./tests/e2e/test_setup.sh
./tests/e2e/test_migrate.sh
./tests/e2e/test_update.sh
```

## Prerequisites

Required:
- git
- bash

Optional (recommended):
- jq (required for JSON validation tests)

## Test Suites

### install.sh Tests (`test_install.sh`)

Tests the global installation script (`install.sh`) that installs agentic-config centrally.

**Functions tested:**
- `test_fresh_install` - Verifies fresh installation creates correct directory structure (core/, VERSION, global command symlinks)
- `test_custom_path_install` - Tests installation to custom location via `AGENTIC_CONFIG_DIR`
- `test_path_persistence_dotpath` - Validates path written to `~/.agents/.path`
- `test_path_persistence_shell` - Validates shell profile updated with `AGENTIC_CONFIG_PATH` export
- `test_update_existing` - Tests update behavior performs hard reset of existing installation
- `test_dry_run` - Verifies `--dry-run` mode creates no files
- `test_nightly_mode` - Tests `--nightly` flag skips git reset, preserving local changes
- `test_self_hosted_reconciliation` - Validates config version reconciliation for self-hosted installations
- `test_xdg_config_persistence` - Validates XDG config file creation at `~/.config/agentic/config`

**Coverage:**
- Installation directory structure creation
- Global command symlink creation in `~/.claude/commands/`
- Path persistence (dotpath, shell profile, XDG config)
- Update/reinstall behavior
- Dry-run mode
- Nightly mode (skip git reset)
- Self-hosted config reconciliation

### /agentic setup Tests (`test_setup.sh`)

Tests project-level setup via `scripts/setup-config.sh` (invoked by `/agentic setup` command).

**Functions tested:**
- `test_setup_new_project` - Verifies setup creates config, symlinks agents/, creates .claude/ structure
- `test_setup_project_type_detection` - Tests automatic project type detection (python-poetry, python-pip, typescript, rust)
- `test_setup_explicit_type` - Tests `--type` flag for explicit project type
- `test_setup_agents_md` - Validates AGENTS.md creation from template
- `test_setup_dry_run` - Verifies `--dry-run` creates no files
- `test_setup_gitignore_creation` - Tests .gitignore creation with sensible defaults (outputs/)
- `test_setup_git_init` - Validates git initialization when not in repo
- `test_setup_preserve_agents_md` - Tests existing AGENTS.md content preserved to PROJECT_AGENTS.md
- `test_setup_copy_mode` - Tests `--copy` flag creates copies instead of symlinks
- `test_setup_global_path_recording` - Validates `agentic_global_path` recorded in config
- `test_setup_hooks_installation` - Tests hooks installation and settings.json registration
- `test_setup_selective_tools` - Tests `--tools` flag for selective tool installation (claude, gemini)

**Coverage:**
- .agentic-config.json creation
- Project type detection and configuration
- agents/ symlink creation
- .claude/ command and skill symlinks
- AGENTS.md/PROJECT_AGENTS.md handling
- Hooks installation and registration
- Git initialization
- .gitignore management
- Copy vs symlink modes
- Selective tool installation

### /agentic migrate Tests (`test_migrate.sh`)

Tests migration from manual installation to centralized system via `scripts/migrate-existing.sh`.

**Functions tested:**
- `test_migrate_manual_installation` - Tests conversion of manual agents/ directory to symlink
- `test_migrate_backup_creation` - Validates backup directory creation (`.agentic-config.backup.<timestamp>`)
- `test_migrate_preserve_agents_content` - Tests custom AGENTS.md content moved to PROJECT_AGENTS.md
- `test_migrate_backup_agents` - Validates manual agents/ directory backed up
- `test_migrate_dry_run` - Verifies `--dry-run` makes no changes
- `test_migrate_install_commands` - Tests all command symlinks installed
- `test_migrate_install_hooks` - Validates hooks installed and registered
- `test_migrate_global_path_recording` - Tests `agentic_global_path` recorded
- `test_migrate_installation_mode` - Validates `install_mode` set to "symlink"
- `test_migrate_preserve_custom_commands` - Tests custom commands preserved alongside new symlinks
- `test_migrate_no_agent_dir` - Tests migration succeeds without .agent directory
- `test_migrate_path_persistence` - Validates dotpath updated

**Coverage:**
- Manual to centralized migration
- Backup creation and preservation
- AGENTS.md content migration
- Command and skill symlink installation
- Hooks installation
- Custom command preservation
- Path persistence
- Configuration creation

### /agentic update Tests (`test_update.sh`)

Tests project update via `scripts/update-config.sh` (invoked by `/agentic update` command).

**Functions tested:**
- `test_update_version_bump` - Tests version bumped in .agentic-config.json
- `test_update_missing_commands` - Validates missing command symlinks restored
- `test_update_missing_skills` - Tests missing skill symlinks restored
- `test_update_clean_orphans` - Validates broken symlinks removed
- `test_update_preserve_agents_md` - Tests AGENTS.md preserved without `--force`
- `test_update_force_refresh` - Tests `--force` backs up and refreshes templates
- `test_update_reconcile_config` - Validates missing config fields restored
- `test_update_nightly_rebuild` - Tests `--nightly` forces rebuild even with same version
- `test_update_copy_mode_backup` - Validates backup created for copy mode installations
- `test_update_path_persistence` - Tests dotpath restored if missing
- `test_self_hosted_symlink_audit` - Tests self-hosted installations audit and restore command symlinks

**Coverage:**
- Version reconciliation
- Symlink repair (commands, skills)
- Orphan symlink cleanup
- AGENTS.md preservation vs refresh
- Config field reconciliation
- Nightly mode rebuild
- Copy mode backup handling
- Path persistence refresh
- Self-hosted symlink audit

## Test Utilities

Shared utilities in `test_utils.sh`:

### Environment Management

- `setup_test_env()` - Creates isolated test environment with:
  - Temporary $HOME and $XDG_CONFIG_HOME
  - Test copy of agentic-config repository
  - Environment variable configuration for local testing
  - Branch-aware installation (uses current branch)

- `cleanup_test_env()` - Removes test environment and unsets variables

### Assertions

- `assert_eq <expected> <actual> <msg>` - String equality
- `assert_file_exists <file> <msg>` - File existence
- `assert_dir_exists <dir> <msg>` - Directory existence
- `assert_symlink_exists <link> <msg>` - Symlink existence (may be broken)
- `assert_symlink_valid <link> <msg>` - Symlink exists and target exists
- `assert_file_contains <file> <pattern> <msg>` - File contains grep pattern
- `assert_json_field <file> <jq_field> <expected> <msg>` - JSON field equality (requires jq)
- `assert_command_success <cmd> <msg>` - Command exits with 0
- `assert_command_failure <cmd> <msg>` - Command exits with non-zero

All assertions:
- Print colored PASS/FAIL status
- Increment PASS_COUNT or FAIL_COUNT
- Return appropriate exit codes

### Helpers

- `create_test_project <dir> <type>` - Creates test project with git repo
  - Supported types: generic, python-poetry, python-pip, typescript, rust
  - Initializes git repository
  - Creates type-specific files (pyproject.toml, package.json, etc.)

- `print_test_summary <name>` - Prints pass/fail summary and returns FAIL_COUNT

## Environment Isolation

Tests run in complete isolation to prevent interference with host system:

1. **Temporary HOME** - Each test uses fresh temporary home directory
2. **Environment Variables** - Custom $HOME, $XDG_CONFIG_HOME, $AGENTIC_CONFIG_PATH
3. **Local Repository** - Tests use `file://` protocol to clone from local repo (current branch)
4. **Cleanup Guarantee** - All test environments cleaned up via trap handlers

This ensures:
- No modification to user's actual configuration
- No interference between test runs
- Reproducible test results
- Safe parallel execution

## Writing New Tests

1. Source utilities: `source "$SCRIPT_DIR/test_utils.sh"`
2. Create test function: `test_feature_name() { ... }`
3. Structure:
   ```bash
   test_feature_name() {
     echo "=== test_feature_name ==="
     setup_test_env

     # Test setup
     local project_dir="$TEST_ROOT/test-project"
     create_test_project "$project_dir" "generic"

     # Execute operation under test
     "$TEST_AGENTIC/scripts/some-script.sh" "$project_dir"

     # Assertions
     assert_file_exists "$project_dir/.agentic-config.json" "Config created"

     cleanup_test_env
   }
   ```
4. Call test at end of file
5. Add to `run_all.sh` if creating new test suite

**Best Practices:**
- Use descriptive test names: `test_<action>_<scenario>`
- Include cleanup_test_env even if test fails (use trap if needed)
- Use assertion messages to explain what's being validated
- Test both success and failure paths
- Test edge cases (missing files, empty directories, etc.)

## CI/CD Integration

Tests are designed for CI/CD pipelines:

**Exit Codes:**
- 0 - All tests passed
- Non-zero - One or more tests failed

**Output:**
- Colored output when TTY detected
- Plain text for CI environments
- Summary includes suite-level and test-level results

**Example GitHub Actions integration:**
```yaml
- name: Run E2E Tests
  run: ./tests/e2e/run_all.sh
```

**Example pre-commit hook:**
```bash
#!/bin/bash
./tests/e2e/run_all.sh || {
  echo "E2E tests failed"
  exit 1
}
```

## Troubleshooting

### Tests fail with "jq not installed"
- Install jq: `brew install jq` (macOS) or `apt-get install jq` (Linux)
- Tests gracefully skip JSON validation if jq unavailable

### Tests fail with permission errors
- Ensure test scripts are executable: `chmod +x tests/e2e/*.sh`

### Tests leave temporary files
- Tests should clean up automatically
- Manual cleanup: `rm -rf /tmp/tmp.*` (careful - only remove test directories)

### Tests fail when run from different branch
- Tests use current branch via `git branch --show-current`
- Ensure you're on the branch you want to test

### Symlink tests fail on Windows
- Windows symlinks require special permissions
- Consider running tests in WSL or Linux environment
