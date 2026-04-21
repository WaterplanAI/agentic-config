# Plugin Catalog

Complete catalog of agentic-config skills organized by plugin.

## Overview

| Plugin | Focus | Skills |
|--------|-------|--------|
| `ac-workflow` | Spec workflow, pimux-backed orchestration | 6 |
| `ac-git` | Git automation, PRs, releases | 7 |
| `ac-qa` | QA, E2E testing, browser automation | 7 |
| `ac-tools` | Utilities, integrations, prototyping, bootstrap | 17 |
| `ac-meta` | Meta-prompting, self-improvement | 2 |
| `ac-safety` | Security guardrails (credential, write-scope, destructive-bash, supply-chain, playwright) | 2 |
| `ac-audit` | Tool audit logging (JSONL append-only log) | 1 |

## ac-workflow (6 skills)

| Skill | Description |
|-------|-------------|
| `spec` | Core specification workflow engine with explicit stage assets and repo-scoped commit contract |
| `mux` | Mux-style coordination alias on top of runtime-only `pimux` |
| `mux-ospec` | Explicit full/lean/leanest spec-stage orchestration with mandatory `SUCCESS_CRITERIA` and `CONFIRM_SC` gate |
| `mux-roadmap` | Roadmap -> phase -> stage orchestration on top of runtime-only `pimux` |
| `mux-subagent` | MUX subagent protocol for delegated data-plane execution |
| `product-manager` | Decomposes large features into concrete development phases with DAG dependencies |

In pi, canonical shipped IDs are `ac-workflow-mux`, `ac-workflow-mux-ospec`, and `ac-workflow-mux-roadmap`, with user-facing aliases `mux`, `mux-ospec`, and `mux-roadmap`.
`pimux` remains runtime/tooling only.

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

## ac-tools (17 skills)

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
| `gcp-setup` | Interactive GCP Cloud Build + Cloud Run setup |
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

### mux-ospec workflow (authoritative)

- `full`: `CREATE (optional) -> GATHER -> CONSOLIDATE -> SUCCESS_CRITERIA -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SENTINEL`
- `lean`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> DOCUMENT -> SELF_VALIDATION`
- `leanest`: `CREATE (optional) -> CONFIRM_SC -> PLAN -> IMPLEMENT -> REVIEW -> FIX -> TEST -> SELF_VALIDATION`

Rules:
- `GATHER = RESEARCH`
- `SUCCESS_CRITERIA` is a real stage boundary
- `CONFIRM_SC` is a mandatory user approval gate before `PLAN`
- `REVIEW`, `TEST`, `SENTINEL`, and `SELF_VALIDATION` are PASS-only gates
- blocked/stuck default is user escalation
- notify-first pacing; no polling loops

### OpenAI stage mapping (single authoritative repo surface)

| Stage family | Stages | Mapping |
|---|---|---|
| high-tier | `CREATE`, `CONSOLIDATE`, `SUCCESS_CRITERIA`, `PLAN`, `REVIEW`, `SENTINEL`, `SELF_VALIDATION` | `openai-codex/gpt-5.4:xhigh` |
| medium-tier | `GATHER`, `IMPLEMENT`, `FIX`, `TEST`, `DOCUMENT` | `openai-codex/gpt-5.3-codex:high` |
| user gate | `CONFIRM_SC` | user approval (no model) |

## See Also

- [Getting Started](getting-started.md) -- Setup and first use
- [Composition Hierarchy](composition-hierarchy.md) -- L0-L4 layer architecture design doc
- [pimux Workflow Topologies](pimux-workflow-topologies.md) -- `pimux`, mux, ospec, and roadmap runtime shapes
- [Distribution Guide](distribution.md) -- Team adoption tiers
