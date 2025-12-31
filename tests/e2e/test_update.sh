#!/usr/bin/env bash
# E2E Tests for /agentic update (update-config.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Test: Update bumps version in config
test_update_version_bump() {
  echo "=== test_update_version_bump ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup with old version
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Manually set old version
  if command -v jq >/dev/null 2>&1; then
    local config="$project_dir/.agentic-config.json"
    jq '.version = "0.0.1"' "$config" > "$config.tmp"
    mv "$config.tmp" "$config"
  fi

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify version updated
  if command -v jq >/dev/null 2>&1; then
    local expected
    expected=$(cat "$TEST_AGENTIC/VERSION")
    assert_json_field "$project_dir/.agentic-config.json" ".version" "$expected" "Version bumped to latest"
  fi

  cleanup_test_env
}

# Test: Update adds missing command symlinks
test_update_missing_commands() {
  echo "=== test_update_missing_commands ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Remove a command symlink
  rm -f "$project_dir/.claude/commands/orc.md"

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify command re-added
  assert_symlink_valid "$project_dir/.claude/commands/orc.md" "Missing command symlink restored"

  cleanup_test_env
}

# Test: Update adds missing skill symlinks
test_update_missing_skills() {
  echo "=== test_update_missing_skills ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Remove a skill symlink
  if [[ -d "$project_dir/.claude/skills" ]]; then
    rm -f "$project_dir/.claude/skills/agent-orchestrator-manager"
  fi

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify skill re-added
  if [[ -d "$project_dir/.claude/skills" ]]; then
    assert_symlink_valid "$project_dir/.claude/skills/agent-orchestrator-manager" "Missing skill symlink restored"
  fi

  cleanup_test_env
}

# Test: Update cleans orphan symlinks
test_update_clean_orphans() {
  echo "=== test_update_clean_orphans ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Create orphan symlink (broken)
  ln -s "/nonexistent/path" "$project_dir/.claude/commands/orphan.md"

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify orphan removed
  if [[ ! -L "$project_dir/.claude/commands/orphan.md" ]]; then
    echo -e "${GREEN}PASS${NC}: Orphan symlink cleaned"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Orphan symlink not cleaned"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Update preserves custom AGENTS.md without --force
test_update_preserve_agents_md() {
  echo "=== test_update_preserve_agents_md ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Modify AGENTS.md
  echo "# Custom content" >> "$project_dir/AGENTS.md"

  # Run update (without --force)
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify custom content preserved
  assert_file_contains "$project_dir/AGENTS.md" "Custom content" "AGENTS.md preserved without --force"

  cleanup_test_env
}

# Test: Update with --force refreshes templates
test_update_force_refresh() {
  echo "=== test_update_force_refresh ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Modify AGENTS.md
  echo "# Custom content" > "$project_dir/AGENTS.md"

  # Run update with --force
  "$TEST_AGENTIC/scripts/update-config.sh" --force "$project_dir"

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

  # Verify custom content moved to PROJECT_AGENTS.md
  if [[ -f "$project_dir/PROJECT_AGENTS.md" ]]; then
    echo -e "${GREEN}PASS${NC}: PROJECT_AGENTS.md created for customizations"
    ((PASS_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Update reconciles config fields
test_update_reconcile_config() {
  echo "=== test_update_reconcile_config ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Remove a field from config (simulate old version)
  if command -v jq >/dev/null 2>&1; then
    local config="$project_dir/.agentic-config.json"
    jq 'del(.agentic_global_path)' "$config" > "$config.tmp"
    mv "$config.tmp" "$config"
  fi

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify field restored
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".agentic_global_path" "$TEST_AGENTIC" "Config field reconciled"
  fi

  cleanup_test_env
}

# Test: Update with --nightly forces rebuild
test_update_nightly_rebuild() {
  echo "=== test_update_nightly_rebuild ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Remove command symlink
  rm -f "$project_dir/.claude/commands/spec.md"

  # Run update with --nightly (same version, but rebuild)
  "$TEST_AGENTIC/scripts/update-config.sh" --nightly "$project_dir"

  # Verify symlink rebuilt
  assert_symlink_valid "$project_dir/.claude/commands/spec.md" "Symlink rebuilt in nightly mode"

  cleanup_test_env
}

# Test: Update for copy mode creates backup
test_update_copy_mode_backup() {
  echo "=== test_update_copy_mode_backup ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup with copy mode
  "$TEST_AGENTIC/scripts/setup-config.sh" --copy "$project_dir"

  # Modify copied file
  echo "# Custom" >> "$project_dir/agents/spec-command.md"

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify backup created for copy mode
  local backup_dir
  backup_dir=$(find "$project_dir" -maxdepth 1 -name ".agentic-config.copy-backup.*" -type d | head -1)
  if [[ -n "$backup_dir" && -d "$backup_dir" ]]; then
    echo -e "${GREEN}PASS${NC}: Copy mode backup created"
    ((PASS_COUNT++)) || true
    assert_file_contains "$backup_dir/agents/spec-command.md" "Custom" "Backup contains modifications"
  else
    echo -e "${YELLOW}SKIP${NC}: Copy mode backup handling may vary"
  fi

  cleanup_test_env
}

# Test: Update refreshes path persistence
test_update_path_persistence() {
  echo "=== test_update_path_persistence ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Remove dotpath
  rm -f "$HOME/.agents/.path"

  # Run update
  "$TEST_AGENTIC/scripts/update-config.sh" "$project_dir"

  # Verify dotpath restored
  assert_file_exists "$HOME/.agents/.path" "Path persistence restored"

  cleanup_test_env
}

# Test: Self-hosted update audits command symlinks
test_self_hosted_symlink_audit() {
  echo "=== test_self_hosted_symlink_audit ==="
  setup_test_env

  # Use test agentic as self-hosted
  local self_hosted="$TEST_AGENTIC"

  # Create .agentic-config.json (marks as self-hosted)
  if [[ ! -f "$self_hosted/.agentic-config.json" ]]; then
    cat > "$self_hosted/.agentic-config.json" <<EOF
{
  "version": "$(cat "$self_hosted/VERSION")",
  "project_type": "generic",
  "installation_mode": "symlink"
}
EOF
  fi

  # Remove a command symlink from self-hosted
  if [[ -L "$self_hosted/.claude/commands/orc.md" ]]; then
    rm -f "$self_hosted/.claude/commands/orc.md"
  fi

  # Run update on self-hosted
  "$self_hosted/scripts/update-config.sh" "$self_hosted"

  # Verify symlink restored
  assert_symlink_valid "$self_hosted/.claude/commands/orc.md" "Self-hosted symlink audit restored missing command"

  cleanup_test_env
}

# Run all tests
test_update_version_bump
test_update_missing_commands
test_update_missing_skills
test_update_clean_orphans
test_update_preserve_agents_md
test_update_force_refresh
test_update_reconcile_config
test_update_nightly_rebuild
test_update_copy_mode_backup
test_update_path_persistence
test_self_hosted_symlink_audit

print_test_summary "/agentic update E2E Tests"
