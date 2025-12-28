# Project Guidelines

## Environment & Tooling
- **Package Manager:** uv
- **Type Checking:** uv run pyright
- **Linting:** uv run ruff check [--fix] <path>
- **Build:** Only when explicitly requested

## Style & Conventions
- Type hints for all public functions, descriptive names, small pure functions
- After edits: uv run ruff check --fix <file> && uv run pyright <file>

## Core Principles
- Verify over assume
- Failures first (lead with errors)
- Always re-raise (never swallow exceptions)
- DO NOT OVERCOMPLICATE
- DO NOT OVERSIMPLIFY

## Critical Rules
- NEVER amend commits unless user says 'amend commit'
- NEVER commit files in gitignored directories unless explicitly requested - DO NOT use git add -f to bypass .gitignore
- Minimal changes; avoid ambiguity; no placeholders
- Keep prompts concise; log costs
- EFFICIENCY in application performance and user experience - REFLECT this in EVERY implementation

## Dry-Run Verification

Before ANY file write operation (Write, Edit, NotebookEdit, Bash commands that modify files), verify dry-run status:

1. Check if `outputs/session/status.yml` exists
2. If exists, read `dry_run` field
3. If `dry_run: true`, SKIP the file operation and instead:
   - DESCRIBE what WOULD be changed
   - LOG the proposed change for user review
4. Exception: `outputs/session/status.yml` itself may always be modified
5. For Bash commands:
   - Read-only commands are allowed (ls, cat, grep, find, git status, git diff, etc.)
   - File-writing commands must be skipped (echo >, cp, mv, touch, tee, dd, git add, git commit, etc.)
   - DESCRIBE what the command WOULD do instead of executing

## /spec Workflow
Reference agents/spec/{STAGE}.md for detailed instructions.
- Default path: specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md
- Modify AI Section only; never touch Human Section
- Commit after each stage: spec(<NNN>): <STAGE> - <title>

## Git Workflow
- Base branch: main (not master)
- git status returns CWD-relative paths - use those exact paths with git add
- Never commit to main; never amend unless 'amend commit' explicitly requested
- One stage = one commit: spec(<NNN>): <STAGE> - <title>

## Project-Specific Instructions
READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE

<!-- PROJECT_AGENTS.md contains project-specific guidelines that override defaults -->
