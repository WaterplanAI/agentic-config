# canonical wrapper source

This directory is the canonical source root for the generated Claude and pi wrapper surfaces managed by `tools/generate_canonical_wrappers.py`.

## Layout

```text
canonical/
  <plugin>/
    package.yaml
    assets/
    skills/
      <skill>/
        skill.yaml
        body.md
        assets/
```

- `package.yaml` defines package/plugin output roots, package-shared copied trees, placeholder values, runtime attachments, and pi package-manifest wiring owned by the generator.
- `skills/<skill>/skill.yaml` defines skill metadata, render targets, allowed tools, optional render-specific body-file overrides for high-diff compatibility wrappers, optional render-specific extra frontmatter fields, render-specific placeholder values, and skill-local copied trees.
- `body.md` holds the shared semantic markdown body for the skill.
- `assets/` stores copied support files. Package-level assets render into declared package/plugin destinations. Skill-level assets render into declared skill destinations.

## Current shipped coverage

The canonical tree now covers the current generated surface with `42` canonical skill definitions across:
- `ac-audit`
- `ac-git`
- `ac-meta`
- `ac-qa`
- `ac-safety`
- `ac-tools`
- `ac-workflow`

That breaks down into:
- `42` shipped Claude/pi skill pairs in the current generated package surface
- no explicit deferred pi pressure case remains inside the current canonical skill tree
- one additional shipped package-owned direct `tmux-agent` migration in `@agentic-config/pi-ac-workflow` that intentionally sits outside the current canonical tree so the exact extension logic stays non-lossy

Track D now also ships the shared mux foundation assets plus the full generated mux skill family under `ac-workflow`:
- `mux`
- `mux-ospec`
- `mux-roadmap`
- `mux-subagent`

The generated pi mux orchestrators are intentionally honest adaptations built on the shared mux foundation. They preserve one-layer coordination, explicit report/signal state, and phase/roadmap progress mirrors without claiming Claude-only nested-skill or task-notification parity.
The shipped pi `mux-ospec` wrapper assumes an existing spec path, and the shipped pi `mux-roadmap` wrapper assumes an already-structured roadmap with a live `## Implementation Progress` mirror.

For the shipped pi surface, generated outputs under `packages/` are the authoritative maintenance path for canonical surfaces. The exact `tmux-agent` migration is intentionally package-owned outside the generator because the current canonical/runtime-attachment system cannot honestly own the full extension logic without narrowing it. Remaining runtime carry-forward work now sits outside the current canonical skill tree and is limited to broader generic runtime gaps beyond the shared pi foundations.
Generated outputs intentionally coexist with still-manual siblings. The generator writes only declared canonical paths and does not perform destructive cleanup.

## Commands

Write generated outputs:

```bash
python tools/generate_canonical_wrappers.py
```

Check for drift without writing:

```bash
python tools/generate_canonical_wrappers.py --check
```

Run a filtered package wave:

```bash
python tools/generate_canonical_wrappers.py --plugin ac-git --check
python tools/generate_canonical_wrappers.py --plugin ac-workflow
```

## What the generator owns

For the declared canonical scope, the generator owns:
- Claude skill outputs under `plugins/<plugin>/skills/<skill>/SKILL.md`
- pi skill outputs under `packages/pi-<plugin>/skills/<plugin>-<skill>/SKILL.md`
- package-shared copied support trees
- skill-local copied support trees
- package-local `extensions/hook-compat.js` when declared in canonical runtime attachments
- the generator-owned subset of `package.json` wiring:
  - `pi.skills`
  - `pi.extensions`
  - `dependencies`
  - `bundledDependencies`

Shared runtime implementation remains in `@agentic-config/pi-compat`; canonical runtime attachments only describe the package-local registration surface.

## Placeholders

Built-in placeholder keys currently supported by the generator:
- `{{PACKAGE_ASSETS}}`
- `{{SKILL_ASSETS}}`
- `{{SPEC_ROOT}}`

Package and render blocks may define additional explicit placeholder values when a seeded surface needs a small harness-specific substitution. Copied UTF-8 assets may use the same explicit placeholders as `body.md`; unknown template markers remain untouched.
