# ac-workflow

Spec workflow, MUX orchestration, and product management -- create, plan, implement, review, test specs with structured stage progression.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-workflow@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-workflow@agentic-plugins --scope user
claude plugin install ac-workflow@agentic-plugins --scope project
claude plugin install ac-workflow@agentic-plugins --scope local
```

## Skills

| Skill | Description |
|-------|-------------|
| `mux` | Parallel research-to-deliverable orchestration via multi-agent multiplexer |
| `mux-ospec` | Orchestrated spec execution with phase decomposition |
| `mux-roadmap` | Multi-track roadmap orchestration with cross-session continuity |
| `mux-subagent` | MUX subagent protocol for delegated execution |
| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |
| `spec` | Core specification workflow engine with stage agents |

## Agents (Spec Stages)

| Agent | Stage | Description |
|-------|-------|-------------|
| `CREATE` | Create | Generate new spec from prompt or template |
| `RESEARCH` | Research | Gather information and context for spec |
| `PLAN` | Plan | Write detailed implementation plan with diffs |
| `PLAN_REVIEW` | Plan Review | Review and refine the implementation plan |
| `IMPLEMENT` | Implement | Execute plan tasks with exact diffs |
| `REVIEW` | Review | Code review of implementation |
| `TEST` | Test | Run tests and validate implementation |
| `DOCUMENT` | Document | Update documentation for changes |
| `VALIDATE` | Validate | Final validation against acceptance criteria |
| `VALIDATE_INLINE` | Validate (Inline) | Inline validation variant |
| `FIX` | Fix | Apply fixes from review/test feedback |
| `AMEND` | Amend | Amend previous commit with fixes |

## Configuration

Spec files are stored in `specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md` by default.

External spec storage is supported via `.env` or `.agentic-config.conf.yml`:

```bash
# .env
EXT_SPECS_REPO_URL=ssh://github.com/<owner>/<specs-repo>.git
# Project-relative clone path (default: .specs)
EXT_SPECS_LOCAL_PATH=.specs
```

## Usage Examples

```
# Create a new spec
/spec CREATE specs/2026/02/main/001-my-feature.md

# Plan implementation (writes exact diffs)
/spec PLAN specs/2026/02/main/001-my-feature.md

# Implement the plan
/spec IMPLEMENT specs/2026/02/main/001-my-feature.md
```

## License

MIT
