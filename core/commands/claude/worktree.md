---
description: Create new git worktree with symlinked/copied assets and environment setup
argument-hint: <worktree_name> [assets_path]
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Task
---

# Create New Worktree

Creates a new git worktree with:
- Shared assets (symlinked or copied)
- Independent environment per project type
- Proper `.envrc` configuration for direnv

## Arguments

- `worktree_name` (required): Name for the worktree and branch
- `assets_path` (optional): Path to external assets directory to symlink from

## Parallelization

**CRITICAL**: Use Task tool with `model: haiku` for parallel execution when:
- Setting up assets in multiple directories
- Installing dependencies in multiple environments
- Any operation that can run independently

Spawn separate haiku agents for each independent task to maximize parallelization.

Example - parallel environment setup:
```
Task(model: haiku, prompt: "Setup Python venv in /path/to/backend")
Task(model: haiku, prompt: "Run npm install in /path/to/frontend")
Task(model: haiku, prompt: "Create symlinks for assets in /path/to/data")
```

Send all independent Task calls in a SINGLE message to run them concurrently.

## Pre-Flight Checks

1. **Verify git repo root**:
   ```bash
   git rev-parse --show-toplevel
   ```

2. **Validate worktree name**:
   - Must be provided
   - No spaces or special chars (except `-` and `_`)

3. **Check for existing worktree/branch**:
   - If worktree exists: STOP and report
   - If branch exists: Ask user to confirm reuse

## Asset Discovery

### When `assets_path` is provided

Use the provided path directly. Mirror its structure into the worktree via symlinks.

### When `assets_path` is NOT provided (inference mode)

**Step 1: Check for sibling assets directory**

Look for directories matching `<repo-name>-assets` pattern:
```bash
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
REPO_PARENT=$(dirname "$(git rev-parse --show-toplevel)")
ASSETS_CANDIDATES=(
  "$REPO_PARENT/${REPO_NAME}-assets"
  "$REPO_PARENT/assets"
  "$REPO_PARENT/.${REPO_NAME}-assets"
)
```

If found, use it as `assets_path`.

**Step 2: Analyze .gitignore for local assets**

If no sibling assets directory found, parse `.gitignore` to identify:

```bash
# Find gitignored directories/files that exist locally
git ls-files --others --ignored --exclude-standard --directory
```

Filter for:
- Directories containing data files (`inputs/`, `data/`, `fixtures/`)
- Environment files (`.env`, `.env.local`, `*.env`)
- Config files that vary per environment (`config.local.*`)
- Large binary directories (`models/`, `weights/`, `cache/`)

**Step 3: Classify assets**

For each discovered asset, classify:

| Asset Type | Action | Reason |
|------------|--------|--------|
| `.env` files | **Copy** | Secrets, may need per-worktree customization |
| `inputs/`, `data/` dirs | **Symlink** | Large, read-only shared data |
| `config.*.local` | **Copy** | May need per-worktree customization |
| Binary/model dirs | **Symlink** | Large, read-only |

## Execution Flow

**CRITICAL: AUTONOMOUS EXECUTION REQUIRED**

This command MUST execute ALL steps (1-8) in sequence WITHOUT stopping for user input. After the `/branch` command completes in Step 2, IMMEDIATELY continue to Step 3. Do NOT wait for user confirmation between steps.

**Execution pattern:**
1. Generate unique name
2. Run `/branch` command → when it completes, CONTINUE IMMEDIATELY
3. Create worktree → CONTINUE
4. Setup assets → CONTINUE
5. Setup environment → CONTINUE
6. Enable direnv → CONTINUE
7. Commit changes → CONTINUE
8. Display summary → DONE

---

## Execution Steps

### Step 1: Generate unique name

```bash
UUID_PREFIX=$(uuidgen | cut -c1-6 | tr 'A-Z' 'a-z')
FULL_NAME="$UUID_PREFIX-<worktree_name>"
```

This ensures branch name and worktree directory match exactly.

### Step 2: Create branch with spec directory

**Use the `/branch` command with the full name**:
```
/branch $FULL_NAME
```

Creates AND COMMITS (CRITICAL):
- Branch: `$FULL_NAME` (e.g., `a1b2c3-feature-name`)
- Spec dir: `specs/<YYYY>/<MM>/$FULL_NAME/`
- Backlog: `000-backlog.md`

**Why commit is critical**: If spec dir is not committed before `git worktree add`, the files won't exist in the new worktree (worktree is created from the branch's committed state).

**AFTER /branch COMPLETES**: Do NOT stop. Do NOT show todos. IMMEDIATELY proceed to Step 3.

### Step 3: Create worktree

```bash
git worktree add "trees/$FULL_NAME" "$FULL_NAME"
```

Branch and worktree directory now have the same name.

### Step 4: Setup assets based on .worktree.yml

**4a. Discover all `.worktree.yml` files:**
```bash
find "$WORKTREE_PATH" -name ".worktree.yml" -type f
```

**4b. For each config file, process assets with correct path resolution:**

```bash
for CONFIG_FILE in $(find "$WORKTREE_PATH" -name ".worktree.yml"); do
  CONFIG_DIR=$(dirname "$CONFIG_FILE")
  CONFIG_RELATIVE=$(realpath --relative-to="$WORKTREE_PATH" "$CONFIG_DIR")

  # Read source from config (use yq or grep+sed)
  SOURCE_VALUE=$(yq '.assets.source' "$CONFIG_FILE")

  # CRITICAL: Resolve source relative to CONFIG_DIR, not CWD
  if [[ -n "$SOURCE_VALUE" && "$SOURCE_VALUE" != "null" ]]; then
    ASSETS_SOURCE=$(cd "$CONFIG_DIR" && realpath "$SOURCE_VALUE")
  else
    # Fallback to inference
    ASSETS_SOURCE="$INFERRED_ASSETS_PATH/$CONFIG_RELATIVE"
  fi

  # Process symlinks
  for ASSET in $(yq '.assets.symlink[]' "$CONFIG_FILE"); do
    SOURCE="$ASSETS_SOURCE/$ASSET"
    TARGET="$CONFIG_DIR/$ASSET"
    rm -rf "$TARGET"
    ln -sf "$SOURCE" "$TARGET"
  done

  # Process copies
  for ASSET in $(yq '.assets.copy[]' "$CONFIG_FILE"); do
    SOURCE="$ASSETS_SOURCE/$ASSET"
    TARGET="$CONFIG_DIR/$ASSET"
    [[ -f "$SOURCE" ]] && cp "$SOURCE" "$TARGET"
  done
done
```

**If action = COPY:**
```bash
cp -r "$SOURCE_PATH" "$WORKTREE_PATH/$RELATIVE_PATH"
```

**If action = SYMLINK:**
```bash
# Remove placeholder if exists (may show as deleted in git status - expected)
rm -rf "$WORKTREE_PATH/$RELATIVE_PATH"

# Create symlink with absolute path to source
ln -sf "$ABSOLUTE_SOURCE_PATH" "$WORKTREE_PATH/$RELATIVE_PATH"
```

**Important:** Symlinked paths that replace tracked placeholder files will show as `deleted` in `git status`. This is expected and should NOT be committed.

**COMMON BUG**: Do NOT resolve `assets.source` from repo root or CWD. Always `cd` to the config file's directory first.

### Step 5: Detect and setup environment

**PARALLELIZE**: When multiple environments are configured, spawn separate haiku agents for each.

**Detect project type by presence of:**

| File | Project Type |
|------|--------------|
| `pyproject.toml`, `requirements.txt` | Python |
| `package.json` | Node.js |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `Gemfile` | Ruby |

**For each project root (may be multiple in monorepo) - RUN IN PARALLEL:**

```
# Send ALL environment setup tasks in a SINGLE message:
Task(model: haiku, prompt: "Setup Python venv at <path1>: create .venv, install deps")
Task(model: haiku, prompt: "Setup Node at <path2>: npm install")
Task(model: haiku, prompt: "Setup Python venv at <path3>: create .venv, install deps")
```

#### Python projects

1. Create `.envrc`:
   ```sh
   dotenv_if_exists .env
   source .venv/bin/activate
   ```

2. Symlink `.env` to worktree root:
   ```bash
   ln -sf <relative_path_to_root>/.env .env
   ```

3. Create venv and install:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   [ -f requirements.dev.txt ] && pip install -r requirements.dev.txt
   [ -f pyproject.toml ] && pip install -e .
   ```

#### Node.js projects

1. Create `.envrc`:
   ```sh
   dotenv_if_exists .env
   PATH_add node_modules/.bin
   ```

2. Install dependencies:
   ```bash
   npm install  # or yarn/pnpm based on lockfile
   ```

#### Other project types

Detect and configure accordingly. Prioritize:
- Linking environment files
- Installing dependencies
- Setting up direnv

### Step 6: Enable direnv

For each configured directory:
```bash
direnv allow
```

If direnv not installed, warn but continue.

### Step 7: Commit setup changes

**CRITICAL**: Commit all worktree setup changes to leave a clean state.

```bash
cd "$WORKTREE_PATH"
git add -A
git status --short

# Only commit if there are changes
if ! git diff --cached --quiet; then
  git commit -m "chore(worktree): setup $WORKTREE_NAME

- Configure asset symlinks
- Setup development environment
- Create .envrc for direnv"
fi
```

**What gets committed:**
- New files: `.envrc`, copied assets
- Deleted placeholders: files replaced by symlinks show as deleted (expected)

**What stays untracked (gitignored):**
- `.venv/`, `node_modules/`, `.env` (secrets)

### Step 8: Summary

Display:
```
Worktree created:
  Path: trees/<UUID>-<worktree_name>
  Branch: <worktree_name>
  Spec: specs/<YYYY>/<MM>/<worktree_name>/

Assets configured:
  [COPY] .env
  [SYMLINK] data/inputs -> /abs/path/to/assets/data/inputs
  [SYMLINK] models/ -> /abs/path/to/assets/models/

Environments setup:
  - ./app (Python, venv created)
  - ./frontend (Node.js, npm installed)
```

## Error Handling

| Condition | Action |
|-----------|--------|
| Worktree exists | STOP, report path |
| Branch exists | Ask to reuse or abort |
| Assets path not found | STOP if explicit, warn if inferred |
| venv creation fails | Warn, continue with other dirs |
| Dependency install fails | Warn, continue |
| direnv not installed | Warn, continue |
| Symlink target missing | Warn, skip that asset |

## Project Configuration (Optional)

Projects can define `.worktree.yml` at repo root or in subdirectories:

```yaml
# .worktree.yml
assets:
  source: ../my-project-assets  # Override default discovery

  symlink:
    - data/inputs
    - models/

  copy:
    - .env
    - config.local.yml

environments:
  - path: backend
    type: python

  - path: frontend
    type: node

skip_branch_command: false  # Set true to skip /branch integration
```

When `.worktree.yml` exists, use its configuration instead of inference.

## Path Resolution Rules (CRITICAL)

**All paths in `.worktree.yml` are resolved relative to the config file's directory, NOT the current working directory or repo root.**

### When processing `.worktree.yml`:

1. **Determine config directory**:
   ```bash
   CONFIG_DIR=$(dirname "$CONFIG_FILE")
   ```

2. **Resolve `assets.source`**:
   ```bash
   # If source is relative path
   ASSETS_SOURCE=$(cd "$CONFIG_DIR" && realpath "$SOURCE_VALUE")
   ```

3. **Resolve symlink/copy paths**:
   - Source: `$ASSETS_SOURCE/<path>`
   - Target: `$WORKTREE_PATH/$CONFIG_RELATIVE_PATH/<path>`

### Example - Monorepo with subproject config

```
repo/
├── .worktree.yml              # Root config (if any)
└── services/
    └── api/
        └── .worktree.yml      # Subproject config
```

If `services/api/.worktree.yml` has:
```yaml
assets:
  source: ../../../repo-assets/services/api
  copy:
    - .env
```

Resolution:
```bash
CONFIG_DIR="services/api"
# source resolved from CONFIG_DIR:
ASSETS_SOURCE=$(cd "services/api" && realpath "../../../repo-assets/services/api")
# → /abs/path/repo-assets/services/api

# .env source: $ASSETS_SOURCE/.env
# .env target: $WORKTREE_PATH/services/api/.env
```

### Common Bug: Using CWD instead of CONFIG_DIR

**WRONG**:
```bash
# Resolves source relative to repo root - INCORRECT
ASSETS_SOURCE=$(realpath "$SOURCE_VALUE")
```

**CORRECT**:
```bash
# Resolves source relative to where .worktree.yml is located
ASSETS_SOURCE=$(cd "$CONFIG_DIR" && realpath "$SOURCE_VALUE")
```
