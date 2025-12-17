---
description: Generate standardized Conventional Commit message for squashed commits
argument-hint: [target]
project-agnostic: true
allowed-tools:
  - Bash
  - Read
---

# Squash Commit Message Generator

Generates standardized Conventional Commits extended format message for squashed commits.

**CRITICAL**: This command assumes squashing has ALREADY been performed. It only generates and amends the commit message.

## Usage
```
/squash_commit [target] [--with-squashed-commits]
```

**Arguments**:
- `target`: Optional commit hash or branch name. Defaults to `origin/main`.
- `--with-squashed-commits`: Optional flag to include 'Squashed commits:' footer with original commit list. Default: disabled.

**Examples**:
```
/squash_commit                              # Uses origin/main (default), no squashed commits footer
/squash_commit develop                      # Use origin/develop as base, no footer
/squash_commit abc123f                      # Use specific commit hash as base, no footer
/squash_commit origin/feature               # Use specific remote branch, no footer
/squash_commit --with-squashed-commits      # Include squashed commits footer
/squash_commit develop --with-squashed-commits  # With footer and custom target
```

---

## Workflow Steps

### Step 1: Pre-Flight Validation

#### 1.1 Safety Checks
```bash
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Check if on protected branch
if [ "$BRANCH" = "main" ]; then
  echo "ERROR: Cannot amend commits on protected branch: $BRANCH"
  exit 1
fi

# Check for uncommitted changes
if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "ERROR: Uncommitted changes detected. Commit or stash changes first."
  git -C "$ROOT" status --short
  exit 1
fi

# Verify there is at least one commit
if ! git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
  echo "ERROR: No commits found in current branch"
  exit 1
fi
```

#### 1.2 Parse Arguments and Fetch Target
```bash
# Parse arguments
INCLUDE_SQUASHED_COMMITS="false"
TARGET=""

for arg in "$@"; do
  case "$arg" in
    --with-squashed-commits)
      INCLUDE_SQUASHED_COMMITS="true"
      ;;
    *)
      if [ -z "$TARGET" ]; then
        TARGET="$arg"
      fi
      ;;
  esac
done

# Fetch latest from origin (always fetch main for default case)
echo "Fetching latest from origin..."
git -C "$ROOT" fetch origin main 2>/dev/null || true

# Resolve target: use argument or default to origin/main
if [ -n "$TARGET" ]; then
  # If target looks like a branch name (no origin/ prefix, not a hash), fetch it
  if ! echo "$TARGET" | grep -qE '^[0-9a-f]{7,40}$' && ! echo "$TARGET" | grep -q '/'; then
    echo "Fetching origin/$TARGET..."
    git -C "$ROOT" fetch origin "$TARGET" 2>/dev/null || true
  fi
  echo "Target: $TARGET (user provided)"
else
  TARGET="origin/main"
  echo "Target: origin/main (default)"
fi
echo "Include squashed commits footer: $INCLUDE_SQUASHED_COMMITS"
echo ""

# Resolve target to commit hash (supports branches, remote branches, and commit hashes)
TARGET_REF=""
if git -C "$ROOT" rev-parse --verify "$TARGET" >/dev/null 2>&1; then
  TARGET_REF="$TARGET"
elif git -C "$ROOT" rev-parse --verify "origin/$TARGET" >/dev/null 2>&1; then
  TARGET_REF="origin/$TARGET"
else
  echo "ERROR: Cannot resolve target '$TARGET'"
  echo "Provide a valid commit hash, branch name, or remote branch (e.g., origin/main)"
  echo ""
  echo "Available remote branches:"
  git -C "$ROOT" branch -r | grep -v HEAD
  exit 1
fi

TARGET_HASH=$(git -C "$ROOT" rev-parse "$TARGET_REF")
echo "Resolved target: $TARGET_REF ($TARGET_HASH)"
```

---

### Step 2: Context Gathering

#### 2.1 Analyze Git Diff File-by-File
```bash
echo "=========================================="
echo "FILE-BY-FILE DIFF ANALYSIS"
echo "=========================================="
echo ""

# Get list of changed files
CHANGED_FILES=$(git -C "$ROOT" diff --name-only "$TARGET_REF..HEAD")

# For each file, show summary of changes
for file in $CHANGED_FILES; do
  echo "--- $file ---"
  # Show stat for this file
  git -C "$ROOT" diff --stat "$TARGET_REF..HEAD" -- "$file" | tail -1
  # Show first few lines of actual diff for context
  git -C "$ROOT" diff "$TARGET_REF..HEAD" -- "$file" | head -30
  echo ""
done
```

#### 2.2 Read Git Log for Context
```bash
echo "=========================================="
echo "GIT LOG (commits being squashed)"
echo "=========================================="
echo ""

# Show all commits from target to HEAD
git -C "$ROOT" log --oneline "$TARGET_REF..HEAD"
echo ""

# Show detailed log with messages
echo "Detailed commit messages:"
echo "--------------------------"
git -C "$ROOT" log --format="commit %h%nAuthor: %an%nDate: %ad%n%n%s%n%b%n---" "$TARGET_REF..HEAD"
echo ""

# Store commit hashes for "Squashed commits:" section
SQUASHED_COMMITS=$(git -C "$ROOT" log --oneline "$TARGET_REF..HEAD")
COMMITS_AHEAD=$(git -C "$ROOT" rev-list --count "$TARGET_REF..HEAD")

if [ "$COMMITS_AHEAD" -eq 0 ]; then
  echo "WARNING: No commits ahead of $TARGET_REF. Branch may be up-to-date."
fi
```

#### 2.3 Analyze File Statistics
```bash
echo "=========================================="
echo "CHANGE STATISTICS"
echo "=========================================="
echo ""

# Overall stats
git -C "$ROOT" diff --stat "$TARGET_REF..HEAD"
echo ""

# Count by file type
echo "Files by type:"
git -C "$ROOT" diff --name-only "$TARGET_REF..HEAD" | sed 's/.*\.//' | sort | uniq -c | sort -rn
echo ""
```

---

### Step 3: Generate Commit Message

**INSTRUCTION**: Generate a standardized Conventional Commits extended format message.

#### 3.1 Title Format (50 char max)
```
<type>(<scope>): <description>
```

**Type Classification** (analyze diff to determine):

| Type | Description | When to Use |
|------|-------------|-------------|
| `feat` | New feature | Adding new functionality |
| `fix` | Bug fix | Correcting broken behavior |
| `docs` | Documentation | README, comments, docstrings |
| `style` | Formatting | No code logic change |
| `refactor` | Code restructuring | No behavior change |
| `perf` | Performance | Optimization improvements |
| `test` | Tests | Adding/fixing tests |
| `chore` | Maintenance | Build, deps, tooling |
| `build` | Build system | Webpack, vite, etc. |
| `ci` | CI/CD | GitHub Actions, etc. |

**Scope Derivation**:
- Extract from common path in modified files
- Use `/` for nested scopes (e.g., `api/auth`)
- Omit if changes span unrelated areas

**Breaking Changes**:
- Add `!` after scope: `feat(api)!: description`

#### 3.2 Body Format
Structure the body with these sections as applicable:

```
## Added
- New feature or file added (path/to/file)

## Changed
- Modified behavior or refactored code (path/to/file)

## Fixed
- Bug fix description (path/to/file)

## Removed
- Deleted feature or file (path/to/file)
```

**Rules**:
- Only include sections with actual changes
- Each bullet should reference the affected file/component
- Be specific about what changed, not just "updated X"

#### 3.3 Footer Format

**Default Footer** (always included):
```
Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Optional Squashed Commits Section** (only if `--with-squashed-commits` flag is used):
```
Squashed commits:
- <hash> <original message>
- <hash> <original message>

Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Additional Footer Items** (if applicable):
- `BREAKING CHANGE: <description>`
- `Fixes: #<issue-number>`
- `Closes: #<issue-number>`
- `Refs: <spec-path>`

---

### Step 4: Generate Commit Message Preview

**INSTRUCTION**: Use the gathered context to generate the complete message.

**Process**:
1. Analyze git diff file-by-file for change types
2. Read git log for original commit messages
3. Determine primary type from changes
4. Derive scope from file paths
5. Write title (max 50 chars)
6. Construct body with Added/Changed/Fixed/Removed sections
7. Build footer (conditionally include squashed commits list if `INCLUDE_SQUASHED_COMMITS="true"`)

**Output Format (without --with-squashed-commits flag, default)**:
```
==========================================
PROPOSED COMMIT MESSAGE:
==========================================
<type>(<scope>): <description>

## Added
- ...

## Changed
- ...

## Fixed
- ...

## Removed
- ...

Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
==========================================
```

**Output Format (with --with-squashed-commits flag)**:
```
==========================================
PROPOSED COMMIT MESSAGE:
==========================================
<type>(<scope>): <description>

## Added
- ...

## Changed
- ...

## Fixed
- ...

## Removed
- ...

Squashed commits:
- <hash> <message>
- <hash> <message>

Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
==========================================
```

---

### Step 5: User Confirmation

**INSTRUCTION**: Show proposed commit message and ask for confirmation.

**Ask user**:
1. "Does this commit message accurately reflect the changes?"
2. "Would you like to amend the commit with this message? (yes/no/edit)"

**Options**:
- `yes`: Proceed with amending the commit
- `no`: Abort without changes
- `edit`: Allow user to modify the message before amending

---

### Step 6: Amend Commit

**CRITICAL**: This step modifies git history. Ensure user confirmed.

```bash
echo "Amending HEAD commit with semantic message..."
echo ""

# Store the semantic commit message (use heredoc for multi-line)
git -C "$ROOT" commit --amend -m "$(cat <<'EOF'
[GENERATED_COMMIT_MESSAGE_HERE]
EOF
)"

echo "Commit amended successfully."
```

**Safety Note**:
- Only amends HEAD commit (no rebase involved)
- Modifies only message, not history structure
- Requires force-push if commit was already pushed

---

### Step 7: Verification & Next Steps

#### 7.1 Verify Amendment Success
```bash
echo "Verifying amended commit..."
echo ""

# Show final commit
echo "Amended commit:"
git -C "$ROOT" log --oneline -1
echo ""

# Show commit details
git -C "$ROOT" show --stat HEAD
```

#### 7.2 Provide Next Steps
```bash
echo "=========================================="
echo "COMMIT AMENDED"
echo "=========================================="
echo ""
echo "Branch: $BRANCH"
echo "Target base: $TARGET_REF"
echo ""
echo "Next steps:"
echo "  1. Review commit: git show HEAD"
echo "  2. Push (force required if already pushed): git push --force-with-lease origin $BRANCH"
echo "  3. Create PR if ready"
echo ""
echo "IMPORTANT: If commit was already pushed, force-push is required."
echo "Only force-push to feature branches, never to $TARGET_REF."
echo "=========================================="
```

---

## Safety Checks Summary

- Verify not on protected branch (main)
- Check for uncommitted changes
- Verify HEAD commit exists
- Confirm target branch exists
- Show proposed message preview
- Require user confirmation
- Warn about force-push requirement if needed

---

## Edge Cases

### No Commits Ahead of Target
If branch is up-to-date with target:
- WARNING: "No commits ahead of $TARGET_REF. Branch may be up-to-date."
- Proceed anyway (user may want to improve existing commit message)

### Invalid Target Reference
If target cannot be resolved:
- ERROR: "Cannot resolve target '<target>'"
- List available remote branches
- Suggest valid formats: commit hash, branch name, or remote ref

---

## Example Output

### Default Behavior (without --with-squashed-commits)

For a branch with changes to API and tests:

```
feat(api): add user authentication endpoints

## Added
- POST /auth/login endpoint (src/api/auth.ts)
- POST /auth/register endpoint (src/api/auth.ts)
- JWT token validation middleware (src/middleware/auth.ts)

## Changed
- Updated route configuration (src/routes/index.ts)
- Extended User model with password hash (src/models/user.ts)

## Fixed
- Corrected error handling in validation (src/utils/validate.ts)

Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
```

### With --with-squashed-commits Flag

```
feat(api): add user authentication endpoints

## Added
- POST /auth/login endpoint (src/api/auth.ts)
- POST /auth/register endpoint (src/api/auth.ts)
- JWT token validation middleware (src/middleware/auth.ts)

## Changed
- Updated route configuration (src/routes/index.ts)
- Extended User model with password hash (src/models/user.ts)

## Fixed
- Corrected error handling in validation (src/utils/validate.ts)

Squashed commits:
- abc123f feat: add login endpoint
- def456a feat: add register endpoint
- 789ghij fix: validation error handling
- klm012n test: add auth tests

Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
```
