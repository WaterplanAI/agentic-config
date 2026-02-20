---
description: "Release workflow: branch, changelog, PR, tag, GH release"
argument-hint: "[--auto] [--preview]"
project-agnostic: false
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
  - Write
  - AskUserQuestion
---

# Release Command

Automated release workflow: pre-flight, branch, changelog+version update, PR, merge, tag, GH release.

## Arguments

- `--auto` — Skip all confirmation gates (pre-flight + PR merge)
- `--preview` — Create GH release as prerelease instead of latest

## Phase 1: Pre-flight

### 1.1 Read Current State

```bash
CURRENT_VERSION=$(cat VERSION)
# Parse semver: MAJOR.MINOR.PATCH
NEXT_PATCH=$((PATCH + 1))
NEXT_VERSION="$MAJOR.$MINOR.$NEXT_PATCH"
TODAY=$(date +%Y-%m-%d)
```

Read CHANGELOG.md and extract the `## [Unreleased]` section content (everything between `## [Unreleased]` and the next `## [` header).

### 1.2 Validate

- CHANGELOG `[Unreleased]` section MUST have content (not empty)
- If empty: **STOP** — "No unreleased changes in CHANGELOG.md. Nothing to release."
- Current branch MUST be `main`
- Working tree MUST be clean (`git status --porcelain` empty)

### 1.3 Explain Procedure

Display to user:

```
Release v{NEXT_VERSION}

Current: v{CURRENT_VERSION}
Next:    v{NEXT_VERSION}

Unreleased changes:
{unreleased content summary — first 10 lines}

Procedure:
1. Create branch release/v{NEXT_VERSION}
2. Update CHANGELOG.md and VERSION
3. Create PR, squash-merge to main
4. Tag v{NEXT_VERSION} on main
5. Create GH release ({"prerelease" if --preview else "latest"})

Proceed?
```

**Confirmation gate**: Use AskUserQuestion (yes/no). Skip if `--auto`.

## Phase 2: Branch

```bash
git checkout -b release/v{NEXT_VERSION}
```

## Phase 3: Update Files

### 3.1 CHANGELOG.md

Replace the `## [Unreleased]` section:

**Before:**
```
## [Unreleased]

### Added
- item A
...
```

**After:**
```
## [Unreleased]

## [{NEXT_VERSION}] - {TODAY}

### Added
- item A
...
```

The `[Unreleased]` section becomes empty (just the header), and a new versioned section is inserted immediately below it with all the previous unreleased content.

### 3.2 VERSION

Write `{NEXT_VERSION}` to VERSION file (single line, no trailing newline beyond what exists).

### 3.3 Commit

```bash
git add CHANGELOG.md VERSION
git commit -m "chore(release): prepare v{NEXT_VERSION}"
```

## Phase 4: PR + Merge

### 4.1 Push Branch

```bash
git push -u origin release/v{NEXT_VERSION}
```

### 4.2 Create PR

Create a concise PR:

```bash
gh pr create --title "chore(release): v{NEXT_VERSION}" --body "$(cat <<'EOF'
## Release v{NEXT_VERSION}

{Concise 2-5 bullet summary of unreleased changes — high-level only, not the full changelog}
EOF
)"
```

Capture the PR number from output.

### 4.3 Confirmation Gate

Display PR URL. **Ask user to confirm merge** via AskUserQuestion. Skip if `--auto`.

### 4.4 Merge

```bash
gh pr merge {PR_NUMBER} --squash --admin
```

## Phase 5: Checkout Main

```bash
git checkout main
git pull origin main
```

## Phase 6: Tag

### 6.1 Extract Changelog Entry

Extract the `## [{NEXT_VERSION}]` section content from CHANGELOG.md (everything between `## [{NEXT_VERSION}]` header line and the next `## [` header). Include the `###` sub-headers (Added, Changed, Fixed, Removed) but NOT the `## [{NEXT_VERSION}]` line itself.

### 6.2 Create Annotated Tag

```bash
git tag -a "v{NEXT_VERSION}" -m "$(cat <<'EOF'
{changelog entry content with ### headers}
EOF
)"
```

The tag message mirrors the changelog entry content — same format as existing tags (e.g., v0.1.18).

### 6.3 Push Tag

```bash
git push origin "v{NEXT_VERSION}"
```

## Phase 7: GH Release

```bash
gh release create "v{NEXT_VERSION}" \
  --title "v{NEXT_VERSION}" \
  --notes "$(cat <<'EOF'
{changelog entry content — same as tag message}
EOF
)" \
  {--prerelease if --preview, otherwise --latest}
```

Default: `--latest`. If `--preview` argument provided: `--prerelease` instead.

## Phase 8: Summary

```
Release complete: v{NEXT_VERSION}

- Branch: release/v{NEXT_VERSION} (merged)
- PR: {PR_URL}
- Tag: v{NEXT_VERSION}
- Release: {RELEASE_URL}

Cleanup (optional):
  git branch -d release/v{NEXT_VERSION}
  git push origin --delete release/v{NEXT_VERSION}
```

## Abort Conditions

| Condition | Action |
|-----------|--------|
| Empty [Unreleased] | STOP — nothing to release |
| Dirty working tree | STOP — commit or stash first |
| Not on main | STOP — checkout main first |
| PR creation fails | STOP — show error |
| Merge fails | STOP — show error, branch still exists |
| Tag push fails | Retry with `--force` if tag exists on remote from failed attempt |
| User declines at any gate | STOP — clean up branch if created |
