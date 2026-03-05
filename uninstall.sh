#!/usr/bin/env bash
# Agentic-Config legacy uninstall script (v0.1.x symlink mechanism)
set -euo pipefail

DRY_RUN=false
YES=false
VERBOSE=false
MODE=""
PROJECT_PATH=""
GLOBAL_PATH_OVERRIDE=""
GLOBAL_PATH_SOURCE=""

METADATA_FILE=""
METADATA_GLOBAL_PATH=""
METADATA_SYMLINKS=()
METADATA_COPIED=()

REMOVED_SYMLINKS=0
REMOVED_PATH_ENTRIES=0
REMOVED_CLAUDE_BLOCKS=0
REMOVED_REPO_DIR=0
SKIPPED_ITEMS=0

if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' NC=''
fi

usage() {
  cat <<'EOF'
Usage:
  uninstall.sh --global [--dry-run] [--yes] [--verbose] [--global-path <path>]
  uninstall.sh --project [path] [--dry-run] [--yes] [--verbose] [--global-path <path>]

Modes:
  --global              Reverse legacy global wiring from v0.1.x install:
                        - ~/.claude/commands/agentic*.md symlinks
                        - '## Agentic-Config Global' section in ~/.claude/CLAUDE.md
                        - persisted AGENTIC_CONFIG_PATH entries
                        Prompts to remove cloned global repo directory (default yes).

  --project [path]      Remove only project symlinks that point to the legacy global path.
                        Default path is current directory.

Safety policy:
  - Project mode is symlink-only.
  - Never touches AGENTS.md, PROJECT_AGENTS.md, or copied files.

Options:
  --global-path <path>  Override discovered global agentic-config path
  --dry-run             Print planned actions without changing files
  --yes                 Non-interactive confirmations (accept defaults)
  --verbose             Show skipped paths/details
  -h, --help            Show this help message
EOF
}

abort() {
  printf "${RED}ERROR:${NC} %s\n" "$1" >&2
  exit 1
}

info() {
  printf "${BLUE}==>${NC} %s\n" "$1"
}

warn() {
  printf "${YELLOW}==>${NC} %s\n" "$1"
}

success() {
  printf "${GREEN}==>${NC} %s\n" "$1"
}

strip_quotes_and_trim() {
  local value="$1"

  # Trim leading whitespace
  value="${value#"${value%%[![:space:]]*}"}"
  # Trim trailing whitespace
  value="${value%"${value##*[![:space:]]}"}"

  if [[ ${#value} -ge 2 && "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
    value="${value:1:${#value}-2}"
  elif [[ ${#value} -ge 2 && "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
    value="${value:1:${#value}-2}"
  fi

  printf '%s' "$value"
}

normalize_path() {
  local raw_path="${1:-}"
  local base_dir="${2:-}"
  [[ -n "$raw_path" ]] || return 1

  python3 - "$raw_path" "$base_dir" <<'PY'
import os
import sys

raw = sys.argv[1]
base = sys.argv[2]

expanded = os.path.expandvars(os.path.expanduser(raw))
if not os.path.isabs(expanded):
    if base:
        expanded = os.path.join(base, expanded)
    else:
        expanded = os.path.abspath(expanded)

print(os.path.realpath(expanded))
PY
}

paths_equivalent() {
  local path_a="${1:-}"
  local path_b="${2:-}"

  [[ -n "$path_a" && -n "$path_b" ]] || return 1

  local norm_a=""
  local norm_b=""
  norm_a="$(normalize_path "$path_a" "" 2>/dev/null || true)"
  norm_b="$(normalize_path "$path_b" "" 2>/dev/null || true)"

  [[ -n "$norm_a" && -n "$norm_b" && "$norm_a" == "$norm_b" ]]
}

is_within_path() {
  local child="${1%/}"
  local parent="${2%/}"

  [[ -n "$child" && -n "$parent" ]] || return 1
  [[ "$parent" == "/" ]] && return 0

  [[ "$child" == "$parent" || "$child" == "$parent/"* ]]
}

run_remove_file() {
  local path="$1"
  local context="$2"

  if $DRY_RUN; then
    info "[dry-run] Would remove: $path ($context)"
    return 0
  fi

  rm -f "$path"
  info "Removed: $path ($context)"
}

run_remove_dir() {
  local path="$1"
  local context="$2"

  if $DRY_RUN; then
    info "[dry-run] Would remove directory: $path ($context)"
    return 0
  fi

  rm -rf "$path"
  info "Removed directory: $path ($context)"
}

confirm_default_yes() {
  local prompt="$1"

  if $YES; then
    return 0
  fi

  if [[ ! -t 0 ]]; then
    warn "No interactive terminal detected. Skipping deletion prompt (use --yes to approve non-interactively)."
    return 1
  fi

  local response=""
  read -r -p "$prompt [Y/n] " response
  case "$response" in
    ""|y|Y|yes|YES|Yes)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

metadata_add_inline_list() {
  local list_raw="$1"
  local list_name="$2"

  local content="$list_raw"
  content="${content#[}"
  content="${content%]}"

  local old_ifs="$IFS"
  IFS=','
  # shellcheck disable=SC2206
  local parts=($content)
  IFS="$old_ifs"

  local item
  for item in "${parts[@]}"; do
    item="$(strip_quotes_and_trim "$item")"
    [[ -n "$item" ]] || continue
    if [[ "$list_name" == "symlinks" ]]; then
      METADATA_SYMLINKS+=("$item")
    else
      METADATA_COPIED+=("$item")
    fi
  done
}

parse_json_metadata() {
  local file="$1"
  local parsed=""

  parsed="$(python3 - "$file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

global_path = data.get("agentic_global_path")
if isinstance(global_path, str) and global_path:
    print(f"GLOBAL\t{global_path}")

for item in data.get("symlinks", []):
    if isinstance(item, str) and item:
        print(f"SYMLINK\t{item}")

for item in data.get("copied", []):
    if isinstance(item, str) and item:
        print(f"COPIED\t{item}")
PY
)" || return 1

  local kind=""
  local value=""
  while IFS=$'\t' read -r kind value || [[ -n "$kind" ]]; do
    case "$kind" in
      GLOBAL)
        METADATA_GLOBAL_PATH="$value"
        ;;
      SYMLINK)
        METADATA_SYMLINKS+=("$value")
        ;;
      COPIED)
        METADATA_COPIED+=("$value")
        ;;
    esac
  done <<< "$parsed"

  return 0
}

parse_yaml_metadata() {
  local file="$1"
  local section=""

  while IFS= read -r line || [[ -n "$line" ]]; do
    local stripped="$line"
    stripped="${stripped%%#*}"
    stripped="${stripped%"${stripped##*[![:space:]]}"}"

    [[ -n "${stripped//[[:space:]]/}" ]] || continue

    if [[ "$stripped" =~ ^[[:space:]]*agentic_global_path:[[:space:]]*(.*)$ ]]; then
      METADATA_GLOBAL_PATH="$(strip_quotes_and_trim "${BASH_REMATCH[1]}")"
      section=""
      continue
    fi

    if [[ "$stripped" =~ ^[[:space:]]*symlinks:[[:space:]]*(.*)$ ]]; then
      section="symlinks"
      local rest=""
      rest="$(strip_quotes_and_trim "${BASH_REMATCH[1]}")"
      if [[ "$rest" == \[*\] ]]; then
        metadata_add_inline_list "$rest" "symlinks"
        section=""
      fi
      continue
    fi

    if [[ "$stripped" =~ ^[[:space:]]*copied:[[:space:]]*(.*)$ ]]; then
      section="copied"
      local rest=""
      rest="$(strip_quotes_and_trim "${BASH_REMATCH[1]}")"
      if [[ "$rest" == \[*\] ]]; then
        metadata_add_inline_list "$rest" "copied"
        section=""
      fi
      continue
    fi

    if [[ "$stripped" =~ ^[[:space:]]*-[[:space:]]*(.*)$ ]]; then
      local item=""
      item="$(strip_quotes_and_trim "${BASH_REMATCH[1]}")"
      [[ -n "$item" ]] || continue

      if [[ "$section" == "symlinks" ]]; then
        METADATA_SYMLINKS+=("$item")
      elif [[ "$section" == "copied" ]]; then
        METADATA_COPIED+=("$item")
      fi
      continue
    fi

    if [[ "$stripped" =~ ^[^[:space:]].*:[[:space:]]* ]]; then
      section=""
    fi
  done < "$file"

  return 0
}

load_project_metadata() {
  local project_root="$1"

  METADATA_FILE=""
  METADATA_GLOBAL_PATH=""
  METADATA_SYMLINKS=()
  METADATA_COPIED=()

  local json_file="$project_root/.agentic-config.json"
  local yaml_file="$project_root/.agentic-config.yaml"
  local yml_file="$project_root/.agentic-config.yml"
  local conf_yml_file="$project_root/.agentic-config.conf.yml"

  if [[ -f "$json_file" ]]; then
    parse_json_metadata "$json_file" || abort "Failed to parse metadata: $json_file"
    METADATA_FILE="$json_file"
    return 0
  fi

  if [[ -f "$yaml_file" ]]; then
    parse_yaml_metadata "$yaml_file" || abort "Failed to parse metadata: $yaml_file"
    METADATA_FILE="$yaml_file"
    return 0
  fi

  if [[ -f "$yml_file" ]]; then
    parse_yaml_metadata "$yml_file" || abort "Failed to parse metadata: $yml_file"
    METADATA_FILE="$yml_file"
    return 0
  fi

  # Accept legacy conf file if users stored uninstall metadata there.
  if [[ -f "$conf_yml_file" ]]; then
    parse_yaml_metadata "$conf_yml_file" || abort "Failed to parse metadata: $conf_yml_file"
    METADATA_FILE="$conf_yml_file"
    return 0
  fi

  return 1
}

discover_global_path() {
  local context="$1"       # project|global
  local project_root="$2"  # optional

  GLOBAL_PATH_SOURCE=""

  if [[ -n "$GLOBAL_PATH_OVERRIDE" ]]; then
    normalize_path "$GLOBAL_PATH_OVERRIDE" "$project_root"
    GLOBAL_PATH_SOURCE="--global-path"
    return 0
  fi

  if [[ "$context" == "project" && -n "$METADATA_GLOBAL_PATH" ]]; then
    normalize_path "$METADATA_GLOBAL_PATH" "$project_root"
    GLOBAL_PATH_SOURCE="metadata"
    return 0
  fi

  if [[ -f "$HOME/.agents/.path" ]]; then
    local dot_path=""
    dot_path="$(<"$HOME/.agents/.path")"
    dot_path="$(strip_quotes_and_trim "$dot_path")"
    if [[ -n "$dot_path" ]]; then
      normalize_path "$dot_path" "$project_root"
      GLOBAL_PATH_SOURCE="$HOME/.agents/.path"
      return 0
    fi
  fi

  local xdg_config_file="${XDG_CONFIG_HOME:-$HOME/.config}/agentic/config"
  if [[ -f "$xdg_config_file" ]]; then
    local line=""
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$line" == path=* ]]; then
        local xdg_path="${line#path=}"
        xdg_path="$(strip_quotes_and_trim "$xdg_path")"
        if [[ -n "$xdg_path" ]]; then
          normalize_path "$xdg_path" "$project_root"
          GLOBAL_PATH_SOURCE="XDG config"
          return 0
        fi
      fi
    done < "$xdg_config_file"
  fi

  if [[ -n "${AGENTIC_CONFIG_PATH:-}" ]]; then
    normalize_path "$AGENTIC_CONFIG_PATH" "$project_root"
    GLOBAL_PATH_SOURCE="AGENTIC_CONFIG_PATH"
    return 0
  fi

  normalize_path "$HOME/.agents/agentic-config" "$project_root"
  GLOBAL_PATH_SOURCE="default (~/.agents/agentic-config)"
  return 0
}

resolve_link_target() {
  local link_path="$1"
  local raw_target=""

  raw_target="$(readlink "$link_path" 2>/dev/null || true)"
  [[ -n "$raw_target" ]] || return 1

  if [[ "$raw_target" == /* ]]; then
    normalize_path "$raw_target" ""
  else
    normalize_path "$(dirname "$link_path")/$raw_target" ""
  fi
}

link_points_to_global() {
  local link_path="$1"
  local resolved_global="$2"

  [[ -L "$link_path" ]] || return 1

  local resolved_target=""
  resolved_target="$(resolve_link_target "$link_path" 2>/dev/null || true)"
  [[ -n "$resolved_target" ]] || return 1

  is_within_path "$resolved_target" "$resolved_global"
}

collect_pattern_candidates() {
  local project_root="$1"
  local pattern="$2"
  local output_file="$3"

  local full_pattern=""
  if [[ "$pattern" == /* ]]; then
    full_pattern="$pattern"
  else
    full_pattern="$project_root/$pattern"
  fi

  if [[ "$full_pattern" == *"*"* || "$full_pattern" == *"?"* || "$full_pattern" == *"["* ]]; then
    shopt -s nullglob
    # shellcheck disable=SC2206
    local matches=( $full_pattern )
    shopt -u nullglob

    local match=""
    for match in "${matches[@]}"; do
      printf '%s\n' "$match" >> "$output_file"
    done
    return 0
  fi

  if [[ -e "$full_pattern" || -L "$full_pattern" ]]; then
    printf '%s\n' "$full_pattern" >> "$output_file"
  fi
}

collect_project_symlink_candidates() {
  local project_root="$1"
  local output_file="$2"

  local pattern=""
  for pattern in "${METADATA_SYMLINKS[@]}"; do
    collect_pattern_candidates "$project_root" "$pattern" "$output_file"
  done

  local root=""
  for root in agents .agent .claude .gemini .codex; do
    local target="$project_root/$root"
    [[ -e "$target" || -L "$target" ]] || continue

    if [[ -L "$target" ]]; then
      printf '%s\n' "$target" >> "$output_file"
      continue
    fi

    if [[ -d "$target" ]]; then
      find "$target" -type l -print >> "$output_file"
    fi
  done
}

remove_marker_section_from_claude_md() {
  local file="$1"
  local marker="$2"

  [[ -f "$file" ]] || return 0

  if [[ -L "$file" ]]; then
    warn "Skipping marker cleanup for symlinked file: $file"
    ((SKIPPED_ITEMS++)) || true
    return 0
  fi

  local tmp_file=""
  tmp_file="$(mktemp)"

  awk -v marker="$marker" '
BEGIN { skip = 0 }
{
  if ($0 == marker) {
    skip = 1
    next
  }

  if (skip && $0 ~ /^## /) {
    skip = 0
  }

  if (!skip) {
    print
  }
}
' "$file" > "$tmp_file"

  if cmp -s "$file" "$tmp_file"; then
    rm -f "$tmp_file"
    return 0
  fi

  if $DRY_RUN; then
    info "[dry-run] Would remove marker section '$marker' from $file"
    rm -f "$tmp_file"
    return 0
  fi

  mv "$tmp_file" "$file"
  ((REMOVED_CLAUDE_BLOCKS++)) || true
  info "Removed marker section '$marker' from $file"
}

cleanup_dotpath_file() {
  local resolved_global="$1"
  local dotpath_file="$HOME/.agents/.path"

  [[ -f "$dotpath_file" ]] || return 0

  local current=""
  current="$(<"$dotpath_file")"
  current="$(strip_quotes_and_trim "$current")"

  if [[ -n "$current" ]] && paths_equivalent "$current" "$resolved_global"; then
    run_remove_file "$dotpath_file" "path persistence"
    ((REMOVED_PATH_ENTRIES++)) || true
  elif $VERBOSE; then
    info "Skipping ~/.agents/.path (points to different path)"
  fi
}

cleanup_shell_profile_file() {
  local profile_file="$1"
  local resolved_global="$2"
  local marker="# agentic-config path"

  [[ -f "$profile_file" ]] || return 0

  local tmp_file=""
  tmp_file="$(mktemp)"

  local changed=0
  local drop_next_export=0
  local line=""

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$marker" ]]; then
      changed=1
      drop_next_export=1
      continue
    fi

    if [[ "$drop_next_export" -eq 1 ]]; then
      if [[ "$line" =~ ^[[:space:]]*export[[:space:]]+AGENTIC_CONFIG_PATH= ]]; then
        changed=1
        drop_next_export=0
        continue
      fi
      drop_next_export=0
    fi

    if [[ "$line" =~ ^[[:space:]]*export[[:space:]]+AGENTIC_CONFIG_PATH=(.*)$ ]]; then
      local raw_value=""
      raw_value="${BASH_REMATCH[1]}"
      raw_value="${raw_value%%#*}"
      raw_value="$(strip_quotes_and_trim "$raw_value")"

      if [[ -n "$raw_value" ]] && paths_equivalent "$raw_value" "$resolved_global"; then
        changed=1
        continue
      fi
    fi

    printf '%s\n' "$line" >> "$tmp_file"
  done < "$profile_file"

  if [[ "$changed" -eq 0 ]]; then
    rm -f "$tmp_file"
    return 0
  fi

  if $DRY_RUN; then
    info "[dry-run] Would clean AGENTIC_CONFIG_PATH entries from $profile_file"
    rm -f "$tmp_file"
    return 0
  fi

  mv "$tmp_file" "$profile_file"
  ((REMOVED_PATH_ENTRIES++)) || true
  info "Cleaned AGENTIC_CONFIG_PATH entries from $profile_file"
}

cleanup_shell_profiles() {
  local resolved_global="$1"

  cleanup_shell_profile_file "$HOME/.zshrc" "$resolved_global"
  cleanup_shell_profile_file "$HOME/.bashrc" "$resolved_global"
  cleanup_shell_profile_file "$HOME/.bash_profile" "$resolved_global"
}

cleanup_xdg_config_file() {
  local resolved_global="$1"
  local xdg_config_file="${XDG_CONFIG_HOME:-$HOME/.config}/agentic/config"

  [[ -f "$xdg_config_file" ]] || return 0

  local tmp_file=""
  tmp_file="$(mktemp)"

  local changed=0
  local line=""

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == path=* ]]; then
      local value="${line#path=}"
      value="$(strip_quotes_and_trim "$value")"
      if [[ -n "$value" ]] && paths_equivalent "$value" "$resolved_global"; then
        changed=1
        continue
      fi
    fi

    printf '%s\n' "$line" >> "$tmp_file"
  done < "$xdg_config_file"

  if [[ "$changed" -eq 0 ]]; then
    rm -f "$tmp_file"
    return 0
  fi

  if $DRY_RUN; then
    info "[dry-run] Would clean matching path entry from $xdg_config_file"
    rm -f "$tmp_file"
    return 0
  fi

  if [[ ! -s "$tmp_file" ]]; then
    rm -f "$tmp_file"
    rm -f "$xdg_config_file"
    info "Removed empty XDG config: $xdg_config_file"
  else
    mv "$tmp_file" "$xdg_config_file"
    info "Cleaned matching path entry from $xdg_config_file"
  fi

  ((REMOVED_PATH_ENTRIES++)) || true
}

is_safe_delete_target() {
  local candidate="$1"
  local resolved=""

  resolved="$(normalize_path "$candidate" "" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || return 1

  if [[ "$resolved" == "/" || "$resolved" == "$HOME" ]]; then
    return 1
  fi

  local pwd_resolved=""
  pwd_resolved="$(normalize_path "$PWD" "" 2>/dev/null || true)"

  # Never delete a path containing current working directory.
  if [[ -n "$pwd_resolved" ]] && is_within_path "$pwd_resolved" "$resolved"; then
    return 1
  fi

  return 0
}

run_project_uninstall() {
  local target_path="$1"
  [[ -d "$target_path" ]] || abort "Project directory does not exist: $target_path"

  local project_root=""
  project_root="$(cd "$target_path" && pwd)"

  if load_project_metadata "$project_root"; then
    info "Loaded metadata: $METADATA_FILE"
  else
    warn "No metadata file found (.agentic-config.json/.yaml/.yml/.conf.yml)."
    warn "Continuing with fallback symlink scan in standard install directories."
  fi

  local resolved_global=""
  resolved_global="$(discover_global_path "project" "$project_root" 2>/dev/null || true)"
  [[ -n "$resolved_global" ]] || abort "Could not resolve global path"

  info "Mode: project uninstall"
  info "Project path: $project_root"
  info "Global path:  $resolved_global"
  info "Global source: $GLOBAL_PATH_SOURCE"
  echo ""
  warn "Safety mode: symlink-only cleanup."
  warn "AGENTS.md, PROJECT_AGENTS.md, and copied files are intentionally untouched."

  if [[ ${#METADATA_COPIED[@]} -gt 0 ]]; then
    echo ""
    warn "Copied entries detected and intentionally skipped:"
    local copied_item=""
    for copied_item in "${METADATA_COPIED[@]}"; do
      printf '  - %s\n' "$copied_item"
      ((SKIPPED_ITEMS++)) || true
    done
  fi

  local candidates_file=""
  local sorted_candidates_file=""
  candidates_file="$(mktemp)"
  sorted_candidates_file="$(mktemp)"

  collect_project_symlink_candidates "$project_root" "$candidates_file"
  if [[ ! -s "$candidates_file" ]]; then
    warn "No symlink candidates found in known install locations."
  fi

  sort -u "$candidates_file" > "$sorted_candidates_file"

  local candidate=""
  while IFS= read -r candidate || [[ -n "$candidate" ]]; do
    [[ -n "$candidate" ]] || continue

    if paths_equivalent "$candidate" "$project_root/AGENTS.md" || paths_equivalent "$candidate" "$project_root/PROJECT_AGENTS.md"; then
      if $VERBOSE; then
        info "Skipping protected file path: $candidate"
      fi
      ((SKIPPED_ITEMS++)) || true
      continue
    fi

    if [[ ! -L "$candidate" ]]; then
      if $VERBOSE; then
        info "Skipping non-symlink: $candidate"
      fi
      ((SKIPPED_ITEMS++)) || true
      continue
    fi

    if link_points_to_global "$candidate" "$resolved_global"; then
      run_remove_file "$candidate" "project symlink"
      ((REMOVED_SYMLINKS++)) || true
    else
      if $VERBOSE; then
        info "Skipping symlink outside global path: $candidate"
      fi
      ((SKIPPED_ITEMS++)) || true
    fi
  done < "$sorted_candidates_file"

  rm -f "$candidates_file" "$sorted_candidates_file"

  success "Project uninstall completed"
}

run_global_uninstall() {
  local resolved_global=""
  resolved_global="$(discover_global_path "global" "" 2>/dev/null || true)"
  [[ -n "$resolved_global" ]] || abort "Could not resolve global path"

  info "Mode: global uninstall"
  info "Global path:  $resolved_global"
  info "Global source: $GLOBAL_PATH_SOURCE"
  echo ""
  warn "Safety mode: only legacy global wiring is removed automatically."
  warn "Copied project files are never touched by this script."

  local claude_commands_dir="$HOME/.claude/commands"
  local legacy_commands=(agentic agentic-setup agentic-migrate agentic-update agentic-status)

  local command_name=""
  for command_name in "${legacy_commands[@]}"; do
    local command_file="$claude_commands_dir/$command_name.md"
    if [[ ! -e "$command_file" && ! -L "$command_file" ]]; then
      continue
    fi

    if [[ ! -L "$command_file" ]]; then
      if $VERBOSE; then
        info "Skipping non-symlink command file: $command_file"
      fi
      ((SKIPPED_ITEMS++)) || true
      continue
    fi

    if link_points_to_global "$command_file" "$resolved_global"; then
      run_remove_file "$command_file" "global command symlink"
      ((REMOVED_SYMLINKS++)) || true
    else
      if $VERBOSE; then
        info "Skipping command symlink outside global path: $command_file"
      fi
      ((SKIPPED_ITEMS++)) || true
    fi
  done

  remove_marker_section_from_claude_md "$HOME/.claude/CLAUDE.md" "## Agentic-Config Global"

  cleanup_dotpath_file "$resolved_global"
  cleanup_shell_profiles "$resolved_global"
  cleanup_xdg_config_file "$resolved_global"

  if [[ -d "$resolved_global" ]]; then
    if ! is_safe_delete_target "$resolved_global"; then
      warn "Refusing to delete unsafe path: $resolved_global"
      warn "(Path is /, HOME, or contains current working directory.)"
      ((SKIPPED_ITEMS++)) || true
    elif confirm_default_yes "Remove cloned global repository at '$resolved_global'?"; then
      run_remove_dir "$resolved_global" "global repository"
      ((REMOVED_REPO_DIR++)) || true
    else
      info "Kept cloned global repository directory"
      ((SKIPPED_ITEMS++)) || true
    fi
  else
    info "Global repository directory not found: $resolved_global"
  fi

  success "Global uninstall completed"
}

parse_args() {
  local positional=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --global)
        [[ -n "$MODE" && "$MODE" != "global" ]] && abort "Choose exactly one mode: --global OR --project"
        MODE="global"
        shift
        ;;
      --project)
        [[ -n "$MODE" && "$MODE" != "project" ]] && abort "Choose exactly one mode: --global OR --project"
        MODE="project"
        if [[ $# -gt 1 && "$2" != -* ]]; then
          PROJECT_PATH="$2"
          shift 2
        else
          shift
        fi
        ;;
      --global-path)
        [[ $# -lt 2 ]] && abort "--global-path requires a value"
        GLOBAL_PATH_OVERRIDE="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --yes)
        YES=true
        shift
        ;;
      --verbose)
        VERBOSE=true
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --)
        shift
        while [[ $# -gt 0 ]]; do
          positional+=("$1")
          shift
        done
        ;;
      -*)
        abort "Unknown option: $1"
        ;;
      *)
        positional+=("$1")
        shift
        ;;
    esac
  done

  if [[ -z "$MODE" ]]; then
    usage
    abort "Mode required: --global or --project"
  fi

  if [[ "$MODE" == "project" ]]; then
    if [[ -z "$PROJECT_PATH" ]]; then
      if [[ ${#positional[@]} -gt 0 ]]; then
        PROJECT_PATH="${positional[0]}"
      else
        PROJECT_PATH="."
      fi
    elif [[ ${#positional[@]} -gt 0 ]]; then
      abort "Project path provided multiple times"
    fi
  else
    if [[ ${#positional[@]} -gt 0 ]]; then
      abort "Positional arguments are not supported in --global mode"
    fi
  fi
}

print_summary() {
  echo ""
  info "Summary"
  printf '  - Removed symlinks: %s\n' "$REMOVED_SYMLINKS"
  printf '  - Removed path entries: %s\n' "$REMOVED_PATH_ENTRIES"
  printf '  - Removed CLAUDE.md marker blocks: %s\n' "$REMOVED_CLAUDE_BLOCKS"
  printf '  - Removed global repo directories: %s\n' "$REMOVED_REPO_DIR"
  printf '  - Skipped items: %s\n' "$SKIPPED_ITEMS"

  if $DRY_RUN; then
    success "Dry-run complete. No changes were made."
  else
    success "Uninstall complete."
  fi
}

main() {
  command -v python3 >/dev/null 2>&1 || abort "python3 is required"

  parse_args "$@"

  info "Agentic-Config Legacy Uninstaller"
  if $DRY_RUN; then
    warn "DRY-RUN mode enabled"
  fi

  echo ""
  warn "Safety policy: do not modify AGENTS.md, PROJECT_AGENTS.md, or copied files."
  warn "Only symlinks and legacy global wiring are targeted."

  echo ""
  if [[ "$MODE" == "project" ]]; then
    run_project_uninstall "$PROJECT_PATH"
  else
    run_global_uninstall
  fi

  print_summary
}

main "$@"
