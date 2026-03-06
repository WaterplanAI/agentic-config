#!/usr/bin/env bash
# B-002: Hook Testing from Plugin Cache
# SC-7: Hooks fire correctly from plugin cache via ${CLAUDE_PLUGIN_ROOT}
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Hook inventory ==="
echo "Plugin: ac-git"
echo "  hooks/hooks.json:"
echo "    PreToolUse (Bash):"
echo "      - git-commit-guard.py (blocks git commit/push/merge/rebase/cherry-pick with --no-verify)"
echo ""
echo "Plugin: ac-tools"
echo "  hooks/hooks.json:"
echo "    PreToolUse (Bash):"
echo "      - dry-run-guard.py (blocks writes when session status.yml has dry_run: true)"
echo "      - gsuite-public-asset-guard.py (blocks public sharing of gsuite assets)"
echo ""
echo "Plugin: ac-workflow"
echo "  No plugin-level hooks.json (MUX skill-level hooks via SKILL.md frontmatter)"
echo ""

echo "=== Test 1: dry-run-guard ==="
echo "Setup: activate dry-run via /dry-run skill (creates outputs/session/.../status.yml with dry_run: true)"
echo "Load: claude --plugin-dir $REPO_ROOT/plugins/ac-tools"
echo "Action: Try to write a file (should be blocked)"
echo "Expected: Hook blocks the write with dry-run message"
echo ""

echo "=== Test 2: git-commit-guard ==="
echo "Load: claude --plugin-dir $REPO_ROOT/plugins/ac-git"
echo "Action: Try 'git commit -m \"test\" --no-verify' (should be blocked)"
echo "Expected: Hook blocks --no-verify bypass"
echo ""

echo "=== Test 3: gsuite-public-asset-guard ==="
echo "Load: claude --plugin-dir $REPO_ROOT/plugins/ac-tools"
echo "Action: Try to share a gsuite asset publicly"
echo "Expected: Hook blocks public sharing"
echo ""

echo "=== Test 4: Plugin cache verification ==="
echo "After installing via marketplace, verify hooks resolve from cache:"
echo "1. Install ac-git via marketplace"
echo "2. Check plugin cache: ls ~/.claude/plugins/cache/*/ac-git/scripts/hooks/"
echo "3. Verify git-commit-guard.py exists in cache"
echo "4. Trigger a hook and verify it runs from cache path"
echo ""

echo "=== Test 5: \${CLAUDE_PLUGIN_ROOT} resolution ==="
echo "After install, check that hook command resolves correctly:"
echo "  Expected: \${CLAUDE_PLUGIN_ROOT} -> ~/.claude/plugins/cache/<hash>/ac-git/"
echo "  Hook command: uv run --no-project --script \${CLAUDE_PLUGIN_ROOT}/scripts/hooks/git-commit-guard.py"
echo ""

echo "=== PASS/FAIL checklist ==="
echo "[ ] SC-7: dry-run-guard fires from --plugin-dir"
echo "[ ] SC-7: git-commit-guard fires from --plugin-dir"
echo "[ ] SC-7: gsuite-public-asset-guard fires from --plugin-dir"
echo "[ ] SC-7: Hook scripts exist in plugin cache after marketplace install"
echo "[ ] SC-7: \${CLAUDE_PLUGIN_ROOT} resolves to cache dir"
echo "[ ] SC-7: Hooks fire correctly from plugin cache"
