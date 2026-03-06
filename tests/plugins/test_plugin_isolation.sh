#!/usr/bin/env bash
# E2E test: validate each plugin works from isolated cache directory
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"
PASS=0
FAIL=0

for plugin_dir in "$PLUGINS_DIR"/*/; do
  plugin_name=$(basename "$plugin_dir")
  echo "=== Testing plugin: $plugin_name ==="

  # Simulate cache: copy to temp dir
  CACHE_DIR=$(mktemp -d)
  cp -r "$plugin_dir"/* "$CACHE_DIR/" 2>/dev/null || true
  cp -r "$plugin_dir"/.claude-plugin "$CACHE_DIR/" 2>/dev/null || true

  # Test 1: plugin.json exists and is valid JSON
  if python3 -c "import json; json.load(open('$CACHE_DIR/.claude-plugin/plugin.json'))" 2>/dev/null; then
    echo "  [PASS] plugin.json valid"
    PASS=$((PASS+1))
  else
    echo "  [FAIL] plugin.json invalid or missing"
    FAIL=$((FAIL+1))
  fi

  # Test 2: No forbidden library references
  FORBIDDEN_VIOLATIONS=$(python3 - "$CACHE_DIR" <<'PYEOF' 2>/dev/null
import os, sys

cache_dir = sys.argv[1]

FORBIDDEN = ['AGENTIC_GLOBAL', '_AGENTIC_ROOT', 'core/lib/', 'core/tools/', 'core/prompts/', 'core/hooks/']
ALLOWED = ['~/.agents/customization/']

found = []
for root, dirs, files in os.walk(cache_dir):
    for fname in files:
        if not fname.endswith(('.md', '.sh', '.py', '.json')): continue
        fpath = os.path.join(root, fname)
        try:
            content = open(fpath, errors='replace').read()
        except: continue
        for pattern in FORBIDDEN:
            if pattern in content:
                lines = [l.strip() for l in content.splitlines()
                         if pattern in l
                         and not l.strip().startswith('#')
                         and not any(exc in l for exc in ALLOWED)]
                if lines:
                    found.append(f"{fname}: '{pattern}'")
                    break

for f in found:
    print(f)
PYEOF
)
  if [ -n "$FORBIDDEN_VIOLATIONS" ]; then
    echo "  [FAIL] Forbidden patterns found:"
    echo "$FORBIDDEN_VIOLATIONS" | while read -r line; do echo "    $line"; done
    FAIL=$((FAIL+1))
  else
    echo "  [PASS] No forbidden library patterns"
    PASS=$((PASS+1))
  fi

  # Test 3: All skills have SKILL.md
  if [ -d "$CACHE_DIR/skills" ]; then
    SKILL_FAIL=0
    for skill_sub in "$CACHE_DIR/skills"/*/; do
      [ -d "$skill_sub" ] || continue
      if [ ! -f "${skill_sub}SKILL.md" ]; then
        echo "  [FAIL] Missing SKILL.md: $(basename "$skill_sub")"
        SKILL_FAIL=1
      fi
    done
    if [ $SKILL_FAIL -eq 0 ]; then
      echo "  [PASS] All skills have SKILL.md"
      PASS=$((PASS+1))
    else
      FAIL=$((FAIL+1))
    fi
  fi

  # Test 4: Shell scripts pass syntax check
  SHELL_FAIL=0
  while IFS= read -r -d '' sh_file; do
    if ! bash -n "$sh_file" 2>/dev/null; then
      echo "  [FAIL] Shell syntax error: $(basename "$sh_file")"
      SHELL_FAIL=1
    fi
  done < <(find "$CACHE_DIR" -name '*.sh' -print0 2>/dev/null)
  if [ $SHELL_FAIL -eq 0 ]; then
    echo "  [PASS] All shell scripts pass syntax check"
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1))
  fi

  # Test 5: Python scripts pass syntax check
  PY_FAIL=0
  while IFS= read -r -d '' py_file; do
    if ! python3 -c "import ast; ast.parse(open('$py_file').read())" 2>/dev/null; then
      echo "  [FAIL] Python syntax error: $(basename "$py_file")"
      PY_FAIL=1
    fi
  done < <(find "$CACHE_DIR" -name '*.py' -print0 2>/dev/null)
  if [ $PY_FAIL -eq 0 ]; then
    echo "  [PASS] All Python scripts pass syntax check"
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1))
  fi

  # Cleanup
  rm -rf "$CACHE_DIR"
  echo ""
done

echo "================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================"

if [ $FAIL -gt 0 ]; then
  exit 1
fi
