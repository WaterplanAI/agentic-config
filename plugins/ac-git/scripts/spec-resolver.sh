#!/usr/bin/env bash
# Spec Path Resolver
# Provides path resolution and commit routing for external/local specs storage
# Plugin-aware version: uses ${CLAUDE_PLUGIN_ROOT} for all paths

# Source shared bootstrap helpers (CLAUDE_PLUGIN_ROOT resolution + config loader)
# shellcheck source=lib/source-helpers.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/source-helpers.sh"

# Validate spec path against directory traversal attacks
# Usage: _validate_spec_path <path>
# Returns: 0 if valid, 1 if invalid (contains ..)
_validate_spec_path() {
  local path="$1"
  # Reject paths containing .. sequences (directory traversal)
  if [[ "$path" == *".."* ]]; then
    return 1
  fi
  # Reject absolute paths (security: path traversal)
  if [[ "$path" == /* ]]; then
    echo "ERROR: Absolute paths not allowed: $path" >&2
    return 1
  fi
  return 0
}

# Resolve spec path based on external/local configuration
# Usage: resolve_spec_path <relative_spec_path>
# Returns: absolute path to spec file
#
# Examples:
#   resolve_spec_path "2025/12/feat/my-feature/001-spec.md"
#   -> If EXT_SPECS_REPO_URL set: /path/to/repo/.specs/specs/2025/12/feat/my-feature/001-spec.md
#   -> If not set: /path/to/repo/specs/2025/12/feat/my-feature/001-spec.md
resolve_spec_path() {
  local relative_spec_path="$1"

  if [[ -z "$relative_spec_path" ]]; then
    echo "ERROR: Relative spec path required" >&2
    echo "Usage: resolve_spec_path <relative_spec_path>" >&2
    return 1
  fi

  # Validate path against traversal attacks
  if ! _validate_spec_path "$relative_spec_path"; then
    echo "ERROR: Invalid spec path - directory traversal not allowed: $relative_spec_path" >&2
    return 1
  fi

  _source_config_loader || return 1
  load_agentic_config

  # Get project root for spec paths (NOT global agentic-config)
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no CLAUDE.md or .git found)" >&2
    return 1
  }
  local resolved_path

  if [[ -n "${EXT_SPECS_REPO_URL:-}" ]]; then
    # External specs repository configured
    # Use :- instead of := to treat empty string as unset (use default)
    # If explicitly set to empty "", use default .specs
    local ext_specs_path="${EXT_SPECS_LOCAL_PATH:-.specs}"

    # Source external-specs.sh from plugin
    local ext_specs_script="${CLAUDE_PLUGIN_ROOT}/scripts/external-specs.sh"
    if [[ -f "$ext_specs_script" ]]; then
      # shellcheck source=external-specs.sh
      source "$ext_specs_script"

      # Initialize external specs repository (clone/pull)
      ext_specs_init || return 1
    else
      echo "ERROR: external-specs.sh not found at $ext_specs_script" >&2
      return 1
    fi

    resolved_path="$project_root/$ext_specs_path/specs/$relative_spec_path"
  else
    # Local specs directory
    resolved_path="$project_root/specs/$relative_spec_path"
  fi

  # Ensure parent directory exists (pure bash - no dirname)
  local parent_dir="${resolved_path%/*}"

  # Bounds check: limit mkdir -p depth to 20 levels (security: resource exhaustion)
  local temp="${parent_dir//[!\/]/}"
  local depth=${#temp}
  if [[ $depth -gt 20 ]]; then
    echo "ERROR: Directory depth exceeds maximum (20 levels): $parent_dir" >&2
    return 1
  fi

  mkdir -p "$parent_dir" || {
    echo "ERROR: Failed to create parent directory for $resolved_path" >&2
    return 1
  }

  echo "$resolved_path"
  return 0
}

# Commit spec changes to appropriate repository
# Usage: commit_spec_changes <spec_path> <stage> <nnn> <title> [--dry-run]
#   --dry-run: Show what would be committed without executing
#
# Examples:
#   commit_spec_changes "/path/.specs/specs/2025/12/feat/x/001-spec.md" "PLAN" "001" "spec-title"
#   commit_spec_changes "/path/specs/2025/12/feat/x/001-spec.md" "PLAN" "001" "spec-title"
#   commit_spec_changes "/path/.specs/specs/..." "PLAN" "001" "title" --dry-run
commit_spec_changes() {
  local spec_path="$1"
  local stage="$2"
  local nnn="$3"
  local title="$4"
  local dry_run=false
  [[ "${5:-}" == "--dry-run" ]] && dry_run=true

  if [[ -z "$spec_path" ]] || [[ -z "$stage" ]] || [[ -z "$nnn" ]] || [[ -z "$title" ]]; then
    echo "ERROR: All parameters required" >&2
    echo "Usage: commit_spec_changes <spec_path> <stage> <nnn> <title> [--dry-run]" >&2
    return 1
  fi

  _source_config_loader || return 1
  load_agentic_config

  # Get project root for git operations (NOT global agentic-config)
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no CLAUDE.md or .git found)" >&2
    return 1
  }
  local ext_specs_path="${EXT_SPECS_LOCAL_PATH:-.specs}"
  local commit_message="spec($nnn): $stage - $title"

  # Check if spec is in external repository
  if [[ -n "${EXT_SPECS_REPO_URL:-}" && -n "$ext_specs_path" && "$spec_path" == "$project_root/$ext_specs_path/specs/"* ]]; then
    # External specs repository - use ext_specs_commit
    if [[ "$dry_run" == true ]]; then
      echo "DRY RUN: commit_spec_changes (external)" >&2
      echo "  Spec: $spec_path" >&2
      echo "  Message: $commit_message" >&2
      echo "  Target: external specs repository" >&2
      # Source and call ext_specs_commit with dry-run
      local ext_specs_script="${CLAUDE_PLUGIN_ROOT}/scripts/external-specs.sh"
      # shellcheck source=external-specs.sh
      [[ -f "$ext_specs_script" ]] && source "$ext_specs_script"
      ext_specs_commit "$commit_message" --dry-run 2>/dev/null || true
      return 0
    fi

    # Source script from plugin
    local ext_specs_script="${CLAUDE_PLUGIN_ROOT}/scripts/external-specs.sh"
    if [[ -f "$ext_specs_script" ]]; then
      # shellcheck source=external-specs.sh
      source "$ext_specs_script"

      ext_specs_commit "$commit_message" || {
        echo "ERROR: Failed to commit to external specs repository" >&2
        return 1
      }

      echo "Committed to external specs repository: $commit_message" >&2
    else
      echo "ERROR: external-specs.sh not found at $ext_specs_script" >&2
      return 1
    fi
  else
    # Local specs directory - use standard git operations in PROJECT
    if [[ "$dry_run" == true ]]; then
      echo "DRY RUN: commit_spec_changes (local)" >&2
      echo "  Spec: $spec_path" >&2
      echo "  Message: $commit_message" >&2
      echo "  Target: main repository at $project_root" >&2
      return 0
    fi

    (cd "$project_root" && git add "$spec_path" && git commit -m "$commit_message" >&2) || {
      local rel_spec_path="$spec_path"
      if [[ "$rel_spec_path" == "$project_root/"* ]]; then
        rel_spec_path="${rel_spec_path#"$project_root"/}"
      fi

      echo "ERROR: Failed to commit to main repository" >&2
      # Reset index state on commit failure (unstage spec file only)
      (cd "$project_root" && git reset -- "$rel_spec_path" 2>/dev/null)
      return 1
    }

    echo "Committed to main repository: $commit_message" >&2
  fi

  return 0
}
