#!/usr/bin/env bash
# B-002: Combination Testing
# SC-5: All 7 plugins load simultaneously without namespace conflicts
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS=(ac-workflow ac-git ac-qa ac-tools ac-meta ac-safety ac-audit)

echo "=== Load all 7 plugins simultaneously ==="
PLUGIN_DIRS=""
for p in "${PLUGINS[@]}"; do
  PLUGIN_DIRS="$PLUGIN_DIRS --plugin-dir $REPO_ROOT/plugins/$p"
done
echo "RUN: claude $PLUGIN_DIRS"
echo ""

echo "=== Verification checklist ==="
echo "1. /help -- all skills from all 7 plugins visible"
echo "2. Core skills resolve directly: /spec, /pull-request, /gsuite, /skill-writer, /configure-safety, /configure-audit"
echo "3. No error messages about duplicate names or conflicts"
echo "4. Skills from all plugins discoverable"
echo "5. Agents from ac-workflow visible in /agents"
echo ""

echo "=== Cross-plugin workflow test ==="
echo "Test: mux calling spec (cross-plugin dependency)"
echo "RUN (inside session): /mux -- verify it can invoke spec skills"
echo ""

echo "=== Enable/disable test ==="
echo "1. Install all 7 via marketplace"
echo "2. Disable one: claude plugin disable ac-tools@agentic-plugins"
echo "3. Verify: /help no longer shows ac-tools skills"
echo "4. Re-enable: claude plugin enable ac-tools@agentic-plugins"
echo "5. Verify: /help shows ac-tools skills again"
echo ""

echo "=== PASS/FAIL checklist ==="
echo "[ ] SC-5: All 7 load without errors"
echo "[ ] SC-5: Core skills resolve directly (/spec, /pull-request, /gsuite, /skill-writer, /configure-safety, /configure-audit)"
echo "[ ] SC-5: No namespace conflicts"
echo "[ ] SC-5: Cross-plugin workflow works"
echo "[ ] SC-5: Enable/disable works"
