#!/usr/bin/env bash
# MCP (Model Context Protocol) Server Configuration Manager
# Handles installation and configuration of MCP servers across AI tools

# Discover available MCP server templates
# Returns: space-separated list of server names
discover_mcp_servers() {
  local servers=()
  local templates_dir="${REPO_ROOT:-$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")}/templates/mcp/servers"

  for f in "$templates_dir"/*.json; do
    [[ ! -f "$f" ]] && continue
    servers+=("$(basename "$f" .json)")
  done
  echo "${servers[*]}"
}

# Get MCP config file path for a specific tool
# Args: $1=tool (claude|gemini|codex|antigravity), $2=scope (global|project), $3=target_path (for project scope)
# Returns: path to config file
get_mcp_config_path() {
  local tool="$1"
  local scope="${2:-project}"
  local target_path="${3:-.}"

  case "$tool" in
    claude)
      if [[ "$scope" == "global" ]]; then
        echo "$HOME/.claude.json"
      else
        echo "$target_path/.mcp.json"
      fi
      ;;
    gemini)
      if [[ "$scope" == "global" ]]; then
        echo "$HOME/.gemini/settings.json"
      else
        echo "$target_path/.gemini/settings.json"
      fi
      ;;
    codex)
      # Codex only supports global config
      echo "$HOME/.codex/config.toml"
      ;;
    antigravity)
      # Antigravity only supports project config
      echo "$target_path/.antigravity/mcp.json"
      ;;
    *)
      echo "ERROR: Unknown tool: $tool" >&2
      return 1
      ;;
  esac
}

# Check if an MCP server is already configured for a tool
# Args: $1=server_name, $2=tool, $3=target_path
# Returns: 0 if configured, 1 if not
is_mcp_configured() {
  local server_name="$1"
  local tool="$2"
  local target_path="${3:-.}"
  local config_path

  # Determine scope based on tool
  local scope="project"
  [[ "$tool" == "codex" ]] && scope="global"

  config_path=$(get_mcp_config_path "$tool" "$scope" "$target_path")

  [[ ! -f "$config_path" ]] && return 1

  if [[ "$tool" == "codex" ]]; then
    # TOML format: check for [mcp_servers.<name>] section
    grep -q "^\[mcp_servers\.$server_name\]" "$config_path" 2>/dev/null
  else
    # JSON format: check for server in mcpServers object
    if command -v jq &>/dev/null; then
      jq -e ".mcpServers.\"$server_name\"" "$config_path" &>/dev/null
    else
      grep -q "\"$server_name\"" "$config_path" 2>/dev/null
    fi
  fi
}

# Read server definition from template
# Args: $1=server_name
# Returns: exports SERVER_* variables
_load_server_template() {
  local server_name="$1"
  local templates_dir="${REPO_ROOT:-$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")}/templates/mcp/servers"
  local template_file="$templates_dir/$server_name.json"

  if [[ ! -f "$template_file" ]]; then
    echo "ERROR: No template for server: $server_name" >&2
    return 1
  fi

  if command -v jq &>/dev/null; then
    SERVER_COMMAND=$(jq -r '.command' "$template_file")
    SERVER_ARGS=$(jq -r '.args | @json' "$template_file")
    SERVER_ENV=$(jq -r '.env | @json' "$template_file")
    SERVER_POST_INSTALL=$(jq -r '.post_install | @json' "$template_file")
    SERVER_DIRS=$(jq -r '.dirs_to_create | @json' "$template_file")
    SERVER_GITIGNORE=$(jq -r '.gitignore_entries | @json' "$template_file")
  else
    # Fallback: basic grep parsing (limited functionality)
    SERVER_COMMAND=$(grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' "$template_file" | cut -d'"' -f4)
    echo "WARNING: jq not available - MCP configuration will have limited functionality" >&2
    return 1
  fi

  return 0
}

# Install MCP server to JSON-based config (Claude, Gemini, Antigravity)
# Args: $1=server_name, $2=tool, $3=target_path, $4=dry_run
_install_json_mcp() {
  local server_name="$1"
  local tool="$2"
  local target_path="${3:-.}"
  local dry_run="${4:-false}"

  local scope="project"
  [[ "$tool" == "codex" ]] && scope="global"

  local config_path
  config_path=$(get_mcp_config_path "$tool" "$scope" "$target_path")

  # Load server template
  _load_server_template "$server_name" || return 1

  # Create parent directory if needed
  local config_dir
  config_dir=$(dirname "$config_path")
  if [[ ! -d "$config_dir" && "$config_dir" != "." ]]; then
    [[ "$dry_run" == true ]] && echo "   Would create: $config_dir" && return 0
    mkdir -p "$config_dir"
  fi

  # Backup existing config
  if [[ -f "$config_path" ]]; then
    local backup_path="$config_path.bak.$(date +%s)"
    [[ "$dry_run" == true ]] && echo "   Would backup: $config_path -> $backup_path"
    [[ "$dry_run" != true ]] && cp "$config_path" "$backup_path"
  fi

  if [[ "$dry_run" == true ]]; then
    echo "   Would add $server_name to $config_path"
    return 0
  fi

  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq required for JSON MCP configuration" >&2
    return 1
  fi

  # Build server config JSON
  local server_config
  server_config=$(jq -n \
    --arg cmd "$SERVER_COMMAND" \
    --argjson args "$SERVER_ARGS" \
    --argjson env "$SERVER_ENV" \
    '{command: $cmd, args: $args, env: $env}')

  if [[ ! -f "$config_path" ]]; then
    # Create new config
    jq -n --arg name "$server_name" --argjson config "$server_config" \
      '{mcpServers: {($name): $config}}' > "$config_path"
  else
    # Merge into existing config
    local temp_file
    temp_file=$(mktemp)
    jq --arg name "$server_name" --argjson config "$server_config" \
      '.mcpServers = (.mcpServers // {}) | .mcpServers[$name] = $config' \
      "$config_path" > "$temp_file" && mv "$temp_file" "$config_path"
  fi

  echo "   Configured $server_name for $tool at $config_path"
  return 0
}

# Install MCP server to TOML-based config (Codex)
# Args: $1=server_name, $2=target_path, $3=dry_run
_install_toml_mcp() {
  local server_name="$1"
  local target_path="${2:-.}"
  local dry_run="${3:-false}"

  local config_path
  config_path=$(get_mcp_config_path "codex" "global" "$target_path")

  # Load server template
  _load_server_template "$server_name" || return 1

  # Create parent directory if needed
  local config_dir
  config_dir=$(dirname "$config_path")
  if [[ ! -d "$config_dir" ]]; then
    [[ "$dry_run" == true ]] && echo "   Would create: $config_dir" && return 0
    mkdir -p "$config_dir"
  fi

  # Backup existing config
  if [[ -f "$config_path" ]]; then
    local backup_path="$config_path.bak.$(date +%s)"
    [[ "$dry_run" == true ]] && echo "   Would backup: $config_path -> $backup_path"
    [[ "$dry_run" != true ]] && cp "$config_path" "$backup_path"
  fi

  if [[ "$dry_run" == true ]]; then
    echo "   Would add $server_name to $config_path"
    return 0
  fi

  # Build TOML section using string operations (no TOML parser)
  # Convert JSON args array to TOML array format
  local args_toml
  if command -v jq &>/dev/null; then
    # Use jq to format args as TOML array
    args_toml=$(echo "$SERVER_ARGS" | jq -r 'map("\"" + . + "\"") | join(", ")')
  else
    echo "ERROR: jq required for TOML MCP configuration" >&2
    return 1
  fi

  local toml_section
  toml_section="
[mcp_servers.$server_name]
command = \"$SERVER_COMMAND\"
args = [$args_toml]
"

  if [[ ! -f "$config_path" ]]; then
    # Create new config
    echo "$toml_section" > "$config_path"
  else
    # Append to existing config
    echo "$toml_section" >> "$config_path"
  fi

  echo "   Configured $server_name for codex at $config_path"
  return 0
}

# Install MCP server for a specific tool
# Args: $1=server_name, $2=tool, $3=target_path, $4=dry_run
install_mcp_server() {
  local server_name="$1"
  local tool="$2"
  local target_path="${3:-.}"
  local dry_run="${4:-false}"

  # Check if already configured
  if is_mcp_configured "$server_name" "$tool" "$target_path"; then
    echo "   Skipping $server_name for $tool (already configured)"
    return 0
  fi

  if [[ "$tool" == "codex" ]]; then
    _install_toml_mcp "$server_name" "$target_path" "$dry_run"
  else
    _install_json_mcp "$server_name" "$tool" "$target_path" "$dry_run"
  fi
}

# Run post-install steps for an MCP server
# Args: $1=server_name, $2=target_path, $3=dry_run
run_mcp_post_install() {
  local server_name="$1"
  local target_path="${2:-.}"
  local dry_run="${3:-false}"

  _load_server_template "$server_name" || return 1

  # Create directories
  if [[ -n "$SERVER_DIRS" && "$SERVER_DIRS" != "null" ]]; then
    if command -v jq &>/dev/null; then
      local dirs
      dirs=$(echo "$SERVER_DIRS" | jq -r '.[]')
      while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        local full_path="$target_path/$dir"
        if [[ ! -d "$full_path" ]]; then
          if [[ "$dry_run" == true ]]; then
            echo "   Would create directory: $full_path"
          else
            mkdir -p "$full_path"
            echo "   Created directory: $full_path"
          fi
        fi
      done <<< "$dirs"
    fi
  fi

  # Add gitignore entries
  if [[ -n "$SERVER_GITIGNORE" && "$SERVER_GITIGNORE" != "null" ]]; then
    local gitignore_file="$target_path/.gitignore"
    if command -v jq &>/dev/null; then
      local entries
      entries=$(echo "$SERVER_GITIGNORE" | jq -r '.[]')
      while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        if [[ ! -f "$gitignore_file" ]] || ! grep -qF "$entry" "$gitignore_file" 2>/dev/null; then
          if [[ "$dry_run" == true ]]; then
            echo "   Would add to .gitignore: $entry"
          else
            echo "$entry" >> "$gitignore_file"
            echo "   Added to .gitignore: $entry"
          fi
        fi
      done <<< "$entries"
    fi
  fi

  # Run post-install commands (only if not dry-run)
  if [[ -n "$SERVER_POST_INSTALL" && "$SERVER_POST_INSTALL" != "null" && "$dry_run" != true ]]; then
    if command -v jq &>/dev/null; then
      echo "   Running post-install commands..."
      local cmds
      cmds=$(echo "$SERVER_POST_INSTALL" | jq -r '.[]')
      while IFS= read -r cmd; do
        [[ -z "$cmd" ]] && continue
        echo "   > $cmd"
        (cd "$target_path" && eval "$cmd") || {
          echo "   WARNING: Post-install command failed: $cmd" >&2
        }
      done <<< "$cmds"
    fi
  elif [[ "$dry_run" == true && -n "$SERVER_POST_INSTALL" && "$SERVER_POST_INSTALL" != "null" ]]; then
    echo "   Would run post-install commands (skipped in dry-run)"
  fi

  return 0
}

# Install MCP servers for selected tools
# Args: $1=servers (comma-separated), $2=tools (comma-separated or "all"), $3=target_path, $4=dry_run
install_mcp_for_tools() {
  local servers="$1"
  local tools="$2"
  local target_path="${3:-.}"
  local dry_run="${4:-false}"

  # Parse servers list
  local server_list
  IFS=',' read -ra server_list <<< "$servers"

  # Determine tool list
  local tool_list
  if [[ "$tools" == "all" ]]; then
    tool_list=("claude" "gemini" "codex" "antigravity")
  else
    IFS=',' read -ra tool_list <<< "$tools"
  fi

  echo "Installing MCP servers: ${server_list[*]}"
  [[ "$dry_run" == true ]] && echo "   (DRY RUN - no changes will be made)"

  for server in "${server_list[@]}"; do
    echo "   Processing $server..."
    for tool in "${tool_list[@]}"; do
      install_mcp_server "$server" "$tool" "$target_path" "$dry_run"
    done
    run_mcp_post_install "$server" "$target_path" "$dry_run"
  done

  echo "MCP installation complete"
}
