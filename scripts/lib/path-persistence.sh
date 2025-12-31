#!/usr/bin/env bash
# Path Persistence Library
# Manages AGENTIC_CONFIG_PATH persistence across multiple locations

# Persistence Locations (in priority order):
# 1. ~/.agents/.path - Simple file with absolute path
# 2. Shell profiles (~/.bashrc, ~/.zshrc) - Export statement
# 3. ~/.config/agentic/config - XDG-compliant config
# 4. Project .agentic-config.json - agentic_global_path field

# Marker for shell profile entries
AGENTIC_PROFILE_MARKER="# agentic-config path"

# Write path to ~/.agents/.path
persist_to_dotpath() {
  local install_path="$1"
  local dotpath_dir="$HOME/.agents"
  local dotpath_file="$dotpath_dir/.path"

  # Create directory if needed
  if [[ ! -d "$dotpath_dir" ]]; then
    mkdir -p "$dotpath_dir" || {
      echo "WARNING: Could not create $dotpath_dir" >&2
      return 1
    }
  fi

  # Write absolute path
  echo "$install_path" > "$dotpath_file" || {
    echo "WARNING: Could not write to $dotpath_file" >&2
    return 1
  }

  return 0
}

# Add export to shell profile (idempotent)
persist_to_shell_profile() {
  local install_path="$1"
  local profile=""

  # Detect shell and choose profile
  case "${SHELL:-}" in
    */zsh)  profile="$HOME/.zshrc" ;;
    */bash) profile="$HOME/.bashrc" ;;
    *)
      # Try zsh first (common on macOS), then bash
      if [[ -f "$HOME/.zshrc" ]]; then
        profile="$HOME/.zshrc"
      elif [[ -f "$HOME/.bashrc" ]]; then
        profile="$HOME/.bashrc"
      else
        echo "WARNING: Could not detect shell profile" >&2
        return 1
      fi
      ;;
  esac

  # Check if already present (idempotent)
  if grep -q "$AGENTIC_PROFILE_MARKER" "$profile" 2>/dev/null; then
    # Update existing entry if path changed
    local current_path
    current_path=$(grep "export AGENTIC_CONFIG_PATH=" "$profile" 2>/dev/null | sed 's/.*="\([^"]*\)".*/\1/')
    if [[ "$current_path" != "$install_path" ]]; then
      # Remove old entry and add new one
      local temp_file
      temp_file=$(mktemp)
      grep -v "$AGENTIC_PROFILE_MARKER" "$profile" | grep -v "export AGENTIC_CONFIG_PATH=" > "$temp_file"
      cat "$temp_file" > "$profile"
      rm -f "$temp_file"
    else
      return 0  # Already correct
    fi
  fi

  # Validate path contains only safe characters (prevent injection)
  if [[ ! "$install_path" =~ ^[a-zA-Z0-9_./-]+$ ]]; then
    echo "WARNING: Install path contains unsafe characters: $install_path" >&2
    echo "Skipping shell profile persistence for security" >&2
    return 1
  fi

  # Append to profile
  {
    echo ""
    echo "$AGENTIC_PROFILE_MARKER"
    echo "export AGENTIC_CONFIG_PATH=\"$install_path\""
  } >> "$profile" || {
    echo "WARNING: Could not write to $profile" >&2
    return 1
  }

  return 0
}

# Write to XDG config (~/.config/agentic/config)
persist_to_xdg_config() {
  local install_path="$1"
  local xdg_dir="${XDG_CONFIG_HOME:-$HOME/.config}/agentic"
  local config_file="$xdg_dir/config"

  # Create directory if needed
  mkdir -p "$xdg_dir" || {
    echo "WARNING: Could not create $xdg_dir" >&2
    return 1
  }

  # Write config file
  echo "path=$install_path" > "$config_file" || {
    echo "WARNING: Could not write to $config_file" >&2
    return 1
  }

  return 0
}

# Persist to all locations
persist_agentic_path() {
  local install_path="$1"
  local errors=0

  persist_to_dotpath "$install_path" || ((errors++))
  persist_to_shell_profile "$install_path" || ((errors++))
  persist_to_xdg_config "$install_path" || ((errors++))

  return $errors
}

# Discover agentic path using priority order
discover_agentic_path() {
  # Priority 1: Environment variable
  if [[ -n "${AGENTIC_CONFIG_PATH:-}" ]] && [[ -d "$AGENTIC_CONFIG_PATH" ]]; then
    echo "$AGENTIC_CONFIG_PATH"
    return 0
  fi

  # Priority 2: ~/.agents/.path
  local dotpath="$HOME/.agents/.path"
  if [[ -f "$dotpath" ]]; then
    local path
    path=$(cat "$dotpath" 2>/dev/null)
    if [[ -n "$path" ]] && [[ -d "$path" ]]; then
      echo "$path"
      return 0
    fi
  fi

  # Priority 3: XDG config
  local xdg_config="${XDG_CONFIG_HOME:-$HOME/.config}/agentic/config"
  if [[ -f "$xdg_config" ]]; then
    local path
    path=$(grep '^path=' "$xdg_config" 2>/dev/null | cut -d= -f2)
    if [[ -n "$path" ]] && [[ -d "$path" ]]; then
      echo "$path"
      return 0
    fi
  fi

  # Priority 4: Default fallback
  local default_path="$HOME/.agents/agentic-config"
  if [[ -d "$default_path" ]]; then
    echo "$default_path"
    return 0
  fi

  # Nothing found
  return 1
}
