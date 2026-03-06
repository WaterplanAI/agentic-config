#!/usr/bin/env bash
# E2E tests for uninstall.sh (legacy v0.1.x uninstall)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
UNINSTALL_SCRIPT="$REPO_ROOT/uninstall.sh"

PASS_COUNT=0
FAIL_COUNT=0

if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  NC=''
fi

pass() {
  echo -e "${GREEN}PASS${NC}: $1"
  ((PASS_COUNT++)) || true
}

fail() {
  echo -e "${RED}FAIL${NC}: $1"
  ((FAIL_COUNT++)) || true
}

assert_exists() {
  local path="$1"
  local msg="$2"
  if [[ -e "$path" || -L "$path" ]]; then
    pass "$msg"
  else
    fail "$msg"
  fi
}

assert_not_exists() {
  local path="$1"
  local msg="$2"
  if [[ ! -e "$path" && ! -L "$path" ]]; then
    pass "$msg"
  else
    fail "$msg"
  fi
}

assert_contains() {
  local file="$1"
  local text="$2"
  local msg="$3"
  if grep -q "$text" "$file" 2>/dev/null; then
    pass "$msg"
  else
    fail "$msg"
  fi
}

assert_not_contains() {
  local file="$1"
  local text="$2"
  local msg="$3"
  if grep -q "$text" "$file" 2>/dev/null; then
    fail "$msg"
  else
    pass "$msg"
  fi
}

test_project_symlink_only_cleanup() {
  echo "=== test_project_symlink_only_cleanup ==="

  local tmpdir
  tmpdir="$(mktemp -d)"
  local project="$tmpdir/project"
  local global="$tmpdir/global-agentic"

  mkdir -p "$project/.agent" "$project/.claude/commands" "$project/.claude/skills" "$global/core/agents" "$global/core/skills/test-skill"

  ln -s "$global/core/agents" "$project/agents"
  ln -s "$global/core/agents" "$project/.claude/commands/agentic.md"
  ln -s "$global/core/skills/test-skill" "$project/.claude/skills/test-skill"

  echo "do not touch" > "$project/AGENTS.md"
  echo "do not touch" > "$project/PROJECT_AGENTS.md"
  echo "copy" > "$project/.agent/config.yml"

  cat > "$project/.agentic-config.json" <<EOF
{
  "agentic_global_path": "$global",
  "symlinks": ["agents", ".claude/commands/agentic.md", ".claude/skills/*"],
  "copied": ["AGENTS.md", "PROJECT_AGENTS.md", ".agent/config.yml"]
}
EOF

  "$UNINSTALL_SCRIPT" --project "$project" --yes > "$tmpdir/run.log"

  assert_not_exists "$project/agents" "agents symlink removed"
  assert_not_exists "$project/.claude/commands/agentic.md" "command symlink removed"
  assert_not_exists "$project/.claude/skills/test-skill" "skill symlink removed"

  assert_exists "$project/AGENTS.md" "AGENTS.md preserved"
  assert_exists "$project/PROJECT_AGENTS.md" "PROJECT_AGENTS.md preserved"
  assert_exists "$project/.agent/config.yml" "copied file preserved"

  assert_contains "$tmpdir/run.log" "intentionally untouched" "safety messaging shown"

  rm -rf "$tmpdir"
}

test_global_default_noninteractive_does_not_delete_clone() {
  echo "=== test_global_default_noninteractive_does_not_delete_clone ==="

  local tmpdir
  tmpdir="$(mktemp -d)"
  local test_home="$tmpdir/home"
  local global="$tmpdir/global-agentic"

  mkdir -p "$test_home/.claude/commands" "$test_home/.agents" "$test_home/.config/agentic" "$global/core/commands/claude"

  local cmd
  for cmd in agentic agentic-setup agentic-migrate agentic-update agentic-status; do
    touch "$global/core/commands/claude/$cmd.md"
    ln -s "$global/core/commands/claude/$cmd.md" "$test_home/.claude/commands/$cmd.md"
  done

  cat > "$test_home/.claude/CLAUDE.md" <<EOF
# User CLAUDE

## Intro
keep

## Agentic-Config Global
legacy block

## Outro
keep too
EOF

  printf '%s\n' "$global" > "$test_home/.agents/.path"
  cat > "$test_home/.zshrc" <<EOF
# agentic-config path
export AGENTIC_CONFIG_PATH="$global"
EOF
  cat > "$test_home/.config/agentic/config" <<EOF
path=$global
EOF

  HOME="$test_home" AGENTIC_CONFIG_PATH="" "$UNINSTALL_SCRIPT" --global --global-path "$global" > "$tmpdir/run.log"

  for cmd in agentic agentic-setup agentic-migrate agentic-update agentic-status; do
    assert_not_exists "$test_home/.claude/commands/$cmd.md" "global command symlink removed: $cmd"
  done

  assert_not_contains "$test_home/.claude/CLAUDE.md" "Agentic-Config Global" "CLAUDE.md marker removed"
  assert_not_exists "$test_home/.agents/.path" "dotpath removed"
  assert_not_contains "$test_home/.zshrc" "AGENTIC_CONFIG_PATH" "shell profile export removed"
  assert_not_exists "$test_home/.config/agentic/config" "XDG config removed when empty"

  assert_exists "$global" "global clone preserved in non-interactive mode without --yes"
  assert_contains "$tmpdir/run.log" "Skipping deletion prompt" "non-interactive no-delete behavior logged"

  rm -rf "$tmpdir"
}

test_project_yaml_metadata_support() {
  echo "=== test_project_yaml_metadata_support ==="

  local tmpdir
  tmpdir="$(mktemp -d)"
  local project="$tmpdir/project"
  local global="$tmpdir/global-agentic"

  mkdir -p "$project/.claude/commands" "$global/core/commands/claude"
  ln -s "$global/core/commands/claude" "$project/agents"
  ln -s "$global/core/commands/claude" "$project/.claude/commands/agentic.md"

  cat > "$project/.agentic-config.yaml" <<EOF
agentic_global_path: "$global"
symlinks:
  - agents
  - .claude/commands/agentic.md
copied:
  - AGENTS.md
EOF

  "$UNINSTALL_SCRIPT" --project "$project" --yes > "$tmpdir/run.log"

  assert_not_exists "$project/agents" "yaml: agents symlink removed"
  assert_not_exists "$project/.claude/commands/agentic.md" "yaml: command symlink removed"

  rm -rf "$tmpdir"
}

print_summary() {
  echo ""
  echo "=== uninstall.sh E2E summary ==="
  echo "Passed: $PASS_COUNT"
  echo "Failed: $FAIL_COUNT"

  if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
  fi
}

if [[ ! -x "$UNINSTALL_SCRIPT" ]]; then
  echo "ERROR: uninstall.sh is not executable: $UNINSTALL_SCRIPT" >&2
  exit 1
fi

test_project_symlink_only_cleanup
test_global_default_noninteractive_does_not_delete_clone
test_project_yaml_metadata_support
print_summary
