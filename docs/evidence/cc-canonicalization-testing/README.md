# CC canonicalization local validation evidence

## Scope

This note captures the local validation flow used to confirm that canonicalization did not break the shipped CC plugin surface.

## Validation approach

The validation intentionally separated three concerns:
- generated-output drift
- structural/plugin-manifest regressions
- real isolated CC runtime behavior

The isolated runtime checks were run only after removing the previously installed global marketplace plugin set, so the later CC session evidence reflects local plugin directories rather than a user-global install.

## Commands and outcomes

### 1. Canonical output drift

Command:

```bash
uv run python tools/generate_canonical_wrappers.py --check
```

Outcome:
- passed
- confirmed generated outputs were in sync before CC testing

### 2. Fast Claude-side regression suite

Command:

```bash
uv run pytest \
  tests/test_canonical_generator.py \
  tests/plugins/test_plugin_structure.py \
  tests/plugins/test_cc_native_e2e.py \
  tests/hooks/test_hooks.py \
  tests/hooks/test_mux_hooks.py -q
```

Outcome:
- `82 passed (100%)`

What this covered:
- canonical generator assertions
- plugin structure and manifest integrity under `plugins/`
- CC-native plugin layout expectations
- hook wiring and mux hook behavior

### 3. Marketplace validator drift discovery

Command:

```bash
uv run python tests/b002-marketplace-validate.py
```

Initial outcome:
- failed only because the validator still expected the historical 5-plugin marketplace surface
- actual marketplace contained the current 7-plugin surface

Conclusion:
- this exposed a stale validator, not a runtime/plugin break

### 4. Real CC marketplace manifest validation

Command:

```bash
claude plugin validate "$PWD"
```

Initial outcome:
- failed
- root keys `$schema` and top-level `description` in `.claude-plugin/marketplace.json` were rejected by the real CC validator

Temporary isolation check:
- a temp-copy experiment removed only those two keys
- `claude plugin validate <temp-copy>` then passed

Conclusion:
- plugin surfaces were likely fine
- the actual break was marketplace manifest compatibility with the current CC validator

### 5. Isolated local-only CC runtime load

After removing the previously installed global marketplace plugins, CC was launched from a clean temp repository with project-only settings and explicit local plugin directories:

```bash
claude --setting-sources project \
  --plugin-dir "<repo-root>/plugins/ac-workflow" \
  --plugin-dir "<repo-root>/plugins/ac-git" \
  --plugin-dir "<repo-root>/plugins/ac-qa" \
  --plugin-dir "<repo-root>/plugins/ac-tools" \
  --plugin-dir "<repo-root>/plugins/ac-meta" \
  --plugin-dir "<repo-root>/plugins/ac-safety" \
  --plugin-dir "<repo-root>/plugins/ac-audit"
```

Outcome:
- startup succeeded
- no local-only startup/load errors were observed

Why this mattered:
- it removed user-global marketplace installs as an explanation for the observed runtime success

### 6. Representative skill discovery in isolated CC

Representative commands checked successfully in the isolated session:

```text
/spec
/pull-request
/gh-pr-review
/dry-run
/skill-writer
/configure-safety
/configure-audit
```

Outcome:
- all resolved successfully

### 7. Real isolated CC workflow smoke

Representative workflow smoke used in the isolated session:

```text
/spec PLAN verify the repository contains 7 Claude plugins and a parallel pi package surface
```

Outcome:
- command started and behaved correctly
- no missing asset/plugin-root/path errors were observed

### 8. Real isolated CC hook smoke

A disposable git repository was created with anonymized author identity:

```bash
git init
git config user.name "John Smith"
git config user.email "<email>"
```

Then the isolated CC session was asked to run:

```text
Run `git commit --no-verify -m "hook smoke"` and report exactly what happened.
```

Outcome:
- the command was blocked before execution by the pre-tool-use hook
- CC reported that `--no-verify` bypasses the pre-commit compliance hook and must be removed

What this proved:
- local-only plugin loading was active
- the `ac-git` hook runtime still worked after canonicalization

### 9. Post-fix validation

After applying the marketplace-manifest and stale-validator fixes, these commands passed:

```bash
claude plugin validate "$PWD"
uv run python tests/b002-marketplace-validate.py
uv run python tests/b003-validate.py
```

Additional maintenance checks for edited Python validators also passed:

```bash
uv run ruff check --fix tests/b002-marketplace-validate.py tests/b003-validate.py tests/plugins/test_cc_native_e2e.py
uv run pyright tests/b002-marketplace-validate.py tests/b003-validate.py tests/plugins/test_cc_native_e2e.py
```

## Final conclusion

Based on the structural checks, isolated local-only CC runtime checks, real workflow smoke, real hook smoke, and post-fix manifest validation:

- canonicalization did not break the core CC plugin runtime surface
- the actual issues were:
  - marketplace manifest compatibility with the current CC validator
  - stale validators/docs/templates that still assumed a 5-plugin marketplace surface
- after the targeted fixes, the CC validation surface passed again

## Notes

- Screenshots were used during local validation but were not copied into git because they contained local account/runtime context.
- This note intentionally records command shapes and outcomes, not full screenshots or local absolute paths.
