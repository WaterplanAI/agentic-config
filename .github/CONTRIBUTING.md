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
| `priority: low` | Nice to have, not urgent |

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
# Launch claude with all plugin dirs for local development
./dev.sh

# Run Python tests
uv run pytest
```

## Local pi package testing before distribution

Use pi local-path installs when validating the pi packages before npm distribution is enabled.

- Direct `pi install ./packages/<name> -l` is appropriate for standalone packages such as `pi-compat`, `pi-ac-meta`, `pi-ac-qa`, and `pi-ac-workflow`.
- Packages that rely on bundled sibling package trees must be staged with `node_modules/@agentic-config/...` populated before running `pi install ... -l` or pointing `.pi/settings.json` at the staged path.
- See the [Pi Package Adoption Guide](../packages/README.md#local-package-testing-before-distribution) for the exact staged examples for `pi-ac-tools` and `pi-all`.
