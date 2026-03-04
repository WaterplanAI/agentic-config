# ac-git

Git workflow automation -- pull requests, releases, branching, worktrees, and safe history rewriting.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-git@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-git@agentic-plugins --scope user
claude plugin install ac-git@agentic-plugins --scope project
claude plugin install ac-git@agentic-plugins --scope local
```

## Skills

| Skill | Description |
|-------|-------------|
| `branch` | Create new branch with spec directory structure |
| `gh-assets-branch-mgmt` | Manage GitHub assets branch for persistent image/video hosting in PRs |
| `git-find-fork` | Find merge-base/fork-point and detect rewritten history safely |
| `git-safe` | Safe git history manipulation with guardrails |
| `pull-request` | Create comprehensive GitHub Pull Requests |
| `release` | Full release workflow (milestone, squash, tag, push, merge) |
| `worktree` | Create git worktrees with asset symlinks and env setup |

## Configuration

Skills follow Conventional Commits format:
- Format: `<type>(<scope>): <description>`
- Types: feat, fix, docs, chore, refactor, test, style, perf, build, ci
- Commit body uses structured sections: Added, Changed, Fixed, Removed

## Usage Examples

```
# Create a PR with auto-generated description
/pull-request

# Create a release
/release

# Create a new branch with spec dir
/branch feat/my-feature

# Upload assets for PR embedding
# (via gh-assets-branch-mgmt skill)
gh-assets upload screenshot.png
```

## License

MIT
