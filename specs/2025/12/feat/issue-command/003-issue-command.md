# Human Section
Critical: any text/subsection here cannot be modified by AI.

## High-Level Objective (HLO)

Create a `/issue` command that allows users to report issues to the central agentic-config repository (https://github.com/MatiasComercio/agentic-config/issues) using the GitHub CLI. This command streamlines bug reporting and feature requests by extracting context from the current conversation or accepting explicit user input, reducing friction for contributors to report problems or suggest improvements.

## Mid-Level Objectives (MLO)

- CREATE `core/commands/claude/issue.md` command file with proper YAML frontmatter
- IMPLEMENT gh CLI integration for issue creation targeting the central repository
- SUPPORT two input modes:
  - **Context-based**: Extract issue details from current conversation (errors, stack traces, unexpected behavior)
  - **Explicit**: Accept user-provided title and body
- VALIDATE gh CLI authentication before issue creation
- FORMAT issue body with structured sections (description, reproduction steps, environment info)
- INCLUDE automatic environment metadata (OS, git version, branch context)
- ENSURE project-agnostic design (works from any agentic-config installation)

## Details (DT)

### Target Repository
- Issues MUST be created at: `MatiasComercio/agentic-config`
- Use `gh issue create --repo MatiasComercio/agentic-config`

### Command Usage Patterns
```
/issue                           # Context-based: extract from conversation
/issue "Title" "Description"     # Explicit: user provides details
/issue --bug "Title"             # Bug report with template
/issue --feature "Title"         # Feature request with template
```

### Issue Body Structure
```markdown
## Description
<User-provided or context-extracted description>

## Environment
- OS: <detected>
- Shell: <detected>
- Git version: <detected>
- Branch: <current branch if relevant>
- agentic-config version: <from git tag or commit>

## Context
<If extracted from conversation: relevant error messages, stack traces, or unexpected behavior>

## Reproduction Steps
<If applicable>

---
Reported via `/issue` command from agentic-config
```

### Constraints
- MUST validate `gh auth status` before creating issue
- MUST NOT expose sensitive information (API keys, personal paths, etc.)
- SHOULD sanitize paths to be relative or anonymized
- MUST handle cases where no context is available gracefully
- MUST confirm with user before creating issue (show preview)

### Reference Commands
- Similar pattern to: `core/commands/claude/pull_request.md`
- Uses gh CLI like: `core/commands/claude/gh_pr_review.md`

## Behavior

You are implementing a production-ready Claude Code command. Follow the established patterns in existing commands (pull_request.md, gh_pr_review.md). The command must be robust, handle edge cases gracefully, and provide clear user feedback at each step.

# AI Section
Critical: AI can ONLY modify this section.

## Research

### Existing Command Patterns Analysis

**Reference Commands Examined:**
- `core/commands/claude/pull_request.md` - Comprehensive PR creation with gh CLI
- `core/commands/claude/gh_pr_review.md` - Multi-agent PR review orchestration
- `core/commands/claude/adr.md` - Context-aware decision documentation
- `core/commands/claude/branch.md` - Simple branch/spec creation
- `core/commands/claude/squash.md` - Git history manipulation with confirmation

**YAML Frontmatter Structure:**
```yaml
---
description: <short description for /help listing>
argument-hint: <usage pattern>
project-agnostic: true  # Required for central repo commands
allowed-tools:
  - Bash
  - Read
  - Write  # Only if needed
---
```

**Key Patterns Identified:**

1. **Authentication Verification (from pull_request.md)**
   - Execute `gh auth status` FIRST before any operations
   - Extract authenticated user from output
   - Provide clear error with remediation steps (`gh auth login`)

2. **Pre-Flight Validation Structure**
   - Check prerequisites sequentially
   - STOP early with descriptive errors
   - Warn (don't block) for non-critical issues

3. **HEREDOC for Structured Content (gh CLI)**
   ```bash
   gh issue create --repo OWNER/REPO \
     --title "Title" \
     --body "$(cat <<'EOF'
   Structured body content here
   Preserves multi-line formatting
   EOF
   )"
   ```

4. **User Confirmation Gates**
   - Show preview of action before execution
   - Wait for explicit confirmation on destructive/external actions

### gh CLI Issue Creation Analysis

**Command Syntax:**
```bash
gh issue create [flags]
  -R, --repo [HOST/]OWNER/REPO  # Target repository
  -t, --title string            # Issue title
  -b, --body string             # Issue body
  -F, --body-file file          # Body from file
  -l, --label name              # Add labels (repeatable)
  -T, --template name           # Use issue template
  -a, --assignee login          # Assign to user
```

**Target Repository Pattern:**
```bash
gh issue create --repo MatiasComercio/agentic-config \
  --title "Issue Title" \
  --body "Issue body"
```

**Label Support:**
- Bug reports: `--label bug`
- Feature requests: `--label enhancement`
- Multiple labels: `--label bug --label "help wanted"`

### Context Extraction Mechanism (from adr.md)

**Dual-Mode Input Pattern:**
1. **Explicit Mode**: User provides arguments directly
   - `/issue "Title" "Description"` - Use provided values
   - `/issue --bug "Title"` - Use provided title with bug template

2. **Context Mode**: Infer from conversation
   - `/issue` (no args) - Extract from recent conversation
   - Look for: error messages, stack traces, unexpected behavior descriptions
   - If unclear: STOP and ask user to clarify

**Context Extraction Heuristics:**
- Search recent messages for error patterns: `Error:`, `Exception:`, `failed`, `unexpected`
- Extract stack traces: Lines starting with `at `, `File "`, traceback patterns
- Identify reproduction steps from "I tried..." / "When I..." patterns
- Extract expected vs actual behavior descriptions

### Environment Metadata Collection

**Safe Information to Include:**
```bash
# OS detection
uname -s    # Darwin, Linux, etc.
uname -r    # OS version

# Shell detection
echo $SHELL | xargs basename

# Git version
git --version | cut -d' ' -f3

# Current branch (if relevant)
git branch --show-current 2>/dev/null || echo "N/A"

# agentic-config version
git -C "$AGENTIC_GLOBAL" describe --tags --always 2>/dev/null || cat "$AGENTIC_GLOBAL/VERSION"
```

**Information to EXCLUDE (Privacy/Security):**
- Absolute paths containing usernames
- API keys or tokens
- Personal email addresses
- Internal project names
- Private repository information

### Sanitization Patterns

**Path Anonymization:**
```bash
# Replace home directory with ~
path="${path/$HOME/\~}"

# Replace project root with <project>
path="${path/$PROJECT_ROOT/<project>}"
```

**Sensitive Pattern Detection:**
- Check for API keys: `[A-Za-z0-9]{32,}`
- Check for tokens: `ghp_`, `sk-`, `AKIA`
- Check for emails in paths: `@` patterns

### Test Patterns Analysis

**Existing Test Infrastructure:**
- `tests/e2e/` - Shell-based E2E tests with `test_utils.sh`
- `tests/test_dry_run_guard.py` - Python unit tests with `TestResult` class

**Test Utilities Available (test_utils.sh):**
- `setup_test_env()` - Isolated test environment
- `cleanup_test_env()` - Cleanup
- `assert_eq`, `assert_file_exists`, `assert_command_success`
- `create_test_project <dir> <type>`

**Recommended Test Approach:**
- Shell E2E test: `tests/e2e/test_issue_command.sh`
- Test with mock gh CLI or `--dry-run` pattern
- Test both explicit and context modes

### Affected Files

**New File:**
- `core/commands/claude/issue.md` - Main command implementation

**No Changes Required to Existing Files**

### Strategy

**Implementation Approach:**

1. **Command Structure** (following pull_request.md pattern)
   - YAML frontmatter with `project-agnostic: true`
   - Allowed tools: `Bash`, `Read` (no Write needed - gh CLI creates issue)
   - Clear argument-hint: `[title] [description] | --bug | --feature`

2. **Workflow Steps**

   **Step 1: Authentication Verification**
   - Run `gh auth status` and capture output
   - If not authenticated: STOP with clear error and `gh auth login` instruction
   - If authenticated: Continue with confirmation message

   **Step 2: Input Mode Detection**
   - Parse `$ARGUMENTS` to determine mode:
     - If empty: Context extraction mode
     - If `--bug` or `--feature`: Template mode with title
     - If quoted strings: Explicit mode with title/description

   **Step 3: Context Extraction (if needed)**
   - Analyze recent conversation for:
     - Error messages and stack traces
     - Commands that failed
     - Unexpected behavior descriptions
   - Generate title from error summary
   - Generate description from context

   **Step 4: Environment Collection**
   - Gather safe metadata (OS, shell, git version, branch)
   - Sanitize any paths to remove personal information
   - Format as structured environment section

   **Step 5: Issue Preview**
   - Display formatted issue preview to user:
     ```
     === ISSUE PREVIEW ===
     Repository: MatiasComercio/agentic-config
     Title: <title>
     Labels: <labels>

     Body:
     ---
     <formatted body>
     ---

     Create this issue? (yes/no)
     ```
   - Wait for explicit `yes` confirmation

   **Step 6: Create Issue**
   - Execute `gh issue create --repo MatiasComercio/agentic-config ...`
   - Use HEREDOC for body formatting
   - Capture and display issue URL

   **Step 7: Report Results**
   - Display success with issue URL
   - Show next steps (view issue, add more context)

3. **Issue Body Template**
   ```markdown
   ## Description
   <user/context description>

   ## Environment
   - OS: <detected>
   - Shell: <detected>
   - Git: <version>
   - Branch: <if relevant>
   - agentic-config: <version/commit>

   ## Context
   <error messages, stack traces if available>

   ## Reproduction Steps
   <if available>

   ---
   Reported via `/issue` command
   ```

4. **Error Handling**
   - `gh auth status` failure: Clear login instructions
   - No context available: Ask user for explicit input
   - `gh issue create` failure: Show error, suggest manual creation
   - Network issues: Graceful error with retry suggestion

5. **Testing Strategy**
   - Unit test: `tests/test_issue_command.py` (if Python needed)
   - E2E test: `tests/e2e/test_issue_command.sh`
   - Test scenarios:
     - Authenticated vs unauthenticated
     - Explicit input mode
     - Context extraction mode (mock conversation)
     - Sanitization of sensitive data
     - Preview confirmation flow
   - Use `--dry-run` or mock `gh` for non-destructive testing

6. **Security Considerations**
   - Sanitize all paths before including in issue
   - Detect and redact potential secrets
   - Never include `.env` file contents
   - Allow user to edit preview before submission

## Plan

## Plan Review

## Implement

## Test Evidence & Outputs

## Updated Doc

## Post-Implement Review
