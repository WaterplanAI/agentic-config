---
name: ac-git-worktree
description: "Creates a git worktree with asset setup, serial branch/bootstrap creation, shared worker-wave environment setup, and direnv wiring. Triggers on keywords: worktree, create worktree, new worktree, git worktree"
project-agnostic: false
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - AskUserQuestion
  - subagent
---

# Create New Worktree - pi adaptation

Create a new git worktree with:
- serial branch/bootstrap setup using the bundled package scripts
- asset wiring from `.worktree.yml` or bounded inference
- shared worker-wave environment setup through `subagent`
- serial `direnv allow`, commit, and final summary

## Current shipped boundary

This pi wrapper now ships, but it stays inside the bounded IT003 contract:
- branch/bootstrap is handled directly in this skill; do **not** try to invoke `ac-git-branch` from inside the skill
- the shared `pi-compat` worker-wave surface is used only for the environment-setup wave
- `.worktree.yml` discovery, asset wiring, `direnv allow`, final commit, and final summary stay coordinator-owned
- if user input is required, only the coordinator uses `AskUserQuestion`; workers stay non-interactive

## Arguments

- `worktree_name` (required): base name for the branch and worktree
- `assets_path` (optional): explicit path to shared assets to mirror into the worktree

## Required references

Read these when needed:
- `cookbook/setup.md` when no `.worktree.yml` exists or the user wants setup help
- `../../assets/scripts/spec-resolver.sh` for serial branch/spec bootstrap
- `node_modules/@agentic-config/pi-compat/assets/orchestration/protocol/worker.md` for every environment worker
- `node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js`
- `node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js`

## Pre-flight checks

1. Verify repo root:
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   ```

2. Verify the main checkout is clean before branch/bootstrap work:
   ```bash
   git -C "$REPO_ROOT" status --short
   ```
   - If dirty: STOP and ask the user to clean or stash changes first.

3. Validate `worktree_name`:
   - required
   - allow only letters, numbers, `-`, and `_`
   - reject spaces and shell-special characters

4. Generate the unique branch/worktree name:
   ```bash
   UUID_PREFIX=$(uuidgen | cut -c1-6 | tr 'A-Z' 'a-z')
   FULL_NAME="$UUID_PREFIX-<worktree_name>"
   WORKTREE_PATH="$REPO_ROOT/trees/$FULL_NAME"
   ```

5. Check for existing worktree path:
   ```bash
   test -e "$WORKTREE_PATH"
   ```
   - If it already exists: STOP and report the path.

6. Check for existing branch:
   ```bash
   git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$FULL_NAME"
   ```
   - If missing: continue with serial bootstrap.
   - If present: use `AskUserQuestion` to ask whether to reuse the existing branch or abort.
   - On reuse: skip the branch-creation step and assume the original bootstrap commit already exists.

7. Check for live `.worktree.yml` files in the main checkout only:
   ```bash
   find "$REPO_ROOT" \
     \( -path "$REPO_ROOT/.git" -o -path "$REPO_ROOT/.git/*" \
        -o -path "$REPO_ROOT/trees" -o -path "$REPO_ROOT/trees/*" \
        -o -path '*/templates' -o -path '*/templates/*' \
        -o -path '*/example' -o -path '*/example/*' \
        -o -path '*/examples' -o -path '*/examples/*' \
        -o -path '*/fixture' -o -path '*/fixture/*' \
        -o -path '*/fixtures' -o -path '*/fixtures/*' \
        -o -path '*/test' -o -path '*/test/*' \
        -o -path '*/tests' -o -path '*/tests/*' \) -prune -o \
     -name ".worktree.yml" -type f -print
   ```
   - Treat template/example/fixture/test copies as non-live examples, not active worktree configs.
   - If at least one live config exists in the main checkout: use config-driven mode.
   - If none exist: use `AskUserQuestion`:
     - explain that `.worktree.yml` makes asset/environment setup deterministic
     - offer to create one now via `cookbook/setup.md`
     - if the user says yes, read `cookbook/setup.md`, create the file, then continue in config-driven mode
     - if the user says no, continue in inference mode

8. If `assets_path` was provided, validate it before continuing:
   ```bash
   test -d "$ASSETS_PATH"
   ```
   - If the explicit path does not exist: STOP.

## Execution overview

1. Serial branch/bootstrap
2. Create the worktree
3. Apply assets from `.worktree.yml` or inference
4. Build ordered environment targets
5. Run one bounded environment worker wave through `subagent`
6. Run `direnv allow` serially
7. Commit setup changes if any
8. Report the final summary, including warnings

## Step 1: Serial branch/bootstrap

When the branch does not already exist, inline the shipped `ac-git-branch` flow with the bundled helper script:

```bash
source "../../assets/scripts/spec-resolver.sh"

git -C "$REPO_ROOT" checkout -b "$FULL_NAME"

RELATIVE_PATH="$(date +%Y)/$(date +%m)/$FULL_NAME/000-backlog.md"
SPEC_FILE=$(resolve_spec_path "$RELATIVE_PATH")
SPEC_DIR="${SPEC_FILE%/*}"
: > "$SPEC_FILE"

commit_spec_changes "$SPEC_FILE" "CREATE" "000" "backlog"
```

Record for the final summary:
- `FULL_NAME`
- `SPEC_FILE`
- whether the branch was newly created or reused

Why this stays serial and skill-owned:
- the shipped pi branch wrapper already proves this is a bounded bash flow
- it does **not** require generic skill-to-skill invocation
- the commit must exist before `git worktree add` so the backlog file appears in the new worktree

## Step 2: Create the worktree

```bash
mkdir -p "$REPO_ROOT/trees"
git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" "$FULL_NAME"
```

After creation, verify:
```bash
git -C "$WORKTREE_PATH" rev-parse --show-toplevel
git -C "$WORKTREE_PATH" rev-parse --abbrev-ref HEAD
```

## Step 3: Discover and apply assets

Keep this step in the coordinator.

### Mode A: explicit `assets_path`
Use the provided path as the root asset source.

### Mode B: `.worktree.yml`
When config files exist, process every live `.worktree.yml` inside the new worktree, excluding template/example/fixture/test directories.

For each config file:
1. Determine its directory.
2. Resolve `assets.source` relative to that config directory, not the repo root.
3. Apply `assets.symlink` entries as symlinks.
4. Apply `assets.copy` entries as copies.
5. Apply `root_symlinks` from the main checkout root, not from `assets.source`.
6. Record every applied action for the final summary.

Use `yq` when available. Otherwise, use a short `python3` snippet with `yaml.safe_load`. If neither `yq` nor Python YAML parsing is available, STOP and explain that the config cannot be applied honestly.

Representative structure:
```bash
for CONFIG_FILE in $(find "$WORKTREE_PATH" \
  \( -path '*/templates' -o -path '*/templates/*' \
     -o -path '*/example' -o -path '*/example/*' \
     -o -path '*/examples' -o -path '*/examples/*' \
     -o -path '*/fixture' -o -path '*/fixture/*' \
     -o -path '*/fixtures' -o -path '*/fixtures/*' \
     -o -path '*/test' -o -path '*/test/*' \
     -o -path '*/tests' -o -path '*/tests/*' \) -prune -o \
  -name ".worktree.yml" -type f -print); do
  CONFIG_DIR=$(dirname "$CONFIG_FILE")
  CONFIG_RELATIVE=$(realpath --relative-to="$WORKTREE_PATH" "$CONFIG_DIR")

  # Resolve assets.source relative to CONFIG_DIR.
  # Apply copy/symlink actions into CONFIG_DIR.
  # Resolve root_symlinks from the main checkout root.
done
```

### Mode C: inference
If no `.worktree.yml` exists and no explicit `assets_path` was provided, infer assets in this order:

1. sibling assets directories:
   ```bash
   REPO_NAME=$(basename "$REPO_ROOT")
   REPO_PARENT=$(dirname "$REPO_ROOT")
   for candidate in \
     "$REPO_PARENT/${REPO_NAME}-assets" \
     "$REPO_PARENT/assets" \
     "$REPO_PARENT/.${REPO_NAME}-assets"; do
     test -d "$candidate" && echo "$candidate"
   done
   ```

2. ignored local assets:
   ```bash
   git -C "$REPO_ROOT" ls-files --others --ignored --exclude-standard --directory
   ```

Inference rules:
- copy `.env`, `.env.local`, and `config*.local*`
- symlink large shared directories such as `data/`, `inputs/`, `fixtures/`, `models/`, `weights/`, and `cache/`
- if an explicitly requested asset source is missing: STOP
- if an inferred asset candidate is missing: warn and continue

## Step 4: Build the ordered environment target list

Create one ordered target list for the environment wave.

Preferred source of truth:
1. `.worktree.yml` `environments` entries, preserving config order
2. otherwise infer from project markers inside the worktree

Marker-based inference:
- `pyproject.toml` or `requirements.txt` -> `python`
- `package.json` -> `node`
- `Cargo.toml` -> `rust`
- `go.mod` -> `go`
- `Gemfile` -> `ruby`

For each target, capture:
- `worker_id` (stable ordered id such as `01-backend`)
- absolute target path
- detected environment type
- report path under `tmp/worktree/$FULL_NAME/reports/`
- result path under `tmp/worktree/$FULL_NAME/results/`

Create scratch directories **outside** the worktree so they are not committed accidentally:
```bash
RUN_ROOT="$REPO_ROOT/tmp/worktree/$FULL_NAME"
mkdir -p "$RUN_ROOT/reports" "$RUN_ROOT/results"
```

If no environment targets are detected, continue without a worker wave and report that no environment bootstrap was required.

## Step 5: Run the shared environment worker wave

Use exactly one synchronous `subagent` wave for the environment setup step.

- Use `subagent.parallel` when multiple targets are independent.
- Use a single worker only when exactly one target exists.
- Prefer the `worker` agent.
- Workers must stay non-interactive.
- Workers must not launch nested subagents.
- Workers must write their report first, then call `write-result.js`.

### Worker contract
Every worker task must explicitly tell the worker to:
1. read `node_modules/@agentic-config/pi-compat/assets/orchestration/protocol/worker.md`
2. touch only its assigned target path
3. write a detailed markdown report to the assigned report path
4. call:
   ```bash
   node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js \
     --result-path "$RESULT_PATH" \
     --worker-id "$WORKER_ID" \
     --status "$STATUS" \
     --summary "$SUMMARY" \
     --report-path "$REPORT_PATH" \
     --target "$TARGET_PATH"
   ```
5. return a concise completion message after the result file is written

### Worker responsibilities by environment type
#### Python
- create `.venv` if missing
- create/update `.envrc` with:
  ```sh
  dotenv_if_exists .env
  source .venv/bin/activate
  ```
- if a worktree-root `.env` exists and the target is nested, symlink `.env` into the target when that is appropriate for the project layout
- install dependencies from `requirements.txt`, `requirements.dev.txt`, and/or `pyproject.toml` as applicable

#### Node
- create/update `.envrc` with:
  ```sh
  dotenv_if_exists .env
  PATH_add node_modules/.bin
  ```
- install dependencies using the repo's package-manager signal:
  - `pnpm-lock.yaml` -> `pnpm install`
  - `yarn.lock` -> `yarn install`
  - otherwise -> `npm install`

#### Rust / Go / Ruby
- create a minimal `.envrc` when the project needs one
- run the standard bootstrap command if the toolchain is present
- if the required toolchain is missing, return `warn` with a clear summary and manual next step

### Wave result policy
For `worktree`, warnings are allowed when setup completed but produced a non-fatal issue.
Failures and missing result files are not allowed.

After the wave finishes, summarize the ordered results:
```bash
node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js \
  --result "$RUN_ROOT/results/01-...json" \
  --result "$RUN_ROOT/results/02-...json" \
  --fail-on-missing \
  --fail-on-status fail \
  --format json
```

Coordinator rules after summarization:
- if the summary command exits non-zero: STOP and surface the failing or missing workers
- if only `warn` entries exist: continue, but include the warnings in the final summary
- if a worker produced a warning you do not understand, read that worker's report before continuing

## Step 6: Run `direnv allow` serially

Keep this coordinator-owned.

For each environment target path that now contains `.envrc`:
```bash
if command -v direnv >/dev/null; then
  (cd "$TARGET_PATH" && direnv allow)
else
  echo "WARN: direnv not installed; skipped allow for $TARGET_PATH"
fi
```

Treat missing `direnv` as a warning, not a failure.

## Step 7: Commit setup changes in the worktree

Leave the new worktree in a clean committed state whenever there are tracked changes.

```bash
cd "$WORKTREE_PATH"
git add -A
git status --short

if ! git diff --cached --quiet; then
  git commit -m "chore(worktree): setup $FULL_NAME

- Configure asset links and copies
- Bootstrap development environments
- Add direnv configuration"
fi
```

Do not commit transient scratch state from `tmp/worktree/...`; that directory lives outside the worktree root.

## Step 8: Final summary

Report:
- `FULL_NAME`
- worktree path
- branch name
- resolved spec path or reused-branch note
- applied asset actions
- environment targets and their statuses
- whether `direnv allow` succeeded or was skipped
- whether a setup commit was created
- every warning that still needs user attention

## Error handling

| Condition | Action |
|---|---|
| main checkout is dirty before bootstrap | STOP |
| worktree path already exists | STOP |
| branch already exists | Ask user whether to reuse or abort |
| explicit `assets_path` missing | STOP |
| `.worktree.yml` exists but cannot be parsed honestly | STOP |
| inferred asset candidate missing | warn and continue |
| worker result missing | STOP |
| worker status `fail` | STOP |
| worker status `warn` | continue and report explicitly |
| `direnv` missing | warn and continue |

## Path resolution rule for `.worktree.yml`

This is the most important correctness rule in the asset step.

**Resolve every `.worktree.yml` path relative to the config file's directory, not the repo root and not the current shell directory.**

Correct pattern:
```bash
CONFIG_DIR=$(dirname "$CONFIG_FILE")
ASSETS_SOURCE=$(cd "$CONFIG_DIR" && realpath "$SOURCE_VALUE")
```

Wrong pattern:
```bash
ASSETS_SOURCE=$(realpath "$SOURCE_VALUE")
```

The wrong pattern breaks monorepos with nested `.worktree.yml` files.
