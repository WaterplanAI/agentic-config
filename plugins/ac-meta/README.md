# ac-meta

Meta-prompting and self-improvement -- generate new skills and hooks following conventions.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-meta@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-meta@agentic-plugins --scope user
claude plugin install ac-meta@agentic-plugins --scope project
claude plugin install ac-meta@agentic-plugins --scope local
```

## Skills

| Skill | Description |
|-------|-------------|
| `skill-writer` | Expert assistant for authoring Claude Code skills with correct SKILL.md structure |
| `hook-writer` | Expert assistant for authoring Claude Code hooks with correct JSON schemas |

## Usage Examples

```
# Create a new skill
/skill-writer my-new-skill "Automates X workflow"

# Create a new hook
/hook-writer pre-commit-lint "Lint staged files before commit"
```

## License

MIT
