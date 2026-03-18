#!/usr/bin/env bash
# External Specs Storage Git Wrapper
# Manages external specification repository operations
#
# Plugin-aware version: uses ${CLAUDE_PLUGIN_ROOT} for all paths
# NOTE: Uses pure bash (no external commands like dirname) for compatibility
# with restricted shell environments (e.g., Claude Code)

# Source shared bootstrap helpers (CLAUDE_PLUGIN_ROOT resolution + config loader)
# shellcheck source=lib/source-helpers.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/source-helpers.sh"

# Validate git repository URL format
# Supports: git@host:path, ssh://, https://, file://
# Usage: _validate_git_url <url>
# Returns: 0 if valid, 1 if invalid
_validate_git_url() {
  local url="$1"

  # Reject absolute file paths (security: path traversal)
  if [[ "$url" == /* ]]; then
    echo "ERROR: Absolute file paths not allowed: $url" >&2
    return 1
  fi

  # SSH: git@host:path or ssh://
  # HTTPS: https://
  # File: file://
  # Max URL length: 2048 chars (security: resource exhaustion)
  if [[ ${#url} -gt 2048 ]]; then
    echo "ERROR: Git URL exceeds maximum length (2048 chars): ${#url}" >&2
    return 1
  fi
  if [[ "$url" =~ ^(git@[^:]+:|ssh://|https://|file://) ]]; then
    return 0
  fi
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

# Resolve lock directory path (outside clone destination)
# Usage: _ext_specs_lockdir <project_root>
_ext_specs_lockdir() {
  local project_root="$1"
  echo "$project_root/.tmp/agentic-locks/ext-specs"
}

# Initialize external specs repository
# Clones if not present, pulls latest changes if already cloned
# Usage: ext_specs_init [--dry-run]
#   --dry-run: Show what would be done without executing
ext_specs_init() {
  local dry_run=false
  [[ "${1:-}" == "--dry-run" ]] && dry_run=true

  _source_config_loader || return 1
  load_agentic_config

  local repo_url="${EXT_SPECS_REPO_URL:-}"
  local local_path="${EXT_SPECS_LOCAL_PATH:-.specs}"
  # Use project root for .specs directory (NOT plugin root)
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no CLAUDE.md or .git found)" >&2
    echo "Run from within a valid project directory" >&2
    return 1
  }
  local full_path="$project_root/$local_path"

  if [[ -z "$repo_url" ]]; then
    echo "ERROR: EXT_SPECS_REPO_URL not configured" >&2
    echo "Set in: environment variable, .env file, or .agentic-config.conf.yml" >&2
    return 1
  fi

  # Validate URL format before clone
  if ! _validate_git_url "$repo_url"; then
    echo "ERROR: Invalid git URL format: $repo_url" >&2
    echo "Supported formats: git@host:path, ssh://, https://, file://" >&2
    return 1
  fi

  # Dry-run: show what would happen
  if [[ "$dry_run" == true ]]; then
    echo "DRY RUN: ext_specs_init" >&2
    if [[ -d "$full_path/.git" ]]; then
      echo "  Would pull latest changes in: $full_path" >&2
      echo "  Remote: $(cd "$full_path" && git remote get-url origin 2>/dev/null || echo "$repo_url")" >&2
    else
      echo "  Would clone repository to: $full_path" >&2
      echo "  From: $repo_url" >&2
    fi
    return 0
  fi

  # Use mkdir-based locking to serialize concurrent git operations (cross-platform)
  local lockdir
  lockdir="$(_ext_specs_lockdir "$project_root")"
  mkdir -p "${lockdir%/*}" || {
    echo "ERROR: Failed to create lock directory parent: ${lockdir%/*}" >&2
    return 1
  }

  (
    # Acquire exclusive lock with 10s timeout
    _acquire_lock "$lockdir" 10 || exit 1

    # Set trap AFTER successful acquisition to ensure cleanup on any exit
    trap '_release_lock "$lockdir"' EXIT INT TERM

    if [[ -d "$full_path/.git" ]]; then
      echo "External specs repository already exists at: $full_path" >&2
      echo "Pulling latest changes..." >&2
      (cd "$full_path" && git pull >&2) || {
        echo "ERROR: Failed to pull latest changes" >&2
        exit 1
      }
      echo "Successfully updated external specs repository" >&2
    else
      if [[ -e "$full_path" && ! -d "$full_path" ]]; then
        echo "ERROR: Clone destination exists and is not a directory: $full_path" >&2
        exit 1
      fi

      if [[ -d "$full_path" ]]; then
        local -a existing_entries=()
        shopt -s nullglob dotglob
        existing_entries=("$full_path"/*)
        shopt -u nullglob dotglob
        if (( ${#existing_entries[@]} > 0 )); then
          echo "ERROR: Clone destination must be empty: $full_path" >&2
          exit 1
        fi
      fi

      local dest_existed=false
      [[ -d "$full_path" ]] && dest_existed=true

      echo "Cloning external specs repository to: $full_path" >&2
      git clone "$repo_url" "$full_path" >&2 || {
        if [[ "$dest_existed" == false ]]; then
          rm -rf "$full_path" 2>/dev/null || true
        fi
        echo "ERROR: Failed to clone repository from $repo_url" >&2
        exit 1
      }
      echo "Successfully cloned external specs repository" >&2
    fi
  ) || return 1

  return 0
}

# Commit and push changes to external specs repository
# Usage: ext_specs_commit "commit message" [--dry-run]
#   --dry-run: Show what would be committed without executing
ext_specs_commit() {
  local commit_message="$1"
  local dry_run=false
  [[ "${2:-}" == "--dry-run" ]] && dry_run=true

  _source_config_loader || return 1
  load_agentic_config

  local local_path="${EXT_SPECS_LOCAL_PATH:-.specs}"
  # Use project root for .specs directory (NOT plugin root)
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no CLAUDE.md or .git found)" >&2
    echo "Run from within a valid project directory" >&2
    return 1
  }
  local full_path="$project_root/$local_path"

  if [[ -z "$commit_message" ]]; then
    echo "ERROR: Commit message required" >&2
    echo "Usage: ext_specs_commit \"commit message\" [--dry-run]" >&2
    return 1
  fi

  if [[ ! -d "$full_path/.git" ]]; then
    echo "ERROR: External specs repository not initialized at: $full_path" >&2
    echo "Run ext_specs_init first" >&2
    return 1
  fi

  # Dry-run: show what would be committed
  if [[ "$dry_run" == true ]]; then
    echo "DRY RUN: ext_specs_commit" >&2
    echo "  Repository: $full_path" >&2
    echo "  Message: $commit_message" >&2
    echo "  Remote: $(cd "$full_path" && git remote get-url origin 2>/dev/null || echo "unknown")" >&2
    echo "  Changes:" >&2
    (cd "$full_path" && git status --short) | while read -r line; do
      echo "    $line" >&2
    done
    local change_count
    change_count=$(cd "$full_path" && git status --short | wc -l | tr -d ' ')
    echo "  Total files: $change_count" >&2
    return 0
  fi

  # Use mkdir-based locking to serialize concurrent git operations (cross-platform)
  local lockdir
  lockdir="$(_ext_specs_lockdir "$project_root")"
  mkdir -p "${lockdir%/*}" || {
    echo "ERROR: Failed to create lock directory parent: ${lockdir%/*}" >&2
    return 1
  }

  (
    # Acquire exclusive lock with 30s timeout (longer for push operations)
    _acquire_lock "$lockdir" 30 || exit 1

    # Set trap AFTER successful acquisition to ensure cleanup on any exit
    trap '_release_lock "$lockdir"' EXIT INT TERM

    # Separate commit and push for proper rollback on push failure
    (
      cd "$full_path" || {
        echo "ERROR: Failed to change directory to $full_path" >&2
        exit 1
      }

      # Stage all changes
      git add -A >&2 || {
        echo "ERROR: Failed to stage changes" >&2
        exit 2
      }

      # Check if there are changes to commit
      if ! git diff --cached --quiet; then
        # Commit changes
        git commit -m "$commit_message" >&2 || {
          echo "ERROR: Failed to commit changes" >&2
          exit 3
        }

        # Attempt push with rollback on failure
        if ! git push >&2; then
          echo "ERROR: Push failed, rolling back commit" >&2
          if ! git reset HEAD~1 >&2; then
            echo "CRITICAL: Rollback failed. Manual recovery required:" >&2
            echo "  cd $full_path && git reset HEAD~1" >&2
            exit 2  # Distinct exit code for rollback failure
          fi
          exit 4
        fi
      else
        echo "No changes to commit" >&2
        exit 0
      fi
    ) || {
      local exit_code=$?
      echo "ERROR: Failed to commit and push changes to external specs (exit code: $exit_code)" >&2
      exit 1
    }
  ) || return 1

  echo "Successfully committed and pushed changes to external specs repository" >&2
  return 0
}

# Return resolved absolute path to external specs directory
ext_specs_path() {
  _source_config_loader || return 1
  load_agentic_config

  local local_path="${EXT_SPECS_LOCAL_PATH:-.specs}"
  # Use project root for .specs directory (NOT plugin root)
  local project_root
  project_root="$(get_project_root)" || {
    echo "ERROR: Could not find project root (no CLAUDE.md or .git found)" >&2
    return 1
  }
  echo "$project_root/$local_path"
}
