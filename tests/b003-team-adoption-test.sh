#!/usr/bin/env bash
# B-003: Team Adoption Test
# Tests SC-6 (team settings.json), SC-7 (auto-prompt on trust)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== B-003: Team Adoption Test ==="
echo ""

echo "=== Prerequisites ==="
echo "1. A separate test repository (not this repo)"
echo "2. Marketplace already added: claude plugin marketplace add <owner>/agentic-config"
echo ""

echo "=== SC-6: Team adoption via settings.json ==="
echo "STEP 1: In the test repository, create .claude/settings.json:"
echo '  {'
echo '    "extraKnownMarketplaces": {'
echo '      "agentic-plugins": {'
echo '        "source": {'
echo '          "source": "github",'
echo '          "repo": "<owner>/agentic-config"'
echo '        }'
echo '      }'
echo '    },'
echo '    "enabledPlugins": {'
echo '      "ac-workflow@agentic-plugins": true,'
echo '      "ac-git@agentic-plugins": true'
echo '    }'
echo '  }'
echo "STEP 2: Commit and push"
echo "VERIFY: Settings file is valid JSON"
echo ""

echo "=== SC-7: Auto-prompt on trust ==="
echo "STEP 1: Have a different user (or clean Claude Code session) open the test repo"
echo "STEP 2: When Claude Code asks to trust the project, accept"
echo "VERIFY: User is prompted to install ac-workflow and ac-git plugins"
echo "VERIFY: After accepting, plugins are available"
echo "NOTE: This test requires manual verification -- auto-prompt is a Claude Code runtime behavior"
echo ""

echo "=== PASS/FAIL Checklist ==="
echo "[ ] SC-6: settings.json with marketplace ref + enabledPlugins works"
echo "[ ] SC-7: New user auto-prompted to install on project trust"
echo "[ ] Cleanup: Remove test settings.json or revert commit"
