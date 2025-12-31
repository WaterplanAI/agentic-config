#!/usr/bin/env bash
# E2E Tests for /agentic migrate (migrate-existing.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Helper: Create manual installation
create_manual_installation() {
  local project_dir="$1"

  create_test_project "$project_dir" "generic"

  # Create manual agents/ directory
  mkdir -p "$project_dir/agents"
  cat > "$project_dir/agents/spec-command.md" <<'EOF'
# Manual spec command
This is a manually created workflow.
EOF

  # Create manual AGENTS.md
  cat > "$project_dir/AGENTS.md" <<'EOF'
# Manual Agents Configuration

## Custom Section
This is my custom project-specific content.

## Build Rules
- Always use make
EOF

  # Create .claude directory with manual commands
  mkdir -p "$project_dir/.claude/commands"
  cat > "$project_dir/.claude/commands/custom.md" <<'EOF'
# Custom Command
EOF
}

# Test: Migrate converts manual installation
test_migrate_manual_installation() {
  echo "=== test_migrate_manual_installation ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify converted to symlink mode
  assert_file_exists "$project_dir/.agentic-config.json" "Config file created"
  assert_symlink_valid "$project_dir/agents" "agents/ converted to symlink"

  cleanup_test_env
}

# Test: Migrate creates backup
test_migrate_backup_creation() {
  echo "=== test_migrate_backup_creation ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify backup created
  local backup_dir
  backup_dir=$(find "$project_dir" -maxdepth 1 -name ".agentic-config.backup.*" -type d | head -1)
  if [[ -n "$backup_dir" && -d "$backup_dir" ]]; then
    echo -e "${GREEN}PASS${NC}: Backup directory created"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: No backup directory found"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Migrate preserves custom AGENTS.md content
test_migrate_preserve_agents_content() {
  echo "=== test_migrate_preserve_agents_content ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify custom content preserved to PROJECT_AGENTS.md
  assert_file_exists "$project_dir/PROJECT_AGENTS.md" "PROJECT_AGENTS.md created"
  assert_file_contains "$project_dir/PROJECT_AGENTS.md" "Custom Section" "Custom content preserved"
  assert_file_contains "$project_dir/PROJECT_AGENTS.md" "Always use make" "Build rules preserved"

  cleanup_test_env
}

# Test: Migrate backs up manual agents/ directory
test_migrate_backup_agents() {
  echo "=== test_migrate_backup_agents ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify manual agents/ in backup
  local backup_dir
  backup_dir=$(find "$project_dir" -maxdepth 1 -name ".agentic-config.backup.*" -type d | head -1)
  if [[ -n "$backup_dir" ]]; then
    assert_file_exists "$backup_dir/agents/spec-command.md" "Manual agents/ backed up"
    assert_file_contains "$backup_dir/agents/spec-command.md" "manually created workflow" "Manual content in backup"
  fi

  cleanup_test_env
}

# Test: Migrate dry-run mode
test_migrate_dry_run() {
  echo "=== test_migrate_dry_run ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run with --dry-run
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --dry-run "$project_dir" || true

  # Verify no changes made
  if [[ ! -f "$project_dir/.agentic-config.json" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run did not create config"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run created files"
    ((FAIL_COUNT++)) || true
  fi

  # Verify agents/ still directory
  if [[ -d "$project_dir/agents" && ! -L "$project_dir/agents" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run preserved agents/ directory"
    ((PASS_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Migrate installs all command symlinks
test_migrate_install_commands() {
  echo "=== test_migrate_install_commands ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify commands installed
  assert_symlink_valid "$project_dir/.claude/commands/spec.md" "spec command installed"
  assert_symlink_valid "$project_dir/.claude/commands/orc.md" "orc command installed"
  assert_symlink_valid "$project_dir/.claude/commands/squash.md" "squash command installed"

  cleanup_test_env
}

# Test: Migrate installs hooks
test_migrate_install_hooks() {
  echo "=== test_migrate_install_hooks ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify hooks installed
  assert_dir_exists "$project_dir/.claude/hooks/pretooluse" "pretooluse hooks installed"

  # Verify settings.json hook registration
  if [[ -f "$project_dir/.claude/settings.json" ]]; then
    assert_file_contains "$project_dir/.claude/settings.json" "pretooluse" "Hooks registered"
  fi

  cleanup_test_env
}

# Test: Migrate records agentic_global_path
test_migrate_global_path_recording() {
  echo "=== test_migrate_global_path_recording ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify global path recorded
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".agentic_global_path" "$TEST_AGENTIC" "Global path recorded"
  fi

  cleanup_test_env
}

# Test: Migrate sets installation_mode to symlink
test_migrate_installation_mode() {
  echo "=== test_migrate_installation_mode ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify installation mode
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".install_mode" "symlink" "Installation mode set to symlink"
  fi

  cleanup_test_env
}

# Test: Migrate preserves custom commands
test_migrate_preserve_custom_commands() {
  echo "=== test_migrate_preserve_custom_commands ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify custom command preserved
  assert_file_exists "$project_dir/.claude/commands/custom.md" "Custom command preserved"

  # Should coexist with new symlinks
  assert_symlink_valid "$project_dir/.claude/commands/spec.md" "New commands coexist with custom"

  cleanup_test_env
}

# Test: Migrate handles missing .agent directory
test_migrate_no_agent_dir() {
  echo "=== test_migrate_no_agent_dir ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Remove .agent if exists
  rm -rf "$project_dir/.agent"

  # Run migrate (should succeed) (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify migration succeeded
  assert_file_exists "$project_dir/.agentic-config.json" "Migration succeeded without .agent"

  cleanup_test_env
}

# Test: Migrate updates path persistence
test_migrate_path_persistence() {
  echo "=== test_migrate_path_persistence ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_manual_installation "$project_dir"

  # Run migrate (with --force to skip confirmation)
  "$TEST_AGENTIC/scripts/migrate-existing.sh" --force "$project_dir"

  # Verify dotpath created
  assert_file_exists "$HOME/.agents/.path" "Dotpath created"
  assert_file_contains "$HOME/.agents/.path" "$TEST_AGENTIC" "Dotpath contains correct path"

  cleanup_test_env
}

# Run all tests
test_migrate_manual_installation
test_migrate_backup_creation
test_migrate_preserve_agents_content
test_migrate_backup_agents
test_migrate_dry_run
test_migrate_install_commands
test_migrate_install_hooks
test_migrate_global_path_recording
test_migrate_installation_mode
test_migrate_preserve_custom_commands
test_migrate_no_agent_dir
test_migrate_path_persistence

print_test_summary "/agentic migrate E2E Tests"
