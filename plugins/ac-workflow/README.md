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

Primary/public stage set used by mux-ospec/spec workflows:

| Agent | Stage | Description |
|-------|-------|-------------|
| `CREATE` | Create | Generate new spec from prompt or template |
| `GATHER` | Gather | Gather information and context for spec (`GATHER` is the public alias for compatibility `RESEARCH`) |
| `CONSOLIDATE` | Consolidate | Synthesize gathered evidence into a coherent implementation direction |
| `SUCCESS_CRITERIA` | Success Criteria | Define explicit pass/fail outcomes before planning |
| `CONFIRM_SC` | Confirm Success Criteria | Mandatory user approval gate before `PLAN` |
| `PLAN` | Plan | Write detailed implementation plan with diffs |
| `IMPLEMENT` | Implement | Execute plan tasks with exact diffs |
| `REVIEW` | Review | Code review of implementation (PASS-only advancement) |
| `FIX` | Fix | Apply fixes from review/test/sentinel feedback |
| `TEST` | Test | Run tests and validate implementation (PASS-only advancement) |
| `DOCUMENT` | Document | Update documentation for changes |
| `SENTINEL` | Sentinel | Final full-mode validation gate (PASS-only advancement) |
| `SELF_VALIDATION` | Self Validation | Final lean/leanest validation gate (PASS-only advancement) |

Compatibility/internal stages may still exist (`RESEARCH`, `PLAN_REVIEW`, `VALIDATE`, `VALIDATE_INLINE`, `AMEND`), but public mux-ospec flows use the primary stages above.

## Configuration

Spec files use `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md` by default.

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
/spec CREATE .specs/specs/2026/02/main/001-my-feature.md

# Plan implementation (writes exact diffs)
/spec PLAN .specs/specs/2026/02/main/001-my-feature.md

# Implement the plan
/spec IMPLEMENT .specs/specs/2026/02/main/001-my-feature.md
```

## License

MIT
