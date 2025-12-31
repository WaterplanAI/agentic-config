#!/usr/bin/env bash
# Agentic-Config Installer
# Usage: curl -sL https://raw.githubusercontent.com/MatiasComercio/agentic-config/main/install.sh | bash
#        curl -sL ... | bash -s -- /custom/path  # Custom install location
#        curl -sL ... | bash -s -- --dry-run     # Preview mode
#        curl -sL ... | bash -s -- --nightly     # Skip git reset (use local state)
set -euo pipefail

# Parse arguments
DRY_RUN=false
NIGHTLY=false
DEST_PATH=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --nightly) NIGHTLY=true ;;
    -*) ;; # Ignore other flags
    *) DEST_PATH="$arg" ;;  # Positional argument = destination path
  esac
done

# Configuration (override via environment variables or positional argument)
# AGENTIC_CONFIG_DIR: Installation directory (default: ~/.agents/agentic-config)
# AGENTIC_CONFIG_REPO: Git repository URL (default: https://github.com/MatiasComercio/agentic-config.git)
# AGENTIC_CONFIG_BRANCH: Git branch to install (default: main)
# Positional argument takes precedence over environment variable
if [[ -n "$DEST_PATH" ]]; then
  AGENTIC_CONFIG_DIR="$DEST_PATH"
fi
INSTALL_DIR="${AGENTIC_CONFIG_DIR:-$HOME/.agents/agentic-config}"
REPO_URL="${AGENTIC_CONFIG_REPO:-https://github.com/MatiasComercio/agentic-config.git}"
BRANCH="${AGENTIC_CONFIG_BRANCH:-main}"

# Colors (disabled if not TTY)
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' NC=''
fi

abort() {
  printf "${RED}ERROR: %s${NC}\n" "$1" >&2
  exit 1
}

info() {
  printf "${BLUE}==> ${NC}%s\n" "$1"
}

success() {
  printf "${GREEN}==> ${NC}%s\n" "$1"
}

warn() {
  printf "${YELLOW}==> ${NC}%s\n" "$1"
}

# Pre-flight checks: ensure git is installed
command -v git >/dev/null 2>&1 || abort "git is required but not installed"

info "Agentic-Config Installer"
if $DRY_RUN; then
  warn "DRY-RUN MODE: No changes will be made"
fi
if $NIGHTLY; then
  warn "NIGHTLY MODE: Skipping git reset (using local state)"
fi
echo ""

# Determine OS - only macOS (Darwin) and Linux are supported
OS="$(uname -s)"
case "$OS" in
  Darwin|Linux) ;;
  *) abort "Unsupported operating system: $OS" ;;
esac

# Create parent directory if needed
PARENT_DIR="$(dirname "$INSTALL_DIR")"
if [[ ! -d "$PARENT_DIR" ]]; then
  info "Creating directory: $PARENT_DIR"
  $DRY_RUN || mkdir -p "$PARENT_DIR"
fi

# Clone or update: detect existing installation by checking for .git directory
# If .git exists: fetch latest and reset hard (discards local changes) unless --nightly
# If directory exists but no .git: backup and clone fresh
# Otherwise: clone to new directory
if [[ -d "$INSTALL_DIR/.git" ]]; then
  if $NIGHTLY; then
    info "Using existing installation (nightly mode)..."
    cd "$INSTALL_DIR"
    success "Using local state"
  else
    info "Updating existing installation..."
    if $DRY_RUN; then
      info "Would: git fetch + reset --hard origin/$BRANCH + git clean"
    else
      cd "$INSTALL_DIR"
      git fetch origin "$BRANCH" --quiet
      git reset --hard "origin/$BRANCH" --quiet
      git clean -fd --quiet
    fi
    success "Updated to latest version"
  fi
else
  if [[ -d "$INSTALL_DIR" ]]; then
    warn "Directory exists but is not a git repo: $INSTALL_DIR"
    warn "Backing up to ${INSTALL_DIR}.backup"
    $DRY_RUN || mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d%H%M%S)"
  fi
  info "Cloning agentic-config to $INSTALL_DIR..."
  if $DRY_RUN; then
    info "Would: git clone $REPO_URL -> $INSTALL_DIR"
  else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi
  success "Cloned successfully"
fi

# Run global install: creates symlinks in ~/.claude/commands/ and updates ~/.claude/CLAUDE.md
info "Installing global commands..."
if $DRY_RUN; then
  info "Would: run install-global.sh (symlinks to ~/.claude/commands/)"
else
  cd "$INSTALL_DIR"
  if ! AGENTIC_CONFIG_PATH="$INSTALL_DIR" ./scripts/install-global.sh; then
    abort "install-global.sh failed"
  fi
fi

# Persist AGENTIC_CONFIG_PATH to all locations
info "Persisting AGENTIC_CONFIG_PATH..."
if $DRY_RUN; then
  info "Would: persist path to ~/.agents/.path, shell profile, and XDG config"
else
  if ! source "$INSTALL_DIR/scripts/lib/path-persistence.sh" || ! persist_agentic_path "$INSTALL_DIR"; then
    warn "Some persistence locations failed (non-fatal)"
  fi
fi

# Reconcile self-hosted config (if this is the agentic-config repo itself)
if [[ -f "$INSTALL_DIR/.agentic-config.json" ]]; then
  info "Reconciling self-hosted configuration..."
  if $DRY_RUN; then
    info "Would: update-config.sh --nightly $INSTALL_DIR"
  else
    NIGHTLY_FLAG=""
    $NIGHTLY && NIGHTLY_FLAG="--nightly"
    if ! AGENTIC_CONFIG_PATH="$INSTALL_DIR" "$INSTALL_DIR/scripts/update-config.sh" $NIGHTLY_FLAG "$INSTALL_DIR"; then
      warn "Self-hosted config reconciliation failed (non-fatal)"
    fi
  fi
fi

echo ""
if $DRY_RUN; then
  success "Dry-run complete! Run without --dry-run to install."
else
  success "Installation complete!"
fi
echo ""
printf "${GREEN}Next steps:${NC}\n"
echo "  1. Open Claude Code in any project:"
echo "     claude"
echo ""
echo "  2. Try these commands:"
echo "     /agentic setup    - Setup agentic-config in current project"
echo "     /agentic status   - Show all installations"
echo ""
echo "  3. For orchestrated workflows:"
echo "     /o_spec           - Run orchestrated spec workflow"
echo "     /spec CREATE      - Create a new spec"
echo ""
printf "Documentation: ${BLUE}https://github.com/MatiasComercio/agentic-config${NC}\n"
printf "Install location: ${BLUE}$INSTALL_DIR${NC}\n"
