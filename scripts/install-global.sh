#!/usr/bin/env bash
set -euo pipefail

AGENTIC_CONFIG_PATH="${AGENTIC_CONFIG_PATH:-$HOME/.agents/agentic-config}"
CLAUDE_USER_DIR="$HOME/.claude"
CLAUDE_COMMANDS_DIR="$CLAUDE_USER_DIR/commands"
CLAUDE_MD="$CLAUDE_USER_DIR/CLAUDE.md"

# Ensure directories exist
mkdir -p "$CLAUDE_COMMANDS_DIR"

# Symlink all agentic commands
for cmd in agentic agentic-setup agentic-migrate agentic-update agentic-status; do
  src="$AGENTIC_CONFIG_PATH/core/commands/claude/${cmd}.md"
  if [[ -f "$src" ]]; then
    ln -sf "$src" "$CLAUDE_COMMANDS_DIR/${cmd}.md"
    echo "  ✓ Linked /${cmd}"
  fi
done

# Append to CLAUDE.md if not already present
MARKER="## Agentic-Config Global"
if ! grep -q "$MARKER" "$CLAUDE_MD" 2>/dev/null; then
  cat >> "$CLAUDE_MD" << 'EOF'

## Agentic-Config Global
When `/agentic` command is triggered, read the appropriate agent definition from:
`~/.agents/agentic-config/core/agents/agentic-{action}.md`

Actions: setup, migrate, update, status, validate, customize

Example: `/agentic setup` → read `~/.agents/agentic-config/core/agents/agentic-setup.md` and follow its instructions.
EOF
  echo "✓ Added agentic-config section to $CLAUDE_MD"
else
  echo "⊘ Agentic-config section already in $CLAUDE_MD"
fi

echo ""
echo "Installation complete. Global commands available:"
echo "  /agentic, /agentic-setup, /agentic-migrate, /agentic-update, /agentic-status"
