# Release Command

Full release workflow: validate changelog, prepare a squashed release commit and tag, rebase, push, and merge to `main`.

**No arguments required** - auto-detect the current branch, release version, and release inputs.

## Compatibility Note

This pi wrapper preserves the original release workflow but performs the former milestone-preparation steps directly because `ac-tools-milestone` does not ship as a separate pi wrapper in the current package surface.

## Context Awareness

Before any destructive history rewrite, use `/skill:ac-git-git-safe` to inspect the dry-run plan and confirm the exact squash/tag steps you intend to execute.

## Phase 1: Prepare the Release Locally

### 1.1 Pre-Flight

Verify all of the following before rewriting history:
- git state is clean
- branch is not `main`
- commits exist ahead of `origin/main`
- `CHANGELOG.md` has a populated `[Unreleased]` section
- the next release version can be derived from `VERSION` or the latest `v*.*.*` tag

Suggested checks:
```bash
git status --short
git fetch origin main
git rev-parse --abbrev-ref HEAD
git log --oneline origin/main..HEAD
git tag -l 'v*.*.*' | sort -V | tail -1
test -f VERSION && cat VERSION
test -f CHANGELOG.md && sed -n '/\[Unreleased\]/,/^## /p' CHANGELOG.md
```

### 1.2 Determine Release Inputs

Capture these values for the rest of the flow:
- `BRANCH`: current branch name
- `VERSION`: next release tag (prefer patch bump from `VERSION`, otherwise patch bump from latest semantic tag)
- `COMMITS_INCLUDED`: the commit list that will be squashed

### 1.3 Prepare the Squashed Release Commit

Use the same dry-run-first safety rules as `ac-git-git-safe`:
1. propose the exact squash plan before executing
2. create a backup branch before rewriting history
3. squash the commits ahead of `origin/main` into one conventional commit
4. keep `CHANGELOG.md` aligned with the release contents
5. create an annotated tag for `{VERSION}` on the squashed commit
6. do **not** push yet

After the squash/tag step succeeds, capture:
- `VERSION`
- `BRANCH`
- `SQUASH_SHA`
- the final squashed commit message
- the commit list that was included

If local preparation fails: **STOP** - show the error and do not proceed.

## Phase 2: Rebase onto `origin/main`

After the local squash/tag preparation succeeds:

### 2.1 Fetch Latest
```bash
git fetch origin main
```

### 2.2 Check Rebase Need
```bash
git rev-list HEAD..origin/main --count
```

If count > 0, `main` has advanced and a rebase is required.

### 2.3 Perform Rebase
```bash
git rebase origin/main
```

If rebase conflicts:
1. show conflicting files with `git status`
2. provide resolution guidance
3. wait for the user to resolve conflicts manually
4. continue with `git rebase --continue`
5. if the user aborts, run `git rebase --abort`
   - note that `{VERSION}` still points to the pre-rebase squashed commit until Phase 3 updates it

## Phase 3: Re-create Tag If Rebase Changed SHA

### 3.1 Check If Tag Needs Update
```bash
TAG_SHA=$(git rev-list -n1 {VERSION} 2>/dev/null)
HEAD_SHA=$(git rev-parse HEAD)
```

If `TAG_SHA != HEAD_SHA`:

### 3.2 Delete Old Tag
```bash
git tag -d {VERSION}
```

### 3.3 Create New Tag on Rebased Commit
```bash
git tag -a {VERSION} -m "Release {VERSION}"
```

## Phase 4: Push Branch and Tag

### 4.1 Force Push Branch
```bash
git push --force-with-lease origin {BRANCH}
```

Due to squash + possible rebase, force push is required.

### 4.2 Push Tag
```bash
git push origin {VERSION}
```

If the tag already exists on remote from an earlier failed attempt:
```bash
git push --delete origin {VERSION}
git push origin {VERSION}
```

## Phase 5: Merge to `main`

### 5.1 Confirmation Gate

**STOP HERE** and show:

```
Ready to merge to main:
- Branch: {BRANCH}
- Version: {VERSION}
- Commit: {HEAD_SHA short}

This will:
1. Checkout main
2. Pull latest
3. Fast-forward merge from {BRANCH}
4. Push main

Proceed with merge to main? (yes/no)
```

**Wait for explicit `yes`**. Any other response aborts the merge while keeping the release branch/tag valid.

### 5.2 Execute Merge (on `yes`)

```bash
git checkout main
git pull origin main
git merge --ff-only {BRANCH}
```

If fast-forward fails:
```
Fast-forward merge failed. This means main has diverged.

Options:
(A) Force merge (creates merge commit)
(B) Abort - investigate manually

Choose (A/B):
```

**On `A`:**
```bash
git merge {BRANCH} -m "chore(release): merge {BRANCH} for {VERSION}"
```

**On `B`:** STOP - check out back to `{BRANCH}`.

### 5.3 Push Main
```bash
git push origin main
```

## Phase 6: Final Report

Display summary:

```
## Release Complete

### Version Released
- Tag: {VERSION}
- Commit: {FINAL_SHA}
- Message: {commit message first line}

### Commits Included
{COMMITS_INCLUDED}

### Branch Status
- Feature branch: {BRANCH} (pushed)
- Main branch: merged and pushed
- Tag: {VERSION} (pushed)

### Remote URLs
- Branch: {remote URL for branch}
- Main: {remote URL for main}
- Release: {remote URL for tag}

### Cleanup (optional)
To delete feature branch:
  git branch -d {BRANCH}
  git push origin --delete {BRANCH}
```

## Abort Conditions

| Condition | Action |
|-----------|--------|
| Local release preparation fails | STOP: Show the validation/squash/tag error |
| Rebase conflicts unresolved | STOP: Provide manual resolution steps |
| Push fails | STOP: Show error and suggest manual push |
| Fast-forward merge fails | Offer force merge or abort |
| User declines merge | Release is valid, just not merged to `main` |

## Usage

```bash
# Full auto - no arguments needed
/skill:ac-git-release
```

The command will:
1. validate release prerequisites and derive the release inputs
2. prepare the squashed release commit and annotated tag locally
3. rebase onto `origin/main`
4. re-tag if needed
5. push branch and tag
6. merge to `main` with confirmation
7. report the final release state
