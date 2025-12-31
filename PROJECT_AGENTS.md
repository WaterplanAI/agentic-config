# Project-Specific Guidelines

Project overrides for agentic-config repository.

## Content Rules

- DO NOT use emojis in markdown files
- ALWAYS ensure every git-tracked asset is project-agnostic and anonymous
- All documentation and code must be anonymized (no personal names, emails, or identifiable information)
- CRITICAL: NEVER add `outputs/` content to git - this directory is gitignored for a reason

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
