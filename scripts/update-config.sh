#!/usr/bin/env bash
set -euo pipefail

# Updates agentic configuration from central repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LATEST_VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/version-manager.sh"
source "$SCRIPT_DIR/lib/path-persistence.sh"

# Dynamically discover all available commands from core directory
discover_available_commands() {
  local cmds=()
  for f in "$REPO_ROOT/core/commands/claude/"*.md; do
    [[ ! -f "$f" ]] && continue
    local name=$(basename "$f" .md)
    # Skip agentic-* commands (globally installed)
    [[ "$name" == agentic-* ]] && continue
    cmds+=("$name")
  done
  echo "${cmds[@]}"
}

# Discover ALL commands (for self-hosted repo sync)
discover_all_commands() {
  local cmds=()
  for f in "$REPO_ROOT/core/commands/claude/"*.md; do
    [[ ! -f "$f" ]] && continue
    cmds+=("$(basename "$f" .md)")
  done
  echo "${cmds[@]}"
}

# Check if target is the self-hosted agentic-config repo
is_self_hosted() {
  local target="$1"

  # Verify all markers exist (symlink targets must exist)
  if [[ -f "$target/VERSION" && -d "$target/core/commands/claude" && -d "$target/core/agents" ]]; then
    # Additional check: ensure symlink targets exist (if target contains symlinks)
    [[ -d "$target/core" ]] || return 1
    return 0
  fi
  return 1
}

# Clean up invalid nested symlinks inside core/ directories
cleanup_invalid_nested_symlinks() {
  local target="$1"
  local cleaned=0

  # Only run for self-hosted repos that have core/ directory
  if [[ ! -d "$target/core" ]]; then
    return 0
  fi

  # Remove self-referential symlink in agents
  if [[ -L "$target/core/agents/agents" ]]; then
    rm -f "$target/core/agents/agents"
    ((cleaned++)) || true
  fi

  # Remove self-referential symlinks in skills
  for skill_dir in "$target/core/skills/"*/; do
    [[ ! -d "$skill_dir" ]] && continue
    local skill_name=$(basename "$skill_dir")
    local invalid_link="${skill_dir}${skill_name}"
    if [[ -L "$invalid_link" ]]; then
      rm -f "$invalid_link"
      ((cleaned++)) || true
    fi
  done

  if [[ $cleaned -gt 0 ]]; then
    echo "  Cleaned up $cleaned invalid nested symlink(s) in core/"
  fi
}

# Sync all command symlinks for self-hosted repo
sync_self_hosted_commands() {
  local target="$1"
  local is_self=false

  # Check if target IS the repo root (self-restoration mode)
  if [[ "$(cd "$target" && pwd)" == "$REPO_ROOT" ]]; then
    is_self=true
  fi

  local all_cmds=($(discover_all_commands))
  local synced=0
  local missing=()

  echo "Self-hosted repo detected - syncing ALL command symlinks..."

  for cmd in "${all_cmds[@]}"; do
    local src="$REPO_ROOT/core/commands/claude/$cmd.md"
    local dest="$target/.claude/commands/$cmd.md"

    if [[ ! -L "$dest" ]]; then
      missing+=("$cmd")
      if [[ "$INSTALL_MODE" == "copy" ]]; then
        cp "$src" "$dest"
      else
        if [[ "$is_self" == true ]]; then
          # Self-restoration: use relative path (same as init.md)
          (cd "$target/.claude/commands" && ln -sf "../../core/commands/claude/$cmd.md" "$cmd.md")
        else
          # Verify source exists before creating symlink
          if [[ ! -f "$src" ]]; then
            echo "  WARNING: Source file missing for $cmd.md - skipping" >&2
            continue
          fi
          # Cross-repo sync: use absolute path
          ln -sf "$src" "$dest"
        fi
      fi
      echo "  ✓ $cmd.md (created)"
      ((synced++)) || true
    fi
  done

  if [[ $synced -eq 0 ]]; then
    echo "  (all commands already symlinked)"
  else
    echo "Synced $synced missing command symlink(s)"
  fi
}

# Sync all hook symlinks for self-hosted repo
sync_self_hosted_hooks() {
  local target="$1"
  local is_self=false

  # Check if target IS the repo root (self-restoration mode)
  if [[ "$(cd "$target" && pwd)" == "$REPO_ROOT" ]]; then
    is_self=true
  fi

  local synced=0
  local missing=()

  echo "Self-hosted repo detected - syncing ALL hook symlinks..."

  for hook_file in "$REPO_ROOT/core/hooks/pretooluse/"*.py; do
    [[ ! -f "$hook_file" ]] && continue
    local hook=$(basename "$hook_file")
    local dest="$target/.claude/hooks/pretooluse/$hook"

    if [[ ! -L "$dest" ]]; then
      missing+=("$hook")
      mkdir -p "$target/.claude/hooks/pretooluse"
      if [[ "$is_self" == true ]]; then
        # Self-restoration: use relative path
        (cd "$target/.claude/hooks/pretooluse" && ln -sf "../../../core/hooks/pretooluse/$hook" "$hook")
      else
        # Cross-repo sync: use absolute path
        ln -sf "$hook_file" "$dest"
      fi
      echo "  ✓ $hook (created)"
      ((synced++)) || true
    fi
  done

  [[ $synced -eq 0 ]] && echo "  (all hooks already symlinked)"
}

# Skills: all directories in core/skills/
discover_available_skills() {
  local skills=()
  for d in "$REPO_ROOT/core/skills/"*/; do
    [[ ! -d "$d" ]] && continue
    local name=$(basename "$d")
    skills+=("$name")
  done
  echo "${skills[@]}"
}

# Discover commands and skills dynamically (no hardcoded lists!)
AVAILABLE_CMDS=($(discover_available_commands))
AVAILABLE_SKILLS=($(discover_available_skills))

# Defaults
FORCE=false
NIGHTLY=false

usage() {
  cat <<EOF
Usage: update-config.sh [OPTIONS] [target_path]

Update agentic configuration to latest version from central repository.

Options:
  --force                Force update of copied files without prompting
  --nightly              Force symlink rebuild and config reconciliation (ignores version match)
  -h, --help             Show this help message

Notes:
  - Symlinked files update automatically
  - Copied files (.agent/config.yml, AGENTS.md) require manual review
  - If target_path not specified, uses current directory
  - Nightly mode updates config schema to latest even when version matches
EOF
}

# Parse arguments
TARGET_PATH="."
while [[ $# -gt 0 ]]; do
  case $1 in
    --force)
      FORCE=true
      shift
      ;;
    --nightly)
      NIGHTLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      TARGET_PATH="$1"
      shift
      ;;
  esac
done

# Function to clean up orphaned symlinks
# Returns count via stdout (no other output to stdout)
cleanup_orphan_symlinks() {
  local target="$1"
  local dir="$2"
  local removed=0

  if [[ -d "$target/$dir" ]]; then
    for link in "$target/$dir"/*; do
      if [[ -L "$link" && ! -e "$link" ]]; then
        rm "$link"
        # Progress to stderr so it doesn't interfere with count capture
        echo "  Removed orphan: $(basename "$link")" >&2
        ((removed++)) || true
      fi
    done
  fi
  echo "$removed"
}

# Function to migrate customizations to PROJECT_AGENTS.md
migrate_to_project_agents() {
  local target="$1"
  local agents_file="$target/AGENTS.md"
  local project_file="$target/PROJECT_AGENTS.md"

  # Skip if PROJECT_AGENTS.md already exists
  [[ -f "$project_file" ]] && return 0

  # Skip if AGENTS.md doesn't exist
  [[ ! -f "$agents_file" ]] && return 0

  # Check if AGENTS.md has customization marker
  local marker_line=$(grep -n "CUSTOMIZE BELOW THIS LINE" "$agents_file" 2>/dev/null | cut -d: -f1)
  [[ -z "$marker_line" ]] && return 0

  # Extract content after marker (skip marker line + 1 comment line)
  local total_lines=$(wc -l < "$agents_file")
  local content_start=$((marker_line + 2))

  # Skip if no content after marker
  [[ $content_start -ge $total_lines ]] && return 0

  # Extract content and check if it's substantial (not just comments)
  local custom_content=$(tail -n +$content_start "$agents_file" | grep -v '^$' | grep -v '^<!--' | head -20)
  [[ -z "$custom_content" ]] && return 0

  # Has real customizations - migrate
  echo "Migrating customizations to PROJECT_AGENTS.md..."
  tail -n +$content_start "$agents_file" > "$project_file"
  echo "Migration complete: customizations preserved in PROJECT_AGENTS.md"

  return 0
}

# Validate
if [[ ! -d "$TARGET_PATH" ]]; then
  echo "ERROR: Directory does not exist: $TARGET_PATH" >&2
  exit 1
fi

TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

# Check if centralized config exists
if [[ ! -f "$TARGET_PATH/.agentic-config.json" ]]; then
  echo "ERROR: No centralized configuration found" >&2
  echo "   Run setup-config.sh or migrate-existing.sh first" >&2
  exit 1
fi

CURRENT_VERSION=$(check_version "$TARGET_PATH")
INSTALL_MODE=$(get_install_mode "$TARGET_PATH")

# Validate INSTALL_MODE
if [[ "$INSTALL_MODE" != "symlink" && "$INSTALL_MODE" != "copy" ]]; then
  echo "ERROR: Invalid install_mode in .agentic-config.json: $INSTALL_MODE" >&2
  echo "   Valid values: symlink, copy" >&2
  echo "   Fix: Update .agentic-config.json or re-run setup-config.sh" >&2
  exit 1
fi

echo "Agentic Configuration Update"
echo "   Current version: $CURRENT_VERSION"
echo "   Latest version:  $LATEST_VERSION"
echo "   Install mode:    $INSTALL_MODE"

# Fix Codex symlink if needed (run even if versions match)
if [[ -L "$TARGET_PATH/.codex/prompts/spec.md" ]]; then
  CURRENT_TARGET=$(readlink "$TARGET_PATH/.codex/prompts/spec.md")
  if [[ "$CURRENT_TARGET" == *"spec-command.md" ]]; then
    echo "Fixing Codex spec symlink..."
    if [[ "$INSTALL_MODE" == "copy" ]]; then
      rm -f "$TARGET_PATH/.codex/prompts/spec.md"
      cp "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
    else
      ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
    fi
    echo "  ✓ Updated Codex symlink to use proper command file"
  fi
fi

# CRITICAL: Self-hosted repo sync (always run to catch new commands)
if is_self_hosted "$TARGET_PATH"; then
  # Clean up any invalid nested symlinks first
  cleanup_invalid_nested_symlinks "$TARGET_PATH"
  sync_self_hosted_commands "$TARGET_PATH"
  sync_self_hosted_hooks "$TARGET_PATH"
fi

# Handle version match - but still check for missing assets/orphans
if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]]; then
  if [[ "$NIGHTLY" == true ]]; then
    echo "Nightly mode: reconciling config and rebuilding symlinks..."
    echo ""
    echo "Reconciling configuration..."
    reconcile_config "$TARGET_PATH" "$LATEST_VERSION"
    # Continue to symlink rebuild (don't exit)
  elif [[ "$FORCE" == true ]]; then
    echo "Already up to date (force mode - checking templates)..."
    # Continue to template check section (don't exit)
  else
    echo "Already up to date!"
    # Still check for missing commands/skills and clean orphans
    # This handles cases where user manually deleted files
    NEED_MAINTENANCE=false

    # Check for missing commands
    for cmd in "${AVAILABLE_CMDS[@]}"; do
      if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]] && [[ ! -e "$TARGET_PATH/.claude/commands/$cmd.md" ]]; then
        NEED_MAINTENANCE=true
        break
      fi
    done

    # Check for missing skills
    if [[ "$NEED_MAINTENANCE" == false ]]; then
      for skill in "${AVAILABLE_SKILLS[@]}"; do
        if [[ -d "$REPO_ROOT/core/skills/$skill" ]] && [[ ! -e "$TARGET_PATH/.claude/skills/$skill" ]]; then
          NEED_MAINTENANCE=true
          break
        fi
      done
    fi

    # Check for orphan symlinks
    if [[ "$NEED_MAINTENANCE" == false ]]; then
      if [[ -d "$TARGET_PATH/.claude/commands" ]]; then
        for link in "$TARGET_PATH/.claude/commands"/*; do
          if [[ -L "$link" && ! -e "$link" ]]; then
            NEED_MAINTENANCE=true
            break
          fi
        done
      fi
    fi

    # Check if config needs reconciliation (missing fields)
    if [[ "$NEED_MAINTENANCE" == false ]] && command -v jq >/dev/null 2>&1; then
      config="$TARGET_PATH/.agentic-config.json"
      if [[ ! $(jq -r '.agentic_global_path // empty' "$config") ]]; then
        NEED_MAINTENANCE=true
      fi
    fi

    if [[ "$NEED_MAINTENANCE" == false ]]; then
      # Nothing to do, just refresh path and exit
      echo "Refreshing path persistence..."
      if persist_agentic_path "$REPO_ROOT"; then
        echo "  ✓ Path persisted to all locations"
      else
        echo "  ⊘ Some persistence locations failed (non-fatal)"
      fi
      exit 0
    else
      echo "Performing maintenance (restoring missing assets, cleaning orphans)..."
      echo ""
      # Continue to maintenance section below
    fi
  fi
fi

# Get project type from config
if command -v jq &>/dev/null; then
  PROJECT_TYPE=$(jq -r '.project_type' "$TARGET_PATH/.agentic-config.json")

  # Validate PROJECT_TYPE against known types
  KNOWN_TYPES=("generic" "python" "node" "rust" "go" "java")
  VALID_TYPE=false
  for known_type in "${KNOWN_TYPES[@]}"; do
    if [[ "$PROJECT_TYPE" == "$known_type" ]]; then
      VALID_TYPE=true
      break
    fi
  done
  if [[ "$VALID_TYPE" == false ]]; then
    echo "WARNING: Unknown project_type '$PROJECT_TYPE' - using 'generic' template as fallback" >&2
    PROJECT_TYPE="generic"
  fi
else
  PROJECT_TYPE=$(grep -o '"project_type"[[:space:]]*:[[:space:]]*"[^"]*"' "$TARGET_PATH/.agentic-config.json" | cut -d'"' -f4)
fi
TEMPLATE_DIR="$REPO_ROOT/templates/$PROJECT_TYPE"

# Run version update flow if there's a version change OR force mode
if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]] || [[ "$FORCE" == true ]]; then
  if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
    # Check if updates are opt-in
    AUTO_CHECK=$(jq -r '.auto_check // true' "$TARGET_PATH/.agentic-config.json" 2>/dev/null || echo "true")
    if [[ "$AUTO_CHECK" == "false" ]]; then
      echo "WARNING: Auto-check disabled for this project"
      echo "   To enable: jq '.auto_check = true' .agentic-config.json > tmp && mv tmp .agentic-config.json"
    fi

    echo ""
    echo "Update available: $CURRENT_VERSION → $LATEST_VERSION"
    echo ""
    echo "Symlinked files will update automatically:"
    echo "  - agents/ (workflows)"
    echo "  - .claude/commands/spec.md"
    echo "  - .gemini/commands/spec.toml"
    echo "  - .codex/prompts/spec.md"
    echo ""
  fi

  # Check for changes in templates
  echo "Checking for template updates..."
  HAS_CONFIG_CHANGES=false
  HAS_AGENTS_CHANGES=false

  if [[ -f "$TEMPLATE_DIR/.agent/config.yml.template" ]]; then
    if ! diff -q "$TARGET_PATH/.agent/config.yml" "$TEMPLATE_DIR/.agent/config.yml.template" >/dev/null 2>&1; then
      HAS_CONFIG_CHANGES=true
    fi
  fi

  if [[ -f "$TEMPLATE_DIR/AGENTS.md.template" ]]; then
    # Check first 20 lines (template section) for changes
    if ! diff -q <(head -20 "$TARGET_PATH/AGENTS.md") <(head -20 "$TEMPLATE_DIR/AGENTS.md.template") >/dev/null 2>&1; then
      HAS_AGENTS_CHANGES=true
    fi
  fi

  if [[ "$HAS_CONFIG_CHANGES" == false && "$HAS_AGENTS_CHANGES" == false ]]; then
    echo "No template changes detected"
  else
    echo ""
    [[ "$HAS_CONFIG_CHANGES" == true ]] && echo "  .agent/config.yml has updates"
    [[ "$HAS_AGENTS_CHANGES" == true ]] && echo "  AGENTS.md template has updates"
    echo ""

    if [[ "$FORCE" == true ]]; then
      # Create backup before force updating
      if [[ "$HAS_CONFIG_CHANGES" == true || "$HAS_AGENTS_CHANGES" == true ]]; then
        BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)"
        mkdir -p "$BACKUP_DIR"
        [[ "$HAS_CONFIG_CHANGES" == true && -f "$TARGET_PATH/.agent/config.yml" ]] && cp "$TARGET_PATH/.agent/config.yml" "$BACKUP_DIR/config.yml"
        [[ "$HAS_AGENTS_CHANGES" == true && -f "$TARGET_PATH/AGENTS.md" ]] && cp "$TARGET_PATH/AGENTS.md" "$BACKUP_DIR/AGENTS.md"
        echo "Created backup: $BACKUP_DIR"
      fi

      # Migrate customizations to PROJECT_AGENTS.md if needed
      migrate_to_project_agents "$TARGET_PATH"

      echo "Force updating templates..."
      [[ "$HAS_CONFIG_CHANGES" == true ]] && cp "$TEMPLATE_DIR/.agent/config.yml.template" "$TARGET_PATH/.agent/config.yml"
      [[ "$HAS_AGENTS_CHANGES" == true ]] && cp "$TEMPLATE_DIR/AGENTS.md.template" "$TARGET_PATH/AGENTS.md"
      echo "Templates updated"
    else
      echo "To view changes:"
      [[ "$HAS_CONFIG_CHANGES" == true ]] && echo "  diff $TARGET_PATH/.agent/config.yml $TEMPLATE_DIR/.agent/config.yml.template"
      [[ "$HAS_AGENTS_CHANGES" == true ]] && echo "  diff $TARGET_PATH/AGENTS.md $TEMPLATE_DIR/AGENTS.md.template"
      echo ""
      echo "To update:"
      echo "  update-config.sh --force $TARGET_PATH"
      echo ""
      echo "Or manually merge changes from templates"
    fi
  fi
fi

# Track whether copy mode replaced assets (for version tracking)
COPY_MODE_REPLACED=false

# Handle copy mode updates
if [[ "$INSTALL_MODE" == "copy" && "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
  echo ""
  echo "Copy mode detected - backing up and updating copied assets..."

  # Create backup directory
  COPY_BACKUP_DIR="$TARGET_PATH/.agentic-config.copy-backup.$(date +%s)"
  mkdir -p "$COPY_BACKUP_DIR"
  echo "   Backup: $COPY_BACKUP_DIR"

  # Backup all copied assets
  BACKED_UP_ITEMS=()
  if [[ -d "$TARGET_PATH/agents" && ! -L "$TARGET_PATH/agents" ]]; then
    cp -r "$TARGET_PATH/agents" "$COPY_BACKUP_DIR/"
    BACKED_UP_ITEMS+=("agents/")
  fi

  if [[ -d "$TARGET_PATH/.claude/commands" ]]; then
    mkdir -p "$COPY_BACKUP_DIR/.claude/commands"
    for cmd in "$TARGET_PATH/.claude/commands"/*.md; do
      if [[ -f "$cmd" && ! -L "$cmd" ]]; then
        cp "$cmd" "$COPY_BACKUP_DIR/.claude/commands/"
        BACKED_UP_ITEMS+=(".claude/commands/$(basename "$cmd")")
      fi
    done
  fi

  if [[ -d "$TARGET_PATH/.claude/skills" ]]; then
    mkdir -p "$COPY_BACKUP_DIR/.claude/skills"
    for skill in "$TARGET_PATH/.claude/skills"/*; do
      if [[ -d "$skill" && ! -L "$skill" ]]; then
        cp -r "$skill" "$COPY_BACKUP_DIR/.claude/skills/"
        BACKED_UP_ITEMS+=(".claude/skills/$(basename "$skill")")
      fi
    done
  fi

  if [[ -d "$TARGET_PATH/.claude/agents" ]]; then
    mkdir -p "$COPY_BACKUP_DIR/.claude/agents"
    for agent in "$TARGET_PATH/.claude/agents"/*.md; do
      if [[ -f "$agent" && ! -L "$agent" ]]; then
        cp "$agent" "$COPY_BACKUP_DIR/.claude/agents/"
        BACKED_UP_ITEMS+=(".claude/agents/$(basename "$agent")")
      fi
    done
  fi

  echo "   Backed up ${#BACKED_UP_ITEMS[@]} item(s)"

  # Replace with latest versions (with backup verification)
  REPLACED_ITEMS=()
  if [[ -d "$TARGET_PATH/agents" && ! -L "$TARGET_PATH/agents" ]]; then
    # Verify backup was successful before deleting (check directory exists and has content)
    BACKUP_COUNT=$(find "$COPY_BACKUP_DIR/agents" -type f 2>/dev/null | wc -l | tr -d ' ')
    ORIGINAL_COUNT=$(find "$TARGET_PATH/agents" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [[ -d "$COPY_BACKUP_DIR/agents" && "$BACKUP_COUNT" -ge "$ORIGINAL_COUNT" ]]; then
      rm -rf "$TARGET_PATH/agents"
      cp -r "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
      REPLACED_ITEMS+=("agents/")
    else
      echo "   WARNING: Backup verification failed for agents/ (expected $ORIGINAL_COUNT files, got $BACKUP_COUNT) - skipping replacement"
    fi
  fi

  # Copy all commands
  for cmd_file in "$REPO_ROOT/core/commands/claude/"*.md; do
    cmd=$(basename "$cmd_file")
    if [[ -f "$TARGET_PATH/.claude/commands/$cmd" && ! -L "$TARGET_PATH/.claude/commands/$cmd" ]]; then
      cp "$cmd_file" "$TARGET_PATH/.claude/commands/$cmd"
      REPLACED_ITEMS+=(".claude/commands/$cmd")
    fi
  done

  # Copy all skills
  for skill_dir in "$REPO_ROOT/core/skills/"*/; do
    skill=$(basename "$skill_dir")
    if [[ -d "$TARGET_PATH/.claude/skills/$skill" && ! -L "$TARGET_PATH/.claude/skills/$skill" ]]; then
      # Verify backup exists before destructive operation
      if [[ -d "$COPY_BACKUP_DIR/.claude/skills/$skill" ]]; then
        rm -rf "$TARGET_PATH/.claude/skills/$skill"
      else
        echo "   WARNING: Backup verification failed for skill $skill - skipping replacement"
        continue
      fi
      cp -r "$skill_dir" "$TARGET_PATH/.claude/skills/$skill"
      REPLACED_ITEMS+=(".claude/skills/$skill")
    fi
  done

  echo "   Replaced ${#REPLACED_ITEMS[@]} item(s) with latest versions"

  # Track that copy mode made replacements (for version tracking)
  if [[ ${#REPLACED_ITEMS[@]} -gt 0 ]]; then
    COPY_MODE_REPLACED=true
  fi

  echo ""
  echo "IMPORTANT: Copy mode update complete"
  echo "   Review changes and manually merge any customizations from backup"
  echo "   Backup location: $COPY_BACKUP_DIR"
fi

# Check if target IS the repo root (self-hosted mode for relative symlinks)
IS_SELF_HOSTED=false
if [[ "$(cd "$TARGET_PATH" && pwd)" == "$REPO_ROOT" ]]; then
  IS_SELF_HOSTED=true
fi

# Install all commands from core (respect install_mode)
echo ""
echo "Installing commands..."
echo "   Available: ${AVAILABLE_CMDS[*]}"
mkdir -p "$TARGET_PATH/.claude/commands"
CMDS_INSTALLED=0
for cmd in "${AVAILABLE_CMDS[@]}"; do
  if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]]; then
    # Check if command not yet installed (neither symlink nor file)
    if [[ ! -e "$TARGET_PATH/.claude/commands/$cmd.md" ]]; then
      if [[ "$INSTALL_MODE" == "copy" ]]; then
        cp "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
      else
        if [[ "$IS_SELF_HOSTED" == true ]]; then
          # Self-hosted: use relative path per PROJECT_AGENTS.md
          (cd "$TARGET_PATH/.claude/commands" && ln -sf "../../core/commands/claude/$cmd.md" "$cmd.md")
        else
          # Cross-project: use absolute path
          ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
        fi
      fi
      echo "  ✓ $cmd.md"
      ((CMDS_INSTALLED++)) || true
    fi
  fi
done
[[ $CMDS_INSTALLED -eq 0 ]] && echo "  (all commands already installed)"

# Install all skills from core (respect install_mode)
echo "Installing skills..."
echo "   Available: ${AVAILABLE_SKILLS[*]}"
mkdir -p "$TARGET_PATH/.claude/skills"
SKILLS_INSTALLED=0
SKILLS_BACKUP_DIR=""
for skill in "${AVAILABLE_SKILLS[@]}"; do
  if [[ -d "$REPO_ROOT/core/skills/$skill" ]]; then
    # Check if skill not yet installed (neither symlink nor directory)
    if [[ ! -e "$TARGET_PATH/.claude/skills/$skill" ]]; then
      if [[ "$INSTALL_MODE" == "copy" ]]; then
        cp -r "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
      else
        if [[ "$IS_SELF_HOSTED" == true ]]; then
          # Self-hosted: use relative path per PROJECT_AGENTS.md
          (cd "$TARGET_PATH/.claude/skills" && ln -sf "../../core/skills/$skill" "$skill")
        else
          # Cross-project: use absolute path
          ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
        fi
      fi
      echo "  ✓ $skill"
      ((SKILLS_INSTALLED++)) || true
    elif [[ ! -L "$TARGET_PATH/.claude/skills/$skill" && -d "$TARGET_PATH/.claude/skills/$skill" ]]; then
      # Existing directory (not symlink) - backup and replace for symlink mode only
      if [[ "$INSTALL_MODE" != "copy" ]]; then
        if [[ -z "$SKILLS_BACKUP_DIR" ]]; then
          SKILLS_BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)/skills"
          mkdir -p "$SKILLS_BACKUP_DIR"
        fi
        mv "$TARGET_PATH/.claude/skills/$skill" "$SKILLS_BACKUP_DIR/$skill"
        echo "  ⚠ Backed up: $skill → $SKILLS_BACKUP_DIR/$skill"
        if [[ "$IS_SELF_HOSTED" == true ]]; then
          # Self-hosted: use relative path per PROJECT_AGENTS.md
          (cd "$TARGET_PATH/.claude/skills" && ln -sf "../../core/skills/$skill" "$skill")
        else
          # Cross-project: use absolute path
          ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
        fi
        echo "  ✓ $skill (converted to symlink)"
        ((SKILLS_INSTALLED++)) || true
      fi
    fi
  fi
done
[[ $SKILLS_INSTALLED -eq 0 ]] && echo "  (all skills already installed)"

# Install all hooks from core (respect install_mode)
echo "Installing hooks..."
mkdir -p "$TARGET_PATH/.claude/hooks/pretooluse"
HOOKS_INSTALLED=0
for hook_file in "$REPO_ROOT/core/hooks/pretooluse/"*.py; do
  [[ ! -f "$hook_file" ]] && continue
  hook=$(basename "$hook_file")
  if [[ ! -e "$TARGET_PATH/.claude/hooks/pretooluse/$hook" ]]; then
    if [[ "$INSTALL_MODE" == "copy" ]]; then
      cp "$hook_file" "$TARGET_PATH/.claude/hooks/pretooluse/$hook"
    else
      if [[ "$IS_SELF_HOSTED" == true ]]; then
        # Self-hosted: use relative path per PROJECT_AGENTS.md
        (cd "$TARGET_PATH/.claude/hooks/pretooluse" && ln -sf "../../../core/hooks/pretooluse/$hook" "$hook")
      else
        # Cross-project: use absolute path
        ln -sf "$hook_file" "$TARGET_PATH/.claude/hooks/pretooluse/$hook"
      fi
    fi
    echo "  ✓ $hook"
    ((HOOKS_INSTALLED++)) || true
  fi
done
[[ $HOOKS_INSTALLED -eq 0 ]] && echo "  (all hooks already installed)"

# Register hooks in .claude/settings.json (ensure dry-run-guard is configured)
echo "Verifying hook registration in settings.json..."
SETTINGS_FILE="$TARGET_PATH/.claude/settings.json"

# Backup SETTINGS_FILE before modify (if it exists)
if [[ -f "$SETTINGS_FILE" ]]; then
  cp "$SETTINGS_FILE" "$SETTINGS_FILE.bak.$(date +%s)" 2>/dev/null || true
fi

HOOK_CONFIG="{
  \"hooks\": {
    \"PreToolUse\": [
      {
        \"matcher\": \"Write|Edit|NotebookEdit|Bash\",
        \"hooks\": [
          {
            \"type\": \"command\",
            \"command\": \"bash -c 'AGENTIC_ROOT=\\\"\$PWD\\\"; while [ ! -f \\\"\$AGENTIC_ROOT/.agentic-config.json\\\" ] && [ \\\"\$AGENTIC_ROOT\\\" != \\\"/\\\" ]; do AGENTIC_ROOT=\$(dirname \\\"\$AGENTIC_ROOT\\\"); done; cd \\\"\$AGENTIC_ROOT\\\" && uv run --no-project --script .claude/hooks/pretooluse/dry-run-guard.py \\\"\$AGENTIC_ROOT\\\"'\"
          }
        ]
      }
    ]
  }
}"

HOOK_REGISTERED=false
if [[ ! -f "$SETTINGS_FILE" ]]; then
  # Create new settings.json with hook config
  echo "$HOOK_CONFIG" > "$SETTINGS_FILE"
  echo "  ✓ Created settings.json with hook registration"
  HOOK_REGISTERED=true
elif command -v jq &>/dev/null; then
  # Check if hooks.PreToolUse already has dry-run-guard
  if ! jq -e '.hooks.PreToolUse[]?.hooks[]? | select(.command | contains("dry-run-guard"))' "$SETTINGS_FILE" &>/dev/null; then
    # Add our hook configuration
    jq --argjson hook "$HOOK_CONFIG" '
      .hooks = (.hooks // {}) |
      .hooks.PreToolUse = ((.hooks.PreToolUse // []) + $hook.hooks.PreToolUse)
    ' "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp" && mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
    echo "  ✓ Added dry-run-guard hook to settings.json"
    HOOK_REGISTERED=true
  else
    echo "  (hook already registered)"
  fi
else
  # No jq - check if we can detect the hook in the file
  if ! grep -q "dry-run-guard" "$SETTINGS_FILE" 2>/dev/null; then
    echo "  WARNING: Cannot verify hook registration (jq not available)"
    echo "  Ensure dry-run-guard hook is registered in $SETTINGS_FILE"
  else
    echo "  (hook appears to be registered)"
  fi
fi

# Clean up orphaned symlinks
echo "Cleaning up orphaned symlinks..."
ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/commands")
if [[ "${ORPHANS:-0}" -gt 0 ]]; then
  echo "  Cleaned $ORPHANS orphan command symlink(s)"
else
  echo "  (no orphans found)"
fi

ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/skills")
if [[ "${ORPHANS:-0}" -gt 0 ]]; then
  echo "  Cleaned $ORPHANS orphan skill symlink(s)"
fi

# Reconcile config and update version (only after all operations complete)
# Run when: version mismatch, force mode, nightly mode, or maintenance detected missing fields
if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
  if [[ "$FORCE" == true || "${HAS_CONFIG_CHANGES:-false}" == false || "$COPY_MODE_REPLACED" == true ]]; then
    echo "Reconciling configuration..."
    reconcile_config "$TARGET_PATH" "$LATEST_VERSION"
  fi
elif [[ "$NIGHTLY" == true ]]; then
  # Nightly already reconciled above, just confirm
  echo "  (config already reconciled in nightly mode)"
elif [[ "${NEED_MAINTENANCE:-false}" == true ]]; then
  # Same version but maintenance mode detected missing config fields
  echo "Reconciling configuration..."
  reconcile_config "$TARGET_PATH" "$CURRENT_VERSION"
fi

# Refresh path persistence (ensure all locations are up to date)
echo "Refreshing path persistence..."

# Check git availability before git operations
if ! command -v git >/dev/null 2>&1; then
  echo "WARNING: git command not found - skipping git-based validation" >&2
  # Continue anyway - git not required for all operations
fi

if persist_agentic_path "$REPO_ROOT"; then
  echo "  ✓ Path persisted to all locations"
else
  echo "  ⊘ Some persistence locations failed (non-fatal)"
fi

echo ""
echo "Update complete!"
