# Release Command

Full release workflow: validate changelog, squash commits, create tag, sync the VERSION file plus repo/package version metadata, rebase, push, and merge to main.

**No arguments required** - all values auto-detected.

## Context Awareness

**INVOKE** `git-safe` skill to gain context about safe history rewriting patterns.

## Phase 1: Invoke /milestone (No Args)

**INVOKE** `/milestone` with no arguments.

This will:
1. Auto-detect base branch (origin/main)
2. Auto-detect version (patch bump from VERSION file or latest tag)
3. Validate CHANGELOG [Unreleased] section
4. Squash commits into single commit
5. Create annotated version tag

**IMPORTANT**: When /milestone prompts "Proceed with push? (yes/no)", answer **"no"**.

We will push after rebase to ensure clean history.

**Capture** from /milestone output:
- `VERSION`: The version tag created (e.g., `v1.2.3`)
- `BRANCH`: Current branch name
- `SQUASH_SHA`: The squashed commit SHA

If /milestone fails: **STOP** - show error, do not proceed.

## Phase 1.5: Sync `VERSION`, package manifests, and version-pinned install docs

After `/milestone` succeeds, ensure the tracked version file, shipped package manifests, and pinned install examples all match the released version.

### 1.5.1 Normalize the plain version
```bash
PLAIN_VERSION=$(printf '%s' "{VERSION}" | sed 's/^v//')
```

### 1.5.2 Update `VERSION`
Set the `VERSION` file contents to `{PLAIN_VERSION}` exactly.

### 1.5.3 Update the repository root package metadata
Update the repository root `package.json` version field to `{PLAIN_VERSION}`.

Then refresh the root lockfile so the tracked version stays aligned:

```bash
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
```

### 1.5.4 Update every shipped package manifest under `packages/*/package.json`
For each package manifest:
- set its own `version` field to `{PLAIN_VERSION}`
- update every internal `@agentic-config/*` dependency pin to `{PLAIN_VERSION}`
- keep exact sibling-version alignment intact across the monorepo package set

This includes the umbrella package plus all shipped plugin packages.
Use a scripted edit rather than hand-editing selected manifests so no package is skipped.

### 1.5.5 Update version-pinned install docs
Update these tracked files to use the released version values:
- `README.md`
- `docs/getting-started.md`
- `docs/distribution.md`
- `packages/README.md`

Required sync rules:
- primary git-tag examples for this repository must use `WaterplanAI/agentic-config@{VERSION}`
- branch-based dev examples may keep `@main` or another branch example when the intent is explicitly local testing/dev rather than a release tag
- keep existing wording intact unless a pinned version string must change
- npm distribution should remain documented as future work unless the repository has explicitly enabled and validated that path

### 1.5.6 Commit the sync if anything changed
```bash
git add VERSION package.json package-lock.json packages/*/package.json README.md docs/getting-started.md docs/distribution.md packages/README.md
if ! git diff --cached --quiet; then
  git commit -m "docs(release): sync version references for {VERSION}"
fi
```

Notes:
- This step is mandatory when the root package version, any `packages/*/package.json` manifest, pinned git-tag examples, or the `VERSION` file changed.
- If this creates a follow-up commit after `/milestone`, the existing tag re-create step below must move `{VERSION}` to the new `HEAD`.

## Phase 2: Rebase onto origin/main

After successful /milestone (declined push):

### 2.1 Fetch Latest
```bash
git fetch origin main
```

### 2.2 Check Rebase Needed
```bash
git rev-list HEAD..origin/main --count
```

If count > 0 (main has new commits), rebase is needed.

### 2.3 Perform Rebase
```bash
git rebase origin/main
```

If rebase conflicts:
1. Show conflicting files: `git status`
2. Provide resolution guidance
3. Wait for user to resolve manually
4. After resolution: `git rebase --continue`
5. If user wants to abort: `git rebase --abort`
   - Note: Tag {VERSION} still points to pre-rebase commit

## Phase 3: Re-create Tag (if rebase changed SHA)

### 3.1 Check if Tag Needs Update
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

Due to squash + rebase, force push is required.

### 4.2 Push Tag
```bash
git push origin {VERSION}
```

If tag already exists on remote (from failed previous attempt):
```bash
git push --delete origin {VERSION}
git push origin {VERSION}
```

## Phase 5: Merge to Main

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

**Wait for explicit "yes"**. Any other response = abort merge (release still valid).

### 5.2 Execute Merge (on "yes")

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

**On "A":**
```bash
git merge {BRANCH} -m "chore(release): merge {BRANCH} for {VERSION}"
```

**On "B":** STOP - checkout back to {BRANCH}.

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
- VERSION file: synced to {PLAIN_VERSION}
- Root package metadata: synced in package.json and package-lock.json
- Shipped package manifests: synced across packages/*/package.json
- Version-pinned docs: synced in README.md, docs/getting-started.md, docs/distribution.md, and packages/README.md

### Commits Included
{list from squash - from /milestone output}

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
| /milestone fails | STOP: Show /milestone error |
| Rebase conflicts unresolved | STOP: Provide manual resolution steps |
| Push fails | STOP: Show error, suggest manual push |
| Fast-forward merge fails | Offer force merge or abort |
| User declines merge | Release is valid, just not merged to main |

## Usage

```bash
# Full auto - no arguments needed
/release
```

The command will:
1. Run /milestone (no args) - validates, squashes, tags
2. Rebase onto origin/main
3. Re-tag if needed
4. Push branch and tag
5. Merge to main (with confirmation)
6. Report results
