#!/usr/bin/env bash
# E2E Tests for /agentic setup (setup-config.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Test: Setup in new project creates correct structure
test_setup_new_project() {
  echo "=== test_setup_new_project ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify structure created
  assert_file_exists "$project_dir/.agentic-config.json" "Config file created"
  assert_symlink_valid "$project_dir/agents" "agents/ symlink created"
  assert_dir_exists "$project_dir/.claude" ".claude/ directory created"
  assert_symlink_valid "$project_dir/.claude/commands/spec.md" "spec command symlinked"
  assert_dir_exists "$project_dir/.claude/hooks" "hooks directory created"

  cleanup_test_env
}

# Test: Setup detects project type correctly
test_setup_project_type_detection() {
  echo "=== test_setup_project_type_detection ==="
  setup_test_env

  local project_dir="$TEST_ROOT/python-project"
  create_test_project "$project_dir" "python-poetry"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify detected type
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".project_type" "python-poetry" "Project type detected"
  fi

  cleanup_test_env
}

# Test: Setup with explicit project type
test_setup_explicit_type() {
  echo "=== test_setup_explicit_type ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup with explicit type
  "$TEST_AGENTIC/scripts/setup-config.sh" --type typescript "$project_dir"

  # Verify type set
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".project_type" "typescript" "Explicit project type set"
  fi

  cleanup_test_env
}

# Test: Setup creates AGENTS.md from template
test_setup_agents_md() {
  echo "=== test_setup_agents_md ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify AGENTS.md created
  assert_file_exists "$project_dir/AGENTS.md" "AGENTS.md created"
  assert_file_contains "$project_dir/AGENTS.md" "# Project Guidelines" "AGENTS.md has header"

  # Verify symlinks to AGENTS.md
  if [[ -L "$project_dir/CLAUDE.md" ]]; then
    echo -e "${GREEN}PASS${NC}: CLAUDE.md symlinked to AGENTS.md"
    ((PASS_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Setup dry-run mode
test_setup_dry_run() {
  echo "=== test_setup_dry_run ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run with --dry-run
  "$TEST_AGENTIC/scripts/setup-config.sh" --dry-run "$project_dir"

  # Nothing should be created
  if [[ ! -f "$project_dir/.agentic-config.json" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run did not create config"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run created files"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Setup creates .gitignore if missing
test_setup_gitignore_creation() {
  echo "=== test_setup_gitignore_creation ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Remove .gitignore if exists
  rm -f "$project_dir/.gitignore"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify .gitignore created with sensible defaults
  assert_file_exists "$project_dir/.gitignore" ".gitignore created"
  assert_file_contains "$project_dir/.gitignore" "outputs/" ".gitignore contains outputs/"

  cleanup_test_env
}

# Test: Setup initializes git if not in repo
test_setup_git_init() {
  echo "=== test_setup_git_init ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"

  # Run setup (no git repo)
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify git initialized
  assert_dir_exists "$project_dir/.git" "Git repository initialized"

  cleanup_test_env
}

# Test: Setup preserves existing AGENTS.md content
test_setup_preserve_agents_md() {
  echo "=== test_setup_preserve_agents_md ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Create existing AGENTS.md with custom content
  cat > "$project_dir/AGENTS.md" <<'EOF'
# My Custom Content

This is important project-specific content.
EOF

  # Run setup with --force
  "$TEST_AGENTIC/scripts/setup-config.sh" --force "$project_dir"

  # Verify content preserved to PROJECT_AGENTS.md
  assert_file_exists "$project_dir/PROJECT_AGENTS.md" "PROJECT_AGENTS.md created"
  assert_file_contains "$project_dir/PROJECT_AGENTS.md" "My Custom Content" "Custom content preserved"

  cleanup_test_env
}

# Test: Setup with copy mode
test_setup_copy_mode() {
  echo "=== test_setup_copy_mode ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup with --copy
  "$TEST_AGENTIC/scripts/setup-config.sh" --copy "$project_dir"

  # Verify files copied (not symlinked)
  if [[ -d "$project_dir/agents" && ! -L "$project_dir/agents" ]]; then
    echo -e "${GREEN}PASS${NC}: agents/ copied in copy mode"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: agents/ should be directory in copy mode"
    ((FAIL_COUNT++)) || true
  fi

  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".install_mode" "copy" "Installation mode set to copy"
  fi

  cleanup_test_env
}

# Test: Setup records agentic_global_path
test_setup_global_path_recording() {
  echo "=== test_setup_global_path_recording ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify agentic_global_path recorded
  if command -v jq >/dev/null 2>&1; then
    assert_json_field "$project_dir/.agentic-config.json" ".agentic_global_path" "$TEST_AGENTIC" "Global path recorded"
  fi

  cleanup_test_env
}

# Test: Setup installs hooks and registers in settings.json
test_setup_hooks_installation() {
  echo "=== test_setup_hooks_installation ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup
  "$TEST_AGENTIC/scripts/setup-config.sh" "$project_dir"

  # Verify hooks installed
  assert_dir_exists "$project_dir/.claude/hooks/pretooluse" "pretooluse hooks directory created"

  # Verify settings.json has hook registration
  if [[ -f "$project_dir/.claude/settings.json" ]]; then
    assert_file_contains "$project_dir/.claude/settings.json" "pretooluse" "Hooks registered in settings.json"
  fi

  cleanup_test_env
}

# Test: Setup with selective tools
test_setup_selective_tools() {
  echo "=== test_setup_selective_tools ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  create_test_project "$project_dir" "generic"

  # Run setup with only claude
  "$TEST_AGENTIC/scripts/setup-config.sh" --tools claude "$project_dir"

  # Verify claude installed, others not
  assert_dir_exists "$project_dir/.claude" ".claude/ created"

  if [[ ! -d "$project_dir/.gemini" ]]; then
    echo -e "${GREEN}PASS${NC}: .gemini/ not created with --tools claude"
    ((PASS_COUNT++)) || true
  fi

  cleanup_test_env
}

# Run all tests
test_setup_new_project
test_setup_project_type_detection
test_setup_explicit_type
test_setup_agents_md
test_setup_dry_run
test_setup_gitignore_creation
test_setup_git_init
test_setup_preserve_agents_md
test_setup_copy_mode
test_setup_global_path_recording
test_setup_hooks_installation
test_setup_selective_tools

print_test_summary "/agentic setup E2E Tests"
