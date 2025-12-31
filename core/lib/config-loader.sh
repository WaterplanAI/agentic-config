#!/usr/bin/env bash
# Agentic Config Loader
# Loads configuration from multiple sources with priority:
#   1. Environment variables (highest)
#   2. .env file
#   3. .agentic-config.conf.yml file (lowest)
#
# NOTE: Uses pure bash (no external commands) for compatibility with
# restricted shell environments (e.g., Claude Code)

# Bootstrap: find agentic root using priority-based discovery
if [[ -z "${_AGENTIC_ROOT:-}" ]]; then
  # Use shared bootstrap pattern
  _agp=""
  [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path) 2>/dev/null || _agp=""
  AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
  unset _agp
  if [[ -d "$AGENTIC_GLOBAL" ]] && [[ -f "$AGENTIC_GLOBAL/VERSION" ]]; then
    _AGENTIC_ROOT="$AGENTIC_GLOBAL"
  else
    echo "ERROR: Cannot locate agentic-config installation" >&2
    return 1 2>/dev/null || exit 1
  fi
fi

# Always source agentic-root.sh if not already sourced
if ! declare -f get_project_root >/dev/null 2>&1; then
  source "$_AGENTIC_ROOT/core/lib/agentic-root.sh"
fi

# Parse YAML value (simple key: value format, pure bash - no grep/sed)
# Usage: _config_parse_yaml_value <file> <key>
_config_parse_yaml_value() {
  local file="$1"
  local key="$2"

  if [[ ! -f "$file" ]]; then
    return 1
  fi

  # Match "key: value" or "key: 'value'" or 'key: "value"'
  local line value
  while IFS= read -r line; do
    # Exact match: key followed by colon and space/tab/end (not substring)
    if [[ "$line" =~ ^[[:space:]]*"${key}":[[:space:]] ]] || [[ "$line" == "${key}:" ]]; then
      # Extract value after "key:"
      value="${line#*:}"
      # Trim leading whitespace
      value="${value#"${value%%[![:space:]]*}"}"
      # Remove surrounding quotes if present
      # Handle unbalanced quotes gracefully (check both start and end match)
      if [[ "$value" == \"*\" ]]; then
        # Double quotes - only strip if balanced
        value="${value:1:${#value}-2}"
      elif [[ "$value" == \'*\' ]]; then
        # Single quotes - only strip if balanced
        value="${value:1:${#value}-2}"
      # Unbalanced quotes: leave as-is (no stripping needed)
      # The value already has the quote prefix, which is intentional
      fi
      if [[ -n "$value" ]]; then
        echo "$value"
        return 0
      fi
    fi
  done < "$file"
  return 1
}

# Load configuration with priority: ENV > .env > .agentic-config.conf.yml
# Sets variables: EXT_SPECS_REPO_URL, EXT_SPECS_LOCAL_PATH
# Usage: load_agentic_config
#
# NOTE: Uses get_project_root() to find config files in the PROJECT directory,
# not get_agentic_root() which returns the GLOBAL installation path
load_agentic_config() {
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no .agentic-config.json, CLAUDE.md, or .git found)" >&2
    return 1
  }
  local env_file="$project_root/.env"
  local yaml_file="$project_root/.agentic-config.conf.yml"

  # Track original ENV values (highest priority)
  local env_repo_url="${EXT_SPECS_REPO_URL:-}"
  local env_local_path="${EXT_SPECS_LOCAL_PATH:-}"

  # Clear config vars to prevent state leaks across multi-project sessions
  unset EXT_SPECS_REPO_URL EXT_SPECS_LOCAL_PATH

  # Load from .agentic-config.conf.yml (lowest priority)
  if [[ -f "$yaml_file" ]]; then
    local yaml_repo_url yaml_local_path
    yaml_repo_url=$(_config_parse_yaml_value "$yaml_file" "ext_specs_repo_url") || true
    yaml_local_path=$(_config_parse_yaml_value "$yaml_file" "ext_specs_local_path") || true

    # Set from YAML if not already set
    [[ -z "${EXT_SPECS_REPO_URL:-}" ]] && [[ -n "$yaml_repo_url" ]] && export EXT_SPECS_REPO_URL="$yaml_repo_url"
    [[ -z "${EXT_SPECS_LOCAL_PATH:-}" ]] && [[ -n "$yaml_local_path" ]] && export EXT_SPECS_LOCAL_PATH="$yaml_local_path"
  fi

  # Load from .env (medium priority, overrides YAML)
  if [[ -f "$env_file" ]]; then
    # Safe .env parsing: validate KEY=VALUE patterns only
    # Only export known safe keys (scoped list)
    # CRITICAL: This prevents arbitrary environment pollution
    local -a KNOWN_SAFE_KEYS=(
      "EXT_SPECS_REPO_URL" "EXT_SPECS_LOCAL_PATH"
    )
    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
      # Skip comments and empty lines
      [[ "$line" =~ ^[[:space:]]*# ]] && continue
      [[ -z "${line// }" ]] && continue

      # Validate KEY=VALUE format (KEY must be valid identifier)
      if [[ "$line" =~ ^[a-zA-Z_][a-zA-Z0-9_]*= ]]; then
        key="${line%%=*}"
        value="${line#*=}"

        # Only export if key is in known safe list
        local is_safe=false
        for safe_key in "${KNOWN_SAFE_KEYS[@]}"; do
          if [[ "$key" == "$safe_key" ]]; then
            is_safe=true
            break
          fi
        done

        if [[ "$is_safe" == true ]]; then
          # Remove surrounding quotes if present (handle "value" or 'value')
          if [[ "$value" == "\""*"\"" ]] || [[ "$value" == "'"*"'" ]]; then
            value="${value:1:${#value}-2}"
          fi
          export "$key=$value"
        fi
      else
        # Log warning for invalid lines (fail-open: continue processing)
        echo "WARNING: Skipping invalid .env line: ${line:0:50}..." >&2
      fi
    done < "$env_file"
  fi

  # Restore original ENV values (highest priority)
  [[ -n "$env_repo_url" ]] && export EXT_SPECS_REPO_URL="$env_repo_url"
  [[ -n "$env_local_path" ]] && export EXT_SPECS_LOCAL_PATH="$env_local_path"

  return 0
}

# Get config value with priority resolution
# Usage: get_agentic_config <key>
# Example: get_agentic_config ext_specs_repo_url
#
# NOTE: Uses get_project_root() to find config files
get_agentic_config() {
  local key="$1"
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no .agentic-config.json, CLAUDE.md, or .git found)" >&2
    return 1
  }

  # Map key names to environment variable names
  local env_var
  case "$key" in
    ext_specs_repo_url) env_var="EXT_SPECS_REPO_URL" ;;
    ext_specs_local_path) env_var="EXT_SPECS_LOCAL_PATH" ;;
    *) env_var="${key^^}" ;; # Uppercase fallback
  esac

  # Priority 1: Environment variable
  local env_value="${!env_var:-}"
  if [[ -n "$env_value" ]]; then
    echo "$env_value"
    return 0
  fi

  # Priority 2: .env file (pure bash - no grep/cut/sed)
  local env_file="$project_root/.env"
  if [[ -f "$env_file" ]]; then
    local line dotenv_value
    while IFS= read -r line; do
      if [[ "$line" == "${env_var}="* ]]; then
        dotenv_value="${line#*=}"
        # Remove surrounding quotes if present
        if [[ "$dotenv_value" == \"*\" ]] || [[ "$dotenv_value" == \'*\' ]]; then
          dotenv_value="${dotenv_value:1:${#dotenv_value}-2}"
        fi
        if [[ -n "$dotenv_value" ]]; then
          echo "$dotenv_value"
          return 0
        fi
      fi
    done < "$env_file"
  fi

  # Priority 3: .agentic-config.conf.yml
  local yaml_file="$project_root/.agentic-config.conf.yml"
  if [[ -f "$yaml_file" ]]; then
    local yaml_value
    yaml_value=$(_config_parse_yaml_value "$yaml_file" "$key")
    if [[ -n "$yaml_value" ]]; then
      echo "$yaml_value"
      return 0
    fi
  fi

  return 1
}
