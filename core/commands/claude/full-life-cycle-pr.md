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
2. Initial confirmation gate (only user prompt in entire workflow)
3. `/branch` - Create and checkout new branch
4. `/o_spec` - Run full spec workflow (CREATE -> IMPLEMENT -> TEST -> DOCUMENT)
5. `/milestone --skip-tag --auto` - Squash commits and rebase to origin/main (autonomous)
6. `/pull_request` - Create comprehensive PR

## State Persistence

This command maintains workflow state in a YAML file for reliable resumption after interruptions.

### State File Location

```
outputs/orc/{YYYY}/{MM}/{DD}/{HHMMSS}-{UUID}/workflow_state.yml
```

### State Schema

```yaml
session_id: "HHMMSS-xxxxxxxx"  # Short UUID (8-char)
command: "full-life-cycle-pr"
started_at: "2025-12-19T11:51:52Z"
updated_at: "2025-12-19T12:30:00Z"
status: "in_progress"  # pending | in_progress | completed | failed

arguments:
  branch_name: "feat/my-feature"
  spec_arg: "Add authentication module"
  modifier: "normal"

current_step: 3
current_step_status: "in_progress"  # pending | in_progress | completed | failed
steps:
  - step: 1
    name: "branch"
    status: "completed"
    started_at: "2025-12-19T11:51:52Z"
    completed_at: "2025-12-19T11:52:30Z"
  - step: 2
    name: "o_spec"
    status: "completed"
    started_at: "2025-12-19T11:52:31Z"
    completed_at: "2025-12-19T11:55:00Z"

# Extension for nested command tracking
nested_invocations:
  - parent_step: 2           # Which step invoked the nested command
    command: "o_spec"
    session_id: "HHMMSS-yyyyyyyy"  # Link to nested session
    input_args:
      modifier: "normal"
      spec_path: "specs/2025/12/feat/my-feature/001-spec.md"
    substeps:
      - step: 1
        stage: "CREATE"
        status: "completed"
      - step: 2
        stage: "RESEARCH"
        status: "completed"
      - step: 3
        stage: "PLAN"
        status: "in_progress"
    output_result:
      final_status: "completed"
      commits_created: ["abc1234", "def5678"]
      spec_path: "specs/2025/12/feat/my-feature/001-spec.md"

error_context: null
resume_instruction: "Resume from step 3 with: /full-life-cycle-pr resume"
```

### Resume Behavior

On command start:
1. Check for existing `in_progress` state files in `outputs/orc/{YYYY}/{MM}/{DD}/*/workflow_state.yml`
2. If found for `full-life-cycle-pr`: display session info and ask user to resume or start fresh
3. On resume: load state, continue from `current_step`
4. On start fresh: archive old state (rename with `.archived` suffix), initialize new session

### State Update Protocol (AI-Interpreted)

State updates use a two-phase PRE/POST pattern for real-time visibility:

**PRE (before step execution):**
1. Read `workflow_state.yml`
2. Set `current_step` to current step number
3. Set `current_step_status` to `"in_progress"`
4. Add/update step entry in `steps` with `status: "in_progress"`, `started_at: <timestamp>`
5. Update `updated_at` timestamp
6. Write state file

**POST (after step completion):**
1. Read `workflow_state.yml`
2. Set `current_step_status` to `"completed"`
3. Update step entry in `steps` with `status: "completed"`, `completed_at: <timestamp>`
4. Update `updated_at` timestamp
5. If final step: set `status: "completed"`
6. Write state file

**On Error:** Set `current_step_status: "failed"`, `status: "failed"`, populate `error_context`

### Orchestrator Behavioral Constraint

**CRITICAL**: This command MUST maintain orchestrator role:
- ALWAYS delegate via sub-commands (`/branch`, `/o_spec`, `/milestone`, `/pull_request`)
- NEVER execute tasks directly (editing files, running tests, etc.)
- On user interruption: acknowledge feedback, update state, delegate corrective action via sub-commands
- State file serves as context anchor preventing context loss

---

## Step 0: Resume Detection

**EXECUTE BEFORE PRE-FLIGHT**: Check for existing in-progress sessions.

```bash
# Check for in-progress workflow state
TODAY=$(date +%Y/%m/%d)
STATE_DIR="outputs/orc/$TODAY"

if [ -d "$STATE_DIR" ]; then
  for state_file in "$STATE_DIR"/*/workflow_state.yml; do
    if [ -f "$state_file" ]; then
      CMD=$(grep -E '^command:' "$state_file" 2>/dev/null | cut -d'"' -f2)
      STATUS=$(grep -E '^status:' "$state_file" 2>/dev/null | cut -d'"' -f2)
      if [ "$CMD" = "full-life-cycle-pr" ] && [ "$STATUS" = "in_progress" ]; then
        echo "=========================================="
        echo "EXISTING IN-PROGRESS SESSION DETECTED"
        echo "=========================================="
        echo "Session: $(dirname "$state_file")"
        echo ""
        cat "$state_file"
        echo ""
        echo "Options: 'resume' to continue, 'fresh' to start new session"
      fi
    fi
  done
fi
```

**AI Decision**: If in-progress session detected, ask user whether to resume or start fresh. On resume, load `current_step` from state file and jump to appropriate step.

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
# Parse arguments safely, respecting quoted strings
# Pattern: <branch-name> <"spec arg" or path> [modifier]
BRANCH_NAME=""
SPEC_ARG=""
MODIFIER="normal"

# Extract branch name (first unquoted word)
BRANCH_NAME=$(echo "$ARGUMENTS" | awk '{print $1}')
REMAINING=$(echo "$ARGUMENTS" | sed "s/^[^ ]* *//")

# Extract SPEC_ARG (handles quoted strings or single word)
if [[ "$REMAINING" =~ ^\"([^\"]*)\" ]]; then
  # Quoted string: "Add new feature"
  SPEC_ARG="${BASH_REMATCH[1]}"
  REMAINING=$(echo "$REMAINING" | sed 's/^"[^"]*" *//')
elif [[ "$REMAINING" =~ ^\'([^\']*)\' ]]; then
  # Single-quoted string: 'Add new feature'
  SPEC_ARG="${BASH_REMATCH[1]}"
  REMAINING=$(echo "$REMAINING" | sed "s/^'[^']*' *//")
else
  # Unquoted: assume single word (path or simple arg)
  SPEC_ARG=$(echo "$REMAINING" | awk '{print $1}')
  REMAINING=$(echo "$REMAINING" | sed "s/^[^ ]* *//")
fi

# Extract modifier (remaining first word, default: normal)
MODIFIER=$(echo "$REMAINING" | awk '{print $1}')
[[ -z "$MODIFIER" ]] && MODIFIER="normal"

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

## Step 2: Display Confirmation Gate (ONLY user prompt)

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
echo "This will execute AUTONOMOUSLY after confirmation:"
echo "  1. Create branch: /branch $BRANCH_NAME"
echo "  2. Run spec workflow: /o_spec $MODIFIER \"$SPEC_ARG\""
echo "  3. Squash & rebase: /milestone --skip-tag --auto"
echo "  4. Create PR: /pull_request"
echo ""
echo "NOTE: This is the ONLY confirmation gate. After 'yes', workflow runs to completion."
echo ""
read -p "Proceed with full lifecycle? (yes/no): " CONFIRM
echo ""

if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted by user."
  exit 0
fi

# Initialize session after confirmation
SESSION_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)
SESSION_TIMESTAMP=$(date +%H%M%S)
SESSION_ID="${SESSION_TIMESTAMP}-${SESSION_UUID}"
SESSION_DIR="outputs/orc/$(date +%Y/%m/%d)/${SESSION_ID}"

mkdir -p "$SESSION_DIR"

# Create initial workflow_state.yml
cat > "$SESSION_DIR/workflow_state.yml" << EOF
session_id: "$SESSION_ID"
command: "full-life-cycle-pr"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status: "in_progress"

arguments:
  branch_name: "$BRANCH_NAME"
  spec_arg: "$SPEC_ARG"
  modifier: "$MODIFIER"

current_step: 1
current_step_status: "pending"
steps: []
nested_invocations: []

error_context: null
resume_instruction: "Resume with: /full-life-cycle-pr resume"
EOF

echo "Session initialized: $SESSION_DIR"
```

---

## Step 3: Execute /branch

```bash
echo "=========================================="
echo "STEP 1/4: Creating branch"
echo "=========================================="
echo ""
```

**State Update (PRE)**: Before invoking /branch:
- Set `current_step: 1`
- Set `current_step_status: "in_progress"`
- Add step entry: `{step: 1, name: "branch", status: "in_progress", started_at: <timestamp>}`
- Update `updated_at`

**INVOKE**: `/branch $BRANCH_NAME`

**Error Handling**: If `/branch` fails, STOP immediately and display error.

**State Update (POST)**: After successful /branch:
- Set `current_step_status: "completed"`
- Update step entry: `{status: "completed", completed_at: <timestamp>}`
- Update `updated_at`

---

## Step 4: Execute /o_spec

```bash
echo ""
echo "=========================================="
echo "STEP 2/4: Running spec workflow"
echo "=========================================="
echo ""
```

**State Update (PRE)**: Before invoking /o_spec:
- Set `current_step: 2`
- Set `current_step_status: "in_progress"`
- Add step entry: `{step: 2, name: "o_spec", status: "in_progress", started_at: <timestamp>}`
- Initialize nested invocation entry in `nested_invocations`:
  ```yaml
  - parent_step: 2
    command: "o_spec"
    session_id: null  # Will be populated by o_spec
    input_args:
      modifier: "$MODIFIER"
      spec_path: "$SPEC_ARG"
    substeps: []
    output_result: null
  ```
- Update `updated_at`

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

**State Update (POST)**: After successful /o_spec:
- Set `current_step_status: "completed"`
- Update step entry: `{status: "completed", completed_at: <timestamp>}`
- Update nested invocation entry with:
  - `session_id`: from o_spec's workflow_state.yml
  - `substeps`: mirror of o_spec's steps array
  - `output_result`: `{final_status: "completed", spec_path: <resolved_path>}`
- Update `updated_at`

---

## Step 5: Execute /milestone (without tagging, autonomous)

```bash
echo ""
echo "=========================================="
echo "STEP 3/4: Squashing commits and rebasing"
echo "=========================================="
echo ""
```

**State Update (PRE)**: Before invoking /milestone:
- Set `current_step: 3`
- Set `current_step_status: "in_progress"`
- Add step entry: `{step: 3, name: "milestone", status: "in_progress", started_at: <timestamp>}`
- Update `updated_at`

**INVOKE**: `/milestone --skip-tag --auto`

**Arguments**:
- `--skip-tag` = no tag creation (only squash + rebase)
- `--auto` = skip confirmation gates (autonomous execution)
- Auto-detects base branch (origin/main)
- Auto-validates CHANGELOG [Unreleased] section

**Behavior**:
- Will validate CHANGELOG has entries (required)
- Will squash all commits since origin/main into one
- Will generate Conventional Commit message
- Will rebase onto origin/main
- Will push automatically (`--auto` skips confirmation gates)

**Error Handling**: If `/milestone` fails:
```
ERROR: Milestone validation or squashing failed

Possible causes:
- CHANGELOG [Unreleased] section is empty
- Rebase conflicts occurred
- Git state issues

Review error message above and fix manually.
```

**State Update (POST)**: After successful /milestone:
- Set `current_step_status: "completed"`
- Update step entry: `{status: "completed", completed_at: <timestamp>}`
- Update `updated_at`

---

## Step 6: Execute /pull_request

```bash
echo ""
echo "=========================================="
echo "STEP 4/4: Creating pull request"
echo "=========================================="
echo ""
```

**State Update (PRE)**: Before invoking /pull_request:
- Set `current_step: 4`
- Set `current_step_status: "in_progress"`
- Add step entry: `{step: 4, name: "pull_request", status: "in_progress", started_at: <timestamp>}`
- Update `updated_at`

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

**State Update (POST)**: After successful /pull_request:
- Set `current_step_status: "completed"`
- Set `status: "completed"` (final step)
- Update step entry: `{status: "completed", completed_at: <timestamp>}`
- Update `updated_at`

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
3. **Single confirmation gate**: One "yes" at start, then fully autonomous execution
4. **Step-by-step display**: Shows clear progress indicators
5. **Error context**: Provides helpful error messages with current state
6. **Graceful degradation**: Each command failure provides recovery options
7. **Safe push strategy**: Uses `--force-with-lease` for squash operations
8. **Protected branch check**: Prevents running from main/master

---

## Design Decisions

1. **Autonomous after confirmation**: Single confirmation gate at start, then `--auto` flag to sub-commands
2. **Sequential execution**: Each command runs one at a time with clear boundaries
3. **No tagging in milestone**: Uses milestone with `--skip-tag` flag to squash without creating release tag
4. **Default modifier "normal"**: Balances quality and speed (skips PLAN_REVIEW, uses opus for critical stages)
5. **Full auto-detect in milestone**: Uses `--skip-tag --auto` flags while maintaining smart defaults
6. **Inline prompt support**: Accepts both spec file paths and inline prompts for quick feature creation
7. **GH_USER validation**: Checks .env for GH_USER to ensure PR authentication works
8. **Command composition**: Leverages existing battle-tested commands rather than reimplementing logic

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
