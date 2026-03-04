#!/usr/bin/env bash
# B-002: Scope Testing
# Tests user, project, local scopes for plugin installation.
# SC-4: All 3 testable scopes correctly update respective settings files
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Prerequisites ==="
echo "1. Marketplace must be added first: claude plugin marketplace add $REPO_ROOT"
echo "2. Clean up any previous test installs"
echo ""

echo "=== Test 1: User scope ==="
echo "RUN: claude plugin install ac-workflow@agentic-plugins --scope user"
echo "VERIFY: Check ~/.claude/settings.json contains:"
echo '  "enabledPlugins": { "ac-workflow@agentic-plugins": true }'
echo "CLEANUP: claude plugin uninstall ac-workflow@agentic-plugins --scope user"
echo ""

echo "=== Test 2: Project scope ==="
echo "RUN: claude plugin install ac-workflow@agentic-plugins --scope project"
echo "VERIFY: Check .claude/settings.json in repo contains:"
echo '  "enabledPlugins": { "ac-workflow@agentic-plugins": true }'
echo "CLEANUP: claude plugin uninstall ac-workflow@agentic-plugins --scope project"
echo ""

echo "=== Test 3: Local scope ==="
echo "RUN: claude plugin install ac-workflow@agentic-plugins --scope local"
echo "VERIFY: Check user-local per-repo settings contains plugin entry"
echo "CLEANUP: claude plugin uninstall ac-workflow@agentic-plugins --scope local"
echo ""

echo "=== Automated settings verification ==="
echo "After each install, run:"
echo '  python3 -c "'
echo '  import json'
echo '  from pathlib import Path'
echo '  # For user scope:'
echo '  s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())'
echo '  assert "ac-workflow@agentic-plugins" in s.get("enabledPlugins", {})'
echo '  print("User scope: PASS")'
echo '  "'
echo ""

echo "=== PASS/FAIL checklist ==="
echo "[ ] SC-4: User scope -- settings.json updated"
echo "[ ] SC-4: Project scope -- .claude/settings.json updated"
echo "[ ] SC-4: Local scope -- local settings updated"
echo "[ ] Cleanup: all test installs removed"
