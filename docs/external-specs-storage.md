# External Specs Storage

Store specification files in a separate repository to reduce clutter while maintaining version control.

## Configuration

Configuration sources (priority order):
1. Environment variables (highest)
2. `.env` file
3. `.agentic-config.conf.yml` file (lowest)

### Required Settings

| Key | ENV Variable | Description |
|-----|--------------|-------------|
| `ext_specs_repo_url` | `EXT_SPECS_REPO_URL` | Git repository URL (SSH or HTTPS) |
| `ext_specs_local_path` | `EXT_SPECS_LOCAL_PATH` | Local clone path (default: `.specs`) |

### Examples

**.env file:**
```bash
EXT_SPECS_REPO_URL=git@github.com:user/project--specs.git
EXT_SPECS_LOCAL_PATH=.specs
```

**.agentic-config.conf.yml:**
```yaml
ext_specs_repo_url: git@github.com:user/project--specs.git
ext_specs_local_path: .specs
```

## Library Functions

### spec-resolver.sh

Source: `core/lib/spec-resolver.sh`

**Purpose**: Resolves spec file paths and commits spec changes to appropriate repository (external or local).

**Usage**:

```bash
# Pure bash (no external commands like cat) for restricted shell compatibility
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"
```

**resolve_spec_path** `<relative_path>` - Returns absolute spec path
- If `EXT_SPECS_REPO_URL` configured: routes to external repo
- Otherwise: routes to local `specs/` directory
- Initializes external repo if needed

**commit_spec_changes** `<spec_path> <stage> <nnn> <title> [--dry-run]` - Commits spec changes
- Detects location by path prefix
- External: commits and pushes to external repo
- Local: commits to main repo
- `--dry-run`: Preview changes without executing

### external-specs.sh

Source: `scripts/external-specs.sh`

```bash
source scripts/external-specs.sh
```

**ext_specs_init** `[--dry-run]` - Clone/pull external repository
- Serializes concurrent access using file locking
- Returns error if lock cannot be acquired (10s timeout)
- `--dry-run`: Preview clone/pull without executing

**ext_specs_commit** `<message> [--dry-run]` - Commit and push to external repo
- Serializes concurrent operations using file locking
- Returns error if lock cannot be acquired (30s timeout)
- Rolls back commit if push fails
- `--dry-run`: Preview commit/push without executing

**ext_specs_path** - Return absolute path to external specs directory
- Validates project root exists
- Returns error if not in valid project directory

### config-loader.sh

Source: `core/lib/config-loader.sh`

```bash
# Pure bash (no external commands like cat) for restricted shell compatibility
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/config-loader.sh"

load_agentic_config  # Load all config with priority
get_agentic_config "ext_specs_repo_url"  # Get specific value
```
- Works correctly in nested directories and git worktrees
- Clears external specs config on each load to prevent multi-project state leaks
- Safe for multi-project workflows in same terminal session

### agentic-root.sh

Source: `core/lib/agentic-root.sh`

```bash
# Pure bash (no external commands like cat) for restricted shell compatibility
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/agentic-root.sh"
```

**compare_versions** `<v1> <v2>` - Compare semantic versions
- Pure bash implementation (cross-platform)
- Handles different segment counts (1.0 vs 1.0.0)
- Returns: 0 if v1 == v2, 1 if v1 > v2, 2 if v1 < v2
- Example: `compare_versions "1.10.0" "1.2.0"` returns 1 (1.10.0 > 1.2.0)

## Command Integration

Commands automatically use spec-resolver when external specs configured:

- `/branch` - Creates spec directories in resolved location
- `/spec` stages - Commits via `commit_spec_changes`
- `/o_spec` - Resolves paths at session initialization
- `/po_spec` - Resolves phase spec paths

No code changes needed when switching between external/local.

## Behavior

**With external specs configured:**
- Spec files stored in `.specs/specs/...`
- Commits go to external repository
- Main repo stays clean of spec content

**Without configuration:**
- Spec files stored in `specs/...`
- Commits go to main repository
- Backward compatible behavior

## Safety Features

### Concurrent Operation Protection

Cross-platform file locking prevents race conditions in concurrent scenarios:
- Uses mkdir-based atomic locking (works on macOS, Linux, BSD)
- No external dependencies (flock not required)
- Clone/pull operations serialized with 10s timeout
- Commit/push operations serialized with 30s timeout
- Lock directory: `.specs/.agentic-lock`
- Automatic cleanup via trap on function exit

**Lock Cleanup Mechanism:**
```bash
(
  _acquire_lock "$lockdir" 30 || exit 1

  # Set trap AFTER successful acquisition to ensure cleanup on any exit
  trap '_release_lock "$lockdir"' EXIT

  # ... git operations ...
  # Trap fires on any exit (success or failure)
)
```

The trap is set **after** successful lock acquisition to:
- Prevent releasing non-existent locks if acquisition fails
- Guarantee cleanup on all exit paths (success, failure, signal)
- Avoid lock leaks that would block future operations

### Input Validation

All inputs are validated for security and safety:

**URL Validation:**
- Rejects absolute file paths (prevents path traversal)
- Maximum URL length: 2048 characters
- Accepts SSH, HTTPS, and file:// protocols

**Path Validation:**
- Rejects absolute paths (security)
- Rejects paths containing `..` sequences (directory traversal)
- Maximum directory depth: 20 levels (prevents resource exhaustion)
- Shell profile paths validated with regex `^[a-zA-Z0-9_./-]+$` (prevents shell injection)
  - Rejects paths containing: quotes, backticks, dollar signs, semicolons, pipes, etc.
  - Prevents arbitrary code execution when shell profiles are sourced
  - Example: `/home/user/$(whoami)` is rejected before being written to `.bashrc`

**YAML/Config Parsing:**
- Exact key matching (prevents substring false positives)
- Graceful handling of unbalanced quotes
- .env parser scoped to known safe keys only

### Project Root Validation

All operations validate project root exists:
- Checks for `.agentic-config.json`, `CLAUDE.md`, or `.git` markers
- Returns explicit error if no markers found
- Prevents operations in invalid directories

### Error Handling

Improved error handling with recovery guidance:

**Distinct Exit Codes:**
- 1: Directory change failed
- 2: Git add failed or rollback failed
- 3: Git commit failed
- 4: Git push failed

**Rollback Protection:**
- Automatic rollback on push failure
- Manual recovery instructions if rollback fails
- Index reset on commit failure (unstages all files)

### Bootstrap Consistency

All shell scripts use unified bootstrap logic:
- Consistent 5-priority discovery system
- VERSION file validation
- Pure bash implementation (no external commands like `cat`)
- Compatible with restricted shell environments

### Temp File Cleanup

Temporary files cleaned up on both success and error paths to prevent `/tmp` pollution.
