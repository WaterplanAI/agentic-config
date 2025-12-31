# TEST
STAGE: TEST
GOAL: Verify implementation passes all project tests.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. READ `# AI Section > ## Implement` for affected files.
2. REFLECT your understanding and what you will do (CONCISELY).
3. RUN ALL project tests sequentially:
   - TypeScript: `bunx tsc --noEmit`
   - Lint: `bun run lint`
   - Unit tests: `bun test` (if exists)
   - Any project-specific tests in package.json
4. IF ANY test fails:
   - FIX code logic (NEVER modify tests)
   - RUN ALL tests again (not just failed ones)
   - REPEAT fix-and-rerun-all loop until ALL tests pass
5. ONLY commit when ALL tests pass.
6. APPEND results to `# AI Section > ## Test Evidence & Outputs`:
   - Commands run
   - Pass/Fail status
   - Fixes applied (if any)
   - Number of fix-rerun cycles (if > 0)
7. SUMMARIZE result (max: 100 words).
8. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "TEST" "<NNN>" "<title>"
   ```

## Behavior

- FIX code, not tests.
- SURFACE ERRORS FIRST.
- CONCISE. Bullet list format.
