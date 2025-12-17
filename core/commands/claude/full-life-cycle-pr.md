---
description: Orchestrate complete PR lifecycle from branch creation to PR submission
argument-hint: <branch-name> <spec-path|inline-prompt> [modifier]
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - SlashCommand
---

# Full Life-Cycle PR Command

Orchestrates a complete PR lifecycle by composing existing commands and invoking skills.

## Usage
```
/full-life-cycle-pr <branch-name> <spec-path|inline-prompt> [modifier]
```

**Arguments**:
- `branch-name` (required): Name for the new branch
- `spec-path|inline-prompt` (required): Path to spec file or inline prompt for feature
- `modifier` (optional): Workflow modifier for /o_spec (full/normal/lean/leanest, default: normal)

**Examples**:
```
/full-life-cycle-pr my-feature "Add new authentication module"
/full-life-cycle-pr my-feature specs/path/to/spec.md normal
/full-life-cycle-pr bugfix-123 "Fix memory leak in parser" lean
```

---

## Workflow Overview

This command executes the following steps sequentially:
1. Pre-flight validation (git state, arguments)
2. `/branch` - Create and checkout new branch
3. `/o_spec` - Run full spec workflow (CREATE -> IMPLEMENT -> TEST -> DOCUMENT)
4. `/milestone --skip-tag` - Squash commits and rebase to origin/main (without tagging)
5. `/pull_request` - Create comprehensive PR

---

## Step 1: Pre-Flight Checks

### 1.1 Git State Validation

```bash
# Check for clean working tree
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: Working tree is dirty. Commit or stash changes first."
  git status --short
  exit 1
fi

# Verify not on protected branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo "ERROR: Cannot run from protected branch: $CURRENT_BRANCH"
  echo "Please checkout a different branch first."
  exit 1
fi

# Fetch latest main/master
git fetch origin main 2>/dev/null || git fetch origin master 2>/dev/null
```

### 1.2 Argument Validation

```bash
# Parse arguments safely (avoid command injection)
IFS=' ' read -ra ARGS <<< "$ARGUMENTS"
BRANCH_NAME="${ARGS[0]}"
SPEC_ARG="${ARGS[1]}"
MODIFIER="${ARGS[2]:-normal}"

# Validate branch name exists
if [ -z "$BRANCH_NAME" ]; then
  echo "ERROR: Branch name is required"
  echo "Usage: /full-life-cycle-pr <branch-name> <spec-path|inline-prompt> [modifier]"
  exit 1
fi

# Validate branch name format (security: prevent injection via malformed names)
if ! [[ "$BRANCH_NAME" =~ ^[a-zA-Z0-9/_-]+$ ]]; then
  echo "ERROR: Invalid branch name: $BRANCH_NAME"
  echo "Branch names must only contain: letters, numbers, /, _, -"
  exit 1
fi

# Validate spec argument
if [ -z "$SPEC_ARG" ]; then
  echo "ERROR: Spec path or inline prompt is required"
  echo "Usage: /full-life-cycle-pr <branch-name> <spec-path|inline-prompt> [modifier]"
  exit 1
fi

# Validate modifier
if [ -n "$MODIFIER" ]; then
  case "$MODIFIER" in
    full|normal|lean|leanest)
      ;;
    *)
      echo "ERROR: Invalid modifier: $MODIFIER"
      echo "Valid modifiers: full, normal, lean, leanest"
      exit 1
      ;;
  esac
fi

# Check if branch already exists
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
  echo "ERROR: Branch '$BRANCH_NAME' already exists"
  echo "Please use a different branch name or delete the existing branch."
  exit 1
fi
```

### 1.3 .env Validation

```bash
# Check for .env file and GH_USER (safe parsing - no sourcing)
GH_USER=""
if [ -f .env ]; then
  # Safe extraction: grep for line, cut value, strip quotes
  GH_USER=$(grep -E '^GH_USER=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" | head -1)
  if [ -z "$GH_USER" ]; then
    echo "WARNING: GH_USER not set in .env file"
    echo "Pull request creation may fail authentication check."
    echo "Set GH_USER in .env to match your GitHub username."
  else
    echo "Found GH_USER=$GH_USER in .env"
  fi
else
  echo "WARNING: No .env file found"
  echo "Pull request creation may proceed without user validation."
fi
```

---

## Step 2: Display Confirmation Gate

```bash
echo ""
echo "=========================================="
echo "FULL LIFE-CYCLE PR WORKFLOW"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Branch: $BRANCH_NAME"
echo "  Spec: $SPEC_ARG"
echo "  Modifier: $MODIFIER"
echo "  Base branch: origin/main"
echo ""
echo "This will execute:"
echo "  1. Create branch: /branch $BRANCH_NAME"
echo "  2. Run spec workflow: /o_spec $MODIFIER \"$SPEC_ARG\""
echo "  3. Squash & rebase: /milestone --skip-tag"
echo "  4. Create PR: /pull_request"
echo ""
echo "Each step will run sequentially. You can abort at any confirmation gate."
echo ""
read -p "Proceed with full lifecycle? (yes/no): " CONFIRM
echo ""

if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted by user."
  exit 0
fi
```

---

## Step 3: Execute /branch

```bash
echo "=========================================="
echo "STEP 1/4: Creating branch"
echo "=========================================="
echo ""
```

**INVOKE**: `/branch $BRANCH_NAME`

**Error Handling**: If `/branch` fails, STOP immediately and display error.

---

## Step 4: Execute /o_spec

```bash
echo ""
echo "=========================================="
echo "STEP 2/4: Running spec workflow"
echo "=========================================="
echo ""
```

**INVOKE**: `/o_spec $MODIFIER "$SPEC_ARG"`

**Notes**:
- Pass the FULL spec argument (path or inline prompt) wrapped in quotes
- The /o_spec command will handle spec creation if needed
- All spec stages will run sequentially (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT)

**Error Handling**: If `/o_spec` fails at any stage, STOP and display:
```
ERROR: Spec workflow failed at {STAGE}

Current state:
- Branch: {BRANCH_NAME} (created)
- Commits: {git log --oneline origin/main..HEAD}

You can:
1. Fix the issue and manually continue with remaining steps
2. Delete branch and start over: git branch -D {BRANCH_NAME}
```

---

## Step 5: Execute /milestone (without tagging)

```bash
echo ""
echo "=========================================="
echo "STEP 3/4: Squashing commits and rebasing"
echo "=========================================="
echo ""
```

**INVOKE**: `/milestone --skip-tag`

**Arguments**: Use `--skip-tag` flag to skip tag creation
- Auto-detects base branch (origin/main)
- Auto-validates CHANGELOG [Unreleased] section
- `--skip-tag` flag = no tag creation (only squash + rebase)

**Behavior**:
- Will validate CHANGELOG has entries (required)
- Will squash all commits since origin/main into one
- Will generate Conventional Commit message
- Will rebase onto origin/main
- Will ask for confirmation before pushing

**Error Handling**: If `/milestone` fails:
```
ERROR: Milestone validation or squashing failed

Possible causes:
- CHANGELOG [Unreleased] section is empty
- Rebase conflicts occurred
- Git state issues

Review error message above and fix manually.
```

---

## Step 6: Execute /pull_request

```bash
echo ""
echo "=========================================="
echo "STEP 4/4: Creating pull request"
echo "=========================================="
echo ""
```

**INVOKE**: `/pull_request`

**Arguments**: Use NO arguments to use defaults
- Target branch: main (default)
- GH_USER: from .env (validated in Step 1)

**Behavior**:
- Will verify GitHub authentication
- Will gather commit and diff information
- Will generate comprehensive PR body
- Will create PR using gh CLI

**Error Handling**: If `/pull_request` fails:
```
ERROR: Pull request creation failed

Possible causes:
- GitHub authentication mismatch
- Network issues
- gh CLI not installed

You can manually create PR:
  1. Push branch: git push -u origin {BRANCH_NAME}
  2. Visit: https://github.com/{repo}/compare/{BRANCH_NAME}
```

---

## Step 7: Success Report

```bash
echo ""
echo "=========================================="
echo "FULL LIFE-CYCLE PR COMPLETE"
echo "=========================================="
echo ""
echo "Successfully completed all steps:"
echo "  1. Created branch: $BRANCH_NAME"
echo "  2. Ran spec workflow: $MODIFIER mode"
echo "  3. Squashed commits and rebased to origin/main"
echo "  4. Created pull request"
echo ""
echo "PR URL: {displayed by /pull_request}"
echo ""
echo "Next steps:"
echo "  - Review PR and address any feedback"
echo "  - Monitor CI checks"
echo "  - Request reviewers if needed: gh pr edit --add-reviewer <user>"
echo ""
```

---

## Safety Features

1. **Pre-flight validation**: Ensures clean git state before starting
2. **Argument validation**: Validates all required arguments before execution
3. **Confirmation gate**: Requires explicit "yes" to proceed with workflow
4. **Step-by-step display**: Shows clear progress indicators
5. **Error context**: Provides helpful error messages with current state
6. **Graceful degradation**: Each command failure provides recovery options
7. **No forced pushes**: All commands use safe push strategies
8. **Protected branch check**: Prevents running from main/master

---

## Design Decisions

1. **Sequential execution**: Each command runs one at a time with clear boundaries
2. **No tagging in milestone**: Uses milestone with `--skip-tag` flag to squash without creating release tag
3. **Default modifier "normal"**: Balances quality and speed (skips PLAN_REVIEW, uses opus for critical stages)
4. **Full auto-detect in milestone**: Uses `--skip-tag` flag while maintaining smart defaults (backlog optional, changelog required)
5. **Inline prompt support**: Accepts both spec file paths and inline prompts for quick feature creation
6. **GH_USER validation**: Checks .env for GH_USER to ensure PR authentication works
7. **Command composition**: Leverages existing battle-tested commands rather than reimplementing logic

---

## Edge Cases

### Branch Already Exists
Pre-flight check catches this and aborts before any changes.

### Spec Workflow Fails Mid-Stage
User can manually fix and continue from where it failed, or delete branch and restart.

### CHANGELOG Not Updated
`/milestone` will catch this and require user to update before proceeding.

### Rebase Conflicts
`/milestone` provides conflict resolution guidance and allows abort.

### GitHub Authentication Failure
`/pull_request` validates auth first and provides clear error with fix instructions.

### Network Issues During PR Creation
Shows manual PR creation commands as fallback.
