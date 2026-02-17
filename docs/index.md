# Commands & Skills Index

Complete catalog of agentic-config commands and skills with composition patterns.

## Composition Pattern

The key innovation of agentic-config is **composability** - commands invoke other commands, creating compounding automation effects.

### The Hierarchy

```
/full-life-cycle-pr (complete PR workflow)
        |
        +---> /branch (create branch + spec dir)
        +---> /po_spec (phased orchestrator)
        |           |
        |           +---> /o_spec (E2E orchestrator) [per phase]
        |                     |
        |                     +---> /spec (stage executor) [8 stages]
        |                              |
        |                              +---> Stage agents (CREATE, RESEARCH, PLAN, ...)
        |
        +---> /milestone (squash + tag)
        +---> /pull_request (create PR)
```

### Compounding Effects

| Layer | What it does | Compounding |
|-------|--------------|-------------|
| `/spec` | Single stage on one spec | 1 commit |
| `/o_spec` | Full 8-stage workflow | 8 commits, model specialization |
| `/po_spec` | DAG-aware phase execution | N phases x 8 stages, parallelization |
| `/full-life-cycle-pr` | Complete PR workflow | Branch + phases + squash + PR |

---

## Explicit Composition Examples

### /spec - Foundation Layer

Executes a single stage on a spec file.

```bash
/spec CREATE specs/2026/01/feat/auth/001-oauth.md     # Create spec
/spec RESEARCH specs/2026/01/feat/auth/001-oauth.md   # Research codebase
/spec PLAN specs/2026/01/feat/auth/001-oauth.md       # Design solution
/spec IMPLEMENT specs/2026/01/feat/auth/001-oauth.md  # Write code
/spec REVIEW specs/2026/01/feat/auth/001-oauth.md     # Code review
/spec TEST specs/2026/01/feat/auth/001-oauth.md       # Run/write tests
/spec DOCUMENT specs/2026/01/feat/auth/001-oauth.md   # Update docs
```

**Result:** 1 commit per stage with message `spec(001): STAGE - title`

---

### /o_spec - Orchestrator Layer

Runs the full 8-stage workflow with model optimization.

```bash
# Default (normal modifier)
/o_spec specs/2026/01/feat/auth/001-oauth.md

# With explicit modifier
/o_spec full specs/2026/01/feat/auth/001-oauth.md    # Maximum quality
/o_spec lean specs/2026/01/feat/auth/001-oauth.md    # Speed-focused
/o_spec leanest specs/2026/01/feat/auth/001-oauth.md # Maximum speed
```

**Modifiers:**

| Modifier | Stages | Models | Use Case |
|----------|--------|--------|----------|
| `full` | 8 (incl. PLAN_REVIEW) | Opus + Sonnet | Maximum quality |
| `normal` | 7 | Opus + Sonnet | Balanced (default) |
| `lean` | 6 (skip RESEARCH) | All Sonnet | Speed-focused |
| `leanest` | 6 (skip RESEARCH) | Sonnet + Haiku | Maximum speed/cost |

**Stage Sequence (normal):**
```
CREATE --> RESEARCH --> PLAN --> IMPLEMENT --> REVIEW --> TEST --> DOCUMENT
  |          |           |           |           |         |          |
opus       opus        opus      sonnet       opus    sonnet     sonnet
```

**Result:** 7-8 commits, each stage executed by optimal model

---

### /po_spec - Phased Orchestrator

Decomposes large features into phases with DAG-aware parallel execution.

```bash
# From inline prompt
/po_spec "Add OAuth2 with session management and RBAC"

# From spec file
/po_spec specs/2026/01/feat/auth/001-full-auth.md
```

**Phase Decomposition Example:**

Input: "Add OAuth2 with session management and RBAC"

```yaml
Phases:
  1. Auth models & migrations       (no deps)
  2. OAuth provider config          (no deps)
  3. Auth endpoints                 (deps: 1, 2)
  4. Session management             (deps: 3)
  5. RBAC middleware                (deps: 1)
  6. Integration tests              (deps: 3, 4, 5)
```

**DAG Execution:**
```
Batch 1: [phase-1, phase-2]     (parallel - no deps)
            |
Batch 2: [phase-3, phase-5]     (parallel - deps satisfied)
            |
Batch 3: [phase-4]              (serial - depends on 3)
            |
Batch 4: [phase-6]              (serial - depends on 3,4,5)
```

**Result:** N phases x 8 stages = 48+ commits for complex features, with parallelization

---

### /full-life-cycle-pr - Complete PR Workflow

Orchestrates the entire PR lifecycle with single confirmation.

```bash
/full-life-cycle-pr feat/oauth "Add OAuth2 authentication"

# With modifier
/full-life-cycle-pr feat/oauth "Add OAuth2 authentication" lean
```

**Workflow:**
```
Step 1: /branch feat/oauth
        --> Creates branch + specs/2026/01/feat/oauth/000-backlog.md

Step 2: /po_spec "Add OAuth2 authentication"
        --> Decomposes into phases
        --> Executes all phases via /o_spec
        --> Commits per stage

Step 3: /milestone --skip-tag --auto
        --> Squashes all commits into ONE
        --> Rebases onto origin/main
        --> Pushes

Step 4: /pull_request
        --> Creates PR with comprehensive description
```

**Result:** Complete feature from idea to PR with single "yes" confirmation

---

## Commands Catalog

### Agentic Management

| Command | Description |
|---------|-------------|
| `/agentic` | Main dispatcher (setup, migrate, update, status, validate, customize) |
| `/agentic-setup` | Setup agentic-config in current or specified directory |
| `/agentic-migrate` | Migrate existing manual agentic installation to centralized system |
| `/agentic-update` | Update agentic-config to latest version |
| `/agentic-status` | Show status of all agentic-config installations |
| `/agentic-export` | Export project asset to agentic-config repository |
| `/agentic-import` | Import external asset into agentic-config repository |

### Spec Workflow

| Command | Description |
|---------|-------------|
| `/spec` | Execute single stage (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT) |
| `/o_spec` | E2E spec orchestrator with modifiers (full/normal/lean/leanest) |
| `/po_spec` | Phased orchestrator - decomposes large features into DAG phases |
| `/branch` | Create new branch with spec directory structure |

### Git & Versioning

| Command | Description |
|---------|-------------|
| `/squash` | Squash all commits since base into single commit with Conventional Commits |
| `/squash_commit` | Generate standardized Conventional Commit message for squashed commits |
| `/squash_and_rebase` | Squash all commits into one, then rebase onto target branch |
| `/rebase` | Rebase current branch onto target branch |
| `/milestone` | Validate backlog completion, then squash+tag or identify gaps |
| `/release` | Full release workflow - milestone, rebase, push, merge to main |

### Pull Requests & Reviews

| Command | Description |
|---------|-------------|
| `/full-life-cycle-pr` | Orchestrate complete PR lifecycle from branch creation to submission |
| `/pull_request` | Create comprehensive GitHub Pull Request with auth validation |
| `/gh_pr_review` | Review GitHub PR with multi-agent orchestration |
| `/ac-issue` | Report issues to agentic-config repository via GitHub CLI |

### Orchestration

| Command | Description |
|---------|-------------|
| `/orc` | Orchestrate task accomplishment using multi-agent delegation |
| `/spawn` | Spawn a subagent with specified model and task |
| `/mux-roadmap` | Multi-track roadmap orchestration with cross-session state management |

### E2E Testing

| Command | Description |
|---------|-------------|
| `/browser` | Open browser at URL for E2E testing via playwright-cli |
| `/browser` | Open browser at URL for E2E testing via playwright-cli |
| `/test_e2e` | Execute E2E test from definition file |
| `/e2e_review` | Review spec implementation with E2E visual browser validation |
| `/prepare_app` | Start development server for E2E testing |
| `/e2e-template` | Template for E2E test definitions |
| `/video_query` | Query video using Gemini API (native video upload) |

### Utilities

| Command | Description |
|---------|-------------|
| `/adr` | Document architecture decisions with auto-numbering |
| `/fork-terminal` | Open new kitty terminal session with optional command |
| `/worktree` | Create new git worktree with symlinked/copied assets |

---

## Skills Catalog

### Workflow & Planning

| Skill | Description |
|-------|-------------|
| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |
| `agent-orchestrator-manager` | Orchestrates multi-agent workflows via /spawn, parallelizes independent work |
| `mux` | Parallel research-to-deliverable orchestration via multi-agent multiplexer |
| `mux-ospec` | Orchestrated spec workflow combining MUX delegation with stage-based execution |
| `mux-subagent` | Protocol compliance skill for MUX subagents with file-based communication |

### Code Generation

| Skill | Description |
|-------|-------------|
| `command-writer` | Expert assistant for creating Claude Code custom slash commands |
| `skill-writer` | Expert assistant for authoring Claude Code skills |
| `hook-writer` | Expert assistant for authoring Claude Code hooks with correct JSON schemas |
| `single-file-uv-scripter` | Creates self-contained Python scripts with inline PEP 723 metadata |

### Design & Prototyping

| Skill | Description |
|-------|-------------|
| `human-agentic-design` | Generates interactive HTML prototypes optimized for dual human+agent interaction |
| `had` | Alias for human-agentic-design |

### Git Utilities

| Skill | Description |
|-------|-------------|
| `git-find-fork` | Finds true merge-base/fork-point, detects history rewrites from rebases |
| `git-rewrite-history` | Rewrites git history safely with dry-run-first workflow |
| `gh-assets-branch-mgmt` | Manages GitHub assets branch for persistent image hosting in PRs |

### Browser & E2E Testing

| Skill | Description |
|-------|-------------|
| `playwright-cli` | Token-efficient browser automation via CLI commands (replaces Playwright MCP) |

### Browser & E2E Testing

| Skill | Description |
|-------|-------------|
| `playwright-cli` | Token-efficient browser automation via CLI commands (replaces Playwright MCP) |

### Testing & Safety

| Skill | Description |
|-------|-------------|
| `dry-run` | Simulates command execution without file modifications |
| `dr` | Alias for dry-run |

### Integrations

| Skill | Description |
|-------|-------------|
| `gsuite` | Google Suite integration for Sheets, Docs, Slides, Gmail, Calendar, Tasks with multi-account support |

### Utilities

| Skill | Description |
|-------|-------------|
| `cpc` | Copy text to clipboard via pbcopy (macOS) |

---

## Workflow Diagrams

### O_SPEC Stage Sequence

```
CREATE --> RESEARCH --> PLAN --> [PLAN_REVIEW] --> IMPLEMENT --> REVIEW --> TEST --> DOCUMENT
   |           |          |            |              |            |         |          |
create      analyze    design      validate       write code   review    verify    update
 spec      codebase   solution      plan          & commit      impl     tests     docs
```

### Full Lifecycle PR Flow

```
User: /full-life-cycle-pr feat/my-feature "Add new feature"
                     |
                     v
            +----------------+
            | Confirmation   |  <-- Single "yes" prompt
            +----------------+
                     |
     +---------------+---------------+
     v               v               v
+---------+    +-----------+    +-----------+
| /branch |    | /po_spec  |    | /milestone|
+---------+    +-----------+    +-----------+
     |               |               |
     v               v               v
 creates         executes         squashes
 branch +        N phases         all into
 backlog         via /o_spec      1 commit
                     |               |
                     v               v
               8 stages per    +-----------+
               phase, parallel | /pull_req |
               where possible  +-----------+
                                    |
                                    v
                               creates PR
                               on GitHub
```

---

## Related Documentation

- [External Specs Storage](external-specs-storage.md) - Configure external specs repository
- [Agent Management Guide](agents/AGENTIC_AGENT.md) - Detailed agent usage
- [Playwright CLI Setup](playwright-cli-setup.md) - E2E browser testing configuration
- [Composition Hierarchy](designs/composition-hierarchy.md) - Agentic composition architecture and L0-L4 layers
- [ADR-001: SDK-UV-Script Nesting](decisions/adr-001-sdk-uv-script-nesting.md) - Architecture decision for agent composition
