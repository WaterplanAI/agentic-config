# Worktree Setup Cookbook

Guided setup for `.worktree.yml` configuration in your project.

## What is `.worktree.yml`?

A project-level configuration file that tells the worktree skill how to set up new worktrees. Without it, the skill falls back to inference (scanning sibling directories and `.gitignore`). With it, worktree creation is deterministic and reproducible.

**Benefits of explicit config:**
- Deterministic asset linking (no guessing)
- Consistent environment setup across team members
- Control over which files are symlinked vs copied
- Support for monorepo sub-project environments

## Configuration Fields

For the complete YAML schema and path resolution rules, see the **"Project Configuration"** and **"Path Resolution Rules"** sections in `SKILL.md`.

Quick reference of available fields:

| Field | Type | Purpose |
|-------|------|---------|
| `assets.source` | string | Path to external assets directory (relative to config file) |
| `assets.symlink` | list | Files/dirs to symlink from assets source (large, read-only) |
| `assets.copy` | list | Files/dirs to copy from assets source (secrets, per-worktree config) |
| `environments` | list | Project environments to set up (`path` + `type`) |
| `root_symlinks` | list | Gitignored dirs from main repo root to symlink into worktrees |
| `skip_branch_command` | bool | Skip `/branch` integration (default: false) |

## Step-by-Step Creation

### 1. Identify your assets

```bash
# Check for sibling assets directory
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
ls -la "../${REPO_NAME}-assets" 2>/dev/null

# Check gitignored local assets
git ls-files --others --ignored --exclude-standard --directory
```

### 2. Classify each asset

| Asset | Action | Why |
|-------|--------|-----|
| `.env`, credentials | **copy** | Secrets; may need per-worktree customization |
| `data/`, `inputs/` | **symlink** | Large; read-only; shared across worktrees |
| `models/`, `weights/` | **symlink** | Large binary directories |
| `config.local.*` | **copy** | May need per-worktree values |

### 3. Identify environments

Check for project markers:

```bash
# Find all project roots
find . -maxdepth 3 \( -name "pyproject.toml" -o -name "package.json" -o -name "Cargo.toml" -o -name "go.mod" \) -not -path "*/node_modules/*" -not -path "*/.venv/*"
```

### 4. Create the config file

Place `.worktree.yml` at your repository root (or in subdirectories for monorepo sub-projects).

## Examples

### Python Project

```yaml
# .worktree.yml
assets:
  source: ../my-project-assets

  symlink:
    - data/inputs
    - models/

  copy:
    - .env

environments:
  - path: .
    type: python
```

### Node.js Project

```yaml
# .worktree.yml
assets:
  source: ../project-assets

  copy:
    - .env
    - .env.local

environments:
  - path: .
    type: node
```

### Monorepo

```yaml
# .worktree.yml (root)
assets:
  source: ../monorepo-assets

  symlink:
    - shared/data

  copy:
    - .env

environments:
  - path: services/api
    type: python
  - path: services/web
    type: node

root_symlinks:
  - .specs
```

### Monorepo with Sub-Project Configs

```yaml
# services/api/.worktree.yml
assets:
  source: ../../../monorepo-assets/services/api

  symlink:
    - fixtures/

  copy:
    - .env

environments:
  - path: .
    type: python
```

### Minimal (No External Assets)

```yaml
# .worktree.yml
environments:
  - path: .
    type: python

root_symlinks:
  - .specs
```

## Skipping `/branch` Integration

If your project does not use the `/branch` command for spec directory creation:

```yaml
skip_branch_command: true
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Assets not found | `source` path resolved from wrong directory | Paths are relative to `.worktree.yml` location, not repo root |
| Symlink shows as deleted in git | Expected behavior | Tracked placeholder replaced by symlink; do not commit the deletion |
| Environment setup fails | Missing system dependency | Check Python/Node/etc. is installed; skill warns and continues |
