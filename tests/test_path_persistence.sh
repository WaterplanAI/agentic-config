#!/usr/bin/env bash
# Unit tests for path-persistence.sh
set -euo pipefail

# Test setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_TMP=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

setup() {
  TEST_TMP=$(mktemp -d)
  export HOME="$TEST_TMP/home"
  mkdir -p "$HOME"

  # Create fake install directory
  mkdir -p "$TEST_TMP/install/agentic-config"

  # Source the library
  source "$REPO_ROOT/scripts/lib/path-persistence.sh"
}

teardown() {
  [[ -n "$TEST_TMP" ]] && rm -rf "$TEST_TMP"
  unset AGENTIC_CONFIG_PATH
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local msg="${3:-}"

  if [[ "$expected" == "$actual" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg"
    echo "  Expected: '$expected'"
    echo "  Actual:   '$actual'"
    ((FAIL_COUNT++)) || true
  fi
}

assert_file_exists() {
  local file="$1"
  local msg="${2:-}"

  if [[ -f "$file" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - file does not exist: $file"
    ((FAIL_COUNT++)) || true
  fi
}

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  local msg="${3:-}"

  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - pattern not found: $pattern"
    ((FAIL_COUNT++)) || true
  fi
}

# Test: persist_to_dotpath creates ~/.agents/.path
test_persist_to_dotpath() {
  echo "=== test_persist_to_dotpath ==="
  setup

  local install_path="$TEST_TMP/install/agentic-config"
  persist_to_dotpath "$install_path"

  assert_file_exists "$HOME/.agents/.path" "dotpath file created"
  assert_eq "$install_path" "$(cat "$HOME/.agents/.path")" "dotpath contains correct path"

  teardown
}

# Test: persist_to_xdg_config creates XDG config
test_persist_to_xdg_config() {
  echo "=== test_persist_to_xdg_config ==="
  setup

  local install_path="$TEST_TMP/install/agentic-config"
  persist_to_xdg_config "$install_path"

  assert_file_exists "$HOME/.config/agentic/config" "XDG config created"
  assert_file_contains "$HOME/.config/agentic/config" "path=$install_path" "XDG config contains path"

  teardown
}

# Test: persist_to_shell_profile adds to .zshrc
test_persist_to_shell_profile_zsh() {
  echo "=== test_persist_to_shell_profile_zsh ==="
  setup

  # Create .zshrc and set SHELL
  touch "$HOME/.zshrc"
  export SHELL="/bin/zsh"

  local install_path="$TEST_TMP/install/agentic-config"
  persist_to_shell_profile "$install_path"

  assert_file_contains "$HOME/.zshrc" "# agentic-config path" "marker added"
  assert_file_contains "$HOME/.zshrc" "export AGENTIC_CONFIG_PATH=" "export added"

  teardown
}

# Test: persist_to_shell_profile works for bash
test_persist_to_shell_profile_bash() {
  echo "=== test_persist_to_shell_profile_bash ==="
  setup

  touch "$HOME/.bashrc"
  export SHELL="/bin/bash"

  local install_path="$TEST_TMP/install/agentic-config"
  persist_to_shell_profile "$install_path"

  assert_file_contains "$HOME/.bashrc" "# agentic-config path" "marker added to bashrc"
  assert_file_contains "$HOME/.bashrc" "export AGENTIC_CONFIG_PATH=" "export added to bashrc"

  teardown
}

# Test: persist_to_shell_profile is idempotent
test_persist_to_shell_profile_idempotent() {
  echo "=== test_persist_to_shell_profile_idempotent ==="
  setup

  touch "$HOME/.zshrc"
  export SHELL="/bin/zsh"

  local install_path="$TEST_TMP/install/agentic-config"
  persist_to_shell_profile "$install_path"
  persist_to_shell_profile "$install_path"  # Run twice

  # Should only have one marker
  local count
  count=$(grep -c "# agentic-config path" "$HOME/.zshrc" || echo "0")
  assert_eq "1" "$count" "only one marker after double persist"

  teardown
}

# Test: persist_to_shell_profile updates existing path
test_persist_path_update() {
  echo "=== test_persist_path_update ==="
  setup

  touch "$HOME/.zshrc"
  export SHELL="/bin/zsh"

  local old_path="$TEST_TMP/install/old-path"
  local new_path="$TEST_TMP/install/new-path"
  mkdir -p "$old_path" "$new_path"

  # Persist old path
  persist_to_shell_profile "$old_path"
  # Update to new path
  persist_to_shell_profile "$new_path"

  # Should have new path, not old
  local count
  count=$(grep -c "# agentic-config path" "$HOME/.zshrc" || echo "0")
  assert_eq "1" "$count" "only one marker after update"
  assert_file_contains "$HOME/.zshrc" "$new_path" "new path present"

  teardown
}

# Test: discover_agentic_path finds from dotpath
test_discover_from_dotpath() {
  echo "=== test_discover_from_dotpath ==="
  setup

  local install_path="$TEST_TMP/install/agentic-config"
  mkdir -p "$HOME/.agents"
  echo "$install_path" > "$HOME/.agents/.path"

  local discovered
  discovered=$(discover_agentic_path)
  assert_eq "$install_path" "$discovered" "discovered from dotpath"

  teardown
}

# Test: discover_agentic_path finds from XDG config
test_discover_from_xdg_config() {
  echo "=== test_discover_from_xdg_config ==="
  setup

  local install_path="$TEST_TMP/install/agentic-config"
  mkdir -p "$HOME/.config/agentic"
  echo "path=$install_path" > "$HOME/.config/agentic/config"

  local discovered
  discovered=$(discover_agentic_path)
  assert_eq "$install_path" "$discovered" "discovered from XDG config"

  teardown
}

# Test: discover_agentic_path respects env var priority
test_discover_env_priority() {
  echo "=== test_discover_env_priority ==="
  setup

  local env_path="$TEST_TMP/install/env-path"
  local dotpath="$TEST_TMP/install/agentic-config"
  mkdir -p "$env_path" "$dotpath" "$HOME/.agents"

  echo "$dotpath" > "$HOME/.agents/.path"
  export AGENTIC_CONFIG_PATH="$env_path"

  local discovered
  discovered=$(discover_agentic_path)
  assert_eq "$env_path" "$discovered" "env var takes priority"

  teardown
}

# Run all tests
test_persist_to_dotpath
test_persist_to_xdg_config
test_persist_to_shell_profile_zsh
test_persist_to_shell_profile_bash
test_persist_to_shell_profile_idempotent
test_persist_path_update
test_discover_from_dotpath
test_discover_from_xdg_config
test_discover_env_priority

echo ""
echo "=== Results ==="
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

exit $FAIL_COUNT
