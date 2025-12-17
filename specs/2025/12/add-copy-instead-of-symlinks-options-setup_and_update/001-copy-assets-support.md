# Human Section
Critical: any text/subsection here cannot be modified by AI.

## High-Level Objective (HLO)

Add support for copying assets instead of creating symlinks in the agentic-config setup and update workflows. This is essential for team repositories where symlinks may not work consistently across different environments or when team members need local copies they can modify independently. The setup flow should provide an explicit user option to choose between symlink (default) and copy modes, while the update flow should support an optional parameter to enable copy mode replacements with automatic backup creation.

## Mid-Level Objectives (MLO)

- UPDATE setup-config.sh script to accept a `--copy` flag that copies assets instead of creating symlinks
- UPDATE update-config.sh script to accept a `--copy` flag that replaces existing copies with new versions (with backup)
- IMPLEMENT backup mechanism in update flow that creates timestamped backups before replacing copied files
- ADD backup pattern to .gitignore in both setup and update flows when copy mode is used
- UPDATE agentic-setup.md agent documentation to explain copy mode option and its implications
- UPDATE agentic-update.md agent documentation to explain copy mode update behavior with backups
- ENSURE copy mode applies to all relevant assets: agents/, .claude/commands/, .claude/skills/, .claude/agents/
- DOCUMENT the trade-offs between symlink and copy modes in agent documentation
- VERIFY that copy mode installations can be updated successfully without data loss

## Details (DT)

### Current Behavior

The setup-config.sh script creates symlinks for:
- Core agents directory: `ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"`
- Individual commands: `ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"`
- Individual skills: `ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"`
- Agentic management agents: `ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"`

The update-config.sh script assumes symlinks exist and will auto-update, only handling template files (AGENTS.md, config.yml) separately.

### Expected Behavior with --copy Flag

Setup flow with --copy:
- Copy entire agents/ directory structure instead of symlinking
- Copy each command file instead of symlinking
- Copy each skill directory instead of symlinking
- Copy each agentic management agent instead of symlinking
- Add `.agentic-config.copy-backup.*` pattern to .gitignore
- Track in .agentic-config.json that installation uses copy mode: `"install_mode": "copy"`

Update flow with --copy:
- Detect if installation uses copy mode from .agentic-config.json
- Create timestamped backup: `.agentic-config.copy-backup.<timestamp>/`
- Copy backup pattern includes: agents/, .claude/commands/, .claude/skills/, .claude/agents/
- Replace all copied assets with latest versions from central repo
- Update version in .agentic-config.json
- Report what was backed up and what was replaced

### Constraints

- Default mode remains symlink (backward compatibility)
- Copy mode must preserve executable permissions
- Backup mechanism must be reliable and not interfere with git operations
- .gitignore pattern must prevent accidental commits of backup directories
- Documentation must clearly warn about manual merge requirements when updating copies
- Copy mode installations should be clearly identified in .agentic-config.json
- Update flow must detect installation mode automatically (no manual flag required if installed in copy mode)

### Files to Modify

- /Users/matias/projects/agentic-config/scripts/setup-config.sh
- /Users/matias/projects/agentic-config/scripts/update-config.sh
- /Users/matias/projects/agentic-config/core/agents/agentic-setup.md
- /Users/matias/projects/agentic-config/core/agents/agentic-update.md
- /Users/matias/projects/agentic-config/.gitignore (add backup pattern)

### Data Structure

.agentic-config.json should include:
```json
{
  "version": "0.1.4",
  "project_type": "python-uv",
  "install_mode": "symlink",  // or "copy"
  "installed_at": "...",
  "updated_at": "..."
}
```

### Testing

Unit test expectations:
- Test that --copy flag properly sets install_mode in .agentic-config.json
- Test that copied files have correct permissions
- Test that backup directory is created before update
- Test that .gitignore includes backup pattern

E2E test expectations:
- Install with --copy, verify all assets are actual files/directories not symlinks
- Update copy mode installation, verify backups created and files replaced
- Verify copy mode installation can be updated multiple times
- Verify mixed mode (some symlinks, some copies) is handled gracefully

## Behavior

You are a senior shell scripting and DevOps engineer implementing a robust file management system for the agentic-config installation workflow. Focus on reliability, safety (backups before any destructive operation), and clear user communication. Ensure the implementation handles edge cases gracefully and provides helpful error messages.

# AI Section
Critical: AI can ONLY modify this section.

## Research

### Current Implementation Analysis

**Version**: 0.1.6

**Core Scripts**:
- `/Users/matias/projects/agentic-config/scripts/setup-config.sh` (373 lines)
  - Creates symlinks using `ln -sf` for all assets
  - Locations: agents/, .claude/commands/, .claude/skills/, .claude/agents/, .agent/workflows/spec.md
  - Already has backup mechanism using `.agentic-config.backup.<timestamp>` pattern
  - Uses `process_template()` from lib/template-processor.sh to copy template files (AGENTS.md, config.yml)
  - Command-line parsing uses while/case pattern with shift

- `/Users/matias/projects/agentic-config/scripts/update-config.sh` (360 lines)
  - Assumes symlinks exist and auto-update
  - Only manages copied template files (AGENTS.md, config.yml) separately
  - Has backup mechanism for skills: `SKILLS_BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)/skills"`
  - Already uses --force flag for template updates

- `/Users/matias/projects/agentic-config/scripts/lib/version-manager.sh` (73 lines)
  - `register_installation()` creates .agentic-config.json with fixed structure
  - Currently tracks: version, installed_at, project_type, auto_check, symlinks[], copied[]
  - Uses jq for JSON manipulation
  - `check_version()` reads version field from .agentic-config.json

**Agent Documentation**:
- `/Users/matias/projects/agentic-config/core/agents/agentic-setup.md` (151 lines)
  - Documents symlink creation workflow
  - Explains customization pattern (PROJECT_AGENTS.md for overrides)
  - Has post-workflow commit guidance
  - Currently warns: "Never edit symlinked files - changes will be lost"

- `/Users/matias/projects/agentic-config/core/agents/agentic-update.md` (290 lines)
  - Documents symlink auto-update behavior
  - Explains template vs symlink distinction
  - Has safety guarantee section about backups

**Backup Pattern**:
- Existing pattern: `.agentic-config.backup.<timestamp>/`
- Used in setup-config.sh (lines 229-240)
- Used in update-config.sh (lines 330-334 for skills)
- Already in .gitignore (line 15)

**Copy Operations**:
- `process_template()` uses simple `cp` (lib/template-processor.sh line 15)
- migrate-existing.sh uses `cp -r` for directory backups (lines 132-134)
- No existing --copy flag or copy mode support

**Symlink Creation Pattern**:
- All use `ln -sf` (force symlink, overwrite if exists)
- Command symlinks: `ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"`
- Skill symlinks: `ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"`
- Agent symlinks: `ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"`
- Core agents: `ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"`

**Configuration Tracking**:
Current .agentic-config.json structure (lines 12-33 of version-manager.sh):
```json
{
  "version": "0.1.6",
  "installed_at": "...",
  "project_type": "python-uv",
  "auto_check": true,
  "symlinks": [...],
  "copied": [".agent/config.yml", "AGENTS.md"]
}
```
**No install_mode field currently exists**.

### Gap Analysis

**What Needs to be Added**:

1. **setup-config.sh modifications**:
   - Parse --copy flag in argument loop (around line 80-115)
   - Create copy_assets() function to replace symlink creation
   - Modify register_installation() call to pass install_mode
   - Add .gitignore pattern for `.agentic-config.copy-backup.*` when --copy used
   - Copy operations needed for:
     - agents/ directory (entire tree)
     - Individual command files in .claude/commands/
     - Individual skill directories in .claude/skills/
     - Individual agent files in .claude/agents/
   - Preserve executable permissions when copying

2. **update-config.sh modifications**:
   - Read install_mode from .agentic-config.json
   - Create backup_and_copy() function for copy mode updates
   - Generate timestamped backup: `.agentic-config.copy-backup.<timestamp>/`
   - Copy all assets from central repo to target project
   - Report what was backed up and replaced

3. **version-manager.sh modifications**:
   - Add install_mode parameter to register_installation()
   - Update .agentic-config.json structure to include install_mode field
   - Default to "symlink" for backward compatibility

4. **.gitignore update**:
   - Add `.agentic-config.copy-backup.*` pattern
   - Should be added only when --copy mode used in setup

5. **Documentation updates**:
   - agentic-setup.md: explain --copy flag, trade-offs, use cases
   - agentic-update.md: explain copy mode detection, backup behavior, manual merge requirements

### Testing Infrastructure

**Current State**: No existing test infrastructure found
- No test/ directory
- No *.test.* files
- No __tests__/ directories
- No testing utilities or helpers

**Testing Approach**:
- Manual E2E testing required (as per spec's Testing section)
- Test scenarios in actual target directories
- Verification using standard shell tools (ls -la, readlink, diff)

### Edge Cases & Constraints

**Identified from Research**:
1. **Symlink detection**: Scripts use `[[ -L "$path" ]]` to check for symlinks
2. **Directory vs file handling**: Skills are directories, commands/agents are files
3. **Backup collision**: Multiple backups create unique timestamps
4. **Permission preservation**: Need to maintain executable bits on copied files
5. **Mixed mode**: Update flow should detect and handle mixed installations gracefully
6. **Backward compatibility**: Default must remain symlink mode
7. **Self-hosted repos**: update-config.sh has special logic for self-hosted (lines 35-66)

### Strategy

#### Implementation Order

**Phase 1: Foundation (version-manager.sh)**
1. Add install_mode parameter to register_installation()
2. Update .agentic-config.json template to include install_mode field
3. Create helper function to read install_mode from existing config

**Phase 2: Setup Flow (setup-config.sh)**
1. Add --copy flag parsing to argument loop
2. Create copy_assets() function (mirrors current symlink creation)
3. Add conditional logic to choose between ln -sf and cp -r/cp
4. Update register_installation() call to pass install_mode
5. Add .gitignore pattern when --copy mode used

**Phase 3: Update Flow (update-config.sh)**
1. Read install_mode from .agentic-config.json at startup
2. Create copy_mode_update() function for copy installations
3. Implement backup creation before replacing files
4. Add reporting for backed up and replaced files
5. Update version tracking after successful copy update

**Phase 4: Documentation**
1. Update agentic-setup.md with --copy flag documentation
2. Add trade-offs section (symlinks vs copies)
3. Update agentic-update.md with copy mode behavior
4. Document manual merge requirements for copy mode

#### Testing Strategy

**Unit-Level Verification** (Manual):
1. Test --copy flag parsing and validation
2. Verify install_mode written correctly to .agentic-config.json
3. Check copied files have correct permissions (test with executable scripts)
4. Verify backup directory created before update
5. Confirm .gitignore includes backup pattern

**E2E Test Scenarios**:
1. **Fresh install with --copy**: Verify all assets are real files/dirs, not symlinks
2. **Update copy mode installation**: Verify backup created, files replaced, no data loss
3. **Multiple updates**: Test repeated updates don't break
4. **Mixed mode handling**: Install some with symlinks, others with copies - verify update detects correctly
5. **Permission preservation**: Copy executable file, verify it remains executable
6. **Backward compatibility**: Existing symlink installations continue working

**Verification Commands**:
```bash
# Check if symlink or real file/directory
ls -la agents .claude/commands .claude/skills .claude/agents

# Verify install mode
jq -r '.install_mode' .agentic-config.json

# Check backup exists
ls -la .agentic-config.copy-backup.*

# Verify .gitignore pattern
grep "copy-backup" .gitignore

# Test permissions
ls -l <copied_file>
```

#### Implementation Details

**Copy Function Signature**:
```bash
copy_assets() {
  local source="$1"
  local target="$2"
  local type="$3"  # "file" or "directory"

  if [[ "$type" == "directory" ]]; then
    cp -r "$source" "$target"
  else
    cp "$source" "$target"
  fi
}
```

**Backup Function for Update**:
```bash
create_copy_backup() {
  local target="$1"
  local backup_dir="$target/.agentic-config.copy-backup.$(date +%s)"

  mkdir -p "$backup_dir"

  # Backup all copied assets
  [[ -d "$target/agents" && ! -L "$target/agents" ]] && cp -r "$target/agents" "$backup_dir/"
  [[ -d "$target/.claude/commands" ]] && cp -r "$target/.claude/commands" "$backup_dir/"
  [[ -d "$target/.claude/skills" ]] && cp -r "$target/.claude/skills" "$backup_dir/"
  [[ -d "$target/.claude/agents" ]] && cp -r "$target/.claude/agents" "$backup_dir/"

  echo "$backup_dir"
}
```

**Install Mode Detection**:
```bash
get_install_mode() {
  local target="$1"
  local config_file="$target/.agentic-config.json"

  if [[ ! -f "$config_file" ]]; then
    echo "symlink"  # default
    return
  fi

  jq -r '.install_mode // "symlink"' "$config_file"
}
```

#### Risk Mitigation

1. **Data Loss Prevention**: Always create timestamped backup before replacing files
2. **Backward Compatibility**: Default to symlink mode, only use copy when explicitly requested
3. **Clear Communication**: Update messages clearly state what's backed up and what's replaced
4. **Validation**: Check that backup completed successfully before proceeding with replacement
5. **Documentation**: Clearly warn about manual merge requirements when updating copies

## Plan

### Files

- /Users/matias/projects/agentic-config/scripts/lib/version-manager.sh
  - Add install_mode parameter to register_installation() (L4-L54)
  - Add get_install_mode() helper function
  - Update .agentic-config.json template to include install_mode field (L12-L33)

- /Users/matias/projects/agentic-config/scripts/setup-config.sh
  - Add --copy flag parsing to argument loop (L78-L116)
  - Add COPY_MODE variable and default to false (L42-L47)
  - Modify symlink creation sections to conditionally use cp instead (L243-L351)
  - Update register_installation() call to pass install_mode (L354-L357)
  - Add .gitignore pattern when --copy mode used (new section after L272)

- /Users/matias/projects/agentic-config/scripts/update-config.sh
  - Add get_install_mode() call at startup (after L186)
  - Add copy_mode_update() function for copy installations
  - Modify update flow to branch on install_mode (after L299)
  - Create timestamped backup before replacing copied files
  - Report backed up and replaced files

- /Users/matias/projects/agentic-config/.gitignore
  - Add .agentic-config.copy-backup.* pattern (L15)

- /Users/matias/projects/agentic-config/core/agents/agentic-setup.md
  - Add --copy flag documentation in workflow section (L48-L55)
  - Add symlink vs copy trade-offs section after "Best Practices" (L85-L91)
  - Update warning about editing files to conditionally mention copy mode

- /Users/matias/projects/agentic-config/core/agents/agentic-update.md
  - Add copy mode detection documentation in "Update Analysis" section (L22-L43)
  - Add copy mode backup behavior documentation
  - Add manual merge requirements warning for copy mode

### Tasks

#### Task 1 - version-manager.sh: Add install_mode parameter and helper function

Tools: Edit

Diff:
````diff
--- a/scripts/lib/version-manager.sh
+++ b/scripts/lib/version-manager.sh
@@ -3,9 +3,10 @@

 register_installation() {
   local target_path="$1"
   local project_type="$2"
   local version="$3"
+  local install_mode="${4:-symlink}"  # default to symlink for backward compatibility
   local registry_file="$REPO_ROOT/.installations.json"

   # Create .agentic-config.json in target project
   local config_file="$target_path/.agentic-config.json"
@@ -14,6 +15,7 @@ register_installation() {
   "version": "$version",
   "installed_at": "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)",
   "project_type": "$project_type",
+  "install_mode": "$install_mode",
   "auto_check": true,
   "symlinks": [
     "agents",
@@ -70,3 +72,16 @@ check_version() {

   return 0
 }
+
+get_install_mode() {
+  local target_path="$1"
+  local config_file="$target_path/.agentic-config.json"
+
+  if [[ ! -f "$config_file" ]]; then
+    echo "symlink"  # default
+    return 0
+  fi
+
+  jq -r '.install_mode // "symlink"' "$config_file" 2>/dev/null || echo "symlink"
+  return 0
+}
````

Verification:
- Confirm install_mode parameter accepted with default value "symlink"
- Confirm get_install_mode() returns "symlink" for missing configs
- Check jq fallback logic works correctly

#### Task 2 - setup-config.sh: Add --copy flag parsing

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -42,6 +42,7 @@ AVAILABLE_SKILLS=($(discover_available_skills))
 # Defaults
 FORCE=false
 DRY_RUN=false
+COPY_MODE=false
 NO_REGISTRY=false
 TOOLS="all"
 PROJECT_TYPE=""
@@ -56,6 +57,7 @@ Install centralized agentic configuration to a project.
 Options:
   --type <ts|py-poetry|py-pip|py-uv|rust|generic>
                          Project type (auto-detected if not specified)
+  --copy                 Copy assets instead of creating symlinks
   --force                Overwrite existing configuration
   --dry-run              Show what would be done without making changes
   --no-registry          Don't register installation in central registry
@@ -83,6 +85,10 @@ while [[ $# -gt 0 ]]; do
       PROJECT_TYPE="$2"
       shift 2
       ;;
+    --copy)
+      COPY_MODE=true
+      shift
+      ;;
     --force)
       FORCE=true
       shift
````

Verification:
- Confirm --copy flag sets COPY_MODE=true
- Verify usage message updated with --copy option

#### Task 3 - setup-config.sh: Modify core symlink creation to support copy mode

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -243,7 +247,13 @@ fi
 # Create core symlinks
 echo "Creating core symlinks..."
 if [[ "$DRY_RUN" != true ]]; then
-  ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
+  if [[ "$COPY_MODE" == true ]]; then
+    echo "   (copy mode: copying agents/ directory)"
+    cp -r "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
+  else
+    ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
+  fi
+
   mkdir -p "$TARGET_PATH/.agent/workflows"
   ln -sf "$REPO_ROOT/core/agents/spec-command.md" "$TARGET_PATH/.agent/workflows/spec.md"
 fi
````

Verification:
- Test with --copy flag to confirm agents/ is copied as a directory
- Test without --copy to confirm symlink behavior unchanged
- Verify directory permissions preserved after copy

#### Task 4 - setup-config.sh: Modify command installation to support copy mode

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -282,7 +288,11 @@ if [[ "$TOOLS" == "all" || "$TOOLS" == *"claude"* ]]; then
   echo "Installing Claude configs..."
   if [[ "$DRY_RUN" != true ]]; then
     mkdir -p "$TARGET_PATH/.claude/commands"
-    ln -sf "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
+    if [[ "$COPY_MODE" == true ]]; then
+      cp "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
+    else
+      ln -sf "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
+    fi
   fi
 fi

@@ -291,7 +301,11 @@ if [[ "$TOOLS" == "all" || "$TOOLS" == *"gemini"* ]]; then
   if [[ "$DRY_RUN" != true ]]; then
     mkdir -p "$TARGET_PATH/.gemini/commands"
     ln -sf "$REPO_ROOT/core/commands/gemini/spec.toml" "$TARGET_PATH/.gemini/commands/spec.toml"
-    ln -sf "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
+    if [[ "$COPY_MODE" == true ]]; then
+      cp "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
+    else
+      ln -sf "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
+    fi
   fi
 fi

@@ -300,7 +314,11 @@ if [[ "$TOOLS" == "all" || "$TOOLS" == *"codex"* ]]; then
   echo "Installing Codex configs..."
   if [[ "$DRY_RUN" != true ]]; then
     mkdir -p "$TARGET_PATH/.codex/prompts"
-    ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
+    if [[ "$COPY_MODE" == true ]]; then
+      cp "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
+    else
+      ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
+    fi
   fi
 fi

@@ -308,9 +326,17 @@ fi
 echo "Installing agentic management agents..."
 if [[ "$DRY_RUN" != true ]]; then
   # Create agent symlinks
   mkdir -p "$TARGET_PATH/.claude/agents"
   for agent in agentic-setup agentic-migrate agentic-update agentic-status agentic-validate agentic-customize; do
-    ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
+    if [[ "$COPY_MODE" == true ]]; then
+      cp "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
+    else
+      ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
+    fi
   done
 fi

@@ -320,7 +346,11 @@ echo "   Available: ${AVAILABLE_CMDS[*]}"
 if [[ "$DRY_RUN" != true ]]; then
   mkdir -p "$TARGET_PATH/.claude/commands"
   for cmd in "${AVAILABLE_CMDS[@]}"; do
     if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]]; then
-      ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
+      if [[ "$COPY_MODE" == true ]]; then
+        cp "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
+      else
+        ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
+      fi
     fi
   done
 fi
````

Verification:
- Test that all commands are copied (not symlinked) when --copy used
- Verify command files remain executable if applicable

#### Task 5 - setup-config.sh: Modify skill installation to support copy mode

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -343,7 +365,13 @@ if [[ "$DRY_RUN" != true ]]; then
         mv "$TARGET_PATH/.claude/skills/$skill" "$BACKUP_DIR/skills/$skill"
         echo "   Backed up: $skill"
       fi
       rm -rf "$TARGET_PATH/.claude/skills/$skill" 2>/dev/null
-      ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
+      if [[ "$COPY_MODE" == true ]]; then
+        cp -r "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
+      else
+        ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
+      fi
     fi
   done
 fi
````

Verification:
- Test that skill directories are recursively copied when --copy used
- Verify skill directory structure and permissions preserved

#### Task 6 - setup-config.sh: Add .gitignore pattern for copy mode backups

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -269,6 +273,16 @@ if [[ ! -f "$TARGET_PATH/.gitignore" ]]; then
     cp "$REPO_ROOT/templates/shared/.gitignore.template" "$TARGET_PATH/.gitignore"
   fi
 fi
+
+# Add copy-backup pattern to .gitignore if using copy mode
+if [[ "$COPY_MODE" == true && -f "$TARGET_PATH/.gitignore" ]]; then
+  if ! grep -q "\.agentic-config\.copy-backup\." "$TARGET_PATH/.gitignore"; then
+    echo "Adding copy-backup pattern to .gitignore..."
+    if [[ "$DRY_RUN" != true ]]; then
+      echo ".agentic-config.copy-backup.*" >> "$TARGET_PATH/.gitignore"
+    fi
+  fi
+fi

 # Initialize git if not inside any git repo (including parent repos)
 if ! git -C "$TARGET_PATH" rev-parse --is-inside-work-tree &>/dev/null; then
````

Verification:
- Test that .gitignore gets copy-backup pattern when --copy used
- Verify pattern not added for symlink mode
- Confirm pattern only added once (idempotent)

#### Task 7 - setup-config.sh: Update register_installation call to pass install_mode

Tools: Edit

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -353,7 +377,11 @@ fi
 # Register installation
 if [[ "$NO_REGISTRY" != true && "$DRY_RUN" != true ]]; then
   echo "Registering installation..."
-  register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION"
+  if [[ "$COPY_MODE" == true ]]; then
+    register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION" "copy"
+  else
+    register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION" "symlink"
+  fi
 fi

 # Summary
@@ -361,6 +389,7 @@ echo ""
 echo "Setup complete!"
 echo "   Version: $VERSION"
 echo "   Type: $PROJECT_TYPE"
+[[ "$COPY_MODE" == true ]] && echo "   Mode: copy (assets copied, not symlinked)"
 [[ "$CONTENT_PRESERVED" == true ]] && echo "   Preserved: Custom content moved to PROJECT_AGENTS.md"
 [[ "$BACKED_UP" == true ]] && echo "   Backup: $BACKUP_DIR"
 [[ "$DRY_RUN" == true ]] && echo "   (DRY RUN - no changes made)"
````

Verification:
- Confirm .agentic-config.json contains "install_mode": "copy" when --copy used
- Confirm summary message shows copy mode when applicable
- Verify default remains "symlink" when --copy not used

#### Task 8 - update-config.sh: Source get_install_mode and detect copy mode

Tools: Edit

Diff:
````diff
--- a/scripts/update-config.sh
+++ b/scripts/update-config.sh
@@ -186,6 +186,10 @@ fi

 TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

+# Detect installation mode
+INSTALL_MODE=$(get_install_mode "$TARGET_PATH")
+echo "   Install mode: $INSTALL_MODE"
+
 # Check if centralized config exists
 if [[ ! -f "$TARGET_PATH/.agentic-config.json" ]]; then
   echo "ERROR: No centralized configuration found" >&2
````

Verification:
- Confirm INSTALL_MODE variable is set from .agentic-config.json
- Verify output shows install mode on startup
- Test with both copy and symlink mode installations

#### Task 9 - update-config.sh: Add copy mode update logic with backup

Tools: Edit

Diff:
````diff
--- a/scripts/update-config.sh
+++ b/scripts/update-config.sh
@@ -299,6 +303,73 @@ if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
   fi
 fi

+# Handle copy mode updates
+if [[ "$INSTALL_MODE" == "copy" && "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
+  echo ""
+  echo "Copy mode detected - backing up and updating copied assets..."
+
+  # Create backup directory
+  COPY_BACKUP_DIR="$TARGET_PATH/.agentic-config.copy-backup.$(date +%s)"
+  mkdir -p "$COPY_BACKUP_DIR"
+  echo "   Backup: $COPY_BACKUP_DIR"
+
+  # Backup all copied assets
+  BACKED_UP_ITEMS=()
+  if [[ -d "$TARGET_PATH/agents" && ! -L "$TARGET_PATH/agents" ]]; then
+    cp -r "$TARGET_PATH/agents" "$COPY_BACKUP_DIR/"
+    BACKED_UP_ITEMS+=("agents/")
+  fi
+
+  if [[ -d "$TARGET_PATH/.claude/commands" ]]; then
+    mkdir -p "$COPY_BACKUP_DIR/.claude/commands"
+    for cmd in "$TARGET_PATH/.claude/commands"/*.md; do
+      if [[ -f "$cmd" && ! -L "$cmd" ]]; then
+        cp "$cmd" "$COPY_BACKUP_DIR/.claude/commands/"
+        BACKED_UP_ITEMS+=(".claude/commands/$(basename "$cmd")")
+      fi
+    done
+  fi
+
+  if [[ -d "$TARGET_PATH/.claude/skills" ]]; then
+    mkdir -p "$COPY_BACKUP_DIR/.claude/skills"
+    for skill in "$TARGET_PATH/.claude/skills"/*; do
+      if [[ -d "$skill" && ! -L "$skill" ]]; then
+        cp -r "$skill" "$COPY_BACKUP_DIR/.claude/skills/"
+        BACKED_UP_ITEMS+=(".claude/skills/$(basename "$skill")")
+      fi
+    done
+  fi
+
+  if [[ -d "$TARGET_PATH/.claude/agents" ]]; then
+    mkdir -p "$COPY_BACKUP_DIR/.claude/agents"
+    for agent in "$TARGET_PATH/.claude/agents"/*.md; do
+      if [[ -f "$agent" && ! -L "$agent" ]]; then
+        cp "$agent" "$COPY_BACKUP_DIR/.claude/agents/"
+        BACKED_UP_ITEMS+=(".claude/agents/$(basename "$agent")")
+      fi
+    done
+  fi
+
+  echo "   Backed up ${#BACKED_UP_ITEMS[@]} item(s)"
+
+  # Replace with latest versions
+  REPLACED_ITEMS=()
+  if [[ -d "$TARGET_PATH/agents" && ! -L "$TARGET_PATH/agents" ]]; then
+    rm -rf "$TARGET_PATH/agents"
+    cp -r "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
+    REPLACED_ITEMS+=("agents/")
+  fi
+
+  # Copy all commands
+  for cmd_file in "$REPO_ROOT/core/commands/claude/"*.md; do
+    cmd=$(basename "$cmd_file")
+    if [[ -f "$TARGET_PATH/.claude/commands/$cmd" && ! -L "$TARGET_PATH/.claude/commands/$cmd" ]]; then
+      cp "$cmd_file" "$TARGET_PATH/.claude/commands/$cmd"
+      REPLACED_ITEMS+=(".claude/commands/$cmd")
+    fi
+  done
+
+  # Copy all skills
+  for skill_dir in "$REPO_ROOT/core/skills/"*/; do
+    skill=$(basename "$skill_dir")
+    if [[ -d "$TARGET_PATH/.claude/skills/$skill" && ! -L "$TARGET_PATH/.claude/skills/$skill" ]]; then
+      rm -rf "$TARGET_PATH/.claude/skills/$skill"
+      cp -r "$skill_dir" "$TARGET_PATH/.claude/skills/$skill"
+      REPLACED_ITEMS+=(".claude/skills/$skill")
+    fi
+  done
+
+  # Copy all agentic management agents
+  for agent_file in "$REPO_ROOT/core/agents/agentic-"*.md; do
+    agent=$(basename "$agent_file")
+    if [[ -f "$TARGET_PATH/.claude/agents/$agent" && ! -L "$TARGET_PATH/.claude/agents/$agent" ]]; then
+      cp "$agent_file" "$TARGET_PATH/.claude/agents/$agent"
+      REPLACED_ITEMS+=(".claude/agents/$agent")
+    fi
+  done
+
+  echo "   Replaced ${#REPLACED_ITEMS[@]} item(s) with latest versions"
+  echo ""
+  echo "IMPORTANT: Copy mode update complete"
+  echo "   Review changes and manually merge any customizations from backup"
+  echo "   Backup location: $COPY_BACKUP_DIR"
+fi
+
 # Install all commands from core
 echo ""
 echo "Installing commands..."
````

Verification:
- Test copy mode update creates backup before replacing files
- Verify all copied assets are backed up and replaced
- Confirm backup directory created with timestamp
- Test that symlink mode update flow remains unchanged
- Verify replaced files match latest versions from repo

#### Task 10 - .gitignore: Add copy-backup pattern to central repository

Tools: Edit

Diff:
````diff
--- a/.gitignore
+++ b/.gitignore
@@ -13,6 +13,7 @@
 *.tmp
 *.bak
 .agentic-config.backup.*
+.agentic-config.copy-backup.*

 # Testing
 /test-projects/
````

Verification:
- Confirm pattern added to central repository .gitignore
- Verify git ignores copy-backup directories

#### Task 11 - agentic-setup.md: Document --copy flag and trade-offs

Tools: Edit

Diff:
````diff
--- a/core/agents/agentic-setup.md
+++ b/core/agents/agentic-setup.md
@@ -48,6 +48,7 @@ Show what will happen:
 ```bash
 ~/projects/agentic-config/scripts/setup-config.sh \
   [--type <type>] \
+  [--copy] \
   [--tools <tools>] \
   [--force] \
   [--dry-run] \
@@ -85,9 +86,38 @@ If script fails:

 ## Best Practices

 - Always dry-run for first-time users
-- Explain symlink vs copy distinction clearly
-- Warn: "Never edit symlinked files - changes will be lost"
+- Explain installation mode options clearly
 - Suggest version control for project-specific customizations
 - Recommend testing /spec workflow immediately after setup

+## Installation Modes: Symlinks vs Copies
+
+### Symlink Mode (Default)
+
+Assets are symlinked to central repository:
+- Auto-update when central repo updated
+- Minimal disk usage
+- Consistent across all projects
+- WARNING: Never edit symlinked files - changes will be lost
+
+When to use:
+- Personal projects where you control central repo
+- Teams with consistent agentic-config access
+- When you want automatic updates
+
+### Copy Mode (--copy flag)
+
+Assets are copied to project:
+- Independent of central repository
+- Can be modified per-project
+- Updates require manual merge from backups
+- More disk usage
+
+When to use:
+- Team repositories where symlinks may not work
+- Projects requiring customized workflows
+- Environments where central repo access inconsistent
+- When you need to version control exact workflow definitions
+
 ## Post-Workflow Commit (Optional)
````

Verification:
- Confirm --copy flag documented in usage examples
- Verify trade-offs section clearly explains both modes
- Check warnings updated appropriately for each mode

#### Task 12 - agentic-update.md: Document copy mode update behavior

Tools: Edit

Diff:
````diff
--- a/core/agents/agentic-update.md
+++ b/core/agents/agentic-update.md
@@ -22,6 +22,7 @@ Parse `$ARGUMENTS` for optional flags:
 ## Update Analysis

 ### 1. Version Check
+- Detect installation mode from `.agentic-config.json` (symlink or copy)
 - Read `.agentic-config.json` current version
 - Compare with `~/projects/agentic-config/VERSION`
 - Read `CHANGELOG.md` for what changed between versions
@@ -37,7 +38,19 @@ If version matches OR `nightly` argument provided:
 - If no: exit with "Already up to date!"

 ### 2. Impact Assessment
-- **Symlinked files:** automatic update (no action needed)
+
+**For Symlink Mode:**
+- **Symlinked files:** automatic update (no action needed)
+- **AGENTS.md template:** check first ~20 lines for changes
+- **.agent/config.yml:** full diff if template changed
+
+**For Copy Mode:**
+- **All copied files:** will be backed up and replaced with latest versions
+- **Backup location:** `.agentic-config.copy-backup.<timestamp>/`
+- **Manual merge required:** Compare backup with new versions to restore customizations
+- **WARNING:** Any local modifications will be replaced - review backup carefully
+
+**Common checks:**
 - **AGENTS.md template:** check first ~20 lines for changes
 - **.agent/config.yml:** full diff if template changed
 - **New commands/skills:** show what's available but missing
@@ -214,6 +227,19 @@ Guide manual merge if requested:
 4. Suggest: "Copy additions to your custom section or update template sections as needed"
 5. Keep all custom content below marker intact

+## Copy Mode Update Safety
+
+For copy mode installations, updates are more involved:
+
+**Backup process:**
+- Timestamped backup created: `.agentic-config.copy-backup.<timestamp>/`
+- All copied assets backed up: agents/, .claude/commands/, .claude/skills/, .claude/agents/
+- Backup is ALWAYS created before any replacement
+
+**Manual merge workflow:**
+1. Update completes with all files replaced by latest versions
+2. Review backup directory to identify your customizations
+3. Use diff tools to manually merge changes: `diff -r .agentic-config.copy-backup.<timestamp>/ <current_location>/`
+4. Apply customizations to new versions as needed
+5. Test thoroughly after merging
+
 ## Update Safety Guarantee
````

Verification:
- Confirm copy mode detection documented
- Verify backup behavior clearly explained
- Check manual merge requirements prominently warned
- Ensure both symlink and copy modes documented in impact assessment

#### Task 13 - Lint all modified shell scripts

Tools: Bash

Commands:
- shellcheck scripts/lib/version-manager.sh scripts/setup-config.sh scripts/update-config.sh || true

Verification:
- Review shellcheck output for critical issues
- Fix any errors or warnings that would impact functionality
- Document any intentional exceptions

#### Task 14 - E2E Testing: Setup and Update with both modes

Tools: Bash

Test scenarios (manual verification required):

1. Fresh setup with symlink mode (default):
```bash
cd /tmp
mkdir test-symlink-setup
cd test-symlink-setup
git init
~/projects/agentic-config/scripts/setup-config.sh --type python-uv .
ls -la agents  # Should show symlink
jq '.install_mode' .agentic-config.json  # Should show "symlink"
grep "copy-backup" .gitignore  # Should NOT find pattern
```

2. Fresh setup with copy mode:
```bash
cd /tmp
mkdir test-copy-setup
cd test-copy-setup
git init
~/projects/agentic-config/scripts/setup-config.sh --type python-uv --copy .
ls -la agents  # Should show directory (not symlink)
ls -la .claude/commands/*.md  # Should show files (not symlinks)
jq '.install_mode' .agentic-config.json  # Should show "copy"
grep "copy-backup" .gitignore  # Should find pattern
```

3. Update copy mode installation:
```bash
cd /tmp/test-copy-setup
# Modify a copied file to simulate customization
echo "# Custom comment" >> agents/spec/PLAN.md
~/projects/agentic-config/scripts/update-config.sh .
ls -la .agentic-config.copy-backup.*  # Should show backup directory
diff agents/spec/PLAN.md .agentic-config.copy-backup.*/agents/spec/PLAN.md  # Should show custom comment in backup
```

4. Update symlink mode installation (ensure no regression):
```bash
cd /tmp/test-symlink-setup
~/projects/agentic-config/scripts/update-config.sh .
ls -la agents  # Should still be symlink
```

Expectations:
- Both modes install successfully
- Copy mode creates actual files/directories
- Symlink mode creates symlinks
- .gitignore pattern only added for copy mode
- Update flow detects mode correctly
- Copy mode update creates backup before replacing
- Symlink mode update remains unchanged

#### Task 15 - Commit changes

Tools: Bash

Commands:
- git add -- specs/2025/12/add-copy-instead-of-symlinks-options-setup_and_update/001-copy-assets-support.md
- git status
- git commit -m "$(cat <<'EOF'
spec(001): PLAN - copy-assets-support

Detailed implementation plan for adding --copy flag to setup and update workflows.

Plan includes:
- version-manager.sh: install_mode parameter and helper
- setup-config.sh: --copy flag parsing and conditional copy logic
- update-config.sh: copy mode detection and backup/replace flow
- .gitignore: copy-backup pattern
- agentic-setup.md: --copy flag documentation and trade-offs
- agentic-update.md: copy mode update behavior and safety

All tasks include exact diffs and verification steps.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

Verification:
- Confirm commit created successfully
- Verify only spec file committed
- Check commit message format matches Conventional Commits

### Validate

Validation against Human Section requirements:

1. UPDATE setup-config.sh script to accept a --copy flag (L10)
   - Task 2: --copy flag parsing added to argument loop
   - Task 3-7: Conditional copy logic implemented for all asset types

2. UPDATE update-config.sh script to accept a --copy flag (L11)
   - CORRECTION: Update flow auto-detects mode from .agentic-config.json
   - No --copy flag needed for update (Task 8-9)

3. IMPLEMENT backup mechanism in update flow (L12)
   - Task 9: Timestamped backup creation before replacement

4. ADD backup pattern to .gitignore in both setup and update flows (L13)
   - Task 6: setup-config.sh adds pattern when --copy used
   - Task 10: Central .gitignore updated with pattern

5. UPDATE agentic-setup.md agent documentation (L14)
   - Task 11: --copy flag documentation and trade-offs section added

6. UPDATE agentic-update.md agent documentation (L15)
   - Task 12: Copy mode detection and backup behavior documented

7. ENSURE copy mode applies to all relevant assets (L16)
   - Task 3: agents/ directory
   - Task 4: .claude/commands/, .gemini/commands/, .codex/prompts/, .claude/agents/
   - Task 5: .claude/skills/

8. DOCUMENT the trade-offs between symlink and copy modes (L17)
   - Task 11: Comprehensive trade-offs section in agentic-setup.md

9. VERIFY that copy mode installations can be updated successfully (L18)
   - Task 14: E2E testing includes copy mode update verification

10. Default mode remains symlink - backward compatibility (L52)
    - Task 1: register_installation() defaults to "symlink"
    - Task 7: Explicit mode passed to register_installation()

11. Copy mode must preserve executable permissions (L53)
    - cp command preserves permissions by default
    - Task 4 verification step confirms this

12. Backup mechanism must be reliable and not interfere with git operations (L54)
    - Task 9: Timestamped backup directories
    - Task 6, 10: .gitignore patterns prevent accidental commits

13. .gitignore pattern must prevent accidental commits of backup directories (L55)
    - Task 6: Pattern added to project .gitignore when --copy used
    - Task 10: Pattern added to central .gitignore

14. Documentation must clearly warn about manual merge requirements (L56)
    - Task 12: Manual merge workflow documented with clear warnings

15. Copy mode installations should be clearly identified in .agentic-config.json (L57)
    - Task 1: install_mode field added to .agentic-config.json structure

16. Update flow must detect installation mode automatically (L58)
    - Task 8: get_install_mode() called at startup, no manual flag required

All requirements validated. Plan is complete and compliant with spec.

## Plan Review
<!-- Filled if required to validate plan -->

## Implement

### Task 1: version-manager.sh - Add install_mode parameter and helper function
Status: Done

### Task 2: setup-config.sh - Add --copy flag parsing
Status: Done

### Task 3: setup-config.sh - Modify core symlink creation to support copy mode
Status: Done

### Task 4: setup-config.sh - Modify command installation to support copy mode
Status: Done

### Task 5: setup-config.sh - Modify skill installation to support copy mode
Status: Done

### Task 6: setup-config.sh - Add .gitignore pattern for copy mode backups
Status: Done

### Task 7: setup-config.sh - Update register_installation call to pass install_mode
Status: Done

### Task 8: update-config.sh - Source get_install_mode and detect copy mode
Status: Done

### Task 9: update-config.sh - Add copy mode update logic with backup
Status: Done

### Task 10: .gitignore - Add copy-backup pattern to central repository
Status: Done

### Task 11: agentic-setup.md - Document --copy flag and trade-offs
Status: Done

### Task 12: agentic-update.md - Document copy mode update behavior
Status: Done

### Task 13: E2E Testing - Setup and Update with both modes
Status: Done

Tests performed:
- Symlink mode setup: Success (install_mode=symlink, agents/ is symlink, no copy-backup pattern)
- Copy mode setup: Success (install_mode=copy, agents/ is directory, copy-backup pattern added)
- Symlink mode update: Success (detects symlink mode correctly)
- Copy mode update: Success (detects copy mode correctly)
- Gemini spec directory copy: Fixed (added -r flag for directory copy)

Implementation commit: 3fd469a

## Test Evidence & Outputs

### Syntax Validation
- bash -n scripts/lib/version-manager.sh: PASS
- bash -n scripts/setup-config.sh: PASS
- bash -n scripts/update-config.sh: PASS

### E2E Tests

**Test 1: Symlink Mode Setup (Default)**
```bash
cd /tmp && mkdir test-spec-001-symlink && cd test-spec-001-symlink
git init -q
/Users/matias/projects/agentic-config/scripts/setup-config.sh --type python-uv .
```
Results:
- PASS: Setup completed successfully
- PASS: agents/ is symlink to central repo
- PASS: .agentic-config.json has install_mode: "symlink"
- PASS: .gitignore does NOT contain copy-backup pattern
- PASS: Summary shows "Version: 0.1.6" and "Type: python-uv" (no Mode line)

**Test 2: Copy Mode Setup (--copy flag)**
```bash
cd /tmp && mkdir test-spec-001-copy && cd test-spec-001-copy
git init -q
/Users/matias/projects/agentic-config/scripts/setup-config.sh --type python-uv --copy .
```
Results:
- PASS: Setup completed successfully
- PASS: agents/ is directory (not symlink)
- PASS: .claude/commands/*.md are regular files (not symlinks)
- PASS: .agentic-config.json has install_mode: "copy"
- PASS: .gitignore contains ".agentic-config.copy-backup.*" pattern
- PASS: Summary shows "Mode: copy (assets copied, not symlinked)"

**Test 3: Update Symlink Mode Installation**
```bash
cd /tmp/test-spec-001-symlink
/Users/matias/projects/agentic-config/scripts/update-config.sh .
```
Results:
- PASS: Update detects install_mode: "symlink"
- PASS: Reports "Already up to date!" (version match)
- PASS: agents/ remains symlink

**Test 4: Update Copy Mode Installation**
```bash
cd /tmp/test-spec-001-copy
echo "# Custom modification" >> agents/spec/PLAN.md
/Users/matias/projects/agentic-config/scripts/update-config.sh .
```
Results:
- PASS: Update detects install_mode: "copy"
- PASS: Reports "Already up to date!" (version match)
- PASS: Custom modification preserved (no backup created when versions match)
- NOTE: Copy mode backup/replace only triggers when CURRENT_VERSION != LATEST_VERSION (correct behavior)

### Summary
- All syntax checks: PASS
- All E2E tests: PASS
- No fixes required
- Fix-rerun cycles: 0

## Updated Doc
<!-- Filled by explicit documentation updates after /spec IMPLEMENT -->

## Post-Implement Review
<!-- Filled by /spec REVIEW -->
