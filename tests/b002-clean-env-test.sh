#!/usr/bin/env bash
# B-002: Clean Environment Testing (CC-Native)
# SC-6: Zero AGENTS.md, zero legacy artifacts after plugin install
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLEAN_DIR="/tmp/b002-clean-env-test-$$"

echo "=== Setup clean environment ==="
echo "Creating: $CLEAN_DIR"
mkdir -p "$CLEAN_DIR"
cd "$CLEAN_DIR"
git init
echo "# Test" > README.md
git add . && git commit -m "init"

echo ""
echo "=== Pre-install state ==="
echo "Checking no AGENTS.md exists..."
test ! -f AGENTS.md && echo "  PASS: No AGENTS.md" || echo "  FAIL: AGENTS.md exists"
echo "Checking no .claude/ artifacts..."
test ! -d .claude/skills && echo "  PASS: No .claude/skills/" || echo "  FAIL: .claude/skills/ exists"
test ! -d .claude/commands && echo "  PASS: No .claude/commands/" || echo "  FAIL: .claude/commands/ exists"

echo ""
echo "=== Install plugins (CC-native) ==="
echo "RUN (from $CLEAN_DIR):"
echo "  claude plugin marketplace add $REPO_ROOT"
echo "  claude plugin install ac-workflow@agentic-plugins"
echo "  claude plugin install ac-git@agentic-plugins"
echo "  claude plugin install ac-qa@agentic-plugins"
echo "  claude plugin install ac-tools@agentic-plugins"
echo "  claude plugin install ac-meta@agentic-plugins"
echo "  claude plugin install ac-safety@agentic-plugins"
echo "  claude plugin install ac-audit@agentic-plugins"
echo ""
echo "OR load directly for dev testing:"
echo "  ./dev.sh (from repo root)"
echo ""

echo "=== Post-install verification ==="
echo "RUN:"
echo "  test ! -f $CLEAN_DIR/AGENTS.md && echo 'PASS: No AGENTS.md' || echo 'FAIL: AGENTS.md created'"
echo "  test ! -d $CLEAN_DIR/.claude/skills && echo 'PASS: No .claude/skills/' || echo 'FAIL: legacy .claude/skills/ created'"
echo "  claude plugin list | grep -c 'ac-' | xargs -I{} test {} -eq 7 && echo 'PASS: All 7 plugins installed'"
echo ""

echo "=== PASS/FAIL checklist ==="
echo "[ ] SC-6: No AGENTS.md created after install"
echo "[ ] SC-6: No legacy .claude/skills/ or .claude/commands/ created"
echo "[ ] SC-6: Plugins functional in clean environment"
echo "[ ] SC-6: All 7 ac-* plugins discoverable via 'claude plugin list'"
