#!/usr/bin/env bash
# E2E Test Utilities
# Shared functions for E2E tests

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
PASS_COUNT=0
FAIL_COUNT=0

# Test environment setup
setup_test_env() {
  # Create isolated test environment
  TEST_ROOT=$(mktemp -d)
  export HOME="$TEST_ROOT/home"
  export XDG_CONFIG_HOME="$HOME/.config"
  mkdir -p "$HOME"

  # Setup test agentic-config installation
  TEST_AGENTIC="$TEST_ROOT/agentic-config"
  cp -R "$REPO_ROOT" "$TEST_AGENTIC"

  # Export for scripts
  export AGENTIC_CONFIG_PATH="$TEST_AGENTIC"

  # Configure install.sh to use local repo and current branch
  export AGENTIC_CONFIG_REPO="file://$REPO_ROOT"
  CURRENT_BRANCH=$(cd "$REPO_ROOT" && git branch --show-current)
  export AGENTIC_CONFIG_BRANCH="${CURRENT_BRANCH:-main}"

  # Track created files for cleanup
  TEST_FILES=()
}

# Cleanup test environment
cleanup_test_env() {
  if [[ -n "${TEST_ROOT:-}" && -d "$TEST_ROOT" ]]; then
    rm -rf "$TEST_ROOT"
  fi
  unset HOME
  unset XDG_CONFIG_HOME
  unset AGENTIC_CONFIG_PATH
  unset AGENTIC_CONFIG_REPO
  unset AGENTIC_CONFIG_BRANCH
}

# Assertions
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

assert_dir_exists() {
  local dir="$1"
  local msg="${2:-}"

  if [[ -d "$dir" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - directory does not exist: $dir"
    ((FAIL_COUNT++)) || true
  fi
}

assert_symlink_exists() {
  local link="$1"
  local msg="${2:-}"

  if [[ -L "$link" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - symlink does not exist: $link"
    ((FAIL_COUNT++)) || true
  fi
}

assert_symlink_valid() {
  local link="$1"
  local msg="${2:-}"

  if [[ -L "$link" && -e "$link" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - symlink invalid or broken: $link"
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

assert_json_field() {
  local file="$1"
  local field="$2"
  local expected="$3"
  local msg="${4:-}"

  if ! command -v jq >/dev/null 2>&1; then
    echo -e "${YELLOW}SKIP${NC}: $msg - jq not installed"
    return 0
  fi

  local actual
  actual=$(jq -r "$field" "$file" 2>/dev/null)

  if [[ "$actual" == "$expected" ]]; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg"
    echo "  Expected: '$expected'"
    echo "  Actual:   '$actual'"
    ((FAIL_COUNT++)) || true
  fi
}

assert_command_success() {
  local cmd="$1"
  local msg="${2:-}"

  if eval "$cmd" >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - command failed: $cmd"
    ((FAIL_COUNT++)) || true
  fi
}

assert_command_failure() {
  local cmd="$1"
  local msg="${2:-}"

  if ! eval "$cmd" >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}: $msg"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: $msg - command should have failed: $cmd"
    ((FAIL_COUNT++)) || true
  fi
}

# Helper: Create test project
create_test_project() {
  local project_dir="$1"
  local project_type="${2:-generic}"

  mkdir -p "$project_dir"
  cd "$project_dir" || return 1

  # Initialize git
  git init -q

  # Create project type specific files
  case "$project_type" in
    python-poetry)
      cat > pyproject.toml <<'EOF'
[tool.poetry]
name = "test-project"
version = "0.1.0"
EOF
      ;;
    python-pip)
      cat > requirements.txt <<'EOF'
pytest==7.0.0
EOF
      ;;
    typescript)
      cat > package.json <<'EOF'
{
  "name": "test-project",
  "version": "1.0.0"
}
EOF
      ;;
    rust)
      cat > Cargo.toml <<'EOF'
[package]
name = "test-project"
version = "0.1.0"
EOF
      ;;
  esac
}

# Helper: Mock install.sh clone operation
mock_git_clone() {
  local repo_url="$1"
  local target_dir="$2"

  # Copy test agentic-config instead of cloning
  cp -R "$TEST_AGENTIC" "$target_dir"
}

# Test result summary
print_test_summary() {
  local test_name="$1"

  echo ""
  echo "=== $test_name Results ==="
  echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
  echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

  return $FAIL_COUNT
}
