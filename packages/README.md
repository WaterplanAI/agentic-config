# pi package adoption and topology

This directory contains the current pi package surface for `agentic-config`.

## Current shipped surface
- `9` package roots total:
  - `@agentic-config/pi-compat`
  - `@agentic-config/pi-ac-audit`
  - `@agentic-config/pi-ac-git`
  - `@agentic-config/pi-ac-meta`
  - `@agentic-config/pi-ac-qa`
  - `@agentic-config/pi-ac-safety`
  - `@agentic-config/pi-ac-tools`
  - `@agentic-config/pi-ac-workflow`
  - `@agentic-config/pi-all`
- `42` shipped namespaced skills across `7` plugin packages
- shared `hook-compat` runtime parity plus shared `AskUserQuestion`, `NotebookEdit`, and worker-wave orchestration helpers through `@agentic-config/pi-compat`
- package-owned `pimux` runtime authority for tmux-backed workflow orchestration through `@agentic-config/pi-ac-workflow`
- one-shot install path through `@agentic-config/pi-all`

## Why the package layout is split per plugin
Per-plugin packages remain the core distribution shape.

This keeps adoption efficient and honest:
- teams can install only the plugin families they actually use
- partial parity stays visible package by package instead of being hidden behind one large bundle
- hook-backed packages can bundle `@agentic-config/pi-compat` only where they need it
- package identity stays stable even when some plugin families still carry explicit deferred work
- `@agentic-config/pi-all` can stay a convenience layer instead of the only supported install path

## Why skill names are namespaced
Pi resource IDs follow the locked pattern `<plugin>-<resource>`.

Examples:
- package: `@agentic-config/pi-ac-git`
- skills from that package: `ac-git-branch`, `ac-git-release`
- package: `@agentic-config/pi-ac-tools`
- skills from that package: `ac-tools-dry-run`, `ac-tools-gsuite`

Namespacing matters because pi can load multiple packages at once. The namespaced IDs keep `/skill:...` commands collision-free and make it obvious which plugin family owns each resource.

## ac-workflow runtime chooser

`@agentic-config/pi-ac-workflow` centers tmux orchestration on `pimux`:

- `pimux` is the package-owned tmux control plane for generic and mux-family work
- `ac-workflow-mux`, `ac-workflow-mux-ospec`, and `ac-workflow-mux-roadmap` are structured wrappers on top of `pimux`
- inspectable non-mux hierarchies now stay on `pimux` directly

Contributor note: use canonical shipped IDs `ac-workflow-mux`, `ac-workflow-mux-ospec`, and `ac-workflow-mux-roadmap` with user-facing aliases `mux`, `mux-ospec`, and `mux-roadmap`. `pimux` remains runtime/tooling only.

Simple topology view:

```text
pimux                     L0 -> L1
ac-workflow-mux          L0 -> L1 mux-coordinator -> L2 scout/planner/workers
ac-workflow-mux-ospec    L0 -> L1 stage-owner -> L2 helpers
ac-workflow-mux-roadmap  L0 -> L1 roadmap -> L2 phases -> L3 stages
```

See [docs/pimux-workflow-topologies.md](../docs/pimux-workflow-topologies.md) for the fuller guide, including communication patterns, one-hop reporting, settlement, and typical agent counts.

## What the generated-wrapper strategy means in practice
The current package surface ships primarily through the **Option C canonical-source + generated-wrapper system**, with package-owned workflow runtime surfaces under `@agentic-config/pi-ac-workflow` centered on `pimux`.

That means:
- Claude and pi skill outputs are rendered from `canonical/` for the current generated wrapper set
- package-shared and skill-local support trees are copied from canonical ownership instead of being maintained ad hoc per harness
- package README status surfaces describe generated skill/package outputs plus package-owned `pimux` workflow runtime surfaces as the authoritative maintenance path
- hook-backed runtime parity is still routed through the shared `@agentic-config/pi-compat` adapter plus package-local registrations
- current gaps stay explicit when pi does not yet expose an equivalent runtime surface

The current surface does **not** claim that:
- every remaining non-mux complex surface already ships in pi
- full generic `Task` / subagent runtime is solved as a shared compat primitive
- every Claude marketplace surface has full pi parity

## Install and adoption
### Primary repo-based install via git tag
Use a tagged git ref when you want a reproducible team or automation rollout from the repository itself.

Install the full shipped surface:

```bash
pi install "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha" -l
```

The `-l` flag installs it into the local project config. For a global/user install, remove `-l`.

Equivalent committed `.pi/settings.json` source:

```json
{
  "packages": [
    "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha"
  ]
}
```

Use the equivalent SSH git source for the same repository and tag when needed.

This root install path has been validated end to end against the umbrella package layout, including representative skill and extension loading.

### Branch-based install for local testing and development
Use a branch ref when you want repo-based rollout for local testing or development without cutting a new tag yet.

```bash
pi install "git:github.com/WaterplanAI/agentic-config@main" -l
```

Replace `main` with a feature branch name when testing unpublished pi changes.

### Local package testing before distribution
Local-path installs remain mainly for local development and focused package validation.

Direct local-path installs are appropriate for standalone packages such as:

```bash
pi install ./packages/pi-compat -l
pi install ./packages/pi-ac-meta -l
pi install ./packages/pi-ac-workflow -l
```

For `@agentic-config/pi-ac-audit`, `@agentic-config/pi-ac-git`, `@agentic-config/pi-ac-qa`, `@agentic-config/pi-ac-safety`, `@agentic-config/pi-ac-tools`, and `@agentic-config/pi-all`, stage a temp package directory first.
Those packages reference bundled sibling resources under `node_modules/@agentic-config/...`, and a raw local-path install reads the directory as-is instead of materializing bundled sibling dependencies for you. For repo-based distribution, prefer the tagged git install path above rather than raw local paths.

Representative staged install for `@agentic-config/pi-ac-tools`:

```bash
tmp="$(mktemp -d)"
mkdir -p "$tmp/stage/pi-ac-tools/node_modules/@agentic-config/pi-compat"
cp -R packages/pi-ac-tools/. "$tmp/stage/pi-ac-tools"
cp -R packages/pi-compat/. "$tmp/stage/pi-ac-tools/node_modules/@agentic-config/pi-compat"
pi install "$tmp/stage/pi-ac-tools" -l
```

Representative staged committed-settings test for `@agentic-config/pi-all`:

```bash
tmp="$(mktemp -d)"
mkdir -p "$tmp/stage/pi-all/node_modules/@agentic-config"
cp -R packages/pi-all/. "$tmp/stage/pi-all"
for pkg in pi-compat pi-ac-audit pi-ac-git pi-ac-meta pi-ac-qa pi-ac-safety pi-ac-tools pi-ac-workflow; do
  mkdir -p "$tmp/stage/pi-all/node_modules/@agentic-config/$pkg"
  cp -R "packages/$pkg/." "$tmp/stage/pi-all/node_modules/@agentic-config/$pkg"
done

cat > .pi/settings.json <<EOF
{
  "packages": [
    "$tmp/stage/pi-all"
  ]
}
EOF
```

This staged layout mirrors the bundled dependency structure that the published package tarballs will carry.

### Recommended team-adoption path: committed `.pi/settings.json`
Committed `.pi/settings.json` with a pinned git tag is the preferred team-adoption path because pi can auto-install the same reproducible package set on startup and keep the selected rollout ref versioned with the project.

Full shipped set:

```json
{
  "packages": [
    "git:github.com/WaterplanAI/agentic-config@v0.3.0-alpha"
  ]
}
```

Branch-based dev rollout:

```json
{
  "packages": [
    "git:github.com/WaterplanAI/agentic-config@main"
  ]
}
```

Why the pinned tag is preferred for teams and automation:
- the install ref is versioned with the project
- new teammates get the same pi surface automatically
- tagged rollout stays reproducible
- branch refs remain available for local development and testing

## Availability matrix
This matrix is the current adoption surface. It separates what is available now, what ships with a known partial/current-gap note, and what remains explicitly deferred.

| Package | Available now | Partial / current-gap note | Deferred |
|---|---|---|---|
| `@agentic-config/pi-compat` | shared `hook-compat` foundation plus shared `AskUserQuestion`, `NotebookEdit`, and worker-wave orchestration helpers | worker-wave helpers cover synchronous single/parallel waves only; final synthesis and broader orchestration remain skill-owned | remaining broader generic nested/background subagent runtime primitives beyond the current foundation |
| `@agentic-config/pi-ac-audit` | `ac-audit-configure-audit`; tool audit runtime parity | adapter-backed parity ships through bundled `tool-audit.py` plus `pi-compat` | none |
| `@agentic-config/pi-ac-git` | `ac-git-branch`, `ac-git-gh-assets-branch-mgmt`, `ac-git-git-find-fork`, `ac-git-git-safe`, `ac-git-pull-request`, `ac-git-release`, `ac-git-worktree`; commit guard parity | commit guard parity is package-level runtime behavior, not a separate user-facing skill | none |
| `@agentic-config/pi-ac-meta` | `ac-meta-hook-writer`, `ac-meta-skill-writer` | none | none |
| `@agentic-config/pi-ac-qa` | `ac-qa-browser`, `ac-qa-e2e-review`, `ac-qa-e2e-template`, `ac-qa-gh-pr-review`, `ac-qa-playwright-cli`, `ac-qa-prepare-app`, `ac-qa-test-e2e` | bounded review-worker fan-out and user-confirmed `gh pr review` actions now ship through bundled `pi-compat`; no package-local orchestration helper is introduced | none |
| `@agentic-config/pi-ac-safety` | `ac-safety-configure-safety`, `ac-safety-harden-supply-chain-sec`; credential/destructive-bash/supply-chain/write-scope/playwright guardian parity | Playwright guardian parity now targets the current Bash-based `playwright-cli` surface through bundled `pi-compat`; no separate first-party browser tool is introduced | none |
| `@agentic-config/pi-ac-tools` | `ac-tools-ac-issue`, `ac-tools-adr`, `ac-tools-agentic-export`, `ac-tools-agentic-import`, `ac-tools-agentic-share`, `ac-tools-cpc`, `ac-tools-dr`, `ac-tools-dry-run`, `ac-tools-gcp-setup`, `ac-tools-gsuite`, `ac-tools-had`, `ac-tools-human-agentic-design`, `ac-tools-improve-agents-md`, `ac-tools-milestone`, `ac-tools-setup-voice-mode`, `ac-tools-single-file-uv-scripter`, `ac-tools-video-query`, `ac-tools-voice-user`, `ac-tools-web-search`; package-local `say` and `web-search` extensions; dry-run guard parity including notebook-edit coverage plus `gsuite-public-asset-guard.py` parity | none | none |
| `@agentic-config/pi-ac-workflow` | `ac-workflow-product-manager`, `ac-workflow-spec`, `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`, `ac-workflow-mux-subagent`; package-local `pimux` and `strict-mux-runtime` extensions; shared mux foundation assets under `assets/mux/` | explicit tmux-backed workflow triggers now commit to package-owned `pimux` runtime authority with preserved mux semantics; `mux-ospec` and `mux-roadmap` pass explicit paths through unchanged, auto-derive/create the next current-branch spec path from sufficient inline prompts, and reserve `AskUserQuestion` for missing spawn input, while generic non-mux hierarchies stay on `pimux` directly | none |
| `@agentic-config/pi-all` | one-shot aggregation of the current shipped package set | aggregation only; no first-party skills or extensions of its own | expands only as future package surfaces ship |

## Runtime parity today vs deferred
### Shipped runtime parity today
- `@agentic-config/pi-ac-audit` ships tool-audit parity through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-git` ships commit-guard parity through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-qa` ships `gh-pr-review` on top of the shared `AskUserQuestion` plus worker-wave orchestration foundation from `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-safety` ships the full current guardian surface, including `playwright-cli` Bash protection, through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-tools` ships dry-run parity and GSuite public-share protection through `@agentic-config/pi-compat`, plus package-local `say` and `web-search` extensions
- `@agentic-config/pi-ac-workflow` ships package-owned `pimux` runtime authority for generic and mux-family tmux flows

### Still explicitly deferred in the current shipped surface
- remaining runtime/tool gaps:
  - broader generic nested/background `Task` / subagent runtime primitives beyond the shared `AskUserQuestion` + `NotebookEdit` + worker-wave foundation and the shipped package-owned `pimux` workflow runtime

## Versioning strategy
- All package manifests use the shared repository version from `VERSION` (`0.3.0-alpha`).
- Package manifests use exact sibling package versions in `dependencies` to keep the monorepo package set aligned.
- Install/discovery smoke tests for the current package surface are validated separately from this summary.

## Directory conventions
- `skills/` — exported pi skills. The tracked convention note lives in `skills/_conventions/README.md` so the directory exists without placeholder skills.
- `extensions/` — exported pi extensions. The tracked convention note lives in `extensions/README.md`.
- `assets/` — package-local copied helpers that are not exported directly by pi. Current packages use typed subdirectories such as `assets/scripts/`, `assets/config/`, and `assets/agents/`.
- `README.md` — package-level status surface. Every package root states whether it is active or partial and avoids implying that deferred work already ships.

## Shared dependency conventions
- Packages with hook-backed or shared-compat needs depend on `@agentic-config/pi-compat`, bundle it, expose its extensions through `node_modules/@agentic-config/pi-compat/extensions`, and consume the shared worker-wave helpers through `node_modules/@agentic-config/pi-compat/assets/orchestration` when they need the bounded IT003 orchestration surface.
- `@agentic-config/pi-all` aggregates the per-plugin package roots through bundled dependencies and exposes their skills/extensions directly from `node_modules/...` paths.
- The repository intentionally does not add a root npm workspace. Manifest coherence, staged local install tests, and package/discovery smoke checks are validated separately.

## Package surface summary
| Package | Status | Current exported surface | Shared dependency pattern |
|---|---|---|---|
| `@agentic-config/pi-compat` | active | shared `hook-compat`, `AskUserQuestion`, `NotebookEdit`, and worker-wave orchestration foundations | standalone |
| `@agentic-config/pi-ac-audit` | partial | `ac-audit-configure-audit`; tool audit runtime parity | bundles `pi-compat` |
| `@agentic-config/pi-ac-git` | active | `ac-git-branch`, `ac-git-gh-assets-branch-mgmt`, `ac-git-git-find-fork`, `ac-git-git-safe`, `ac-git-pull-request`, `ac-git-release`, `ac-git-worktree`; commit-guard parity | bundles `pi-compat` |
| `@agentic-config/pi-ac-meta` | active | `ac-meta-hook-writer`, `ac-meta-skill-writer` | standalone |
| `@agentic-config/pi-ac-qa` | active | `ac-qa-browser`, `ac-qa-e2e-review`, `ac-qa-e2e-template`, `ac-qa-gh-pr-review`, `ac-qa-playwright-cli`, `ac-qa-prepare-app`, `ac-qa-test-e2e` | bundles `pi-compat` |
| `@agentic-config/pi-ac-safety` | active | `ac-safety-configure-safety`, `ac-safety-harden-supply-chain-sec`; credential/destructive-bash/supply-chain/write-scope/playwright guardian parity | bundles `pi-compat` |
| `@agentic-config/pi-ac-tools` | active | `ac-tools-ac-issue`, `ac-tools-adr`, `ac-tools-agentic-export`, `ac-tools-agentic-import`, `ac-tools-agentic-share`, `ac-tools-cpc`, `ac-tools-dr`, `ac-tools-dry-run`, `ac-tools-gcp-setup`, `ac-tools-gsuite`, `ac-tools-had`, `ac-tools-human-agentic-design`, `ac-tools-improve-agents-md`, `ac-tools-milestone`, `ac-tools-setup-voice-mode`, `ac-tools-single-file-uv-scripter`, `ac-tools-video-query`, `ac-tools-voice-user`, `ac-tools-web-search`; package-local `say` and `web-search` extensions; dry-run parity; GCP / GSuite / voice surfaces shipped | bundles `pi-compat` |
| `@agentic-config/pi-ac-workflow` | active | `ac-workflow-product-manager`, `ac-workflow-spec`, `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`, `ac-workflow-mux-subagent`; package-local `pimux` and `strict-mux-runtime` extensions; shared mux foundation assets ship with the full mux family | standalone |
| `@agentic-config/pi-all` | active | aggregation of the current shipped set | bundles all package roots |

## Roadmap evidence
The roadmap evidence artifact is:

- [`.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md`](../.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md)

Current carry-forward work:
- broader generic nested/background `Task` / subagent runtime primitives beyond the shared `AskUserQuestion` + `NotebookEdit` + worker-wave foundation and the shipped package-owned `pimux` workflow runtime

Shared/runtime boundary now shipped across package surfaces:
- `AskUserQuestion`
- `NotebookEdit`
- worker-wave orchestration helpers for synchronous single/parallel `subagent` waves
- package-owned `pimux` workflow runtime surface in `@agentic-config/pi-ac-workflow`

Use this guide plus the roadmap `## Implementation Progress` section as the current package-level evidence set.
