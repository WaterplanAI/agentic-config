# Project Guidelines

## Environment & Tooling
- **Package Manager:** uv
- **Type Checking:** uv run pyright
- **Linting:** uv run ruff check [--fix] <path>
- **Build:** Only when explicitly requested
- After edits: uv run ruff check --fix <file> && uv run pyright <file>

## Core Rules
- Verify over assume; failures first; always re-raise (never swallow exceptions)
- Type hints for all public functions, descriptive names, small pure functions
- Minimal changes; avoid ambiguity; no placeholders
- EFFICIENCY in application and UX - reflect in every implementation
- Glob excludes hidden dirs: use explicit non-hidden roots, e.g. `Glob(pattern="*.md", path="plugins/ac-tools/skills/x")`

## Skill Triggering

**MANDATORY** - No exceptions:
- `\<name>` = look up in `.claude/commands/`, `.claude/skills/` (if present), and `plugins/*/skills/`; invoke via Skill tool
- 1% match = invoke. Never skip. Never reimplement skill behavior manually.
- Explicit user request (e.g., "/mux", "/spec") = invoke IMMEDIATELY

## Content & PII
- DO NOT use emojis in markdown files
- All git-tracked content: project-agnostic, anonymized (no real names, emails, companies)
- Use: John Smith, Jane Doe, Example Corp, example.com, `<email>`, `abc123`
- NEVER add `outputs/` content to git
- Pre-commit hook enforces PII. Confirm `PII_AUDIT: PASS`. Fix and re-commit if blocked.
- Check `## Exceptions` for special cases.

## Git Workflow
- Base branch: main (not master); never commit to main
- NEVER amend unless user says 'amend commit'
- NEVER commit gitignored files; do NOT `git add -f`
- Use CWD-relative paths from git status for git add
- Conventional Commits: `<type>(<scope>): <description>`
  - Types: feat, fix, docs, chore, refactor, test, style, perf, build, ci
  - Body sections: Added, Changed, Fixed, Removed
  - Squashed commits include original commit list

## CHANGELOG
- Entries only against origin/main; unreleased changes = ONE logical unit
- No "Fixed" entries for pre-merge iterations
- Add to `[Unreleased]`; do NOT modify released/tagged versions

## Model Tier Terminology

Use tier-based names in core assets, not specific model names:

| Tier | Anthropic | Google | OpenAI |
|------|-----------|--------|--------|
| Low-tier | haiku | flash-lite | codex mini |
| Medium-tier | sonnet | flash | codex |
| High-tier | opus | pro | codex max |

## Specs
- Specs MUST be created in `.specs/` (external specs repo), NEVER in `specs/` (gitignored local dir)
- `/spec CREATE` must target `.specs/` path convention: `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<short-title>.md`
- `specs/` is for local scratch only — never commit, never use as spec destination

## Session Resume
READ @RESUME.md only when user asks "where we left off" / "what's next" / "resume"

## Exceptions

### Git Commit Author Identity
Commits may use personal identity or Claude (`Co-Authored-By: Claude <noreply@anthropic.com>`).

### GitHub Organization Name
`WaterplanAI` may appear in documentation as the public GitHub organization for plugin distribution.

### Pre-commit PII Audit Model Pin
`.githooks/pre-commit` may pin a concrete model ID for deterministic local PII audit behavior, including the current `openai-codex/gpt-5.3-codex:medium` configuration.
