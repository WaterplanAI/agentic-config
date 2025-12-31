#!/usr/bin/env bash
# Manages version tracking and installation registry

register_installation() {
  local target_path="$1"
  local project_type="$2"
  local version="$3"
  local install_mode="${4:-symlink}"  # default to symlink for backward compatibility
  local registry_file="$REPO_ROOT/.installations.json"

  # Discover global agentic-config path (pure bash for compatibility)
  local agentic_global_path="${AGENTIC_CONFIG_PATH:-}"
  # If not set, try ~/.agents/.path
  [[ -z "$agentic_global_path" ]] && [[ -f "$HOME/.agents/.path" ]] && agentic_global_path=$(<"$HOME/.agents/.path")

  # Create .agentic-config.json in target project
  local config_file="$target_path/.agentic-config.json"
  cat > "$config_file" <<EOF
{
  "version": "$version",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "project_type": "$project_type",
  "install_mode": "$install_mode",
  "agentic_global_path": "${agentic_global_path:-}",
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
       --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
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

# Reconcile .agentic-config.json with latest schema
# Adds missing fields without overwriting existing values
# This ensures nightly updates and same-version installs get new config fields
reconcile_config() {
  local target_path="$1"
  local latest_version="$2"
  local config_file="$target_path/.agentic-config.json"

  if [[ ! -f "$config_file" ]]; then
    echo "ERROR: No config file at $config_file" >&2
    return 1
  fi

  # Requires jq for reliable JSON manipulation
  if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not available, skipping config reconciliation" >&2
    return 0
  fi

  local changes_made=false
  local temp_file
  temp_file=$(mktemp) || {
    echo "ERROR: Failed to create temp file" >&2
    return 1
  }

  # Discover agentic global path (pure bash for compatibility)
  local agentic_global_path="${AGENTIC_CONFIG_PATH:-}"
  [[ -z "$agentic_global_path" ]] && [[ -f "$HOME/.agents/.path" ]] && \
    agentic_global_path=$(<"$HOME/.agents/.path")
  [[ -z "$agentic_global_path" ]] && agentic_global_path="$HOME/.agents/agentic-config"

  # Start with current config
  cp "$config_file" "$temp_file"

  # Add missing fields with defaults
  # install_mode: default to symlink
  if ! jq -e '.install_mode' "$temp_file" &>/dev/null; then
    jq '.install_mode = "symlink"' "$temp_file" > "${temp_file}.new" && mv "${temp_file}.new" "$temp_file"
    changes_made=true
    echo "  + Added install_mode: symlink"
  fi

  # agentic_global_path: path to global installation
  if ! jq -e '.agentic_global_path' "$temp_file" &>/dev/null; then
    jq --arg path "$agentic_global_path" '.agentic_global_path = $path' "$temp_file" > "${temp_file}.new" && mv "${temp_file}.new" "$temp_file"
    changes_made=true
    echo "  + Added agentic_global_path: $agentic_global_path"
  fi

  # auto_check: default to true
  if ! jq -e '.auto_check' "$temp_file" &>/dev/null; then
    jq '.auto_check = true' "$temp_file" > "${temp_file}.new" && mv "${temp_file}.new" "$temp_file"
    changes_made=true
    echo "  + Added auto_check: true"
  fi

  # Update version if provided
  if [[ -n "$latest_version" ]]; then
    local current_version
    current_version=$(jq -r '.version // "none"' "$temp_file")
    if [[ "$current_version" != "$latest_version" ]]; then
      jq --arg version "$latest_version" '.version = $version' "$temp_file" > "${temp_file}.new" && mv "${temp_file}.new" "$temp_file"
      changes_made=true
      echo "  ~ Updated version: $current_version -> $latest_version"
    fi
  fi

  # Always update timestamp when reconciling
  local timestamp
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  jq --arg ts "$timestamp" '.updated_at = $ts' "$temp_file" > "${temp_file}.new" && mv "${temp_file}.new" "$temp_file"

  # Apply changes
  if [[ "$changes_made" == true ]]; then
    mv "$temp_file" "$config_file"
    echo "Config reconciled"
  else
    rm -f "$temp_file"
    echo "  (no missing fields)"
  fi

  # Cleanup any remaining temp files
  rm -f "${temp_file}.new" 2>/dev/null || true

  return 0
}
