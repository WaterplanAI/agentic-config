#!/usr/bin/env bash
# E2E Tests for install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Test: Fresh installation creates correct structure
test_fresh_install() {
  echo "=== test_fresh_install ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # Run install script
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Verify installation structure
  assert_dir_exists "$install_dir" "Install directory created"
  assert_file_exists "$install_dir/VERSION" "VERSION file exists"
  assert_dir_exists "$install_dir/core" "core/ directory exists"
  assert_dir_exists "$install_dir/core/commands/claude" "core/commands/claude exists"
  assert_dir_exists "$install_dir/core/agents" "core/agents exists"
  assert_dir_exists "$install_dir/core/skills" "core/skills exists"

  # Verify global command symlinks created
  assert_symlink_valid "$HOME/.claude/commands/agentic-setup.md" "agentic-setup command symlinked"
  assert_symlink_valid "$HOME/.claude/commands/agentic-update.md" "agentic-update command symlinked"
  assert_symlink_valid "$HOME/.claude/commands/agentic-migrate.md" "agentic-migrate command symlinked"

  cleanup_test_env
}

# Test: Custom installation path
test_custom_path_install() {
  echo "=== test_custom_path_install ==="
  setup_test_env

  local custom_path="$TEST_ROOT/custom/location"

  # Run install with custom path
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$custom_path" bash install.sh

  # Verify at custom location
  assert_dir_exists "$custom_path" "Custom install directory created"
  assert_file_exists "$custom_path/VERSION" "VERSION at custom path"

  cleanup_test_env
}

# Test: Path persistence to dotpath
test_path_persistence_dotpath() {
  echo "=== test_path_persistence_dotpath ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # Run install
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Verify dotpath created
  assert_file_exists "$HOME/.agents/.path" "dotpath file created"
  assert_file_contains "$HOME/.agents/.path" "$install_dir" "dotpath contains install path"

  cleanup_test_env
}

# Test: Path persistence to shell profile
test_path_persistence_shell() {
  echo "=== test_path_persistence_shell ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # Create shell profile
  touch "$HOME/.zshrc"
  export SHELL="/bin/zsh"

  # Run install
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Verify shell profile updated
  assert_file_contains "$HOME/.zshrc" "agentic-config path" "shell profile has marker"
  assert_file_contains "$HOME/.zshrc" "export AGENTIC_CONFIG_PATH=" "shell profile exports path"

  cleanup_test_env
}

# Test: Update existing installation
test_update_existing() {
  echo "=== test_update_existing ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # First install
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Create marker file to verify update
  echo "test" > "$install_dir/test_marker"

  # Run install again (should update)
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Marker should be gone (hard reset)
  if [[ ! -f "$install_dir/test_marker" ]]; then
    echo -e "${GREEN}PASS${NC}: Update performed hard reset"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Update did not reset installation"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Dry-run mode
test_dry_run() {
  echo "=== test_dry_run ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # Run with --dry-run
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh --dry-run

  # Nothing should be created
  if [[ ! -d "$install_dir" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run did not create installation"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run created files"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Nightly mode (skip git reset)
test_nightly_mode() {
  echo "=== test_nightly_mode ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # First install
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Create marker file
  echo "test" > "$install_dir/test_marker"

  # Run with --nightly (should preserve marker)
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh --nightly

  # Marker should still exist
  assert_file_exists "$install_dir/test_marker" "Nightly mode preserved local changes"

  cleanup_test_env
}

# Test: Self-hosted config reconciliation
test_self_hosted_reconciliation() {
  echo "=== test_self_hosted_reconciliation ==="
  setup_test_env

  # Use REPO_ROOT as install location (self-hosted)
  local install_dir="$TEST_ROOT/self-hosted"
  cp -R "$REPO_ROOT" "$install_dir"

  # Create .agentic-config.json to trigger reconciliation
  cat > "$install_dir/.agentic-config.json" <<EOF
{
  "version": "0.0.1",
  "project_type": "generic"
}
EOF

  # Run install
  cd "$install_dir"
  AGENTIC_CONFIG_DIR="$install_dir" bash "$install_dir/install.sh" --nightly

  # Verify config updated
  if command -v jq >/dev/null 2>&1; then
    local version
    version=$(jq -r '.version' "$install_dir/.agentic-config.json")
    local expected
    expected=$(cat "$install_dir/VERSION")
    assert_eq "$expected" "$version" "Self-hosted config reconciled to latest version"
  fi

  cleanup_test_env
}

# Test: XDG config persistence
test_xdg_config_persistence() {
  echo "=== test_xdg_config_persistence ==="
  setup_test_env

  local install_dir="$HOME/.agents/agentic-config"

  # Run install
  cd "$REPO_ROOT"
  AGENTIC_CONFIG_DIR="$install_dir" bash install.sh

  # Verify XDG config created
  assert_file_exists "$HOME/.config/agentic/config" "XDG config created"
  assert_file_contains "$HOME/.config/agentic/config" "path=$install_dir" "XDG config contains path"

  cleanup_test_env
}

# Run all tests
test_fresh_install
test_custom_path_install
test_path_persistence_dotpath
test_path_persistence_shell
test_update_existing
test_dry_run
test_nightly_mode
test_self_hosted_reconciliation
test_xdg_config_persistence

print_test_summary "install.sh E2E Tests"
