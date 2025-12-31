#!/usr/bin/env bash
# E2E Tests for /issue command
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Test: Command file exists
test_issue_command_exists() {
  echo "=== test_issue_command_exists ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_exists "$cmd_file" "issue.md command file exists"
}

# Test: YAML frontmatter is valid
test_issue_frontmatter_valid() {
  echo "=== test_issue_frontmatter_valid ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  # Check for required frontmatter fields
  assert_file_contains "$cmd_file" "^---$" "Has YAML frontmatter delimiter"
  assert_file_contains "$cmd_file" "description:" "Has description field"
  assert_file_contains "$cmd_file" "argument-hint:" "Has argument-hint field"
  assert_file_contains "$cmd_file" "project-agnostic: true" "Is project-agnostic"
  assert_file_contains "$cmd_file" "allowed-tools:" "Has allowed-tools field"
  assert_file_contains "$cmd_file" "Bash" "Allows Bash tool"
}

# Test: Command targets correct repository
test_issue_target_repo() {
  echo "=== test_issue_target_repo ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "MatiasComercio/agentic-config" "Targets correct repository"
  assert_file_contains "$cmd_file" "gh issue create" "Uses gh issue create"
}

# Test: Command has authentication verification
test_issue_auth_verification() {
  echo "=== test_issue_auth_verification ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "gh auth status" "Checks gh auth status"
  assert_file_contains "$cmd_file" "gh auth login" "Provides auth login instruction"
}

# Test: Command has preview/confirmation step
test_issue_preview_confirmation() {
  echo "=== test_issue_preview_confirmation ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "ISSUE PREVIEW" "Has issue preview section"
  assert_file_contains "$cmd_file" "yes/no" "Has confirmation prompt"
}

# Test: Command has sanitization logic
test_issue_sanitization() {
  echo "=== test_issue_sanitization ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "Sanitization" "Has sanitization section"
  assert_file_contains "$cmd_file" "REDACTED" "Has redaction logic"
  assert_file_contains "$cmd_file" "ghp_" "Detects GitHub token patterns"
}

# Test: Command supports multiple input modes
test_issue_input_modes() {
  echo "=== test_issue_input_modes ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "\-\-bug" "Supports --bug flag"
  assert_file_contains "$cmd_file" "\-\-feature" "Supports --feature flag"
  assert_file_contains "$cmd_file" "Context Mode" "Supports context mode"
  assert_file_contains "$cmd_file" "Explicit Mode" "Supports explicit mode"
}

# Test: Command collects environment metadata
test_issue_environment_collection() {
  echo "=== test_issue_environment_collection ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "uname -s" "Collects OS info"
  assert_file_contains "$cmd_file" "git --version" "Collects git version"
  assert_file_contains "$cmd_file" "AGENTIC_GLOBAL" "References agentic-config path"
}

# Test: Command has error handling
test_issue_error_handling() {
  echo "=== test_issue_error_handling ==="

  local cmd_file="$REPO_ROOT/core/commands/claude/issue.md"

  assert_file_contains "$cmd_file" "Error Handling" "Has error handling section"
  assert_file_contains "$cmd_file" "gh not installed" "Handles missing gh CLI"
  assert_file_contains "$cmd_file" "Network error" "Handles network errors"
}

# Run all tests
test_issue_command_exists
test_issue_frontmatter_valid
test_issue_target_repo
test_issue_auth_verification
test_issue_preview_confirmation
test_issue_sanitization
test_issue_input_modes
test_issue_environment_collection
test_issue_error_handling

print_test_summary "/issue Command E2E Tests"
