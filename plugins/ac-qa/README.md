# ac-qa

Code review and QA workflows -- E2E review, PR review, browser automation, and test execution.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-qa@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-qa@agentic-plugins --scope user
claude plugin install ac-qa@agentic-plugins --scope project
claude plugin install ac-qa@agentic-plugins --scope local
```

## Skills

| Skill | Description |
|-------|-------------|
| `browser` | Open browser for E2E testing via Playwright |
| `e2e-review` | Visual spec implementation validation with Playwright |
| `e2e-template` | Template for creating E2E test definitions |
| `gh-pr-review` | Review GitHub PRs with multi-agent orchestration |
| `playwright-cli` | Token-efficient browser automation via CLI commands |
| `prepare-app` | Start development server for E2E testing |
| `test-e2e` | Execute E2E test definitions with Playwright |

## Configuration

E2E testing requires Playwright CLI:

```bash
npm install -g @playwright/cli@latest
playwright-cli install-browser
```

## Usage Examples

```
# Review a PR
/gh-pr-review https://github.com/owner/repo/pull/123

# Run E2E visual review
/e2e-review

# Execute E2E tests
/test-e2e tests/e2e/login.md

# Open browser for testing
/browser https://example.com

# Start dev server for testing
/prepare-app

# Token-efficient browser automation
/playwright-cli screenshot https://example.com
```

## License

MIT
