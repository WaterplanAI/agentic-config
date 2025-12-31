#!/usr/bin/env bash
# Agentic Config Root Discovery
# Provides two key functions:
#   - get_agentic_root(): GLOBAL agentic-config installation (where scripts/libs live)
#   - get_project_root(): PROJECT root (where .agentic-config.json, .env live)
#
# NOTE: Uses pure bash (no external commands like cut, dirname, grep) for
# compatibility with restricted shell environments (e.g., Claude Code)

# Priority-based discovery for GLOBAL installation:
# 1. $AGENTIC_CONFIG_PATH environment variable
# 2. ~/.agents/.path file
# 3. ~/.config/agentic/config (XDG)
# 4. .agentic-config.json in current project (agentic_global_path)
# 5. PWD traversal for VERSION + core/ markers
# 6. Default fallback: $HOME/.agents/agentic-config

# Discover from persisted locations (no PWD traversal)
_discover_from_persistence() {
  # Priority 1: Environment variable
  if [[ -n "${AGENTIC_CONFIG_PATH:-}" ]] && [[ -d "$AGENTIC_CONFIG_PATH" ]]; then
    echo "$AGENTIC_CONFIG_PATH"
    return 0
  fi

  # Priority 2: ~/.agents/.path
  if [[ -f "$HOME/.agents/.path" ]]; then
    local path
    path=$(<"$HOME/.agents/.path") 2>/dev/null || path=""
    if [[ -n "$path" ]] && [[ -d "$path" ]]; then
      echo "$path"
      return 0
    fi
  fi

  # Priority 3: XDG config (pure bash - no cut)
  local xdg_config="${XDG_CONFIG_HOME:-$HOME/.config}/agentic/config"
  if [[ -f "$xdg_config" ]]; then
    local line path
    while IFS= read -r line; do
      if [[ "$line" == path=* ]]; then
        path="${line#path=}"
        if [[ -n "$path" ]] && [[ -d "$path" ]]; then
          echo "$path"
          return 0
        fi
      fi
    done < "$xdg_config"
  fi

  # Priority 4: Project-local .agentic-config.json (pure bash - no jq/cut)
  if [[ -f ".agentic-config.json" ]]; then
    local line path
    while IFS= read -r line; do
      if [[ "$line" == *'"agentic_global_path"'* ]]; then
        # Extract value between quotes after the colon
        path="${line#*:}"           # Remove everything before :
        path="${path#*\"}"          # Remove up to first quote
        path="${path%%\"*}"         # Remove from next quote onward
        if [[ -n "$path" ]] && [[ -d "$path" ]]; then
          echo "$path"
          return 0
        fi
      fi
    done < ".agentic-config.json"
  fi

  return 1
}

get_agentic_root() {
  # Try persisted locations first
  local persisted_path
  if persisted_path=$(_discover_from_persistence); then
    echo "$persisted_path"
    return 0
  fi

  # Fallback: PWD traversal (pure bash - no dirname)
  local current_dir="$PWD"
  local max_depth=10
  local depth=0

  # Walk up directory tree looking for VERSION marker
  while [[ "$depth" -lt "$max_depth" ]]; do
    if [[ -f "$current_dir/VERSION" ]] && [[ -d "$current_dir/core" ]]; then
      echo "$current_dir"
      return 0
    fi

    # Move up one directory (pure bash dirname equivalent)
    local parent_dir="${current_dir%/*}"
    [[ -z "$parent_dir" ]] && parent_dir="/"
    if [[ "$parent_dir" == "$current_dir" ]]; then
      break  # Reached filesystem root
    fi
    current_dir="$parent_dir"
    ((depth++)) || true
  done

  # Fallback 1: git repo root (git command may not be available, so handle gracefully)
  local git_root=""
  git_root="$(git rev-parse --show-toplevel 2>/dev/null)" || true
  if [[ -n "$git_root" ]] && [[ -f "$git_root/VERSION" ]]; then
    echo "$git_root"
    return 0
  fi

  # Final fallback: default location
  local default_path="$HOME/.agents/agentic-config"
  if [[ -d "$default_path" ]]; then
    echo "$default_path"
    return 0
  fi

  return 1
}

# Get PROJECT root (where .agentic-config.json and .env live)
# This is DIFFERENT from get_agentic_root() which returns the GLOBAL installation
#
# Priority:
# 1. PWD traversal for project markers (.agentic-config.json, CLAUDE.md, .git)
# 2. Git repository root (fallback)
#
# Returns: 0 if found, 1 if no markers found
get_project_root() {
  # Priority 1: Walk up from CWD looking for project markers
  local current_dir="$PWD"
  local max_depth=10
  local depth=0

  while [[ "$depth" -lt "$max_depth" ]]; do
    # Check for any project marker
    if [[ -f "$current_dir/.agentic-config.json" ]] || \
       [[ -f "$current_dir/CLAUDE.md" ]] || \
       [[ -d "$current_dir/.git" ]]; then
      echo "$current_dir"
      return 0
    fi

    # Move up one directory (pure bash dirname equivalent)
    local parent_dir="${current_dir%/*}"
    [[ -z "$parent_dir" ]] && parent_dir="/"
    if [[ "$parent_dir" == "$current_dir" ]]; then
      break  # Reached filesystem root
    fi
    current_dir="$parent_dir"
    ((depth++)) || true
  done

  # No markers found - return failure
  return 1
}

# Cross-platform file locking using mkdir atomicity
# Usage: _acquire_lock <lockdir> [timeout_seconds]
# Returns: 0 on success, 1 on timeout
_acquire_lock() {
  local lockdir="$1"
  local timeout="${2:-30}"
  local waited=0

  while ! mkdir "$lockdir" 2>/dev/null; do
    if [[ $waited -ge $timeout ]]; then
      echo "ERROR: Could not acquire lock (timeout after ${timeout}s)" >&2
      return 1
    fi
    sleep 1
    ((waited++)) || true
  done

  return 0
}

# Release file lock
# Usage: _release_lock <lockdir>
_release_lock() {
  local lockdir="$1"
  rmdir "$lockdir" 2>/dev/null || true
}

# Compare two semantic versions (pure bash, cross-platform)
# Usage: compare_versions <v1> <v2>
# Returns: 0 if v1 == v2, 1 if v1 > v2, 2 if v1 < v2
#
# Examples:
#   compare_versions "1.10.0" "1.2.0"  # returns 1 (1.10.0 > 1.2.0)
#   compare_versions "1.0" "1.0.0"     # returns 0 (equal, pads with zeros)
compare_versions() {
  local v1="$1" v2="$2"
  [[ "$v1" == "$v2" ]] && return 0

  # Split into arrays
  IFS='.' read -ra V1_PARTS <<< "$v1"
  IFS='.' read -ra V2_PARTS <<< "$v2"

  # Pad shorter version with zeros
  local max_len=${#V1_PARTS[@]}
  [[ ${#V2_PARTS[@]} -gt $max_len ]] && max_len=${#V2_PARTS[@]}

  for ((i=0; i<max_len; i++)); do
    local n1=${V1_PARTS[i]:-0}
    local n2=${V2_PARTS[i]:-0}
    ((n1 > n2)) && return 1  # v1 > v2
    ((n1 < n2)) && return 2  # v1 < v2
  done
  return 0  # equal
}
