#!/usr/bin/env bash
set -euo pipefail

# Agentic Configuration Setup Script
# Installs centralized agentic tools configuration to target project

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/detect-project-type.sh"
source "$SCRIPT_DIR/lib/template-processor.sh"
source "$SCRIPT_DIR/lib/version-manager.sh"

# Dynamically discover all available commands from core directory
discover_available_commands() {
  local cmds=()
  for f in "$REPO_ROOT/core/commands/claude/"*.md; do
    [[ ! -f "$f" ]] && continue
    local name=$(basename "$f" .md)
    cmds+=("$name")
  done
  echo "${cmds[@]}"
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
DRY_RUN=false
COPY_MODE=false
NO_REGISTRY=false
TOOLS="all"
PROJECT_TYPE=""

# Usage
usage() {
  cat <<EOF
Usage: setup-config.sh [OPTIONS] <target_path>

Install centralized agentic configuration to a project.

Options:
  --type <ts|py-poetry|py-pip|py-uv|rust|generic>
                         Project type (auto-detected if not specified)
  --copy                 Copy assets instead of creating symlinks
  --force                Overwrite existing configuration
  --dry-run              Show what would be done without making changes
  --no-registry          Don't register installation in central registry
  --tools <claude,gemini,codex,all>
                         Which AI tool configs to install (default: all)
  -h, --help             Show this help message

Examples:
  # Auto-detect and setup
  setup-config.sh ~/projects/my-app

  # Explicit project type
  setup-config.sh --type typescript ~/projects/my-app

  # Dry run to preview
  setup-config.sh --dry-run ~/projects/my-app
EOF
}

# Parse arguments
TARGET_PATH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --type)
      PROJECT_TYPE="$2"
      shift 2
      ;;
    --copy)
      COPY_MODE=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --no-registry)
      NO_REGISTRY=true
      shift
      ;;
    --tools)
      TOOLS="$2"
      shift 2
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

# Validate target path
if [[ -z "$TARGET_PATH" ]]; then
  echo "ERROR: target_path required" >&2
  usage
  exit 1
fi

# Resolve absolute path
if [[ ! -d "$TARGET_PATH" ]]; then
  echo "ERROR: Directory does not exist: $TARGET_PATH" >&2
  exit 1
fi
TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

echo "Agentic Configuration Setup v$VERSION"
echo "   Target: $TARGET_PATH"

# Auto-detect project type if not specified
if [[ -z "$PROJECT_TYPE" ]]; then
  PROJECT_TYPE=$(detect_project_type "$TARGET_PATH")
  echo "   Detected type: $PROJECT_TYPE"
else
  echo "   Type: $PROJECT_TYPE"
fi

# Validate template exists
TEMPLATE_DIR="$REPO_ROOT/templates/$PROJECT_TYPE"
if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "ERROR: No template for project type: $PROJECT_TYPE" >&2
  echo "   Available: typescript, python-poetry, python-pip, python-uv, rust, generic" >&2
  exit 1
fi

# Check for existing installation
if [[ -L "$TARGET_PATH/agents" || -f "$TARGET_PATH/.agentic-config.json" ]]; then
  EXISTING_VERSION=$(check_version "$TARGET_PATH")
  if [[ "$FORCE" != true ]]; then
    echo "WARNING: Existing installation detected (version: $EXISTING_VERSION)"
    echo "   Use --force to overwrite or run update-config.sh to update"
    exit 0
  fi
  echo "   Overwriting existing installation (version: $EXISTING_VERSION)"
fi

# Preserve custom content from existing config files into PROJECT_AGENTS.md
preserve_custom_content() {
  local target="$1"
  local preserved_content=""
  local source_file=""

  # Check AGENTS.md (if real file, not symlink)
  if [[ -f "$target/AGENTS.md" && ! -L "$target/AGENTS.md" ]]; then
    source_file="$target/AGENTS.md"
  # Check CLAUDE.md (if real file, not symlink)
  elif [[ -f "$target/CLAUDE.md" && ! -L "$target/CLAUDE.md" ]]; then
    source_file="$target/CLAUDE.md"
  # Check GEMINI.md (if real file, not symlink)
  elif [[ -f "$target/GEMINI.md" && ! -L "$target/GEMINI.md" ]]; then
    source_file="$target/GEMINI.md"
  fi

  if [[ -n "$source_file" ]]; then
    preserved_content=$(cat "$source_file")

    # Skip if empty or just whitespace
    if [[ -z "${preserved_content// /}" ]]; then
      return 0
    fi

    # Check if PROJECT_AGENTS.md already exists
    if [[ -f "$target/PROJECT_AGENTS.md" ]]; then
      echo "   PROJECT_AGENTS.md already exists, appending preserved content"
      if [[ "$DRY_RUN" != true ]]; then
        {
          echo ""
          echo "<!-- Preserved from pre-existing $(basename "$source_file") -->"
          echo ""
          echo "$preserved_content"
        } >> "$target/PROJECT_AGENTS.md"
      fi
    else
      echo "   Creating PROJECT_AGENTS.md with preserved content from $(basename "$source_file")"
      if [[ "$DRY_RUN" != true ]]; then
        {
          echo "# Project-Specific Guidelines"
          echo ""
          echo "<!-- Preserved from pre-existing $(basename "$source_file") -->"
          echo ""
          echo "$preserved_content"
        } > "$target/PROJECT_AGENTS.md"
      fi
    fi
    return 0
  fi
  return 1
}

# Preserve custom content BEFORE backup/overwrite
CONTENT_PRESERVED=false
if [[ -f "$TARGET_PATH/AGENTS.md" && ! -L "$TARGET_PATH/AGENTS.md" ]] || \
   [[ -f "$TARGET_PATH/CLAUDE.md" && ! -L "$TARGET_PATH/CLAUDE.md" ]] || \
   [[ -f "$TARGET_PATH/GEMINI.md" && ! -L "$TARGET_PATH/GEMINI.md" ]]; then
  echo "Preserving custom content..."
  if preserve_custom_content "$TARGET_PATH"; then
    CONTENT_PRESERVED=true
  fi
fi

# Backup existing files if they exist
BACKED_UP=false
if [[ -e "$TARGET_PATH/agents" || -e "$TARGET_PATH/.agent" || -e "$TARGET_PATH/AGENTS.md" ]]; then
  BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)"
  echo "Creating backup: $BACKUP_DIR"

  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$BACKUP_DIR"
    [[ -e "$TARGET_PATH/agents" ]] && mv "$TARGET_PATH/agents" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/.agent" ]] && mv "$TARGET_PATH/.agent" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/AGENTS.md" ]] && mv "$TARGET_PATH/AGENTS.md" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/CLAUDE.md" ]] && rm "$TARGET_PATH/CLAUDE.md" 2>/dev/null || true
    [[ -e "$TARGET_PATH/GEMINI.md" ]] && rm "$TARGET_PATH/GEMINI.md" 2>/dev/null || true
    BACKED_UP=true
  fi
fi

# Create core symlinks
echo "Creating core symlinks..."
if [[ "$DRY_RUN" != true ]]; then
  if [[ "$COPY_MODE" == true ]]; then
    echo "   (copy mode: copying agents/ directory)"
    cp -r "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
  else
    ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
  fi
  mkdir -p "$TARGET_PATH/.agent/workflows"
  if [[ "$COPY_MODE" == true ]]; then
    cp "$REPO_ROOT/core/agents/spec-command.md" "$TARGET_PATH/.agent/workflows/spec.md"
  else
    ln -sf "$REPO_ROOT/core/agents/spec-command.md" "$TARGET_PATH/.agent/workflows/spec.md"
  fi
fi

# Install templates
echo "Installing config templates ($PROJECT_TYPE)..."
if [[ "$DRY_RUN" != true ]]; then
  process_template "$TEMPLATE_DIR/.agent/config.yml.template" "$TARGET_PATH/.agent/config.yml"
  process_template "$TEMPLATE_DIR/AGENTS.md.template" "$TARGET_PATH/AGENTS.md"
fi

# Create local symlinks
echo "Creating local symlinks..."
if [[ "$DRY_RUN" != true ]]; then
  ln -sf AGENTS.md "$TARGET_PATH/CLAUDE.md"
  ln -sf AGENTS.md "$TARGET_PATH/GEMINI.md"
fi

# Create .gitignore if not exists
if [[ ! -f "$TARGET_PATH/.gitignore" ]]; then
  echo "Creating default .gitignore..."
  if [[ "$DRY_RUN" != true ]]; then
    cp "$REPO_ROOT/templates/shared/.gitignore.template" "$TARGET_PATH/.gitignore"
  fi
fi

# Add copy-backup pattern to .gitignore if using copy mode
if [[ "$COPY_MODE" == true && -f "$TARGET_PATH/.gitignore" ]]; then
  if ! grep -q "\.agentic-config\.copy-backup\." "$TARGET_PATH/.gitignore"; then
    echo "Adding copy-backup pattern to .gitignore..."
    if [[ "$DRY_RUN" != true ]]; then
      echo ".agentic-config.copy-backup.*" >> "$TARGET_PATH/.gitignore"
    fi
  fi
fi

# Initialize git if not inside any git repo (including parent repos)
if ! git -C "$TARGET_PATH" rev-parse --is-inside-work-tree &>/dev/null; then
  echo "Initializing git repository..."
  if [[ "$DRY_RUN" != true ]]; then
    git -C "$TARGET_PATH" init --quiet
  fi
fi

# Install AI tool configs
if [[ "$TOOLS" == "all" || "$TOOLS" == *"claude"* ]]; then
  echo "Installing Claude configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.claude/commands"
    if [[ "$COPY_MODE" == true ]]; then
      cp "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
    else
      ln -sf "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
    fi
  fi
fi

if [[ "$TOOLS" == "all" || "$TOOLS" == *"gemini"* ]]; then
  echo "Installing Gemini configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.gemini/commands"
    if [[ "$COPY_MODE" == true ]]; then
      cp "$REPO_ROOT/core/commands/gemini/spec.toml" "$TARGET_PATH/.gemini/commands/spec.toml"
      cp -r "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
    else
      ln -sf "$REPO_ROOT/core/commands/gemini/spec.toml" "$TARGET_PATH/.gemini/commands/spec.toml"
      ln -sf "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
    fi
  fi
fi

if [[ "$TOOLS" == "all" || "$TOOLS" == *"codex"* ]]; then
  echo "Installing Codex configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.codex/prompts"
    if [[ "$COPY_MODE" == true ]]; then
      cp "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
    else
      ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
    fi
  fi
fi

# Install agentic management agents
echo "Installing agentic management agents..."
if [[ "$DRY_RUN" != true ]]; then
  # Create agent symlinks
  mkdir -p "$TARGET_PATH/.claude/agents"
  for agent_file in "$REPO_ROOT/core/agents/agentic-"*.md; do
    [[ ! -f "$agent_file" ]] && continue
    agent=$(basename "$agent_file" .md)
    if [[ "$COPY_MODE" == true ]]; then
      cp "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
    else
      ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
    fi
  done
fi

# Install all commands from core
echo "Installing commands..."
echo "   Available: ${AVAILABLE_CMDS[*]}"
if [[ "$DRY_RUN" != true ]]; then
  mkdir -p "$TARGET_PATH/.claude/commands"
  for cmd in "${AVAILABLE_CMDS[@]}"; do
    if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]]; then
      if [[ "$COPY_MODE" == true ]]; then
        cp "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
      else
        ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
      fi
    fi
  done
fi

# Install all skills from core
echo "Installing skills..."
echo "   Available: ${AVAILABLE_SKILLS[*]}"
if [[ "$DRY_RUN" != true ]]; then
  mkdir -p "$TARGET_PATH/.claude/skills"
  for skill in "${AVAILABLE_SKILLS[@]}"; do
    if [[ -d "$REPO_ROOT/core/skills/$skill" ]]; then
      # Backup existing dir (not symlink) before replacing to preserve local customizations
      if [[ -d "$TARGET_PATH/.claude/skills/$skill" && ! -L "$TARGET_PATH/.claude/skills/$skill" ]]; then
        if [[ -z "${BACKUP_DIR:-}" ]]; then
          BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)"
          mkdir -p "$BACKUP_DIR"
          BACKED_UP=true
        fi
        mkdir -p "$BACKUP_DIR/skills"
        mv "$TARGET_PATH/.claude/skills/$skill" "$BACKUP_DIR/skills/$skill"
        echo "   Backed up: $skill"
        # Verify backup was successful before proceeding
        if [[ ! -d "$BACKUP_DIR/skills/$skill" ]]; then
          echo "   WARNING: Backup verification failed for skill $skill - skipping replacement"
          continue
        fi
      fi
      rm -rf "$TARGET_PATH/.claude/skills/$skill" 2>/dev/null
      if [[ "$COPY_MODE" == true ]]; then
        cp -r "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
      else
        ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
      fi
    fi
  done
fi

# Register installation
if [[ "$NO_REGISTRY" != true && "$DRY_RUN" != true ]]; then
  echo "Registering installation..."
  if [[ "$COPY_MODE" == true ]]; then
    register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION" "copy"
  else
    register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION" "symlink"
  fi
fi

# Summary
echo ""
echo "Setup complete!"
echo "   Version: $VERSION"
echo "   Type: $PROJECT_TYPE"
[[ "$COPY_MODE" == true ]] && echo "   Mode: copy (assets copied, not symlinked)"
[[ "$CONTENT_PRESERVED" == true ]] && echo "   Preserved: Custom content moved to PROJECT_AGENTS.md"
[[ "$BACKED_UP" == true ]] && echo "   Backup: $BACKUP_DIR"
[[ "$DRY_RUN" == true ]] && echo "   (DRY RUN - no changes made)"
echo ""
echo "Next steps:"
echo "  1. Review PROJECT_AGENTS.md for project-specific guidelines"
echo "  2. Test with: cd $TARGET_PATH && /spec RESEARCH <spec_path>"
echo "  3. Try /orc, /spawn, /pull_request commands"
echo "  See documentation: $REPO_ROOT/README.md"
