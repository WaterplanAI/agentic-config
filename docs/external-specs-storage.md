# External Specs Storage

Store specification files in a separate repository to keep the main repository focused on product code.

## Configuration

Configuration sources (highest to lowest priority):
1. Environment variables
2. `.env`
3. `.agentic-config.conf.yml`

### Keys

| Key | ENV Variable | Description |
|-----|--------------|-------------|
| `ext_specs_repo_url` | `EXT_SPECS_REPO_URL` | External specs git repository URL |
| `ext_specs_local_path` | `EXT_SPECS_LOCAL_PATH` | Local clone path (default: `.specs`) |

### Example

`.env`
```bash
EXT_SPECS_REPO_URL=https://example.com/example-org/example-specs.git
EXT_SPECS_LOCAL_PATH=.specs
```

`.agentic-config.conf.yml`
```yaml
ext_specs_repo_url: https://example.com/example-org/example-specs.git
ext_specs_local_path: .specs
```

## Scripts and Functions

### `spec-resolver.sh`

Source: `plugins/ac-workflow/scripts/spec-resolver.sh`

```bash
source "${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh"
```

### `resolve_spec_path <relative_path>`
- Routes to external specs repository when `EXT_SPECS_REPO_URL` is set
- Otherwise routes to local `specs/`
- Creates parent directories as needed
- Validates path input:
  - rejects absolute paths
  - rejects `..` traversal
  - limits parent directory depth to 20

### `commit_spec_changes <spec_path> <stage> <nnn> <title> [--dry-run]`
- Routes commit to external repo if `spec_path` is under configured external specs path
- Otherwise commits to the main repository
- Commit format: `spec(<NNN>): <STAGE> - <title>`

### `external-specs.sh`

Source: `plugins/ac-workflow/scripts/external-specs.sh`

```bash
source "${CLAUDE_PLUGIN_ROOT}/scripts/external-specs.sh"
```

### `ext_specs_init [--dry-run]`
- Pulls when external repo is already initialized
- Clones when missing
- Validates repository URL before clone:
  - rejects absolute file paths
  - max length 2048
  - accepts `git@`, `ssh://`, `https://`, `file://`
- Uses cross-process lock at:
  - `<project_root>/.tmp/agentic-locks/ext-specs`
- Clone safety:
  - fails if destination exists and is not a directory
  - fails if destination directory exists but is not empty

### `ext_specs_commit <message> [--dry-run]`
- Runs `git add -A`, `git commit`, `git push` in external specs repo
- Uses same lock path as `ext_specs_init`
- If push fails after commit, attempts rollback with `git reset HEAD~1`

### `ext_specs_path`
- Returns `<project_root>/<EXT_SPECS_LOCAL_PATH or .specs>`

### `config-loader.sh`

Source: `plugins/ac-workflow/scripts/lib/config-loader.sh`

```bash
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/config-loader.sh"

load_agentic_config
get_agentic_config "ext_specs_repo_url"
```

- Loads config with priority: ENV > `.env` > `.agentic-config.conf.yml`
- Restricts `.env` exports to known keys (`EXT_SPECS_REPO_URL`, `EXT_SPECS_LOCAL_PATH`)
- Resolves project root by walking up to `CLAUDE.md` or `.git`

## Command Integration

These workflows use spec resolver automatically:
- `/branch`
- `/spec` stages
- `mux-ospec`

No workflow code changes are needed when switching between local and external spec storage.

## Behavior Summary

With external specs configured:
- Specs are written to `<project_root>/<ext_specs_local_path>/specs/...`
- Spec commits are made in the external specs repository

Without external specs configured:
- Specs are written to `<project_root>/specs/...`
- Spec commits are made in the main repository
