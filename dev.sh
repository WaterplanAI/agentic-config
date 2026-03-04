#!/usr/bin/env bash
# Dev convenience: launch Claude Code with all 5 agentic-config plugins loaded.
# Usage: ./dev.sh [additional claude args...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec claude \
  --plugin-dir "$SCRIPT_DIR/plugins/ac-workflow" \
  --plugin-dir "$SCRIPT_DIR/plugins/ac-git" \
  --plugin-dir "$SCRIPT_DIR/plugins/ac-qa" \
  --plugin-dir "$SCRIPT_DIR/plugins/ac-tools" \
  --plugin-dir "$SCRIPT_DIR/plugins/ac-meta" \
  "$@"
