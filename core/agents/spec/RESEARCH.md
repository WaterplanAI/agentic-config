# Research
STAGE: RESEARCH
GOAL: ACHIEVE `SPEC` Objectives aligned with Details.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. REFLECT your understanding and what you will do (CONCISELY).
2. RESEARCH affected files-lines and logic involved to ACHIEVE GOAL:
   - Identify existing test patterns and utilities
   - Locate test files related to affected components
   - Review test coverage for similar features
   - Include test-related files in research scope (*.test.*, *.spec.*, test/, __tests__/)
3. APPEND the output in section `# AI Section > ## Research`.
4. SUMMARIZE result to user in output (max: 150 words).
5. STRATEGIZE HOW to ACHIEVE GOAL:
   - Include testing strategy (unit tests, e2e tests)
   - Identify test utilities/helpers to use or create
   - Specify expected test coverage
6. APPEND the output in section `# AI Section > ## Research ### Strategy`. YOU MUST NOT APPEND in any other section.
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "RESEARCH" "<NNN>" "<title>"
   ```

## Behavior

- RE-READ ~/.codex/AGENTS.md
