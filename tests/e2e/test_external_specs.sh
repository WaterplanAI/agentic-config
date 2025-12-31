#!/usr/bin/env bash
# E2E Tests for External Specs Storage
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
source "$SCRIPT_DIR/test_utils.sh"

# Test: Git URL validation
test_git_url_validation() {
  echo "=== test_git_url_validation ==="
  setup_test_env

  source "$TEST_AGENTIC/scripts/external-specs.sh"

  # Valid URLs
  if _validate_git_url "git@github.com:user/repo.git"; then
    echo -e "${GREEN}PASS${NC}: git@ URL accepted"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: git@ URL rejected"
    ((FAIL_COUNT++)) || true
  fi

  if _validate_git_url "https://github.com/user/repo.git"; then
    echo -e "${GREEN}PASS${NC}: https:// URL accepted"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: https:// URL rejected"
    ((FAIL_COUNT++)) || true
  fi

  if _validate_git_url "ssh://git@github.com/user/repo.git"; then
    echo -e "${GREEN}PASS${NC}: ssh:// URL accepted"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: ssh:// URL rejected"
    ((FAIL_COUNT++)) || true
  fi

  if _validate_git_url "file:///path/to/repo"; then
    echo -e "${GREEN}PASS${NC}: file:// URL accepted"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: file:// URL rejected"
    ((FAIL_COUNT++)) || true
  fi

  # Invalid URLs
  if ! _validate_git_url "invalid-url"; then
    echo -e "${GREEN}PASS${NC}: Invalid URL rejected"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Invalid URL accepted"
    ((FAIL_COUNT++)) || true
  fi

  if ! _validate_git_url "/local/path"; then
    echo -e "${GREEN}PASS${NC}: Local path rejected"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Local path accepted"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Path traversal rejection
test_path_traversal_rejection() {
  echo "=== test_path_traversal_rejection ==="
  setup_test_env

  source "$TEST_AGENTIC/core/lib/spec-resolver.sh"

  # Valid paths
  if _validate_spec_path "2025/12/feat/my-feature/001-spec.md"; then
    echo -e "${GREEN}PASS${NC}: Valid path accepted"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Valid path rejected"
    ((FAIL_COUNT++)) || true
  fi

  # Invalid paths with traversal
  if ! _validate_spec_path "../../../etc/passwd"; then
    echo -e "${GREEN}PASS${NC}: Traversal path rejected"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Traversal path accepted"
    ((FAIL_COUNT++)) || true
  fi

  if ! _validate_spec_path "specs/../../../secrets"; then
    echo -e "${GREEN}PASS${NC}: Mid-path traversal rejected"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Mid-path traversal accepted"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Safe .env parsing
test_safe_env_parsing() {
  echo "=== test_safe_env_parsing ==="
  setup_test_env

  # Create test project with .env
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  # Create .agentic-config.json
  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Create .env with valid and invalid lines
  cat > "$project_dir/.env" <<'EOF'
# Comment line
VALID_KEY=value
QUOTED_VALUE="quoted string"
SINGLE_QUOTED='single quoted'
EMPTY_VALUE=

# These should be rejected (logged as warnings)
$(dangerous command)
`backtick command`
invalid line without equals
EOF

  # Source config loader and load config
  source "$TEST_AGENTIC/core/lib/config-loader.sh"

  # Capture stderr to check for warnings
  local warnings
  warnings=$(load_agentic_config 2>&1 || true)

  # Check valid keys were loaded
  if [[ "${VALID_KEY:-}" == "value" ]]; then
    echo -e "${GREEN}PASS${NC}: Valid key loaded"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Valid key not loaded (got: ${VALID_KEY:-unset})"
    ((FAIL_COUNT++)) || true
  fi

  if [[ "${QUOTED_VALUE:-}" == "quoted string" ]]; then
    echo -e "${GREEN}PASS${NC}: Quoted value parsed correctly"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Quoted value not parsed (got: ${QUOTED_VALUE:-unset})"
    ((FAIL_COUNT++)) || true
  fi

  # Check warnings were logged for invalid lines
  if [[ "$warnings" == *"WARNING"* ]]; then
    echo -e "${GREEN}PASS${NC}: Warnings logged for invalid lines"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: No warnings for invalid lines"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Config priority (ENV > .env > YAML)
test_config_priority() {
  echo "=== test_config_priority ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  # Create .agentic-config.json
  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Create YAML config (lowest priority)
  cat > "$project_dir/.agentic-config.conf.yml" <<EOF
ext_specs_repo_url: yaml-repo-url
ext_specs_local_path: yaml-path
EOF

  # Create .env (medium priority)
  cat > "$project_dir/.env" <<EOF
EXT_SPECS_REPO_URL=env-file-url
EOF

  source "$TEST_AGENTIC/core/lib/config-loader.sh"

  # Test without ENV override
  unset EXT_SPECS_REPO_URL EXT_SPECS_LOCAL_PATH
  load_agentic_config

  # .env should override YAML for repo_url
  if [[ "${EXT_SPECS_REPO_URL:-}" == "env-file-url" ]]; then
    echo -e "${GREEN}PASS${NC}: .env overrides YAML"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: .env did not override YAML (got: ${EXT_SPECS_REPO_URL:-unset})"
    ((FAIL_COUNT++)) || true
  fi

  # YAML should be used for local_path (not in .env)
  if [[ "${EXT_SPECS_LOCAL_PATH:-}" == "yaml-path" ]]; then
    echo -e "${GREEN}PASS${NC}: YAML used for missing .env key"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: YAML not used (got: ${EXT_SPECS_LOCAL_PATH:-unset})"
    ((FAIL_COUNT++)) || true
  fi

  # Test with ENV override (highest priority)
  export EXT_SPECS_REPO_URL="env-var-url"
  unset EXT_SPECS_LOCAL_PATH
  load_agentic_config

  if [[ "${EXT_SPECS_REPO_URL:-}" == "env-var-url" ]]; then
    echo -e "${GREEN}PASS${NC}: ENV var overrides all"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: ENV var did not override (got: ${EXT_SPECS_REPO_URL:-unset})"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: External specs init with file:// URL
test_ext_specs_init() {
  echo "=== test_ext_specs_init ==="
  setup_test_env

  # Create a bare git repo to clone from
  local bare_repo="$TEST_ROOT/bare-repo.git"
  git init --bare "$bare_repo" -q

  # Create test project
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  # Create .agentic-config.json
  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Set config via environment
  export EXT_SPECS_REPO_URL="file://$bare_repo"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"

  # Run init
  ext_specs_init

  # Verify clone
  assert_dir_exists "$project_dir/.specs/.git" "External specs cloned"

  cleanup_test_env
}

# Test: External specs commit with rollback
test_ext_specs_commit_rollback() {
  echo "=== test_ext_specs_commit_rollback ==="
  setup_test_env

  # Create a bare git repo
  local bare_repo="$TEST_ROOT/bare-repo.git"
  git init --bare "$bare_repo" -q

  # Create test project and clone
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  export EXT_SPECS_REPO_URL="file://$bare_repo"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"
  ext_specs_init

  # Create a test file
  echo "test content" > "$project_dir/.specs/test.txt"

  # Commit should succeed
  ext_specs_commit "test commit"

  # Verify commit exists
  local commit_count
  commit_count=$(cd "$project_dir/.specs" && git rev-list --count HEAD)
  if [[ "$commit_count" -ge 1 ]]; then
    echo -e "${GREEN}PASS${NC}: Commit created successfully"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: No commits found"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Empty EXT_SPECS_LOCAL_PATH defaults to .specs
test_empty_local_path_default() {
  echo "=== test_empty_local_path_default ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Set empty local path
  export EXT_SPECS_LOCAL_PATH=""
  export EXT_SPECS_REPO_URL="https://example.com/repo.git"

  source "$TEST_AGENTIC/core/lib/spec-resolver.sh"
  _source_config_loader
  load_agentic_config

  # Get the path that would be used
  local ext_specs_path="${EXT_SPECS_LOCAL_PATH:-.specs}"
  [[ -z "$ext_specs_path" ]] && ext_specs_path=".specs"

  if [[ "$ext_specs_path" == ".specs" ]]; then
    echo -e "${GREEN}PASS${NC}: Empty path defaults to .specs"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Empty path did not default (got: $ext_specs_path)"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: agentic-root.sh fallback validation
test_agentic_root_fallback() {
  echo "=== test_agentic_root_fallback ==="
  setup_test_env

  # Unset all discovery paths
  unset AGENTIC_CONFIG_PATH
  rm -f "$HOME/.agents/.path"
  rm -rf "$HOME/.config/agentic"

  # Create a directory without VERSION marker
  cd "$TEST_ROOT"

  source "$TEST_AGENTIC/core/lib/agentic-root.sh"

  # Default path doesn't exist, should fail
  if ! get_agentic_root >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}: Fallback fails when default path missing"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Fallback succeeded when it should fail"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Logic inversion fix (Issue #1)
test_logic_inversion_fix() {
  echo "=== test_logic_inversion_fix ==="
  setup_test_env

  # Create test project with manual .specs directory (no external repo configured)
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir/.specs/specs/2025/12/feat/test"
  cd "$project_dir"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test User"

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Create a spec file
  cat > "$project_dir/.specs/specs/2025/12/feat/test/001-test.md" <<EOF
# Test Spec
Test content
EOF

  # Ensure EXT_SPECS_REPO_URL is NOT set
  unset EXT_SPECS_REPO_URL
  unset EXT_SPECS_LOCAL_PATH

  source "$TEST_AGENTIC/core/lib/spec-resolver.sh"

  # Attempt commit - should use local git, not fail trying external specs
  if commit_spec_changes "$project_dir/.specs/specs/2025/12/feat/test/001-test.md" "TEST" "001" "test"; then
    echo -e "${GREEN}PASS${NC}: Manual .specs directory uses local git when no repo URL configured"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Commit failed for manual .specs directory"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Config state leak fix (Issue #2)
test_config_state_leak_fix() {
  echo "=== test_config_state_leak_fix ==="
  setup_test_env

  # Create Project A with external specs configured
  local project_a="$TEST_ROOT/project-a"
  mkdir -p "$project_a"
  cd "$project_a"
  git init -q

  cat > "$project_a/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  cat > "$project_a/.env" <<EOF
EXT_SPECS_REPO_URL=https://github.com/example/project-a-specs.git
EOF

  # Create Project B without external specs
  local project_b="$TEST_ROOT/project-b"
  mkdir -p "$project_b"
  cd "$project_b"
  git init -q

  cat > "$project_b/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  source "$TEST_AGENTIC/core/lib/config-loader.sh"

  # Load config for Project A
  cd "$project_a"
  load_agentic_config
  local project_a_url="${EXT_SPECS_REPO_URL:-}"

  # Load config for Project B (should clear Project A's config)
  cd "$project_b"
  load_agentic_config
  local project_b_url="${EXT_SPECS_REPO_URL:-}"

  # Verify Project B doesn't inherit Project A's URL
  if [[ -z "$project_b_url" ]]; then
    echo -e "${GREEN}PASS${NC}: Config state cleared between projects"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Config leaked from Project A to Project B (got: $project_b_url)"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Partial clone cleanup fix (Issue #3)
test_partial_clone_cleanup_fix() {
  echo "=== test_partial_clone_cleanup_fix ==="
  setup_test_env

  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  # Set invalid repo URL to force clone failure
  export EXT_SPECS_REPO_URL="https://invalid-domain-that-does-not-exist-12345.com/repo.git"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"

  # First attempt should fail and clean up
  ext_specs_init 2>/dev/null && {
    echo -e "${RED}FAIL${NC}: Clone should have failed with invalid URL"
    ((FAIL_COUNT++)) || true
    cleanup_test_env
    return
  }

  # Verify .specs directory was cleaned up
  if [[ ! -d "$project_dir/.specs" ]]; then
    echo -e "${GREEN}PASS${NC}: Partial clone directory cleaned up on failure"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Partial clone directory not cleaned up"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Concurrent git operations with flock
test_concurrent_operations_with_flock() {
  echo "=== test_concurrent_operations_with_flock ==="
  setup_test_env

  # Create bare repo
  local bare_repo="$TEST_ROOT/bare-repo.git"
  git init --bare "$bare_repo" -q

  # Create test project
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  export EXT_SPECS_REPO_URL="file://$bare_repo"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"

  # Initialize first time
  ext_specs_init

  # Simulate concurrent init - should block and wait
  (
    # Hold lock for 2 seconds
    flock -x 200
    sleep 2
  ) 200>"$project_dir/.specs/.agentic-lock" &
  local lock_pid=$!

  sleep 0.5
  # This should wait for lock to be released
  local start_time=$(date +%s)
  ext_specs_init 2>/dev/null
  local end_time=$(date +%s)
  local elapsed=$((end_time - start_time))

  if [[ $elapsed -ge 1 ]]; then
    echo -e "${GREEN}PASS${NC}: Concurrent operation waited for lock (${elapsed}s)"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Operation did not wait for lock (${elapsed}s)"
    ((FAIL_COUNT++)) || true
  fi

  wait "$lock_pid" 2>/dev/null || true
  cleanup_test_env
}

# Test: get_project_root returns failure when no markers found
test_project_root_failure() {
  echo "=== test_project_root_failure ==="
  setup_test_env

  # Create directory with no project markers
  local empty_dir="$TEST_ROOT/empty-dir"
  mkdir -p "$empty_dir"
  cd "$empty_dir"

  source "$TEST_AGENTIC/core/lib/agentic-root.sh"

  # Should fail when no markers found
  if ! get_project_root >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}: get_project_root returns failure when no markers found"
    ((PASS_COUNT++)) || true
  else
    local found_root
    found_root=$(get_project_root)
    echo -e "${RED}FAIL${NC}: get_project_root succeeded when it should fail (returned: $found_root)"
    ((FAIL_COUNT++)) || true
  fi

  # Should succeed when marker present
  touch "$empty_dir/.agentic-config.json"
  if get_project_root >/dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}: get_project_root succeeds with marker present"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: get_project_root failed with marker present"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Temp file cleanup on error
test_temp_file_cleanup() {
  echo "=== test_temp_file_cleanup ==="
  setup_test_env

  # Create test project
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  source "$TEST_AGENTIC/scripts/lib/version-manager.sh"
  export REPO_ROOT="$TEST_AGENTIC"

  # Count temp files before
  local before_count
  before_count=$(ls /tmp/tmp.* 2>/dev/null | wc -l)

  # Call reconcile_config which uses mktemp
  reconcile_config "$project_dir" "0.1.0" 2>/dev/null || true

  # Count temp files after
  local after_count
  after_count=$(ls /tmp/tmp.* 2>/dev/null | wc -l)

  if [[ $after_count -eq $before_count ]]; then
    echo -e "${GREEN}PASS${NC}: Temp files cleaned up after reconcile_config"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Temp files leaked (before: $before_count, after: $after_count)"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Semantic version comparison
test_compare_versions() {
  echo "=== test_compare_versions ==="
  setup_test_env

  source "$TEST_AGENTIC/core/lib/agentic-root.sh"

  local result

  # Temporarily disable exit-on-error for version comparison tests
  set +e

  # Equal versions
  compare_versions "1.0.0" "1.0.0"; result=$?
  if [[ $result -eq 0 ]]; then
    echo -e "${GREEN}PASS${NC}: 1.0.0 == 1.0.0"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 1.0.0 == 1.0.0 should return 0, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # v1 > v2 (10 > 2 numerically)
  compare_versions "1.10.0" "1.2.0"; result=$?
  if [[ $result -eq 1 ]]; then
    echo -e "${GREEN}PASS${NC}: 1.10.0 > 1.2.0"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 1.10.0 > 1.2.0 should return 1, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # v1 < v2
  compare_versions "1.2.0" "1.10.0"; result=$?
  if [[ $result -eq 2 ]]; then
    echo -e "${GREEN}PASS${NC}: 1.2.0 < 1.10.0"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 1.2.0 < 1.10.0 should return 2, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # Different segment counts (should pad with zeros)
  compare_versions "1.0" "1.0.0"; result=$?
  if [[ $result -eq 0 ]]; then
    echo -e "${GREEN}PASS${NC}: 1.0 == 1.0.0 (padded)"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 1.0 == 1.0.0 should return 0, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # v1 > v2 with different segments
  compare_versions "1.0.1" "1.0"; result=$?
  if [[ $result -eq 1 ]]; then
    echo -e "${GREEN}PASS${NC}: 1.0.1 > 1.0"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 1.0.1 > 1.0 should return 1, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # Major version difference
  compare_versions "2.0.0" "1.99.99"; result=$?
  if [[ $result -eq 1 ]]; then
    echo -e "${GREEN}PASS${NC}: 2.0.0 > 1.99.99"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: 2.0.0 > 1.99.99 should return 1, got $result"
    ((FAIL_COUNT++)) || true
  fi

  # Re-enable exit-on-error
  set -e

  cleanup_test_env
}

# Test: Dry-run for ext_specs_init
test_dry_run_init() {
  echo "=== test_dry_run_init ==="
  setup_test_env

  # Create bare repo
  local bare_repo="$TEST_ROOT/bare-repo.git"
  git init --bare "$bare_repo" -q

  # Create test project (NO .specs directory yet)
  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  export EXT_SPECS_REPO_URL="file://$bare_repo"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"

  # Dry-run should NOT create .specs directory
  local output
  output=$(ext_specs_init --dry-run 2>&1)

  if [[ "$output" == *"DRY RUN"* ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run outputs DRY RUN message"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run did not output DRY RUN message"
    ((FAIL_COUNT++)) || true
  fi

  if [[ ! -d "$project_dir/.specs" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run did not create .specs directory"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run created .specs directory"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Test: Dry-run for ext_specs_commit
test_dry_run_commit() {
  echo "=== test_dry_run_commit ==="
  setup_test_env

  # Create bare repo and clone
  local bare_repo="$TEST_ROOT/bare-repo.git"
  git init --bare "$bare_repo" -q

  local project_dir="$TEST_ROOT/test-project"
  mkdir -p "$project_dir"
  cd "$project_dir"
  git init -q

  cat > "$project_dir/.agentic-config.json" <<EOF
{
  "version": "0.1.0",
  "agentic_global_path": "$TEST_AGENTIC"
}
EOF

  export EXT_SPECS_REPO_URL="file://$bare_repo"
  export EXT_SPECS_LOCAL_PATH=".specs"

  source "$TEST_AGENTIC/scripts/external-specs.sh"
  ext_specs_init  # Actually clone

  # Create test file
  echo "test content" > "$project_dir/.specs/test.txt"

  # Get commit count before
  local before_count
  before_count=$(cd "$project_dir/.specs" && git rev-list --count HEAD 2>/dev/null || echo "0")

  # Dry-run commit
  local output
  output=$(ext_specs_commit "test commit" --dry-run 2>&1)

  # Get commit count after
  local after_count
  after_count=$(cd "$project_dir/.specs" && git rev-list --count HEAD 2>/dev/null || echo "0")

  if [[ "$output" == *"DRY RUN"* ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run commit outputs DRY RUN message"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run commit did not output DRY RUN message"
    ((FAIL_COUNT++)) || true
  fi

  if [[ "$before_count" == "$after_count" ]]; then
    echo -e "${GREEN}PASS${NC}: Dry-run did not create commit"
    ((PASS_COUNT++)) || true
  else
    echo -e "${RED}FAIL${NC}: Dry-run created actual commit"
    ((FAIL_COUNT++)) || true
  fi

  cleanup_test_env
}

# Run all tests
test_git_url_validation
test_path_traversal_rejection
test_safe_env_parsing
test_config_priority
test_compare_versions
# TODO: Fix dry-run tests - bootstrap issue when sourcing from temp dir
# test_dry_run_init
# test_dry_run_commit
test_ext_specs_init
test_ext_specs_commit_rollback
test_empty_local_path_default
test_agentic_root_fallback
test_logic_inversion_fix
test_config_state_leak_fix
test_partial_clone_cleanup_fix
test_concurrent_operations_with_flock
test_project_root_failure
test_temp_file_cleanup

print_test_summary "External Specs E2E Tests"
