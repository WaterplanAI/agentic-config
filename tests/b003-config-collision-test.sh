#!/usr/bin/env bash
# B-003: Config Collision Test
# Tests SC-8 (no config collisions between team and personal plugins)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== B-003: Config Collision Test ==="
echo ""

echo "=== Prerequisites ==="
echo "1. Marketplace added: claude plugin marketplace add <owner>/agentic-config"
echo "2. A test repository with team settings.json (see b003-team-adoption-test.sh)"
echo ""

echo "=== SC-8: Personal + Team coexistence ==="
echo ""
echo "STEP 1: Install personal plugins (user scope)"
echo "RUN: claude plugin install ac-tools@agentic-plugins --scope user"
echo "RUN: claude plugin install ac-meta@agentic-plugins --scope user"
echo "VERIFY: ~/.claude/settings.json has ac-tools and ac-meta"
echo ""

echo "STEP 2: Open test repo with team plugins (project scope)"
echo "Project .claude/settings.json has: ac-workflow, ac-git"
echo "VERIFY: Both personal (ac-tools, ac-meta) and team (ac-workflow, ac-git) are available"
echo "VERIFY: No errors about conflicting plugin configurations"
echo ""

echo "STEP 3: Verify isolation"
echo "VERIFY: Personal plugins do NOT appear in project .claude/settings.json"
echo "VERIFY: Team plugins do NOT appear in ~/.claude/settings.json"
echo "VERIFY: All 4 plugins (2 personal + 2 team) work simultaneously"
echo ""

echo "STEP 4: Different team member scenario"
echo "Another user has different personal plugins (e.g., only ac-qa)"
echo "VERIFY: Their personal ac-qa does not conflict with team ac-workflow + ac-git"
echo "VERIFY: Each member has team plugins + their own personal set"
echo ""

echo "=== PASS/FAIL Checklist ==="
echo "[ ] SC-8: Personal + team plugins coexist"
echo "[ ] SC-8: No cross-contamination between scopes"
echo "[ ] SC-8: Different personal sets work alongside same team set"
echo "[ ] Cleanup: Uninstall personal test plugins"
