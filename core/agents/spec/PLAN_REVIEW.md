# PLAN_REVIEW
STAGE: PLAN_REVIEW
GOAL: Validate PLAN robustness, consistency, accuracy before IMPLEMENT.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. READ `# AI Section > ## Plan` thoroughly.
2. REFLECT your understanding (CONCISELY).
3. EVALUATE plan against criteria:
   - Robustness: handles edge cases?
   - Consistency: aligns with Research/Strategy?
   - Accuracy: correct file paths, line numbers?
   - Complexity: not over/under-engineered?
   - Unit Tests: are unit tests planned for each component?
   - E2E Tests: are e2e tests planned for feature validation?
   - Test Coverage: is test coverage adequate for the changes?
4. IF issues found:
   - UPDATE `# AI Section > ## Plan` with fixes
   - DOCUMENT changes in `# AI Section > ## Plan Review`
5. IF no issues: APPEND "Plan validated - no changes needed" to `# AI Section > ## Plan Review`
6. SUMMARIZE result (max: 100 words).
7. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "PLAN_REVIEW" "<NNN>" "<title>"
   ```

## Behavior

- Think hard. Be systematic.
- DO NOT ASSUME.
- CONCISE. Bullet list format.
- SURFACE ERRORS FIRST.
- You can ONLY edit SPEC.
