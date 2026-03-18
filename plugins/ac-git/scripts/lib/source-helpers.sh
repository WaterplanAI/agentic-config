#!/usr/bin/env bash
# Shared bootstrap helpers for ac-git plugin scripts
# Provides CLAUDE_PLUGIN_ROOT resolution and config-loader sourcing
#
# Usage (from scripts/ directory):
#   # shellcheck source=lib/source-helpers.sh
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/source-helpers.sh"

# Bootstrap CLAUDE_PLUGIN_ROOT if not set
# Resolves from this file's location: scripts/lib/ -> ../../ = plugin root
if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  _sh_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  CLAUDE_PLUGIN_ROOT="$(cd "$_sh_dir/../.." && pwd)"
  unset _sh_dir
fi

# Source shared config loader
# Tries CLAUDE_PLUGIN_ROOT first, then falls back to locating via BASH_SOURCE
_source_config_loader() {
  # Already loaded -- skip
  if declare -f load_agentic_config >/dev/null 2>&1; then
    return 0
  fi

  local config_loader="${CLAUDE_PLUGIN_ROOT}/scripts/lib/config-loader.sh"

  # Fallback: resolve relative to BASH_SOURCE entries
  # Checks both lib/config-loader.sh (for callers in scripts/) and
  # config-loader.sh (for this file in scripts/lib/)
  if [[ ! -f "$config_loader" ]]; then
    local script_dir candidate
    for candidate in "${BASH_SOURCE[@]}"; do
      script_dir="$(cd "$(dirname "$candidate")" && pwd 2>/dev/null)" || continue
      if [[ -f "$script_dir/lib/config-loader.sh" ]]; then
        config_loader="$script_dir/lib/config-loader.sh"
        echo "WARNING: CLAUDE_PLUGIN_ROOT fallback activated; resolved to $(cd "$script_dir/.." && pwd)" >&2
        CLAUDE_PLUGIN_ROOT="$(cd "$script_dir/.." && pwd)"
        break
      elif [[ -f "$script_dir/config-loader.sh" ]]; then
        config_loader="$script_dir/config-loader.sh"
        echo "WARNING: CLAUDE_PLUGIN_ROOT fallback activated; resolved to $(cd "$script_dir/../.." && pwd)" >&2
        CLAUDE_PLUGIN_ROOT="$(cd "$script_dir/../.." && pwd)"
        break
      fi
    done
  fi

  if [[ -f "$config_loader" ]]; then
    # shellcheck source=config-loader.sh
    source "$config_loader"
  else
    echo "ERROR: config-loader.sh not found" >&2
    echo "  Searched: ${CLAUDE_PLUGIN_ROOT}/scripts/lib/config-loader.sh" >&2
    echo "  Set CLAUDE_PLUGIN_ROOT to the ac-git plugin directory" >&2
    return 1
  fi
}
