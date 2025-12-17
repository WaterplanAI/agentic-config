# Contributing to agentic-config

Thank you for your interest in contributing!

## Issues and Labels

### Type Labels (GitHub defaults)

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or improvement request |
| `documentation` | Improvements or additions to documentation |
| `duplicate` | Issue or PR already exists |
| `wontfix` | Will not be worked on |

### Priority Labels

| Label | Description |
|-------|-------------|
| `priority: critical` | Must fix immediately |
| `priority: high` | Important, fix soon |
| `low-priority` | Nice to have, not urgent |

### Status Labels

| Label | Description |
|-------|-------------|
| `blocked` | Waiting on external dependency |
| `needs-triage` | Requires initial assessment |

### Effort Labels

| Label | Description |
|-------|-------------|
| `good first issue` | Good for newcomers |
| `complex` | Requires significant effort |

## Pull Requests

- Base branch: `main`
- Use [Conventional Commits](https://conventionalcommits.org) format
- Squash commits before merge

## Development

```bash
# Setup agentic-config in a project
./scripts/setup-config.sh /path/to/project

# Run tests
./scripts/test-python-tooling-variants.sh
```
