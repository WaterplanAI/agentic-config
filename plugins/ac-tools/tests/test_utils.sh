#!/usr/bin/env bash
# Minimal test utilities for plugin tests

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

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

print_test_summary() {
  local test_name="$1"
  echo ""
  echo "=== $test_name Results ==="
  echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
  echo -e "Failed: ${RED}$FAIL_COUNT${NC}"
  return $FAIL_COUNT
}
