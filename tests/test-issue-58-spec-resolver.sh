#!/usr/bin/env bash
# Test for issue #58: spec-resolver.sh stdout pollution and config-loader.sh dependency
# Validates that:
#   1. resolve_spec_path outputs ONLY the resolved path to stdout (no informational messages)
#   2. _source_config_loader finds config-loader.sh via CLAUDE_PLUGIN_ROOT
#   3. _source_config_loader finds config-loader.sh via BASH_SOURCE fallback
#   4. Informational messages go to stderr, not stdout
#   5. Preloaded config-loader still repairs CLAUDE_PLUGIN_ROOT for external specs flows

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_ROOT="$REPO_ROOT/plugins/ac-git"
WORKFLOW_PLUGIN_ROOT="$REPO_ROOT/plugins/ac-workflow"

PASS=0
FAIL=0
TOTAL=0

_test() {
  local name="$1"
  TOTAL=$((TOTAL + 1))
  echo "TEST $TOTAL: $name"
}

_pass() {
  PASS=$((PASS + 1))
  echo "  PASS"
}

_fail() {
  local msg="${1:-}"
  FAIL=$((FAIL + 1))
  echo "  FAIL: $msg"
}

_assert_preloaded_loader_repairs_plugin_root() (
  local plugin_root="$1"
  local plugin_name="$2"
  local tmpdir remote_repo project_dir stderr_file stdout_output stderr_output line_count

  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' EXIT

  remote_repo="$tmpdir/remote.git"
  project_dir="$tmpdir/project"
  stderr_file="$tmpdir/resolve.stderr"

  git init --bare "$remote_repo" >/dev/null 2>&1
  mkdir -p "$project_dir"

  cd "$project_dir"
  git init >/dev/null 2>&1
  echo "test" > CLAUDE.md
  printf 'EXT_SPECS_REPO_URL=file://%s\n' "$remote_repo" > .env

  unset -f load_agentic_config 2>/dev/null || true
  unset -f get_project_root 2>/dev/null || true
  unset EXT_SPECS_REPO_URL 2>/dev/null || true
  unset EXT_SPECS_LOCAL_PATH 2>/dev/null || true

  source "$plugin_root/scripts/lib/config-loader.sh"
  export CLAUDE_PLUGIN_ROOT="/nonexistent/path"
  source "$plugin_root/scripts/spec-resolver.sh"

  _source_config_loader 2>"$stderr_file"

  if [[ "$CLAUDE_PLUGIN_ROOT" != "$plugin_root" ]]; then
    echo "$plugin_name: CLAUDE_PLUGIN_ROOT was not repaired: $CLAUDE_PLUGIN_ROOT" >&2
    exit 1
  fi

  stdout_output=$(resolve_spec_path "2025/03/feat/test/001-spec.md" 2>>"$stderr_file")

  line_count=$(echo "$stdout_output" | wc -l | tr -d ' ')
  if [[ "$line_count" -ne 1 ]]; then
    echo "$plugin_name: expected 1 line on stdout, got $line_count: $stdout_output" >&2
    exit 1
  fi

  if [[ "$stdout_output" != *".specs/specs/2025/03/feat/test/001-spec.md" ]]; then
    echo "$plugin_name: unexpected stdout: $stdout_output" >&2
    exit 1
  fi

  stderr_output=$(<"$stderr_file")
  if [[ "$stderr_output" != *"WARNING: CLAUDE_PLUGIN_ROOT fallback activated"* ]]; then
    echo "$plugin_name: missing fallback warning on stderr: $stderr_output" >&2
    exit 1
  fi
)

# ---- Test 1: _source_config_loader succeeds with correct CLAUDE_PLUGIN_ROOT ----
_test "_source_config_loader finds config-loader.sh via CLAUDE_PLUGIN_ROOT"
(
  unset -f load_agentic_config 2>/dev/null || true
  unset -f get_project_root 2>/dev/null || true
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  source "$PLUGIN_ROOT/scripts/spec-resolver.sh"
  if _source_config_loader 2>/dev/null; then
    if declare -f load_agentic_config >/dev/null 2>&1; then
      exit 0
    else
      exit 1
    fi
  else
    exit 1
  fi
) && _pass || _fail "config-loader.sh not found with correct CLAUDE_PLUGIN_ROOT"

# ---- Test 2: _source_config_loader recovers with bad CLAUDE_PLUGIN_ROOT ----
_test "_source_config_loader recovers via BASH_SOURCE fallback when CLAUDE_PLUGIN_ROOT is wrong"
(
  unset -f load_agentic_config 2>/dev/null || true
  unset -f get_project_root 2>/dev/null || true
  # Set CLAUDE_PLUGIN_ROOT to a bogus path - the helper should fall back
  export CLAUDE_PLUGIN_ROOT="/nonexistent/path"
  source "$PLUGIN_ROOT/scripts/spec-resolver.sh"
  if _source_config_loader 2>/dev/null; then
    exit 0
  else
    exit 1
  fi
) && _pass || _fail "fallback resolution failed"

# ---- Test 3: resolve_spec_path stdout contains ONLY the path (no pollution) ----
_test "resolve_spec_path stdout contains only the resolved path (no informational messages)"
(
  # Create a temporary project directory with CLAUDE.md and .git
  TMPDIR_TEST=$(mktemp -d)
  trap 'rm -rf "$TMPDIR_TEST"' EXIT
  mkdir -p "$TMPDIR_TEST/.git"
  echo "test" > "$TMPDIR_TEST/CLAUDE.md"
  cd "$TMPDIR_TEST"

  unset -f load_agentic_config 2>/dev/null || true
  unset -f get_project_root 2>/dev/null || true
  unset EXT_SPECS_REPO_URL 2>/dev/null || true
  unset EXT_SPECS_LOCAL_PATH 2>/dev/null || true
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  source "$PLUGIN_ROOT/scripts/spec-resolver.sh"

  # Capture stdout and stderr separately
  stdout_output=$(resolve_spec_path "2025/03/feat/test/001-spec.md" 2>/dev/null)
  exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    echo "resolve_spec_path failed with exit code $exit_code" >&2
    exit 1
  fi

  # stdout should contain exactly one line: the resolved path
  line_count=$(echo "$stdout_output" | wc -l | tr -d ' ')
  if [[ "$line_count" -ne 1 ]]; then
    echo "Expected 1 line on stdout, got $line_count: $stdout_output" >&2
    exit 1
  fi

  # The path should end with the relative spec path
  if [[ "$stdout_output" != *"specs/2025/03/feat/test/001-spec.md" ]]; then
    echo "Unexpected stdout: $stdout_output" >&2
    exit 1
  fi

  # No informational messages in stdout
  if [[ "$stdout_output" == *"Successfully"* ]] || \
     [[ "$stdout_output" == *"Cloning"* ]] || \
     [[ "$stdout_output" == *"Pulling"* ]]; then
    echo "Stdout contains informational messages: $stdout_output" >&2
    exit 1
  fi

  exit 0
) && _pass || _fail "stdout contained extra output beyond the resolved path"

# ---- Test 4: Error messages go to stderr ----
_test "Error messages go to stderr, not stdout"
(
  unset -f load_agentic_config 2>/dev/null || true
  unset -f get_project_root 2>/dev/null || true
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  source "$PLUGIN_ROOT/scripts/spec-resolver.sh"

  # Call with empty string argument - should produce error on stderr
  stdout_output=$(resolve_spec_path "" 2>/dev/null || true)
  stderr_output=$(resolve_spec_path "" 2>&1 1>/dev/null || true)

  # stdout should be empty
  if [[ -n "$stdout_output" ]]; then
    echo "Error output leaked to stdout: $stdout_output" >&2
    exit 1
  fi

  # stderr should contain the error
  if [[ -z "$stderr_output" ]]; then
    echo "No error output on stderr" >&2
    exit 1
  fi

  if [[ "$stderr_output" != *"ERROR"* ]]; then
    echo "stderr doesn't contain ERROR: $stderr_output" >&2
    exit 1
  fi

  exit 0
) && _pass || _fail "error output not properly directed to stderr"

# ---- Test 5: external-specs.sh informational messages go to stderr ----
_test "external-specs.sh informational messages go to stderr"
(
  # Verify no bare echo without >&2 in the non-value-returning paths
  operational_stdout_echos=$(grep -n 'echo "' "$PLUGIN_ROOT/scripts/external-specs.sh" \
    | grep -v '>&2' \
    | grep -v 'ext_specs_path()' \
    | grep -v 'echo "$project_root/' \
    | grep -v '_ext_specs_lockdir' \
    || true)

  if [[ -n "$operational_stdout_echos" ]]; then
    echo "Found echo statements without >&2 redirect:" >&2
    echo "$operational_stdout_echos" >&2
    exit 1
  fi

  exit 0
) && _pass || _fail "found informational echo statements going to stdout"

# ---- Test 6: spec-resolver.sh commit messages go to stderr ----
_test "spec-resolver.sh commit success messages go to stderr"
(
  # Check that all "Committed to" messages use >&2
  commit_echos=$(grep -n 'echo "Committed to' "$PLUGIN_ROOT/scripts/spec-resolver.sh" \
    | grep -v '>&2' \
    || true)

  if [[ -n "$commit_echos" ]]; then
    echo "Found commit echo statements without >&2:" >&2
    echo "$commit_echos" >&2
    exit 1
  fi

  exit 0
) && _pass || _fail "commit success messages not redirected to stderr"

# ---- Test 7: preloaded config-loader still repairs CLAUDE_PLUGIN_ROOT ----
_test "preloaded config-loader still repairs CLAUDE_PLUGIN_ROOT for ac-git and ac-workflow"
(
  _assert_preloaded_loader_repairs_plugin_root "$PLUGIN_ROOT" "ac-git"
  _assert_preloaded_loader_repairs_plugin_root "$WORKFLOW_PLUGIN_ROOT" "ac-workflow"
) && _pass || _fail "preloaded config-loader did not repair CLAUDE_PLUGIN_ROOT"

# ---- Summary ----
echo ""
echo "==============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "==============================="

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
