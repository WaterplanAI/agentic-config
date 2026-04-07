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
- `43` shipped namespaced skills across `7` plugin packages
- shared `hook-compat` runtime parity plus shared `AskUserQuestion`, `NotebookEdit`, and worker-wave orchestration helpers through `@agentic-config/pi-compat`
- direct package-owned `tmux-agent` managed-agent runtime surface through `@agentic-config/pi-ac-workflow`
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

## What the generated-wrapper strategy means in practice
The current package surface ships primarily through the **Option C canonical-source + generated-wrapper system**, with one package-owned direct `tmux-agent` migration under `@agentic-config/pi-ac-workflow` where the exact extension logic could not be generator-owned honestly.

That means:
- Claude and pi skill outputs are rendered from `canonical/` for the current generated wrapper set
- package-shared and skill-local support trees are copied from canonical ownership instead of being maintained ad hoc per harness
- package README status surfaces describe generated skill/package outputs plus the direct package-owned `tmux-agent` migration as the authoritative maintenance path for the shipped pi surface
- hook-backed runtime parity is still routed through the shared `@agentic-config/pi-compat` adapter plus package-local registrations
- current gaps stay explicit when pi does not yet expose an equivalent runtime surface

The current surface does **not** claim that:
- every remaining non-mux complex surface already ships in pi
- full generic `Task` / subagent runtime is solved as a shared compat primitive
- every Claude marketplace surface has full pi parity

## Install and adoption
### Manual install
Use manual install when you want a personal/global setup or want to try a subset before committing team settings.

Install the full shipped set:

```bash
pi install npm:@agentic-config/pi-all@0.2.6
```

Install only selected plugin families:

```bash
pi install npm:@agentic-config/pi-ac-git@0.2.6
pi install npm:@agentic-config/pi-ac-tools@0.2.6
pi install npm:@agentic-config/pi-ac-workflow@0.2.6
```

Use `-l` if you want `pi install` to write directly to the project-local `.pi/settings.json` instead of your global settings.

### Local package testing before distribution
Pi also supports local-path installs while these packages are still being validated before npm distribution is enabled.

Direct local-path installs are appropriate for standalone packages such as:

```bash
pi install ./packages/pi-compat -l
pi install ./packages/pi-ac-meta -l
pi install ./packages/pi-ac-workflow -l
```

For `@agentic-config/pi-ac-audit`, `@agentic-config/pi-ac-git`, `@agentic-config/pi-ac-qa`, `@agentic-config/pi-ac-safety`, `@agentic-config/pi-ac-tools`, and `@agentic-config/pi-all`, stage a temp package directory first.
Those packages reference bundled sibling resources under `node_modules/@agentic-config/...`, and a raw local-path install reads the directory as-is instead of materializing bundled sibling dependencies for you.

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
Committed `.pi/settings.json` is the preferred team-adoption path because pi can auto-install missing packages on startup and keep the whole team on the same package set.

Full shipped set:

```json
{
  "packages": [
    "npm:@agentic-config/pi-all@0.2.6"
  ]
}
```

Selective team adoption:

```json
{
  "packages": [
    "npm:@agentic-config/pi-ac-git@0.2.6",
    "npm:@agentic-config/pi-ac-tools@0.2.6",
    "npm:@agentic-config/pi-ac-workflow@0.2.6"
  ]
}
```

Why this is preferred over one-off local instructions:
- the package list is versioned with the project
- new teammates get the same pi surface automatically
- package choice stays visible in code review
- plugin-by-plugin installs remain possible without inventing a second distribution scheme

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
| `@agentic-config/pi-ac-tools` | `ac-tools-ac-issue`, `ac-tools-adr`, `ac-tools-agentic-export`, `ac-tools-agentic-import`, `ac-tools-agentic-share`, `ac-tools-cpc`, `ac-tools-dr`, `ac-tools-dry-run`, `ac-tools-gcp-setup`, `ac-tools-gsuite`, `ac-tools-had`, `ac-tools-human-agentic-design`, `ac-tools-improve-agents-md`, `ac-tools-milestone`, `ac-tools-setup-voice-mode`, `ac-tools-single-file-uv-scripter`, `ac-tools-video-query`; dry-run guard parity including notebook-edit coverage plus `gsuite-public-asset-guard.py` parity | none | none |
| `@agentic-config/pi-ac-workflow` | `ac-workflow-product-manager`, `ac-workflow-spec`, `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`, `ac-workflow-mux-subagent`, `ac-workflow-tmux-agent`; package-local `tmux-agent` extension; shared mux foundation assets under `assets/mux/` | mux surfaces are honest pi adaptations built on synchronous one-layer `subagent` waves plus explicit report/signal state, not nested skill loading or task notifications; `mux-ospec` assumes an existing spec path and `mux-roadmap` assumes an already-structured roadmap with `## Implementation Progress` state; `tmux-agent` ships as a package-owned direct migration of the proven global extension/skill surface to preserve exact command/tool/runtime logic | none |
| `@agentic-config/pi-all` | one-shot aggregation of the current shipped package set | aggregation only; no first-party skills or extensions of its own | expands only as future package surfaces ship |

## Runtime parity today vs deferred
### Shipped runtime parity today
- `@agentic-config/pi-ac-audit` ships tool-audit parity through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-git` ships commit-guard parity through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-qa` ships `gh-pr-review` on top of the shared `AskUserQuestion` plus worker-wave orchestration foundation from `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-safety` ships the full current guardian surface, including `playwright-cli` Bash protection, through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-tools` ships dry-run parity and GSuite public-share protection through `@agentic-config/pi-compat`
- `@agentic-config/pi-ac-workflow` ships the exact `tmux_agent` managed-agent runtime through a package-owned direct extension plus the `ac-workflow-tmux-agent` skill surface

### Still explicitly deferred in the current shipped surface
- remaining runtime/tool gaps:
  - broader generic nested/background `Task` / subagent runtime primitives beyond the shared `AskUserQuestion` + `NotebookEdit` + worker-wave foundation and the shipped package-owned `tmux_agent` managed-agent surface

## Versioning strategy
- All package manifests use the shared repository version from `VERSION` (`0.2.6`).
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
| `@agentic-config/pi-ac-tools` | active | `ac-tools-ac-issue`, `ac-tools-adr`, `ac-tools-agentic-export`, `ac-tools-agentic-import`, `ac-tools-agentic-share`, `ac-tools-cpc`, `ac-tools-dr`, `ac-tools-dry-run`, `ac-tools-gcp-setup`, `ac-tools-gsuite`, `ac-tools-had`, `ac-tools-human-agentic-design`, `ac-tools-improve-agents-md`, `ac-tools-milestone`, `ac-tools-setup-voice-mode`, `ac-tools-single-file-uv-scripter`, `ac-tools-video-query`; dry-run parity; GCP / GSuite / voice surfaces shipped | bundles `pi-compat` |
| `@agentic-config/pi-ac-workflow` | active | `ac-workflow-product-manager`, `ac-workflow-spec`, `ac-workflow-mux`, `ac-workflow-mux-ospec`, `ac-workflow-mux-roadmap`, `ac-workflow-mux-subagent`, `ac-workflow-tmux-agent`; package-local `tmux-agent` extension; shared mux foundation assets ship with the full mux family | standalone |
| `@agentic-config/pi-all` | active | aggregation of the current shipped set | bundles all package roots |

## Roadmap evidence
The roadmap evidence artifact is:

- [`.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md`](../.specs/specs/2026/04/pi-adoption-it001/004-roadmap-it-004.md)

Current carry-forward work:
- broader generic nested/background `Task` / subagent runtime primitives beyond the shared `AskUserQuestion` + `NotebookEdit` + worker-wave foundation and the shipped package-owned `tmux_agent` managed-agent surface

Shared/runtime boundary now shipped across package surfaces:
- `AskUserQuestion`
- `NotebookEdit`
- worker-wave orchestration helpers for synchronous single/parallel `subagent` waves
- package-owned `tmux_agent` managed-agent runtime surface in `@agentic-config/pi-ac-workflow`

Use this guide plus the roadmap `## Implementation Progress` section as the current package-level evidence set.
