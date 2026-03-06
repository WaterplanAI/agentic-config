#!/usr/bin/env bash
# B-003: Marketplace Add + Plugin Install Test
# Tests SC-1 (self-hosted marketplace), SC-2 (marketplace add), SC-3 (all 5 installable)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS=(ac-workflow ac-git ac-qa ac-tools ac-meta)

echo "=== B-003: Marketplace Add + Plugin Install ==="
echo ""
echo "=== Prerequisites ==="
echo "1. Repository must be pushed to GitHub (marketplace.json on accessible branch)"
echo "2. Clean up any previous test installs"
echo ""

echo "=== SC-1: Add self-hosted marketplace ==="
echo "RUN: claude plugin marketplace add <owner>/agentic-config"
echo "VERIFY: Command completes without error"
echo "VERIFY: claude plugin marketplace list shows 'agentic-plugins'"
echo ""

echo "=== SC-2: Verify all 5 plugins visible ==="
echo "RUN: claude plugin search --marketplace agentic-plugins"
echo "VERIFY: All 5 plugins listed:"
for p in "${PLUGINS[@]}"; do
    echo "  - $p"
done
echo ""

echo "=== SC-3: Install each plugin ==="
for p in "${PLUGINS[@]}"; do
    echo "--- $p ---"
    echo "RUN: claude plugin install ${p}@agentic-plugins --scope user"
    echo "VERIFY: Install succeeds without error"
    echo "CLEANUP: claude plugin uninstall ${p}@agentic-plugins --scope user"
    echo ""
done

echo "=== SC-3: Multi-scope test (ac-workflow plugin) ==="
echo "RUN: claude plugin install ac-workflow@agentic-plugins --scope user"
echo "VERIFY: ~/.claude/settings.json has enabledPlugins entry"
echo "CLEANUP: claude plugin uninstall ac-workflow@agentic-plugins --scope user"
echo ""
echo "RUN: claude plugin install ac-workflow@agentic-plugins --scope project"
echo "VERIFY: .claude/settings.json has enabledPlugins entry"
echo "CLEANUP: claude plugin uninstall ac-workflow@agentic-plugins --scope project"
echo ""

echo "=== PASS/FAIL Checklist ==="
echo "[ ] SC-1: Marketplace add succeeds"
echo "[ ] SC-2: All 5 plugins visible in marketplace"
echo "[ ] SC-3: All 5 plugins install without error (user scope)"
echo "[ ] SC-3: Multi-scope install works (user, project)"
echo "[ ] Cleanup: All test installs removed"
