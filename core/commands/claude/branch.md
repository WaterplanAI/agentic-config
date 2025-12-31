---
description: Create new branch with spec directory structure
argument-hint: <branch-name>
allowed-tools:
  - Bash
  - Write
---

# Create Branch with Spec Directory

Create a new git branch and its corresponding spec directory.

## Pre-Flight Checks

1. **Verify clean git state**:
   - If dirty: STOP and list uncommitted changes

2. **Validate branch name**:
   - Must be provided as argument
   - If empty: STOP with "Branch name required"

## Execution

1. **Create and checkout branch**:
   ```bash
   git checkout -b $ARGUMENTS
   ```

2. **Resolve and create spec directory**:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Resolve spec path (handles external vs local)
   RELATIVE_PATH="$(date +%Y)/$(date +%m)/$ARGUMENTS/000-backlog.md"
   SPEC_FILE=$(resolve_spec_path "$RELATIVE_PATH")
   SPEC_DIR="${SPEC_FILE%/*}"  # Pure bash dirname equivalent

   # Create backlog file
   touch "$SPEC_FILE"
   ```
   - Path: Auto-resolved based on .env configuration
     - External: `.specs/specs/<YYYY>/<MM>/<branch-name>/`
     - Local: `specs/<YYYY>/<MM>/<branch-name>/`
   - Creates `000-backlog.md` (empty file)

3. **Commit spec directory**:
   ```bash
   # Extract NNN and title for commit_spec_changes
   # For backlog, use "000" and "backlog"
   commit_spec_changes "$SPEC_FILE" "CREATE" "000" "backlog"
   ```
   - **CRITICAL**: Must commit BEFORE creating worktree, otherwise spec files are lost

4. **Confirm**:
   ```
   - Branch: $ARGUMENTS
   - Spec dir: <resolved-path>
   - Backlog: 000-backlog.md (committed)
   ```
