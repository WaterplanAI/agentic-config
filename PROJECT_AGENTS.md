# Project-Specific Guidelines

Project overrides for agentic-config repository.

## Content Rules

- DO NOT use emojis in markdown files
- ALWAYS ensure every git-tracked asset is project-agnostic and anonymous
- All documentation and code must be anonymized (no personal names, emails, or identifiable information)
- ALWAYS use anonymized text, inputs, and examples unless user explicitly requests real data
  - Use generic names: John Smith, Jane Doe, Example Corp
  - Use example domains: example.com, example.org
  - Use placeholder IDs: `abc123`, `<file_id>`, `<email>`
- CRITICAL: NEVER add `outputs/` content to git - this directory is gitignored for a reason

## PII Compliance Enforcement

**Automated pre-commit hook verifies PII compliance on every commit.**

### What Gets Blocked
- Real email addresses (except @example.com, @example.org)
- Real phone numbers, physical addresses
- Real names tied to identifiable data
- Real company names (not Example Corp, Acme Inc)
- Monetary values (salaries, specific prices, budgets)
- API keys, tokens, credentials

### What Is Allowed
- Anonymized examples: john@example.com, Jane Doe, Example Corp
- Generic companies: Acme Inc, Test Company
- Fictional placeholder domains: @corp.com, @corporate.com, @external.com (not real TLDs)
- Placeholder syntax: `<email>`, `<id>`, `abc123`, `$X`
- System emails: noreply@, @anthropic.com (Co-Authored-By)

### Verification
After every commit, confirm hook output shows:
```
PII_AUDIT: PASS
```

If blocked, fix the PII issue and re-commit.

## Installation Flexibility

CRITICAL - agentic-config MUST be agnostic and work seamlessly in all scenarios:
- Repository root installation
- Subdirectory installation (any depth)
- Non-git directory installation
- All paths, hooks, and configurations must resolve correctly regardless of installation location or current working directory

## Symlinks

CRITICAL - All project symlinks MUST use relative paths (NEVER create symlinks inside `core/` directories):
- Commands: Use `../../core/commands/claude/<name>` from `.claude/commands/`
- Skills: Use `../../core/skills/<name>` from `.claude/skills/`
- Agents: Use `../../core/agents/<name>` from `.claude/agents/`
- NEVER use absolute paths in symlinks
- Reference: .claude/commands/init.md for canonical implementation

## Git Commit Standards

This project uses Conventional Commits (https://conventionalcommits.org) with extended formatting:

- Format: `<type>(<scope>): <description>`
- Types: feat, fix, docs, chore, refactor, test, style, perf, build, ci
- Commit body uses structured sections: Added, Changed, Fixed, Removed
- Squashed commits include original commit list in body

## CHANGELOG

- Add new entries to `[Unreleased]` section
- DO NOT modify already released/tagged versions unless explicitly requested

## Model Tier Terminology

Always use tier-based terminology instead of specific model names in core assets to remain provider-agnostic.

| Tier | Anthropic | Google | OpenAI |
|------|-----------|--------|--------|
| Low-tier | haiku | flash-lite | codex mini |
| Medium-tier | sonnet | flash | codex |
| High-tier | opus | pro | codex max |

**OpenAI reasoning efforts**: Each tier can optionally configure reasoning effort: low, medium (default), high, extra-high.

Example usage:
- Correct: "Use low-tier model for simple reads"
- Incorrect: "Use haiku for simple reads"

## Exceptions

The following are explicitly permitted as exceptions to the rules above:

### Git Commit Author Identity

Commits may be authored by:
- Personal identity (repository maintainer)
- Claude (AI assistant): `Co-Authored-By: Claude <noreply@anthropic.com>`

This is acceptable because git history attribution is separate from content anonymization.

### Emojis in Specific Files

The following files may contain emojis for functional purposes (status indicators, visual signals):
- `core/agents/agentic-validate.md` - validation status markers
- `core/agents/agentic-status.md` - status display formatting
- `core/agents/agentic-update.md` - update status indicators
- `core/agents/agentic-customize.md` - customization status
- `core/commands/claude/milestone.md` - milestone status markers

These emojis serve as machine-readable status signals in agent output, not decorative content.
