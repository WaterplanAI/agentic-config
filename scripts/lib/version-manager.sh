#!/usr/bin/env bash
# Manages version tracking and installation registry

register_installation() {
  local target_path="$1"
  local project_type="$2"
  local version="$3"
  local install_mode="${4:-symlink}"  # default to symlink for backward compatibility
  local registry_file="$REPO_ROOT/.installations.json"

  # Create .agentic-config.json in target project
  local config_file="$target_path/.agentic-config.json"
  cat > "$config_file" <<EOF
{
  "version": "$version",
  "installed_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)",
  "project_type": "$project_type",
  "install_mode": "$install_mode",
  "auto_check": true,
  "symlinks": [
    "agents",
    ".agent/workflows/spec.md",
    ".claude/commands/spec.md",
    ".claude/commands/agentic*.md",
    ".claude/agents/agentic-*.md",
    ".gemini/commands/spec.toml",
    ".gemini/commands/spec",
    ".codex/prompts/spec.md"
  ],
  "copied": [
    ".agent/config.yml",
    "AGENTS.md"
  ]
}
EOF

  # Update central registry
  if command -v jq &>/dev/null; then
    # Create registry file if it doesn't exist
    if [[ ! -f "$registry_file" ]]; then
      echo '{"installations": []}' > "$registry_file"
    fi
    local temp_file=$(mktemp)
    jq --arg path "$target_path" \
       --arg type "$project_type" \
       --arg version "$version" \
       --arg timestamp "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)" \
       '.installations += [{path: $path, type: $type, version: $version, installed_at: $timestamp}]' \
       "$registry_file" > "$temp_file"
    mv "$temp_file" "$registry_file"
  else
    echo "WARNING: jq not installed, skipping central registry update" >&2
  fi

  return 0
}

check_version() {
  local target_path="$1"
  local config_file="$target_path/.agentic-config.json"

  if [[ ! -f "$config_file" ]]; then
    echo "none"
    return 0
  fi

  if command -v jq &>/dev/null; then
    jq -r '.version' "$config_file" 2>/dev/null || echo "none"
  else
    grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$config_file" | cut -d'"' -f4
  fi

  return 0
}

get_install_mode() {
  local target_path="$1"
  local config_file="$target_path/.agentic-config.json"

  if [[ ! -f "$config_file" ]]; then
    echo "symlink"  # default
    return 0
  fi

  if command -v jq &>/dev/null; then
    jq -r '.install_mode // "symlink"' "$config_file" 2>/dev/null || echo "symlink"
  else
    # grep returns empty string (not error) when field not found, so use variable with default
    local mode
    mode=$(grep -o '"install_mode"[[:space:]]*:[[:space:]]*"[^"]*"' "$config_file" 2>/dev/null | cut -d'"' -f4)
    echo "${mode:-symlink}"
  fi

  return 0
}
