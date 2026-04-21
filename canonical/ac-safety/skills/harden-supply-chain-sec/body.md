
# harden-supply-chain-sec

Harden software supply chain security by configuring minimum release age policies across package managers.

## Invocation

```
/harden-supply-chain-sec [<manager>|auto] [global|project] [<duration>] [--exclude pkg1,pkg2] [--guided] [--harden]
```

## Arguments

| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| `manager` | No | `auto` | One of: `pnpm`, `yarn`, `bun`, `npm`, `uv`, `all`, `auto`. `auto` detects from project. `all` = all detected managers. |
| `scope` | No | `project` | `global`, `project`, or `both`. When `global`, skip project root detection; use manager-specific global config paths. When `both`, run project scope first, then global scope (two passes through Sections 4-8a). |
| `duration` | No | `7d` | Human-friendly: `7d`, `24h`, `1w`, `72h`, `3d`. Default is 7 days. |
| `--exclude` | No | (none) | Comma-separated package names. Per-manager semantics differ (see Section 9). |
| `--guided` | No | `false` | Interactive mode: AskUserQuestion at each decision point. Args are pre-filled defaults, not skips. |
| `--harden` | No | `false` | Enable post-config security hardening (Sections 11-13). |

## Behavior

- You are a senior security engineer hardening supply chain configuration.
- Always show dry-run before any writes. Never write without explicit confirmation.
- Fail-open on errors: warn and skip, do not block the user.
- Detection and dry-run phases are read-only. Do not install, enable, or update tooling during preflight.
- Any install/update, audit-tool installation, or lockfile-regeneration command requires a separate explicit confirmation after the exact command is shown.
- Never recommend or run `curl | sh` / `curl | bash` installers.
- Be project-agnostic: no hardcoded paths, repos, or organization names.
- If `--guided` is present, always enter guided mode regardless of other args.
- If `--harden` is present, proceed to hardening gates after config writes.

## CRITICAL: Execution Order

Follow these sections in exact order:
1. Parse arguments (Section 1). If no args: auto-enter guided mode.
2. Guided mode prompts if `--guided` or no args (Section 10)
3. Project root resolution (Section 5)
4. Manager detection and version check (Sections 7, 3)
5. Frozen-lockfile detection (Section 6)
6. Config value computation (Section 4)
7. Dry-run display and Gate 1 confirmation (Section 8)
8. Config writing on confirmation (Section 4)
9. Post-apply summary (Section 8)
10. Post-apply verification (Section 8a)
11. If `--harden` (or selected at Gate 1): Gates 2-2b-3-4 (Sections 11-11b-12-13)
12. If `scope=project`: offer commit (Section 8b)
13. Preferred manager suggestions (Section 15)

---

## Section 1: Parse Arguments and Duration Normalization

Parse the invocation arguments. Apply defaults for missing args:
- `manager` -> `auto`
- `scope` -> `project`
- `duration` -> `7d`
- `--exclude` -> empty
- `--guided` -> false
- `--harden` -> false

### No-Args Auto-Guided

If the skill is invoked with NO arguments (bare `/harden-supply-chain-sec`), automatically enter guided mode (Section 10). This is equivalent to `--guided` being implicitly set. If ANY argument is provided, use the standard defaults and require explicit `--guided` for interactive mode.

### Duration Normalization

Parse human-friendly duration input and convert to each manager's native unit.

**Parsing rules:**
- `Xd` = X days
- `Xh` = X hours
- `Xw` = X weeks (X * 7 days)
- If no unit suffix, assume days
- Minimum: 1 hour. Error if duration < 1 hour.

**Conversion table** (compute at runtime):

| Input | Total hours | pnpm (minutes) | Bun (seconds) | Yarn (duration str) | npm (days, ceil) | uv (duration str) |
|-------|-------------|----------------|---------------|---------------------|------------------|--------------------|
| `7d` | 168 | 10080 | 604800 | `"7d"` | 7 | `"7 days"` |
| `3d` | 72 | 4320 | 259200 | `"3d"` | 3 | `"3 days"` |
| `24h` | 24 | 1440 | 86400 | `"1d"` | 1 | `"24 hours"` |
| `1w` | 168 | 10080 | 604800 | `"7d"` | 7 | `"7 days"` |
| `12h` | 12 | 720 | 43200 | `"12h"` | 1 (ceil) | `"12 hours"` |
| `25h` | 25 | 1500 | 90000 | `"1d1h"` | 2 (ceil) | `"25 hours"` |

**Formulas:**
- `total_hours` = parse input to hours
- pnpm: `total_hours * 60` (integer minutes)
- Bun: `total_hours * 3600` (integer seconds)
- Yarn: if `total_hours >= 24` and evenly divisible by 24 -> `"Xd"` (where X = total_hours / 24), else if `total_hours >= 24` -> `"XdYh"` (where X = floor(total_hours / 24), Y = total_hours % 24), else -> `"Xh"`
- npm: `ceil(total_hours / 24)` (integer days, minimum 1). If `total_hours` is not evenly divisible by 24, show warning: "npm rounds <N>h up to <ceil> days (<ceil*24>h effective protection)"
- uv: if evenly divisible by 24 -> `"X days"` (where X = total_hours / 24), else -> `"N hours"` (where N = total_hours). For uv < 0.9.17, use ISO 8601 timestamp instead (compute as UTC now + duration).

## Section 2: Supported Managers Reference

### Manager Configuration Map

| Manager | Config key | Unit | Min version | Config file (project) | Config file (global) |
|---------|-----------|------|-------------|-----------------------|---------------------|
| pnpm | `minimumReleaseAge` (YAML) / `minimum-release-age` (rc) | minutes (integer) | `>=10.16.0` | `pnpm-workspace.yaml` | `~/.config/pnpm/rc` (Linux), `~/Library/Preferences/pnpm/rc` (macOS), or `~/.npmrc` |
| Yarn v4 | `npmMinimalAgeGate` | duration string | `>=4.10.0` | `.yarnrc.yml` | `~/.yarnrc.yml` (verified: Yarn 4.13.0 reads and enforces `npmMinimalAgeGate` from home `.yarnrc.yml`) |
| Bun | `install.minimumReleaseAge` | seconds (integer) | `>=1.3.0` | `bunfig.toml` | `~/.bunfig.toml` |
| npm | `min-release-age` | days (integer) | `>=11.10.0` | `.npmrc` | `~/.npmrc` (NOTE: `npm config get min-release-age` may return `null` even when set — verify via `npm config get before --global` which shows dynamic `now - duration` timestamp) |
| uv | `exclude-newer` | duration string or ISO 8601 | `>=0.4.0` (duration strings: `>=0.9.17`) | `pyproject.toml` under `[tool.uv]` | `~/.config/uv/uv.toml` |

### Lockfile Detection Map

| Manager | Lockfile | Config markers |
|---------|----------|----------------|
| pnpm | `pnpm-lock.yaml` | `pnpm-workspace.yaml` |
| Yarn v4 | `yarn.lock` | `.yarnrc.yml` |
| Bun | `bun.lock` (legacy: `bun.lockb`) | `bunfig.toml` |
| npm | `package-lock.json` | `.npmrc` |
| uv | `uv.lock` | `pyproject.toml` with `[tool.uv]` section |

### Exclusion Keys

| Manager | Exclusion config key | Semantics | Warning |
|---------|---------------------|-----------|---------|
| pnpm | `minimumReleaseAgeExclude` (array in `pnpm-workspace.yaml`) | Bypasses age gate only | (none) |
| Bun | `install.minimumReleaseAgeExcludes` (array in `bunfig.toml`) | Bypasses age gate only | (none) |
| Yarn v4 | `npmPreapprovedPackages` (array in `.yarnrc.yml`) | Bypasses ALL package gates, not just age | WARN: "Yarn's npmPreapprovedPackages bypasses all package validation gates (audit, age, signature), not just the age gate." |
| npm | (none) | No exclusion mechanism | WARN: "npm does not yet support min-release-age exclusions." |
| uv | `exclude-newer-package` (table in `pyproject.toml` `[tool.uv]`) | Per-package cutoff date/duration override (different model) | WARN: "uv uses per-package cutoff overrides, not a bypass list. Each excluded package gets its own exclude-newer-package entry." |

## Section 3: Version Check Procedure

For each manager to be configured, run the version check BEFORE any config writes.

### Steps

1. Run via Bash: `<manager> --version 2>/dev/null`
   - If command fails (exit code != 0): check Corepack fallback for Yarn (see below).
   - If still fails: manager is NOT installed. Record status: `NOT_INSTALLED`. WARN and SKIP.
2. **Yarn v4 Corepack detection** (special case):
   - `yarn --version` may return nothing or Yarn Classic (1.x) because Yarn v4 is managed via Corepack, NOT the `yarn` npm package.
   - If `yarn --version` fails or returns `1.x`: run `corepack yarn --version 2>/dev/null` as fallback.
   - If Corepack is not installed: run `corepack --version 2>/dev/null` to check, record the prerequisite command, and WARN -- but do NOT run `corepack enable` during detection.
   - If Corepack resolves Yarn v4 (>= 4.x): use that version. Record install command as `corepack prepare yarn@<version> --activate`.
   - If Corepack is unavailable and Yarn is not installed: status = `NOT_INSTALLED`, but include in update commands: `corepack enable && corepack prepare yarn@<version> --activate` for later explicit confirmation.
3. Parse version string from output:
   - pnpm: output is just the version number (e.g., `10.16.0`)
   - yarn: output is just the version number (e.g., `4.13.0`) — may come from Corepack fallback
   - bun: output format `X.Y.Z` (e.g., `1.3.0`)
   - npm: output is just the version number (e.g., `11.10.0`)
   - uv: output format `uv X.Y.Z` -- extract the version after `uv `
4. Compare installed version against minimum version from Section 2 table using semver comparison:
   - Split both versions on `.` into `[major, minor, patch]`
   - Compare major first, then minor, then patch
   - If installed >= minimum: status = `OK`
   - If installed < minimum: status = `TOO_OLD`. WARN with message: "Installed <manager> <version> is below minimum <min_version> required for minimum release age support. Skipping." SKIP this manager.
5. Special case for uv:
   - If installed >= 0.9.17: use duration string format (e.g., `"7 days"`)
   - If installed >= 0.4.0 but < 0.9.17: use ISO 8601 timestamp format. Compute as: current UTC time + duration. Format: `YYYY-MM-DDTHH:MM:SSZ`
   - If installed < 0.4.0: `TOO_OLD`, SKIP.
6. Build version check table for dry-run display (see Section 8).

### Manager Installation/Update Age Gate (Self-Referential Rule)

When the version check reveals a manager needs installation or update (status =
`NOT_INSTALLED` or `TOO_OLD`), any suggestion to install or update that manager
MUST itself respect the minimum release age being configured.

**Before suggesting a manager install/update:**
1. Query the manager's own package registry for its latest version publish date.
   - npm/bun/pnpm: `npm view <manager> time --json` (check the version's publish timestamp)
   - yarn: Yarn v4 is distributed via Corepack, NOT the `yarn` npm package. Query the Yarn GitHub releases API: `gh api repos/yarnpkg/berry/releases --jq '.[].tag_name'` or check https://repo.yarnpkg.com/tags. The `npm view yarn time --json` returns Classic (1.x) metadata and must NOT be used for Yarn v4 version lookups.
   - uv: `pip index versions uv --pre` or check PyPI JSON API `https://pypi.org/pypi/uv/json`
2. If the latest version was published LESS than the configured duration ago:
   - WARN: "<manager> latest version <version> was published <N days> ago, which is below the configured minimum release age of <duration>. Recommend waiting or pinning to an older verified version."
   - Suggest the most recent version that DOES meet the age threshold.
3. If the latest version meets the age threshold: suggest it normally.
4. When presenting install/update guidance, first display the exact command or manual steps. Only execute a command after an explicit confirmation step. Never recommend or run `curl | sh` / `curl | bash` installers.

This rule ensures the hardening tool does not undermine its own security posture
by recommending freshly-published manager binaries.

## Section 4: Config Writing Procedures

For EACH verified manager (status = OK), follow the per-manager procedure below.
All writes happen ONLY after Gate 1 confirmation (Section 8).

### General Safety Pattern

1. READ the target config file (if it exists) using the Read tool.
2. EXTRACT the current value for the manager's config key.
3. If current value equals the proposed value: record as "(unchanged)", SKIP write.
4. COMPUTE the unified diff showing the change.
5. Store diff for dry-run display (Section 8).
6. On Gate 1 confirmation: apply the write.
7. POST-WRITE verification: re-read the file, confirm the value matches the proposed value.
8. If verification fails: WARN with details but do NOT retry automatically.

### Hook Denial Recovery

If a Write or Edit operation is DENIED by a hook (e.g., `write-scope-guardian`,
`supply-chain-guardian`, or any other security hook), do NOT retry or attempt to
bypass the hook. Instead:

1. **STOP** all write operations immediately.
2. **Display** the exact manual steps the user must perform themselves:
   ```
   ================================================================
   BLOCKED: A security hook denied the write operation.
   ================================================================

   Hook: <hook_name> (if identifiable from error)
   File: <target_file>
   Change: <key> = <value>

   To apply this change manually, run:

     <exact shell command or editor instruction for this specific change>

   For example:
     echo '<config_line>' >> <target_file>
     -- OR --
     Open <target_file> and add/update: <key>: <value>

   After making the change, come back and confirm.
   ================================================================
   ```
3. **Ask** using AskUserQuestion:
   - header: `Manual update`
   - question: "I was blocked from writing to <target_file>. The manual steps are shown above. Confirm when you have applied the change."
   - options:
     - label: "Done"
     - description: "I applied the change manually"
     - label: "Skip"
     - description: "Skip this manager and continue with the rest"
4. **If "Done"**: run post-check verification using CLI commands (NOT file re-reads,
   since the same hook may block reads too):
   - pnpm: `pnpm config get minimum-release-age`
   - npm: `npm config get before --global` (expect dynamic timestamp; `min-release-age` returns `null` — display quirk)
   - bun/uv/yarn: use Section 8a functional test (preferred) or file read if allowed
   - If correct: display "Verified: <key> = <value>." and continue.
   - If NOT correct: display the exact discrepancy and re-ask (max 2 retries, then WARN and continue).
5. **If "Skip"**: record as "Skipped (hook denied)" in the post-apply summary and continue.

This pattern applies to ALL write operations: config writes (Section 4), hardening
policy writes (Sections 11-13), and any other file modifications.

### pnpm

**Project scope:**
- File: `<project_root>/pnpm-workspace.yaml`
- If file does not exist: create it with content:
  ```yaml
  packages: []
  minimumReleaseAge: <minutes>
  ```
- If file exists: use Edit tool to add/update `minimumReleaseAge: <minutes>` as a top-level key.
- Value: integer minutes (from Section 1 conversion).

**Global scope:**
- pnpm supports global configuration via rc files using kebab-case key names.
- Detect OS and resolve the global rc path:
  - macOS: `~/Library/Preferences/pnpm/rc`
  - Linux: `~/.config/pnpm/rc`
  - Windows: `~/AppData/Local/pnpm/config/rc`
  - Fallback: `~/.npmrc` (pnpm reads this too)
- If the rc file does not exist: create it with content:
  ```ini
  minimum-release-age=<minutes>
  ```
- If the rc file exists: add/update the `minimum-release-age=<minutes>` line.
- Value: integer minutes (same as project scope).
- NOTE: The rc file uses kebab-case (`minimum-release-age`), NOT camelCase (`minimumReleaseAge`).

**Exclusions (if `--exclude`):**
- Add `minimumReleaseAgeExclude` array to `pnpm-workspace.yaml`:
  ```yaml
  minimumReleaseAgeExclude:
    - "package-name-1"
    - "package-name-2"
  ```
- If key already exists: merge new entries (avoid duplicates).

### Yarn v4

**Project scope:**
- File: `<project_root>/.yarnrc.yml`
- If file does not exist: create it with content:
  ```yaml
  npmMinimalAgeGate: "<duration_string>"
  ```
- If file exists: use Edit tool to add/update `npmMinimalAgeGate: "<duration_string>"`.
- Value: duration string from Section 1 conversion (e.g., `"7d"`).

**Global scope:**
- File: `~/.yarnrc.yml`
- Verified: Yarn 4.13.0 reads and enforces `npmMinimalAgeGate` from `~/.yarnrc.yml`.
- If file does not exist: create it with content:
  ```yaml
  npmMinimalAgeGate: "<duration_string>"
  ```
- If file exists: use Edit tool to add/update `npmMinimalAgeGate: "<duration_string>"`.
- Value: duration string from Section 1 conversion (same as project scope).
- NOTE: `~/.yarnrc.yml` causes Yarn to treat `~` as a project root. This is harmless
  for the age gate setting but may affect other Yarn behaviors if the home directory
  contains a `package.json`. Display a note in the dry-run: "Global `~/.yarnrc.yml`
  will be created/updated. This is safe for `npmMinimalAgeGate` but note that Yarn
  treats directories with `.yarnrc.yml` as project roots."

**Exclusions (if `--exclude`):**
- Add `npmPreapprovedPackages` array to `.yarnrc.yml`:
  ```yaml
  npmPreapprovedPackages:
    - "package-name-1"
    - "package-name-2"
  ```
- WARN: "Yarn's npmPreapprovedPackages bypasses ALL package validation gates (audit, age, signature), not just the age gate. Verify this is intended."

### Bun

**Project scope:**
- File: `<project_root>/bunfig.toml`
- If file does not exist: create it with content:
  ```toml
  [install]
  minimumReleaseAge = <seconds>
  ```
- If file exists: use Edit tool to add/update `minimumReleaseAge = <seconds>` under the `[install]` section.
  - If `[install]` section does not exist: add it.
- Value: integer seconds (from Section 1 conversion).

**Global scope:**
- File: `~/.bunfig.toml`
- Same format as project scope.

**Exclusions (if `--exclude`):**
- Add under `[install]` section:
  ```toml
  minimumReleaseAgeExcludes = ["package-name-1", "package-name-2"]
  ```

### npm

**Project scope:**
- File: `<project_root>/.npmrc`
- If file does not exist: create it with content:
  ```ini
  min-release-age=<days>
  ```
- If file exists: use Edit tool to add/update `min-release-age=<days>`.
  - `.npmrc` uses `key=value` format (INI-style, no spaces around `=`).
  - Preserve existing lines and comments.
- Value: integer days (from Section 1 conversion, ceiling rounding).

**Global scope:**
- File: `~/.npmrc`
- Same format as project scope.
- **Credential guardian fallback**: `.npmrc` may contain auth tokens and be blocked by
  security hooks (credential guardian). If direct Read/Write access is denied:
  - Use `npm config set min-release-age <days> --global` to write.
  - Use `npm config get before --global` to verify (returns dynamic `now - duration`
    timestamp; `npm config get min-release-age` may display `null` even when set — this
    is a display quirk in npm 11.x, not a failure).

**Exclusions (if `--exclude`):**
- WARN: "npm does not yet support min-release-age exclusions. There is no mechanism to exempt specific packages."
- Do NOT write any exclusion config.

### uv

**Project scope:**
- File: `<project_root>/pyproject.toml`
- Section: `[tool.uv]`
- If file does not exist AND (`uv.lock` exists OR user explicitly requested uv): create `pyproject.toml` with:
  ```toml
  [tool.uv]
  exclude-newer = "<value>"
  ```
- If file exists but no `[tool.uv]` section: add the section with the key.
- If file exists and `[tool.uv]` section exists: add/update `exclude-newer = "<value>"` within the section.
- Value depends on uv version (from Section 3):
  - uv >= 0.9.17: duration string, e.g., `"7 days"`
  - uv >= 0.4.0 but < 0.9.17: ISO 8601 timestamp, e.g., `"2026-04-08T00:00:00Z"`

**Global scope:**
- File: `~/.config/uv/uv.toml`
- If file does not exist: create it with:
  ```toml
  exclude-newer = "<value>"
  ```
- If file exists: add/update `exclude-newer` key.
- Note: global `uv.toml` does NOT use `[tool.uv]` section -- it is a flat TOML.

**Exclusions (if `--exclude`):**
- WARN: "uv uses per-package cutoff overrides via exclude-newer-package, not a bypass list. Each excluded package gets its own cutoff entry."
- Add to `[tool.uv]` section in `pyproject.toml` (or flat in `uv.toml` for global):
  ```toml
  [tool.uv.exclude-newer-package]
  package-name-1 = "<far_future_timestamp>"
  package-name-2 = "<far_future_timestamp>"
  ```
- The value for excluded packages should be a far-future timestamp (e.g., `"2099-12-31T23:59:59Z"`) to effectively bypass the age gate.

## Section 5: Project Root Resolution

If `scope=global`: SKIP this section entirely. Global config paths are absolute (Section 4).
If `scope=both`: resolve project root (needed for the project-scope pass).

### Precedence (highest to lowest)

1. **User-specified root**: If user provided an explicit path argument, use it.
2. **Manager-specific root markers** (scan upward from CWD):
   - pnpm: nearest `pnpm-workspace.yaml` (pnpm is always root-scoped)
   - Yarn: nearest `.yarnrc.yml`
   - uv: nearest `pyproject.toml` containing `[tool.uv]` section, or nearest `uv.lock`
   - npm: nearest `package.json`
   - Bun: nearest `package.json`
3. **VCS root**: nearest `.git` directory (fallback)
4. **`package.json#packageManager`**: use as a hint/tie-breaker to identify which manager, NOT as a root override.

### Resolution Steps

1. Determine CWD via Bash: `pwd`
2. For each manager in the detection set, use Bash to scan upward:
   ```bash
   # Example for pnpm -- find nearest pnpm-workspace.yaml
   dir="$(pwd)"
   while [ "$dir" != "/" ]; do
     [ -f "$dir/pnpm-workspace.yaml" ] && echo "$dir" && break
     dir="$(dirname "$dir")"
   done
   ```
3. If multiple managers resolve to different roots:
   - Use manager-specific roots for each manager's config writes (monorepo case).
   - Display all detected roots in dry-run.
4. If no markers found: fall back to VCS root (`.git`).
5. If still ambiguous (e.g., no `.git` either): use AskUserQuestion to ask user for the project root.

### Monorepo Handling

- In monorepos, different managers may have different root locations.
- pnpm always writes to workspace root (`pnpm-workspace.yaml` location).
- Other managers write to the directory containing their respective config files.
- Display each manager's resolved root in the dry-run.

## Section 6: Frozen-Lockfile Detection

Only run when `scope=project`. Detect CI/build configurations that use frozen-lockfile install commands.

### Scan Targets

Use Glob and Grep to scan these files at project root:

| Glob pattern | Description |
|-------------|-------------|
| `.github/workflows/*.yml` | GitHub Actions |
| `.github/workflows/*.yaml` | GitHub Actions (alt extension) |
| `.gitlab-ci.yml` | GitLab CI |
| `Jenkinsfile` | Jenkins |
| `Dockerfile*` | Docker (Dockerfile, Dockerfile.dev, etc.) |
| `Makefile` | Make |
| `package.json` | npm scripts section |

### Patterns to Search (per manager)

Use Grep with these patterns. Record each match as `file:line`.

| Manager | Grep pattern (regex) |
|---------|---------------------|
| npm | `npm\s+ci\b` |
| pnpm | `pnpm\s+install\s+--frozen-lockfile` |
| Yarn | `yarn\s+install\s+--immutable` |
| Bun | `bun\s+ci\b` or `bun\s+install\s+--frozen-lockfile` |
| uv | `uv\s+sync\s+--frozen` |

### Output

Build a table of detected frozen-lockfile usages:

```
| Manager | Command found | Location |
|---------|--------------|----------|
| npm | npm ci | .github/workflows/ci.yml:23 |
| uv | uv sync --frozen | Dockerfile:14 |
```

If no frozen-lockfile usage detected: omit the table from dry-run.

### Post-Apply Warning

After config writes, if any frozen-lockfile usage was detected, display:

```
WARNING: Frozen-lockfile CI commands detected (see above).
After applying minimum release age, you MUST re-resolve your lockfile(s)
before committing, so the lockfile reflects the new policy:

  npm:  npm install
  pnpm: pnpm install
  yarn: yarn install
  bun:  bun install
  uv:   uv sync

Then commit the updated lockfile(s).
Do NOT run the install commands automatically -- review changes first.
```

Only list managers that have both: (a) config being written AND (b) frozen-lockfile detected.

## Section 7: Auto-Detection Procedure

When `manager=auto` (default), detect which package managers are active in the project.

### Detection Steps

1. Resolve project root (Section 5).
2. Use Glob to check for lockfiles and config files at project root:

   ```
   Glob(pattern="pnpm-lock.yaml", path="<project_root>")
   Glob(pattern="yarn.lock", path="<project_root>")
   Glob(pattern="bun.lock", path="<project_root>")
   Glob(pattern="bun.lockb", path="<project_root>")
   Glob(pattern="package-lock.json", path="<project_root>")
   Glob(pattern="uv.lock", path="<project_root>")
   Glob(pattern="pnpm-workspace.yaml", path="<project_root>")
   Glob(pattern=".yarnrc.yml", path="<project_root>")
   Glob(pattern=".pnp.cjs", path="<project_root>")
   Glob(pattern=".yarn", path="<project_root>")
   Glob(pattern="bunfig.toml", path="<project_root>")
   Glob(pattern=".npmrc", path="<project_root>")
   Glob(pattern="pyproject.toml", path="<project_root>")
   Glob(pattern="package.json", path="<project_root>")
   ```

3. Map detection results to managers:
   - pnpm: detected if `pnpm-lock.yaml` OR `pnpm-workspace.yaml` exists
   - Yarn v4: detected if `yarn.lock` exists AND any of the following v4 markers are present:
     - `.yarnrc.yml` exists, OR
     - `package.json` contains a `"packageManager": "yarn@4.x"` field, OR
     - `.pnp.cjs` or `.yarn/` directory exists (Corepack-managed Yarn 4 projects may have these without `.yarnrc.yml` or `packageManager`), OR
     - `yarn --version 2>/dev/null` returns a `4.x` version (runtime check as last resort)
     If only `yarn.lock` exists with NONE of the above markers AND the runtime version check fails or returns 1.x: WARN: "yarn.lock found but cannot confirm Yarn v4. Skipping. Use `manager=yarn` to force."
   - Bun: detected if `bun.lock` OR `bun.lockb` (legacy) OR `bunfig.toml` exists
   - npm: detected if `package-lock.json` exists. If other JS lockfiles (pnpm/yarn/bun) also exist, WARN: "package-lock.json found alongside <other lockfile>. npm included but may be secondary in this monorepo. Use `manager=npm` to configure explicitly if auto-detection excludes it." Still include npm in detection -- do NOT silently skip.
   - uv: detected if `uv.lock` exists OR (`pyproject.toml` exists with `[tool.uv]` section)

4. For uv detection via `pyproject.toml`: Read the file and check if `[tool.uv]` section exists using Grep:
   ```
   Grep(pattern="\\[tool\\.uv\\]", path="<project_root>/pyproject.toml")
   ```

5. Also detect warning-only managers:
   - Cargo: `Cargo.lock` or `Cargo.toml` exists
   - pip: `requirements.txt` or `setup.py` or `setup.cfg` exists (without uv markers)
   - Go: `go.sum` or `go.mod` exists

6. If NO managers detected: ERROR with message listing all files scanned and paths checked. Use AskUserQuestion to ask user to specify manager explicitly.

### When `manager=all`

Run auto-detection, then configure ALL detected supported managers (not warning-only).

### When `manager=<specific>`

Skip detection. Use only the specified manager. Still run version check (Section 3).

## Section 8: Dry-Run Display and Gate 1 Confirmation

ALWAYS display the dry-run before any config writes. This is mandatory, not optional.

### Dry-Run Format

Display the following sections in order. Omit sections with no data.

```
================================================================
PRE-FLIGHT: minimum release age configuration
================================================================

Duration: <duration> (<source: default/user-specified>)
Project root: <resolved_root> (detected via <marker>)
Scope: <project|global>

-- Manager Version Check ------------------------------------------
| Manager | Installed | Required | Status |
|---------|-----------|----------|--------|
| <mgr> | <version> | <min_version> | OK / TOO_OLD / NOT_INSTALLED |

-- Frozen-Lockfile Usage Detected ---------------------------------
(only if scope=project and detections found)
| Manager | Command found | Location |
|---------|--------------|----------|
| <mgr> | <command> | <file>:<line> |

-- Configuration Changes ------------------------------------------
| Manager | Scope | File | Key | Current | New |
|---------|-------|------|-----|---------|-----|
| <mgr> | <scope> | <file> | <key> | <current_or_none> | <new_value> |

(unchanged) shown for keys where current == new

-- File Diffs -----------------------------------------------------
(unified diff per file, showing exact changes)

-- Exclusion Semantics --------------------------------------------
(only if --exclude provided)
| Manager | Exclusion key | Semantics | Notes |
|---------|--------------|-----------|-------|

-- Scope Overlap ---------------------------------------------------
(only if scope=project AND a global config also sets the same key for any manager)
| Manager | Global config | Global value | Note |
|---------|--------------|-------------|------|
| <mgr> | <global_file> | <global_value> | Project config will take precedence |

-- Warnings -------------------------------------------------------
(list all warnings accumulated during detection, version check, etc.)
- <warning message>

-- Warning-Only Managers ------------------------------------------
(only if warning-only managers detected)
| Manager | Status | Guidance |
|---------|--------|----------|
| Cargo | Not configurable (nightly-only) | Use cargo-deny for stable supply-chain controls |
| pip | No native age-gating | Migrate to uv |
| Go | No native age-gating | Use Go module proxy with age policies |

================================================================
```

### Gate 1: Confirmation

After displaying the dry-run, ask using AskUserQuestion:

- header: `Gate 1`
- question: "Apply the configuration changes shown above?" (include a parenthetical
  summary of what will be written vs skipped/unchanged)
- multiSelect: false
- options (select based on context — max 4 options, AskUserQuestion limit):

  **When `scope=project` AND `--harden` not set AND managers have TOO_OLD/NOT_INSTALLED:**
  - label: "Yes, and harden CLAUDE.md/AGENTS.md"
  - description: "Apply config + update CLAUDE.md/AGENTS.md with dependency security policy (Gates 2-4)"
  - label: "Yes"
  - description: "Apply the config changes only"
  - label: "Yes, and show update commands"
  - description: "Apply config + show install/update commands for skipped managers (age-verified)"
  - label: "No"
  - description: "Abort -- no changes will be written"

  **When `scope=project` AND `--harden` not set AND no skipped managers:**
  - label: "Yes, and harden CLAUDE.md/AGENTS.md"
  - description: "Apply config + update CLAUDE.md/AGENTS.md with dependency security policy (Gates 2-4)"
  - label: "Yes"
  - description: "Apply the config changes only"
  - label: "No"
  - description: "Abort -- no changes will be written"

  **When `--harden` already set (any scope):**
  - label: "Yes"
  - description: "Apply the config changes listed above"
  - label: "No"
  - description: "Abort -- no changes will be written"
  - label: "Yes, and show update commands" (only if managers have TOO_OLD/NOT_INSTALLED)
  - description: "Apply changes + show install/update commands for skipped managers (age-verified)"

  **When `scope=global` AND `--harden` not set:**
  - label: "Yes, and harden CLAUDE.md/AGENTS.md"
  - description: "Apply config + update CLAUDE.md/AGENTS.md with dependency security policy (Gates 2-4)"
  - label: "Yes"
  - description: "Apply the config changes listed above"
  - label: "No"
  - description: "Abort -- no changes will be written"
  - label: "Yes, and show update commands" (only if managers have TOO_OLD/NOT_INSTALLED)
  - description: "Apply changes + show install/update commands for skipped managers (age-verified)"

**Option handling:**
- "Yes": proceed with config writes (Section 4).
- "No": abort. Display "Aborted. No changes were written." and STOP.
- "Yes, and harden CLAUDE.md/AGENTS.md": proceed with config writes (Section 4),
  then set `--harden=true` and proceed to Gates 2-4 (Sections 11-13) after verification.
- "Yes, and show update commands": proceed with config writes (Section 4), then
  for each manager with status `TOO_OLD` or `NOT_INSTALLED`:
  1. Look up the manager's latest version that meets the configured minimum release
     age (per Section 3 "Manager Installation/Update Age Gate").
  2. Display the exact install/update guidance pinned to that age-verified version:
     - pnpm: `npm install -g pnpm@<version>`
     - yarn: `corepack enable && corepack prepare yarn@<version> --activate`
     - bun: manual install only -- show the exact Bun version to install and direct the user to the official Bun installation documentation. Do NOT use or display `curl | bash`.
     - npm: `npm install -g npm@<version>`
     - uv: `pip install uv==<version>` if `pip` is available; otherwise show manual installation guidance without `curl | sh`.
  3. After each command, note: "Version <version> published <N days> ago (meets <duration> age gate)."
  4. For commands that are safe to execute directly (`pnpm`, `yarn`, `npm`, and `uv` via `pip`), use AskUserQuestion:
     - header: `Prerequisite`
     - question: "Run the age-verified install/update command for <manager> now?"
     - options:
       - label: "Run now"
       - description: "Execute: <exact_command>"
       - label: "Show command only"
       - description: "Display the exact command without executing it"
       - label: "Skip"
       - description: "Do not install/update this manager now"
  5. If "Run now": execute the exact command.
  6. If "Show command only": display the exact command and continue.
  7. If "Skip": continue without executing anything.
  8. For Bun, always show manual guidance only and continue.

### Post-Apply Display

After successful config writes, display:

```
================================================================
APPLIED: minimum release age configuration
================================================================

| Manager | File | Status |
|---------|------|--------|
| <mgr> | <file> | Written / Unchanged / Skipped (<reason>) |

(frozen-lockfile warning if applicable -- see Section 6)
================================================================
```

## Section 8a: Post-Apply Verification

After every post-apply display, run verification for ALL managers that were configured
(not just hook-denied ones). This confirms the age gate is actually enforced at runtime.

**CRITICAL: Verification method depends on SCOPE. Project and global configs live in
different files and require different test strategies.**

### Scope-Aware Verification Strategy

| Scope | Verification method | Rationale |
|-------|-------------------|-----------|
| project | **Direct file read** (primary) + **functional test in project dir** (secondary) | Project config files are in-tree and readable. Temp dir tests would only hit global config. |
| global | **CLI config get** (pnpm, npm) + **functional test in temp dir** (bun, uv, yarn) | Global files may be hook-blocked. Temp dir inherits global config. |

### Project Scope Verification

**Primary: Direct file read.** The config file is in the project directory — read it
and confirm the expected key/value is present.

| Manager | File | Confirm |
|---------|------|---------|
| pnpm | `pnpm-workspace.yaml` | `minimumReleaseAge: <minutes>` exists |
| bun | `bunfig.toml` | `minimumReleaseAge = <seconds>` under `[install]` |
| npm | `.npmrc` | `min-release-age=<days>` line exists |
| uv | `pyproject.toml` | `exclude-newer = "<value>"` under `[tool.uv]` |
| yarn | `.yarnrc.yml` | `npmMinimalAgeGate: "<duration>"` exists |

**Secondary: Functional test in PROJECT directory.** To confirm runtime enforcement,
run the functional test FROM the project root (not a temp dir). This ensures the
project-level config is what gets tested.

**bun (project scope):**
```bash
cd <project_root>
# Create a minimal test subdir to avoid polluting project
mkdir -p .harden-test && cd .harden-test
echo '{"dependencies":{"<pkg>":"<version>"}}' > package.json
bun install --dry-run 2>&1
rc=$?
cd .. && rm -rf .harden-test
# PASS: output contains "blocked by minimum-release-age"
# FAIL: resolution succeeds — may be masked by global config
```

**uv (project scope):**
```bash
cd <project_root>
# uv reads pyproject.toml from project root
uv pip install --dry-run "<pkg>==<version>" 2>&1
# PASS: output indicates version excluded by exclude-newer
# FAIL: resolution succeeds
```

**yarn (project and global scope):**

NOTE: Yarn 4 does NOT support `install --dry-run`, and running `corepack yarn`
from a subdirectory of an existing Yarn project causes workspace resolution
errors. Yarn functional tests are therefore NOT viable. Rely on direct file
read verification only (the primary check).

For project scope: read `.yarnrc.yml` and confirm `npmMinimalAgeGate` is set.
For global scope: read `~/.yarnrc.yml` and confirm `npmMinimalAgeGate` is set.

Do NOT attempt to create a `.harden-test/` subdirectory for Yarn -- it will
fail due to Yarn's project boundary detection.

**WARNING**: If a global config also exists for the same manager, the functional test
may pass due to global config even if project config is broken. Always do the direct
file read check FIRST. If both global and project configs exist, note this in the report:
"Both project and global configs active — project config takes precedence."

### Global Scope Verification

**CLI-Based (pnpm, npm):**

| Manager | Command | Expected result |
|---------|---------|-----------------|
| pnpm | `pnpm config get minimum-release-age` | `<minutes>` (e.g., `10080`) |
| npm | `npm config get before --global` | Dynamic timestamp = `now - <duration>` (NOTE: `npm config get min-release-age` may return `null` — display quirk in npm 11.x, not a failure. The `before` value shifting with wall-clock time proves the age gate is active.) |
| yarn | Read `~/.yarnrc.yml` and confirm `npmMinimalAgeGate` key | `"<duration_string>"` (e.g., `"7d"`) |

**Functional Test in Temp Dir (bun, uv, yarn):**

For global scope, a temp directory correctly tests global config (no project config present).

**bun (global scope):**
```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
echo '{"dependencies":{"<pkg>":"<version>"}}' > package.json
bun install --dry-run 2>&1
rc=$?
rm -rf "$tmpdir"
# PASS: output contains "blocked by minimum-release-age"
# FAIL: resolution succeeds without error
```

**uv (global scope):**
```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
uv pip install --dry-run "<pkg>==<version>" 2>&1
rc=$?
rm -rf "$tmpdir"
# PASS: output indicates version excluded by exclude-newer
# FAIL: resolution succeeds without error
```

### Test Package Selection (applies to ALL functional tests)

Query the registry for a well-known, high-trust package with a version in the
**safe test window**: published `>= 1 day ago` (minimum) AND `< configured duration`
(so it SHOULD be blocked). Prefer versions `>= 3 days old` (sweet spot).

Candidate packages (tried in order, first match wins):

| Ecosystem | Candidates |
|-----------|------------|
| JS/TS (bun, yarn) | `typescript`, `eslint`, `express`, `npm` |
| Python (uv) | `ruff`, `black`, `requests`, `flask` |

Selection rules:
- Query: `npm view <pkg> time --json` (JS/TS) or PyPI JSON API (Python)
- Find the most recent version where `1 day <= age < configured duration`
- Prefer `age >= 3 days` (versions < 3 days old may be compromised)
- Reject versions `< 1 day old` (too fresh, security risk)
- If NO candidate has a version in the window: skip functional test with message
  "No suitable test package found in safe window. Direct file verification only."

### User Confirmation Gate

BEFORE running any functional test, present to user via AskUserQuestion:

- header: `Post-check`
- question: "Verify <manager> age gate with functional test?"
- options:
  - label: "Approve"
  - description: "<package>@<version> -- published <date> (<N days ago>). Well-known package. Test runs in <project dir | temp dir> with --dry-run. Expected: BLOCKED by <duration> age gate."
  - label: "Skip"
  - description: "Skip functional test, trust config file verification only"

### Report

Display inline after the post-apply status table:

```
================================================================
POST-CHECK VERIFICATION
================================================================

| Manager | Method          | Scope   | Result | Detail                       |
|---------|-----------------|---------|--------|------------------------------|
| pnpm    | File read       | project | PASS   | minimumReleaseAge: 10080     |
| bun     | File + func test| project | PASS   | <pkg>@<ver> BLOCKED (<Nd>)   |
| npm     | CLI before      | global  | PASS   | before = <ts> (now - 7d)     |
| uv      | Func test       | global  | PASS   | <pkg>@<ver> BLOCKED (<Nd>)   |

================================================================
```

If any manager FAILS verification: WARN with details and suggest manual check.

### Security Compliance

- `--dry-run` only: zero writes, zero actual installations
- Project-scope tests run in `.harden-test/` subdir (created + destroyed immediately)
- Global-scope tests run in system temp dir (created + destroyed immediately)
- Only well-known packages used (typescript, eslint, ruff, black — millions of downloads)
- Test version >= 1 day old (3 days preferred) — rejects same-day versions that could be compromised
- User approves exact package + version + publish date BEFORE test execution
- No auth tokens, credentials, or sensitive data involved
- Functional test confirms runtime enforcement, not just config file presence

## Section 8b: Post-Apply Offers (Project Scope)

After verification, when `scope=project`, offer to commit changes.

NOTE: Hardening is offered at Gate 1 (not here) so the user can decide BEFORE
config writes happen, not after. If user selected "Yes, and harden" at Gate 1,
Gates 2-4 run before reaching this section. Defer the commit offer until all
writes (config + hardening) are complete.

### Commit Config Changes

For project scope, config writes modify tracked files (e.g., `bunfig.toml`,
`pnpm-workspace.yaml`, `.npmrc`, `pyproject.toml`, `.yarnrc.yml`). Prompt:

- header: `Commit`
- question: "Commit the supply chain config changes?"
- options:
  - label: "Yes"
  - description: "Stage and commit modified config files with conventional commit message"
  - label: "No"
  - description: "Leave changes uncommitted for manual review"

If "Yes": stage ONLY the config files that were modified by this skill (not unrelated
changes), then commit with message:
`chore(security): configure minimum release age (<duration>)`

If hardening was also applied, include those files and use:
`chore(security): configure minimum release age (<duration>) and dependency policy`

If "No": display "Config changes left uncommitted. Review with `git diff` before committing."

NOTE: If hardening (Gates 2-4) will run after this, defer the commit offer until
AFTER all hardening gates complete, so all changes can be committed together.

## Section 9: Exclusion Handling

When `--exclude pkg1,pkg2` is provided, apply per-manager exclusions following the procedures in Section 4.

### Cross-Manager Semantics Summary

Display this table in the dry-run (Section 8) when `--exclude` is provided:

| Manager | Exclusion mechanism | Identical to pnpm? | Warning |
|---------|-------------------|---------------------|---------|
| pnpm | `minimumReleaseAgeExclude` array | (reference) | None |
| Bun | `install.minimumReleaseAgeExcludes` array | Yes | None |
| Yarn v4 | `npmPreapprovedPackages` array | No (broader) | Bypasses ALL package gates |
| npm | None | N/A | No exclusion mechanism |
| uv | `exclude-newer-package` table | No (different model) | Per-package cutoff, not bypass |

### Handling Per Manager

1. **pnpm**: Write `minimumReleaseAgeExclude` array. Merge with existing entries.
2. **Bun**: Write `install.minimumReleaseAgeExcludes` array. Merge with existing.
3. **Yarn v4**: Write `npmPreapprovedPackages` array. WARN about broader semantics. Merge with existing.
4. **npm**: Do NOT write anything. WARN: "npm does not yet support min-release-age exclusions."
5. **uv**: Write `[tool.uv.exclude-newer-package]` entries. WARN about different model. Each excluded package gets a far-future timestamp (`"2099-12-31T23:59:59Z"`) to effectively bypass the age gate.

### Merge Logic

When adding to an existing exclusion list:
1. Read current entries.
2. Add new entries that are not already present.
3. Do NOT remove existing entries.
4. Show the merged result in the diff.

## Section 10: Guided Mode

When `--guided` is present (or no arguments were provided), run interactive prompts
BEFORE any detection or writing. Use AskUserQuestion for all prompts.

If arguments were provided alongside `--guided`, they serve as pre-filled defaults
shown as "(Recommended)" labels, NOT as automatic values that skip interaction.

### Prompt 1: Scope and Manager Selection

Send a SINGLE AskUserQuestion with TWO questions:

**Question 1:**
- header: `Scope`
- question: "What scope should supply chain hardening apply to?"
- multiSelect: false
- options:
  - label: "Project only" + "(Recommended)" if default
  - description: "Write to project-level config files in the current repo"
  - label: "Global only"
  - description: "Write to user-level config files (~/.npmrc, ~/.bunfig.toml, etc.)"
  - label: "Both"
  - description: "Apply to project first, then global configs"

**Question 2:**
- header: `Managers`
- question: "Which package managers should be configured?"
- multiSelect: false
- options:
  - label: "Auto-detect" + "(Recommended)" if default
  - description: "Scan project for lockfiles and config files to identify active managers"
  - label: "All supported"
  - description: "Configure all 5 supported managers (pnpm, yarn, bun, npm, uv)"
  - label: "Select specific"
  - description: "Choose individual managers to configure"

### Prompt 2: Duration and Hardening

Send a SINGLE AskUserQuestion with TWO questions:

**Question 1:**
- header: `Duration`
- question: "What minimum release age should packages require?"
- multiSelect: false
- options:
  - label: "7 days" + "(Recommended)" if default
  - description: "Industry standard -- blocks packages published less than 7 days ago"
  - label: "3 days"
  - description: "Faster access to new releases, still catches most supply chain attacks"
  - label: "24 hours"
  - description: "Minimal protection -- only blocks same-day malicious publishes"

**Question 2:**
- header: `Hardening`
- question: "Enable post-config security hardening?"
- multiSelect: false
- options:
  - label: "Yes" + "(Recommended)" if default
  - description: "Update CLAUDE.md/AGENTS.md with dependency policy + run security review"
  - label: "No"
  - description: "Only configure package manager age gates, skip policy hardening"

### Prompt 3: Specific Manager Selection (conditional)

ONLY if user selected "Select specific" in Prompt 1 Question 2:

- header: `Managers`
- question: "Which package managers should be configured?"
- multiSelect: true
- options:
  - label: "bun"
  - description: "Recommended for JS/TS -- requires >=1.3.0"
  - label: "uv"
  - description: "Recommended for Python -- requires >=0.4.0"
  - label: "pnpm"
  - description: "Requires >=10.16.0 (project: pnpm-workspace.yaml, global: pnpm rc file)"
  - label: "npm"
  - description: "Requires >=11.10.0 (days granularity, no exclusions yet)"

Yarn is available via the "Other" free-text option (requires >=4.10.0).

### Exclusions

Exclusions are omitted from the guided flow (advanced feature). Users can add
`--exclude pkg1,pkg2` in a follow-up invocation. If a user provides exclusions
via "Other" at any prompt, respect them.

### After Prompts

Use the user's answers (or defaults if they accepted recommendations) as the
effective arguments. Continue to Section 5 (root resolution) with these values.

### `scope=both` Execution

When user selects "Both" scope:
1. Set effective scope to `project`. Run the full flow (Sections 5-8a) for project scope.
2. After project-scope post-apply verification completes, set effective scope to `global`.
3. Run Sections 4-8a again for global scope (skip detection -- reuse managers from step 1).
4. Display a combined post-apply summary covering both scopes.
5. Hardening (Gates 2-4) runs ONCE after both scopes complete (not per-scope).
6. Commit offer (Section 8b) covers all project-scope files modified in step 1.

## Section 11: Hardening A -- Dependency Management Policy (Gate 2)

Only runs when `--harden` is set (or selected at Gate 1) AND Gate 1 was confirmed.
Works for ANY scope — the "Yes, and harden" option is available at Gate 1 for both
project and global scopes. The policy documents all detected managers regardless of
whether config was written at project or global level.

### Pre-Flight

1. Check for existing `CLAUDE.md` or `AGENTS.md` at project root.
   - If `CLAUDE.md` exists: use it as target.
   - If `AGENTS.md` exists (no `CLAUDE.md`): use it as target.
   - If neither exists: create `CLAUDE.md` as target.
2. Read the target file.
3. Check if a `## Dependency Security Policy` section already exists.
   - If yes: update it (replace content between this heading and next `##` heading).
   - If no: append the section at the end of the file.

### Gate 2 Confirmation

Use AskUserQuestion:
```
GATE 2: Dependency Management Policy

This will add/update a "## Dependency Security Policy" section in <target_file>
with version pinning policy and minimum release age requirements.

Proceed? [yes/no]
```

If "no": skip Hardening A, continue to Gate 3 prompt.

### Policy Template

Write the following section. Include ALL detected managers — not just configured ones.
The policy must cover the full supply chain picture: what is enforced, what needs
upgrade, and what requires alternative tooling.

```markdown
## Dependency Security Policy

### Version Pinning

- **Applications**: Pin the EXACT version of every dependency. Do not use floating
  ranges (`^`, `~`, `>=`). Lockfiles must contain exact resolved versions. Any
  version bump must be an explicit, reviewed commit.
- **Libraries**: Semver ranges acceptable in published metadata. Pin exact versions
  in lockfile for CI reproducibility. Never auto-update without review.
- **Package managers themselves**: Pin the exact version of the package manager
  used by the project (e.g., in `packageManager` field, Dockerfile, CI config).
  Manager updates are dependency updates and must follow the same review process.

### Minimum Release Age

All dependencies must satisfy a minimum release age before installation.
This protects against supply chain attacks by ensuring packages have been
publicly available for a quarantine period before use.

#### Configured Managers (enforced)

<for each manager with status=OK that was configured, one row>
| Manager | Duration | Config key | Config file | Status |
|---------|----------|-----------|-------------|--------|

#### Managers Requiring Upgrade (not yet enforced)

<for each manager with status=TOO_OLD or NOT_INSTALLED, one row>
| Manager | Installed | Required | Action |
|---------|-----------|----------|--------|

Include the exact upgrade command for each (age-verified version from Section 3).
After upgrading, re-run `/harden-supply-chain-sec` to configure.

#### Managers Without Native Support (alternative controls required)

<for each warning-only manager detected (Cargo, pip, Go), include guidance>

**Cargo** (if detected):
- No stable minimum release age config. Use `cargo-deny` for supply chain auditing.
- CI: `cargo build --locked`

**pip** (if detected):
- No native age-gating mechanism. Migrate to `uv` which provides `exclude-newer`.
- If migration is not feasible: use `pip install --require-hashes` with pinned versions.

**Go** (if detected):
- No native age-gating mechanism. Use a Go module proxy (e.g., Athens) with age policies.
- Configure `GOPROXY` and `GONOSUMCHECK` to route through a controlled proxy.

### Verification Commands

Before adding new dependencies, verify they meet the minimum release age:

<for each configured manager, show the relevant verification command>
- pnpm: `pnpm install` (age gate enforced automatically)
- yarn: `yarn install` (age gate enforced automatically)
- bun: `bun install` (age gate enforced automatically)
- npm: `npm install` (age gate enforced automatically)
- uv: `uv sync` (exclude-newer enforced automatically)

### CI/CD

All CI pipelines MUST use frozen-lockfile install commands to ensure reproducibility:
<for each configured manager with frozen-lockfile detection, list the command>
```

### Post-Write

After writing, display: "Dependency management policy written to <target_file>."

## Section 11b: Hardening A2 -- Exact Version Pinning Enforcement (Gate 2b)

Runs immediately after Gate 2 (policy write). This step goes beyond documenting
a pinning policy — it CONFIGURES each package manager to reject floating ranges
and guides the user through lockfile re-generation.

### Gate 2b Confirmation

Use AskUserQuestion:

- header: `Gate 2b`
- question: "Configure package managers to enforce exact version pinning? This writes save-exact/install.exact settings and audits existing dependencies for floating ranges."
- options:
  - label: "Yes, enforce pinning"
  - description: "Write exact-pinning config + audit dependencies + guide lockfile re-generation"
  - label: "Skip"
  - description: "Keep pinning as documented policy only (not technically enforced)"

If "Skip": continue to Gate 3.

### Exact Pinning Config Map

For each detected manager (status=OK), write the exact-pinning setting:

| Manager | Config key | Value | File (project) | File (global) | Effect |
|---------|-----------|-------|----------------|---------------|--------|
| bun | `install.exact` | `true` | `bunfig.toml` | `~/.bunfig.toml` | `bun add` saves exact versions instead of `^` ranges |
| npm | `save-exact` | `true` | `.npmrc` | `~/.npmrc` | `npm install <pkg>` saves exact versions |
| pnpm | `save-exact` | `true` | `.npmrc` | pnpm global rc | `pnpm add` saves exact versions |
| yarn | `defaultSemverRangePrefix` | `""` (empty string) | `.yarnrc.yml` | N/A (project only) | `yarn add` saves exact versions instead of `^` ranges |
| uv | N/A | N/A | N/A | N/A | uv uses exact pins in `uv.lock` by default; `pyproject.toml` ranges are acceptable for libraries |

Write these settings using the same General Safety Pattern from Section 4 (read,
diff, dry-run preview, write on confirmation, post-write verify). Apply the Hook
Denial Recovery pattern if writes are blocked.

### Floating Range Audit

After writing pinning config, scan dependency declaration files for existing floating
ranges that should be pinned:

**JS/TS (package.json):**
```bash
# Find dependencies with ^, ~, >=, *, or x ranges
grep -E '"[^^~>=*x]*["]: *"[\^~>=*]' package.json
```
Look in `dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies`.

**Python (pyproject.toml / requirements.txt):**
```bash
# Find dependencies with >=, ~=, !=, or * ranges
grep -E '(>=|~=|!=|\*)' pyproject.toml requirements.txt 2>/dev/null
```

**Cargo (Cargo.toml):**
```bash
# Cargo uses semver by default; find non-exact versions (no = prefix)
grep -E '^\w+ *= *"[^=]' Cargo.toml
```

### Version Resolution Strategy

For each floating range found, determine the correct exact version:

**Step 1: Read lockfile version.**
Resolve the currently locked version for the dependency from the lockfile:
- bun: `bun list` or parse `bun.lock` (or legacy `bun.lockb`)
- npm: parse `package-lock.json` -> `packages["node_modules/<dep>"].version`
- pnpm: parse `pnpm-lock.yaml` -> resolved version for the package
- yarn: parse `yarn.lock` -> resolved version
- uv: parse `uv.lock` -> resolved version
- cargo: parse `Cargo.lock` -> resolved version

**Step 2: Check lockfile version against minimum release age.**
Query the registry for the publish date of the locked version:
- JS/TS: `npm view <pkg>@<locked_version> time --json`
- Python: PyPI JSON API `https://pypi.org/pypi/<pkg>/<locked_version>/json`
- Cargo: `cargo info <pkg>` or crates.io API

**Step 3: Decide.**

| Locked version age | Action | Suggested version |
|--------------------|--------|-------------------|
| `>= configured duration` | Pin to locked version | `<locked_version>` (safe) |
| `< configured duration` | Find older safe version | Query registry for the latest version published `>= configured duration` ago |
| Version not found in registry | WARN, keep as-is | Flag for manual review |

If the locked version does NOT meet the age gate:
- Query the registry for all versions of that package
- Find the most recent version published `>= configured duration` ago
- Suggest that version instead, with a note:
  ```
  "<dep>": "^1.5.0" -> locked 1.5.2 (published 3d ago, FAILS 7d age gate)
                     -> suggest 1.5.1 (published 14d ago, meets 7d age gate)
                     -> lockfile re-generation REQUIRED after pinning
  ```

Display findings:

```
================================================================
FLOATING RANGE AUDIT
================================================================

Found <N> dependencies with floating version ranges:

package.json:
  "typescript": "^5.7.3" -> pin to 5.7.3 (locked, published 45d ago, SAFE)
  "react": "^19.0.0"     -> pin to 19.0.0 (locked, published 120d ago, SAFE)
  "some-pkg": "^2.1.0"   -> locked 2.1.5 (published 2d ago, FAILS 7d age gate)
                          -> suggest 2.1.4 (published 15d ago, SAFE)
                          -> lockfile re-generation REQUIRED

<file>:
  <dep>: <range> -> <resolution>

Summary:
  <N> can be pinned to locked version (safe)
  <M> need an older version (lockfile re-generation required)
  <K> need manual review

================================================================
```

### Lockfile Re-Generation Guidance

After the audit, guide the user through fixing floating ranges and re-generating
lockfiles. Use AskUserQuestion:

- header: `Lockfile`
- question: "Found <N> floating ranges (<M> safe to pin from lockfile, <K> need older version). How would you like to proceed?"
- options:
  - label: "Auto-fix declarations"
  - description: "Pin safe versions from lockfile + downgrade unsafe ones + offer the lockfile re-generation command for explicit confirmation"
  - label: "Show commands only"
  - description: "Display the manual steps without making changes"
  - label: "Skip"
  - description: "Leave dependency versions as-is for now"

**If "Auto-fix declarations":**

1. **Pin safe dependencies** (locked version meets age gate):
   - Replace range with exact locked version in declaration file.
   - These do NOT require lockfile re-generation (version is unchanged).

2. **Downgrade unsafe dependencies** (locked version fails age gate):
   - Replace range with the suggested safe version (from Version Resolution Strategy).
   - These REQUIRE lockfile re-generation because the resolved version will change.
   - Show each downgrade clearly:
     ```
     "<dep>": "^2.1.0" -> "2.1.4" (downgraded from locked 2.1.5 which fails 7d age gate)
     ```

3. Show full diff of all declaration file changes using Edit tool. Wait for approval.

4. **Determine the lockfile re-generation command** (only if any dependencies were downgraded):
   - bun: `bun install`
   - npm: `npm install`
   - pnpm: `pnpm install`
   - yarn: `yarn install`
   - uv: `uv lock`
   - If no downgrades were needed (all safe pins): state that no lockfile re-generation is required.

5. For each affected manager, use AskUserQuestion:
   - header: `Lockfile`
   - question: "Run the lockfile re-generation command for <manager> now?"
   - options:
     - label: "Run now"
     - description: "Execute: <exact_command>"
     - label: "Show command only"
     - description: "Display the exact command without executing it"
     - label: "Skip"
     - description: "Leave the lockfile unchanged for now"

6. If "Run now": execute the exact command.
7. If "Show command only": display the exact command and continue.
8. If "Skip": continue without executing anything.

9. Display: "Review the declaration and lockfile diff with `git diff` before committing."

**If "Show commands only":**

Display the per-manager commands:
```
To pin exact versions and re-generate lockfiles:

bun:
  1. Edit package.json: replace ^ and ~ prefixes with exact versions
  2. Run: bun install
  3. Review: git diff bun.lock

npm:
  1. Edit package.json: replace ^ and ~ prefixes with exact versions
  2. Run: npm install
  3. Review: git diff package-lock.json

pnpm:
  1. Edit package.json: replace ^ and ~ prefixes with exact versions
  2. Run: pnpm install
  3. Review: git diff pnpm-lock.yaml

yarn:
  1. Edit package.json: replace ^ and ~ prefixes with exact versions
  2. Run: yarn install
  3. Review: git diff yarn.lock

uv:
  1. Pin versions in pyproject.toml (replace >= with ==)
  2. Run: uv lock
  3. Review: git diff uv.lock
```

## Section 12: Hardening B -- Dependency Security Review Agent (Gate 3)

Only runs when `--harden` is set (or selected at Gate 1).

### Gate 3 Confirmation

Use AskUserQuestion:
```
GATE 3: Dependency Security Review

This will spawn a security review agent that:
1. Runs audit commands for each detected package manager
2. Checks if resolved dependencies satisfy minimum release age
3. Writes findings to SECURITY-REVIEW.md at project root

This may take a few minutes depending on dependency count.

Proceed? [yes/no]
```

If "no": skip Hardening B, continue to Gate 4 prompt.

### Agent Spawn

Use the Agent tool to spawn a subagent with the following prompt:

```
You are a dependency security review agent. Your task is to audit the project's
dependencies and write a comprehensive security review.

## Instructions

1. For each package manager detected at <project_root>, run the appropriate audit command:
   - npm: `npm audit --json`
   - pnpm: `pnpm audit --json`
   - yarn: `yarn npm audit --json`
   - bun: `bun pm scan` (if available, else note as gap)
   - uv: `pip-audit` (if installed; if missing, note the gap and offer `uv pip install pip-audit` only after explicit confirmation)

2. Parse the audit output. For each vulnerability found, record:
   - Package name
   - Installed version
   - Vulnerability severity (critical, high, medium, low)
   - Advisory URL (if available)
   - Fix available (yes/no, and which version)

3. Check if resolved dependency versions satisfy the minimum release age policy.
   This is informational -- note any packages that were published very recently.

4. Write findings to <project_root>/SECURITY-REVIEW.md with this structure:

   # Dependency Security Review

   Generated: <current date/time>

   ## Summary
   - Total packages audited: <count>
   - Vulnerabilities found: <count by severity>
   - Audit tools used: <list>
   - Audit gaps: <list of tools not available>

   ## Findings
   <table of vulnerabilities>

   ## Recommendations
   <actionable items>

5. If an audit tool is not installed (e.g., pip-audit):
   - Record as a gap in the summary
   - Do NOT silently skip
   - Display the exact install command
   - Use AskUserQuestion:
     - header: `Audit tool`
     - question: "`<tool_name>` is not installed. Run the install command now?"
     - options:
       - label: "Run now"
       - description: "Execute: <exact_command>"
       - label: "Show command only"
       - description: "Display the exact command without executing it"
       - label: "Skip"
       - description: "Continue and record a tooling gap"
   - If "Run now": execute the exact command, then continue the audit if installation succeeds
   - If "Show command only": display the exact command, record a tooling gap, and continue
   - If "Skip": record a tooling gap and continue

6. If no vulnerabilities found: still write the file with a clean summary.
```

### Post-Agent

After agent completes, display: "Security review written to <project_root>/SECURITY-REVIEW.md"
If agent fails: WARN with error details but continue to Gate 4.

## Section 13: Hardening C -- Security Review Protocol (Gate 4)

Only runs when `--harden` is set (or selected at Gate 1).

### Gate 4 Confirmation

Use AskUserQuestion:
```
GATE 4: Permanent Security Review Protocol

This will append a security review protocol to the "## Dependency Security Policy"
section in <target_file>. This protocol instructs AI agents to perform security
checks before and after dependency changes.

Proceed? [yes/no]
```

If "no": skip Hardening C, proceed to post-apply summary.

### Protocol Template

Append the following to the `## Dependency Security Policy` section in the target file
(same file used in Hardening A):

```markdown

### Dependency Change Protocol

When adding, updating, or removing dependencies, follow this protocol:

#### Pre-Install Checks

1. Verify the package has been published for at least the configured minimum release age.
2. Check for known CVEs against the package version.
3. Review the package's recent publish history for suspicious activity.
4. For new dependencies: verify the package name is correct (typosquatting check).

#### Post-Install Audit

1. Run the full dependency audit for all configured managers:
<for each configured manager, list the audit command>
   - npm: `npm audit`
   - pnpm: `pnpm audit`
   - yarn: `yarn npm audit`
   - bun: `bun pm scan`
   - uv: `pip-audit` (if not available, present `uv pip install pip-audit` and wait for explicit confirmation before running it)
2. Review and update SECURITY-REVIEW.md with new findings.
3. Address critical and high severity vulnerabilities before merging.

#### Lockfile Integrity

- Always commit lockfile changes alongside dependency updates.
- Verify lockfile integrity in CI with frozen-install commands.
- Do not manually edit lockfiles.

#### Exception Handling

If a dependency must bypass the minimum release age (e.g., critical security patch):
1. Document the reason in the PR description.
2. Add the package to the exclusion list temporarily.
3. Set a reminder to remove the exclusion after the quarantine period passes.
4. Require explicit approval from a maintainer.
```

### Post-Write

Display: "Security review protocol appended to <target_file>."

## Section 14: Warning-Only Managers

These managers are detected but cannot be configured with minimum release age.
Display warnings in the dry-run (Section 8) and post-apply summary.

### Cargo

**Detection**: `Cargo.lock` or `Cargo.toml` exists at project root.
**Warning**:
```
Cargo: minimum release age (`--publish-time`) requires nightly toolchain
and has no stable persistent config support.

Nightly command (manual, not written to config):
  cargo +nightly install --publish-time 7d <crate>

For stable supply-chain controls, consider:
  cargo install cargo-deny
  cargo deny check advisories

CI frozen lockfile: cargo build --locked
```

### pip

**Detection**: `requirements.txt`, `setup.py`, or `setup.cfg` exists (without `uv.lock` or `[tool.uv]` in pyproject.toml).
**Warning**:
```
pip: No native minimum release age mechanism.

pip supports --uploaded-prior-to <ISO_TIMESTAMP> as a CLI flag, but this
cannot be persisted in configuration files.

Recommended: Migrate to uv, which provides persistent exclude-newer config.
  Migration guide: https://docs.astral.sh/uv/guides/integration/
```

### Go

**Detection**: `go.mod` or `go.sum` exists at project root.
**Warning**:
```
Go modules: No native minimum release age mechanism.

Recommended: Use a Go module proxy (e.g., Athens, GOPROXY) with age policies.
Configure GOPROXY and GONOSUMCHECK environment variables to route through
a proxy that enforces release age requirements.
```

## Section 15: Preferred Manager Prioritization

After ALL hardening completes (or after Gate 1 if `--harden` not set), check if non-preferred managers were configured.

### Preferred Managers

| Ecosystem | Preferred | Non-preferred |
|-----------|----------|---------------|
| JS/TS | bun | npm, yarn, pnpm |
| Python | uv | pip, poetry, pipenv |

### Logic

1. Review which managers were configured in this run.
2. If ANY non-preferred manager was configured:
   - Still apply all hardening normally (migration suggestions do NOT block hardening).
   - After all operations complete, display the migration suggestion block.

### Migration Suggestion Block

Display ONLY if non-preferred managers were configured:

```
================================================================
SUGGESTION: Preferred Package Manager Migration
================================================================

The following non-preferred managers were hardened in this run:
<list non-preferred managers that were configured>

For improved security, performance, and supply chain controls, consider
migrating to the preferred manager for each ecosystem:

<if JS/TS non-preferred detected>
JS/TS: bun
  - Built-in minimum release age support since v1.3.0
  - Fastest install times, native lockfile, TypeScript-first
  - Migration: https://bun.sh/docs/install/migrate

<if Python non-preferred detected>
Python: uv
  - Built-in exclude-newer with duration strings (v0.9.17+)
  - 10-100x faster than pip, drop-in replacement
  - Migration: https://docs.astral.sh/uv/guides/integration/

================================================================
```

### Migration Install Age Gate

When migration suggestions recommend installing a preferred manager (bun, uv),
the recommended version MUST respect the same minimum release age being configured.

Before displaying install commands or version recommendations:
1. Check the preferred manager's latest version publish date (same method as Section 3).
2. If the latest version is below the configured age threshold: recommend the most
   recent version that meets it, with a note explaining why.
3. Include the age-verified version in the migration suggestion output:
   ```
   Recommended version: <version> (published <N days> ago, meets <duration> age gate)
   ```

This prevents the hardening tool from recommending freshly-published manager binaries.

### Important

- Migration suggestions are INFORMATIONAL ONLY.
- They do NOT block or alter any hardening that was already applied.
- They appear AFTER all hardening is complete.
- If only preferred managers were configured: do NOT display this block.

## Section 16: Edge Cases and Error Handling

### No Managers Detected

If `manager=auto` and no supported or warning-only managers are detected:
- ERROR: Display message listing all files and paths that were scanned.
- Use AskUserQuestion to ask: "No package managers detected. Please specify a manager explicitly (pnpm, yarn, bun, npm, uv)."
- If user provides a valid manager: continue with that manager.
- If user declines: abort.

### Mixed Scope Support

If `scope=global` and a manager does not support global config:
- All supported managers (pnpm, bun, npm, uv, yarn) have global config paths.
- Yarn v4 global: `~/.yarnrc.yml` is supported (verified with Yarn 4.13.0). Display
  a note about Yarn treating `~` as a project root (see Section 4, Yarn v4 global scope).

### All Managers Skipped

If all detected managers have status `TOO_OLD` or `NOT_INSTALLED` (none are `OK`):
- Do NOT display Gate 1 (there are zero effective config changes to apply).
- Instead, display a dedicated message:
  ```
  ================================================================
  NO CONFIGURABLE MANAGERS
  ================================================================

  All detected managers require upgrades before minimum release age
  can be configured:

  | Manager | Installed | Required | Status |
  |---------|-----------|----------|--------|
  | <mgr>   | <version> | <min>    | TOO_OLD / NOT_INSTALLED |

  Upgrade commands (age-verified):
  <for each manager, show age-verified install/update command per Section 3>
  ================================================================
  ```
- After displaying: use AskUserQuestion to offer:
  - label: "Show update commands"
  - description: "Display age-verified install/update commands for each manager"
  - label: "Harden CLAUDE.md/AGENTS.md anyway"
  - description: "Write dependency policy documenting current state (all managers need upgrade)"
  - label: "Done"
  - description: "Exit -- upgrade managers first, then re-run"

### File Encoding Preservation

When editing existing files:
- Use the Edit tool which preserves surrounding content.
- Do NOT rewrite entire files -- only modify the specific key/value.
- Preserve comments, blank lines, and indentation.

### Existing Value Identical

If the current config value matches the proposed value:
- Show "(unchanged)" in the dry-run configuration changes table.
- Skip the write for that manager.
- Do NOT count as an error.

### pyproject.toml Without [tool.uv]

If `pyproject.toml` exists but has no `[tool.uv]` section:
- Only add `[tool.uv]` section if `uv.lock` exists at project root OR user explicitly selected uv.
- If neither condition met: SKIP uv with warning "pyproject.toml found but no [tool.uv] section and no uv.lock. Skipping uv."

### Library vs Application (Hardening A only)

When writing the version pinning policy in Hardening A:
- If unclear whether the project is a library or application: use AskUserQuestion:
  "Is this project an application (exact pins) or a library (semver ranges)? This affects the version pinning policy."
- Application: recommend exact version pins.
- Library: recommend semver ranges with lockfile pinning for CI.

### Lockfile Re-Resolution

After config writes, NEVER automatically run install/sync commands.
Always warn the user to re-resolve lockfiles manually and review changes before committing.

### Concurrent Lockfiles (Monorepo)

If multiple lockfiles for the same ecosystem exist (e.g., `package-lock.json` AND `pnpm-lock.yaml`):
- Auto-detection (Section 7) now includes all detected managers with a WARN for npm
  when other JS lockfiles coexist, rather than silently skipping npm.
- Configure all detected managers. Display all in the dry-run.
- Let the user decide via Gate 1 confirmation which to apply.

## Section 17: Verified Behavior

Empirical tests confirming global minimum release age enforcement.
Tested on macOS (darwin arm64), 2026-04-01.

### Environment

| Manager | Version | Global config file | Config key | Value |
|---------|---------|-------------------|------------|-------|
| uv | 0.9.21 | `~/.config/uv/uv.toml` | `exclude-newer` | `"7 days"` |
| Bun | 1.3.3 | `~/.bunfig.toml` | `install.minimumReleaseAge` | `604800` |
| npm | 11.12.0 | `~/.nvm/.../etc/npmrc` | `min-release-age` | `7` |
| pnpm | 10.19.0 | `~/Library/Preferences/pnpm/rc` | `minimum-release-age` | `10080` |

### uv: Test A -- uvx without vs with global config

Tested whether `uvx` respects `~/.config/uv/uv.toml`.

**Procedure:**
1. Moved `uv.toml` aside, ran `uvx ruff@latest --version` -- resolved **ruff 0.15.8** (published 2026-03-26, ~6d old).
2. Restored `uv.toml` (`exclude-newer = "7 days"`), ran same command -- resolved **ruff 0.15.7**.

**Result:** Different versions confirm `uvx` reads and enforces global `exclude-newer`.

### uv: Test C -- PEP 723 inline override

Tested whether inline `[tool.uv]` in a single-file script overrides global config.

**Script:**
```python
# /// script
# dependencies = ["ruff"]
# [tool.uv]
# exclude-newer = "2025-01-01"
# ///
import subprocess
result = subprocess.run(["ruff", "--version"], capture_output=True, text=True)
print(result.stdout.strip())
```

**Result:** `uv run` resolved **ruff 0.8.4** (last version before 2025-01-01). Inline `exclude-newer` overrides global.

### uv: Test D -- PEP 723 without inline (global fallback)

Same script but without `[tool.uv]` section.

**Result:** `uv run` resolved **ruff 0.15.7** -- identical to `uvx` with global config (Test A). Confirms global `exclude-newer` applies to `uv run` scripts when no inline override is present.

### Bun: functional test -- global age gate enforcement

Bun has no `bun config get` CLI equivalent. Verified via functional test.

**Procedure:**
1. Created temp directory with `package.json` pinning `npm@11.12.1` (published 2026-03-26, 5d old).
2. Ran `bun install --dry-run`.

**Result:**
```
error: No version matching "npm" found for specifier "11.12.1"
(blocked by minimum-release-age: 604800 seconds)
```

Error message explicitly names `minimum-release-age: 604800 seconds`, matching `~/.bunfig.toml` value. Confirms global config is read and enforced for install operations.

### npm: config verification

**Procedure:**
1. `npm config set min-release-age 7 --global`
2. `npm config get min-release-age` returns `null` (display quirk in 11.12.0).
3. `npm config ls -l` shows `min-release-age = null ; overridden by global`.
4. `npm config get before --global` returns dynamic timestamp = `now - 7 days`.
5. Two consecutive calls 2 seconds apart showed timestamps shifted by exactly 2 seconds.

**Result:** `before` is dynamically computed as `now() - min-release-age` at runtime. The wall-clock shift proves the rolling age gate is active. The `null` display is a CLI rendering quirk, not a missing value.

### pnpm: config verification

**Procedure:**
1. Created `~/Library/Preferences/pnpm/rc` with `minimum-release-age=10080`.
2. `pnpm config get minimum-release-age` returned `10080`.

**Result:** Direct CLI confirmation. Global rc file is read correctly.

### Summary

| Manager | Test method | Probe package | Expected | Actual | Pass |
|---------|-------------|---------------|----------|--------|------|
| uv (uvx) | Version comparison with/without config | ruff 0.15.8 (6d) | Blocked | 0.15.7 resolved | Yes |
| uv (PEP 723 inline) | Inline override | ruff (pre-2025) | Old version | 0.8.4 resolved | Yes |
| uv (PEP 723 fallback) | No inline, global applies | ruff 0.15.8 (6d) | Blocked | 0.15.7 resolved | Yes |
| Bun | Dry-run install of recent package | npm@11.12.1 (5d) | Blocked | Error with age gate message | Yes |
| npm | Dynamic `before` timestamp | N/A | now - 7d | Confirmed via wall-clock shift | Yes |
| pnpm | CLI config query | N/A | 10080 | 10080 | Yes |
