# Plugin Catalog

Complete catalog of agentic-config skills organized by plugin.

## Overview

| Plugin | Focus | Skills |
|--------|-------|--------|
| `ac-workflow` | Spec workflow, MUX orchestration | 6 |
| `ac-git` | Git automation, PRs, releases | 7 |
| `ac-qa` | QA, E2E testing, browser automation | 7 |
| `ac-tools` | Utilities, integrations, prototyping, bootstrap | 17 |
| `ac-meta` | Meta-prompting, self-improvement | 2 |
| `ac-safety` | Security guardrails (credential, write-scope, destructive-bash, supply-chain, playwright) | 2 |
| `ac-audit` | Tool audit logging (JSONL append-only log) | 1 |

## ac-workflow (6 skills)

| Skill | Description |
|-------|-------------|
| `spec` | Core specification workflow engine with stage agents (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT) |
| `mux` | Parallel research-to-deliverable orchestration via multi-agent multiplexer |
| `mux-ospec` | Orchestrated spec execution with phase decomposition |
| `mux-roadmap` | Multi-track roadmap orchestration with cross-session continuity |
| `mux-subagent` | MUX subagent protocol for delegated execution |
| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |

## ac-git (7 skills)

| Skill | Description |
|-------|-------------|
| `branch` | Create new branch with spec directory structure |
| `git-find-fork` | Finds true merge-base/fork-point, detects history rewrites from rebases |
| `git-safe` | Safe git history manipulation with guardrails (squash, rebase) |
| `gh-assets-branch-mgmt` | Manages GitHub assets branch for persistent image hosting in PRs |
| `pull-request` | Create comprehensive GitHub Pull Requests |
| `release` | Full release workflow (milestone, squash, tag, push, merge) |
| `worktree` | Create git worktrees with assets and environment setup |

## ac-qa (7 skills)

| Skill | Description |
|-------|-------------|
| `browser` | Open browser for E2E testing via Playwright |
| `e2e-review` | Visual spec implementation validation with Playwright |
| `e2e-template` | Template for creating E2E test definitions |
| `gh-pr-review` | Review GitHub PRs with multi-agent orchestration |
| `playwright-cli` | Token-efficient browser automation via CLI commands |
| `prepare-app` | Start development server for E2E testing |
| `test-e2e` | Execute E2E test definitions with Playwright |

## ac-tools (16 skills)

| Skill | Description |
|-------|-------------|
| `improve-agents-md` | Generate and update AGENTS.md (CLAUDE.md) with auto-detected project tooling |
| `ac-issue` | Report issues to agentic-config repository via GitHub CLI |
| `adr` | Document architecture decisions with auto-numbering |
| `agentic-export` | Export project assets to agentic-config repository |
| `agentic-import` | Import external assets into agentic-config repository |
| `agentic-share` | Shared core logic for asset import/export |
| `cpc` | Clipboard-powered code exchange |
| `dr` | Alias for dry-run |
| `dry-run` | Simulate command execution without file modifications |
| `gsuite` | Google Suite integration (Sheets, Docs, Slides, Drive, Gmail, Calendar, Tasks) |
| `had` | Alias for human-agentic-design |
| `human-agentic-design` | Interactive HTML prototype generator |
| `milestone` | Validate backlog and generate milestone/release notes |
| `setup-voice-mode` | Configure voice mode for conversational interaction |
| `single-file-uv-scripter` | Create self-contained Python scripts with PEP 723 inline deps |
| `video-query` | Query video content using Gemini API |

## ac-meta (2 skills)

| Skill | Description |
|-------|-------------|
| `skill-writer` | Expert assistant for authoring Claude Code skills |
| `hook-writer` | Expert assistant for authoring Claude Code hooks |

## ac-safety (2 skills)

| Skill | Description |
|-------|-------------|
| `configure-safety` | Interactive safety.yaml customization |
| `harden-supply-chain-sec` | Harden supply chain security: configure minimum release age, detect frozen-lockfile patterns, apply dependency policies across package managers |

## ac-audit (1 skill)

| Skill | Description |
|-------|-------------|
| `configure-audit` | Interactive audit.yaml configuration (3-tier config resolution) |

---

### O_SPEC Stage Sequence

```
CREATE --> RESEARCH --> PLAN --> [PLAN_REVIEW] --> IMPLEMENT --> REVIEW --> TEST --> DOCUMENT
   |           |          |            |              |            |         |          |
create      analyze    design      validate       write code   review    verify    update
 spec      codebase   solution      plan          & commit      impl     tests     docs
```

### O_SPEC Modifiers

| Modifier | Stages | Models | Use Case |
|----------|--------|--------|----------|
| `full` | 8 (incl. PLAN_REVIEW) | High-tier + Medium-tier | Maximum quality |
| `normal` | 7 | High-tier + Medium-tier | Balanced (default) |
| `lean` | 6 (skip RESEARCH) | All Medium-tier | Speed-focused |
| `leanest` | 6 (skip RESEARCH) | Medium-tier + Low-tier | Maximum speed/cost |

## See Also

- [Getting Started](getting-started.md) -- Setup and first use
- [Composition Hierarchy](composition-hierarchy.md) -- L0-L4 layer architecture design doc
- [Distribution Guide](distribution.md) -- Team adoption tiers
