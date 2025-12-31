#!/usr/bin/env bash
# E2E Test Suite Runner
# Runs all E2E tests and generates comprehensive report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test results tracking
TOTAL_PASS=0
TOTAL_FAIL=0
SUITE_RESULTS=()

# Banner
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Agentic-Config E2E Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Pre-flight checks
echo "==> Pre-flight Checks"
echo ""

# Check git
if ! command -v git >/dev/null 2>&1; then
  echo -e "${RED}ERROR: git is required but not installed${NC}"
  exit 1
fi
echo -e "${GREEN}✓${NC} git installed"

# Check jq (optional but recommended)
if ! command -v jq >/dev/null 2>&1; then
  echo -e "${YELLOW}⚠${NC} jq not installed - some tests will be skipped"
else
  echo -e "${GREEN}✓${NC} jq installed"
fi

# Check repo structure
if [[ ! -f "$REPO_ROOT/VERSION" ]]; then
  echo -e "${RED}ERROR: Not in agentic-config repository${NC}"
  exit 1
fi
echo -e "${GREEN}✓${NC} Repository structure valid"

echo ""
echo "==> Running Test Suites"
echo ""

# Run test suite helper
run_test_suite() {
  local test_script="$1"
  local suite_name="$2"

  echo -e "${BLUE}==> Running: $suite_name${NC}"
  echo ""

  local exit_code=0
  if bash "$test_script"; then
    exit_code=0
    SUITE_RESULTS+=("${GREEN}PASS${NC}|$suite_name")
  else
    exit_code=$?
    SUITE_RESULTS+=("${RED}FAIL${NC}|$suite_name|Exit code: $exit_code")
  fi

  echo ""
  return $exit_code
}

# Track overall pass/fail
SUITES_PASSED=0
SUITES_FAILED=0

# Run all test suites
# Restricted shell tests FIRST - catches bootstrap issues before other tests
if run_test_suite "$SCRIPT_DIR/test_restricted_shell.sh" "Restricted Shell Compatibility"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

if run_test_suite "$SCRIPT_DIR/test_install.sh" "install.sh Tests"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

if run_test_suite "$SCRIPT_DIR/test_setup.sh" "/agentic setup Tests"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

if run_test_suite "$SCRIPT_DIR/test_update.sh" "/agentic update Tests"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

if run_test_suite "$SCRIPT_DIR/test_migrate.sh" "/agentic migrate Tests"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

if run_test_suite "$SCRIPT_DIR/test_external_specs.sh" "External Specs Tests"; then
  ((SUITES_PASSED++)) || true
else
  ((SUITES_FAILED++)) || true
fi

# Final Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}E2E Test Suite Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo "Suite Results:"
for result in "${SUITE_RESULTS[@]}"; do
  IFS='|' read -r status name info <<< "$result"
  if [[ -n "$info" ]]; then
    echo -e "  $status $name ($info)"
  else
    echo -e "  $status $name"
  fi
done

echo ""
echo "Overall:"
echo -e "  Suites Passed: ${GREEN}$SUITES_PASSED${NC}"
echo -e "  Suites Failed: ${RED}$SUITES_FAILED${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"

# Exit with failure if any suite failed
if [[ $SUITES_FAILED -gt 0 ]]; then
  echo -e "${RED}E2E tests FAILED${NC}"
  exit 1
else
  echo -e "${GREEN}All E2E tests PASSED${NC}"
  exit 0
fi
