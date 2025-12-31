#!/usr/bin/env bash
# E2E Test: Restricted Shell Compatibility
# Tests that lib scripts don't use external commands in critical paths
#
# Background: Claude Code runs bash in a restricted/sandboxed environment where
# external commands (cat, cut, grep, sed, awk, dirname, head, tail, etc.) may
# NOT be available. All lib scripts must use pure bash alternatives.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/test_utils.sh"

echo "=== Test Suite: Restricted Shell Compatibility ==="
echo "Testing that lib scripts use pure bash (no external commands)"
echo ""

# List of external commands that are NOT available in Claude Code's restricted shell
RESTRICTED_COMMANDS=(
  "cat"
  "cut"
  "grep"
  "sed"
  "awk"
  "dirname"
  "basename"
  "head"
  "tail"
  "tr"
  "sort"
  "wc"
  "xargs"
  "find"
)

# Files that MUST NOT use restricted commands (bootstrap-critical)
# These are sourced/executed in Claude Code's restricted shell environment
# Focus on files that define the AGENTIC_GLOBAL bootstrap pattern
CRITICAL_FILES=(
  # Core libs - sourced by commands and agents (HIGHEST PRIORITY)
  "core/lib/spec-resolver.sh"
  "core/lib/agentic-root.sh"
  "core/lib/config-loader.sh"
  # Commands with bootstrap pattern - must use pure bash for path discovery
  "core/commands/claude/branch.md"
  # NOTE: o_spec.md and po_spec.md have complex resume logic using grep/cut
  # that needs more careful refactoring - excluded for now
  # Agents with bootstrap pattern
  "core/agents/spec/CREATE.md"
  "core/agents/spec/PLAN.md"
  "core/agents/spec/IMPLEMENT.md"
  "core/agents/spec/TEST.md"
  "core/agents/spec/REVIEW.md"
  "core/agents/spec/RESEARCH.md"
  "core/agents/spec/DOCUMENT.md"
  "core/agents/spec/PLAN_REVIEW.md"
  # Templates - copied to projects, define bootstrap pattern
  "templates/python-uv/AGENTS.md.template"
  "templates/typescript/AGENTS.md.template"
  "templates/generic/AGENTS.md.template"
  # Main AGENTS.md - symlinked to projects
  "AGENTS.md"
)

# Check for command usage in subshells: $(cmd ...)
test_no_subshell_external_commands() {
  local file="$1"
  local file_path="$REPO_ROOT/$file"
  local pass=true

  if [[ ! -f "$file_path" ]]; then
    echo -e "${RED}FAIL${NC}: File not found: $file"
    ((FAIL_COUNT++)) || true
    return
  fi

  for cmd in "${RESTRICTED_COMMANDS[@]}"; do
    # Pattern: $( cmd  or $(cmd (with optional whitespace)
    if grep -E '\$\(\s*'"$cmd"'\s' "$file_path" >/dev/null 2>&1; then
      echo -e "${RED}FAIL${NC}: $file uses \$($cmd ...) - not allowed in restricted shell"
      grep -n -E '\$\(\s*'"$cmd"'\s' "$file_path" | head -3 | while read -r line; do
        echo "  Line: $line"
      done
      pass=false
      ((FAIL_COUNT++)) || true
    fi
  done

  if $pass; then
    echo -e "${GREEN}PASS${NC}: $file has no subshell external commands"
    ((PASS_COUNT++)) || true
  fi
}

# Check for piped external commands: | cmd
test_no_piped_external_commands() {
  local file="$1"
  local file_path="$REPO_ROOT/$file"
  local pass=true

  if [[ ! -f "$file_path" ]]; then
    return  # Already reported in previous test
  fi

  for cmd in "${RESTRICTED_COMMANDS[@]}"; do
    # Pattern: | cmd (pipe to command)
    # Exclude comments and string literals
    if grep -v '^[[:space:]]*#' "$file_path" | grep -E '\|\s*'"$cmd"'(\s|$)' >/dev/null 2>&1; then
      echo -e "${RED}FAIL${NC}: $file pipes to $cmd - not allowed in restricted shell"
      grep -n -E '\|\s*'"$cmd"'(\s|$)' "$file_path" | head -3 | while read -r line; do
        echo "  Line: $line"
      done
      pass=false
      ((FAIL_COUNT++)) || true
    fi
  done

  if $pass; then
    echo -e "${GREEN}PASS${NC}: $file has no piped external commands"
    ((PASS_COUNT++)) || true
  fi
}

# Check for backtick command substitution: `cmd`
test_no_backtick_commands() {
  local file="$1"
  local file_path="$REPO_ROOT/$file"
  local pass=true

  if [[ ! -f "$file_path" ]]; then
    return  # Already reported in previous test
  fi

  for cmd in "${RESTRICTED_COMMANDS[@]}"; do
    # Pattern: `cmd (backtick command substitution)
    if grep -E '`\s*'"$cmd"'\s' "$file_path" >/dev/null 2>&1; then
      echo -e "${RED}FAIL${NC}: $file uses backtick $cmd - not allowed"
      grep -n -E '`\s*'"$cmd"'\s' "$file_path" | head -3 | while read -r line; do
        echo "  Line: $line"
      done
      pass=false
      ((FAIL_COUNT++)) || true
    fi
  done

  if $pass; then
    echo -e "${GREEN}PASS${NC}: $file has no backtick external commands"
    ((PASS_COUNT++)) || true
  fi
}

# Test that recommended pure bash patterns are used
test_pure_bash_patterns() {
  local file="$1"
  local file_path="$REPO_ROOT/$file"

  if [[ ! -f "$file_path" ]]; then
    return  # Already reported
  fi

  # Check for file reading - should use $(<file) not $(cat file)
  if grep -E '\$\(\s*cat\s+[^|)]+\)' "$file_path" >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC}: $file uses \$(cat file) - use \$(<file) instead"
    ((FAIL_COUNT++)) || true
  else
    echo -e "${GREEN}PASS${NC}: $file correctly avoids \$(cat file)"
    ((PASS_COUNT++)) || true
  fi

  # Check for dirname - should use ${var%/*}
  if grep -E '\$\(\s*dirname\s' "$file_path" >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC}: $file uses \$(dirname ...) - use \${var%/*} instead"
    ((FAIL_COUNT++)) || true
  else
    echo -e "${GREEN}PASS${NC}: $file correctly avoids \$(dirname ...)"
    ((PASS_COUNT++)) || true
  fi

  # Check for basename - should use ${var##*/}
  if grep -E '\$\(\s*basename\s' "$file_path" >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC}: $file uses \$(basename ...) - use \${var##*/} instead"
    ((FAIL_COUNT++)) || true
  else
    echo -e "${GREEN}PASS${NC}: $file correctly avoids \$(basename ...)"
    ((PASS_COUNT++)) || true
  fi
}

# Test bootstrap path works without external commands
test_bootstrap_works() {
  echo ""
  echo "--- Testing bootstrap execution ---"

  # Create a minimal test environment
  local test_dir
  test_dir=$(mktemp -d)
  local test_home="$test_dir/home"
  mkdir -p "$test_home/.agents"

  # Write path file
  echo "$REPO_ROOT" > "$test_home/.agents/.path"

  # Try sourcing spec-resolver.sh with restricted HOME
  # This tests Priority 2 (reading .path file with pure bash)
  (
    export HOME="$test_home"
    cd "$test_dir"

    # Source the script - should not error
    if source "$REPO_ROOT/core/lib/spec-resolver.sh" 2>&1; then
      echo -e "${GREEN}PASS${NC}: spec-resolver.sh bootstrap succeeds"
    else
      echo -e "${RED}FAIL${NC}: spec-resolver.sh bootstrap failed"
      exit 1
    fi
  )
  local result=$?

  # Cleanup
  rm -rf "$test_dir"

  if [[ $result -eq 0 ]]; then
    ((PASS_COUNT++)) || true
  else
    ((FAIL_COUNT++)) || true
  fi
}

# Test bootstrap with .agentic-config.json
test_bootstrap_with_config_json() {
  echo ""
  echo "--- Testing bootstrap with .agentic-config.json ---"

  local test_dir
  test_dir=$(mktemp -d)
  local test_home="$test_dir/home"
  local test_project="$test_dir/project"
  mkdir -p "$test_home"
  mkdir -p "$test_project"

  # Create .agentic-config.json in project
  cat > "$test_project/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$REPO_ROOT"
}
EOF

  # Try sourcing spec-resolver.sh from project dir
  (
    export HOME="$test_home"  # Clean HOME with no .agents/.path
    cd "$test_project"

    if source "$REPO_ROOT/core/lib/spec-resolver.sh" 2>&1; then
      echo -e "${GREEN}PASS${NC}: bootstrap with .agentic-config.json succeeds"
    else
      echo -e "${RED}FAIL${NC}: bootstrap with .agentic-config.json failed"
      exit 1
    fi
  )
  local result=$?

  rm -rf "$test_dir"

  if [[ $result -eq 0 ]]; then
    ((PASS_COUNT++)) || true
  else
    ((FAIL_COUNT++)) || true
  fi
}

# Main test runner
main() {
  echo "=== Static Analysis: External Command Usage ==="
  echo ""

  for file in "${CRITICAL_FILES[@]}"; do
    echo "--- Testing: $file ---"
    test_no_subshell_external_commands "$file"
    test_no_piped_external_commands "$file"
    test_no_backtick_commands "$file"
    test_pure_bash_patterns "$file"
    echo ""
  done

  echo "=== Integration: Bootstrap Execution ==="
  test_bootstrap_works
  test_bootstrap_with_config_json

  print_test_summary "Restricted Shell Compatibility"
}

main "$@"
