# IMPLEMENT
STAGE: IMPLEMENT
GOAL: IMPLEMENT EXACT step by step PLAN to achieve `SPEC` Objectives aligned with Details, Research & Strategy.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.
- UPDATE progress for each TODO in spec file:
  - BEFORE start task: `In Progress`
  - AFTER finished task: `Done` or `Failed` or any other task completion status

## Workflow

1. READ `# AI Section > ## Plan`
2. REFLECT your understanding and what you will do (CONCISELY).
3. WRITE TODO list in SPEC `# AI Section > ## Implement`. Each TODO item with `Status: Pending`.
4. IMPLEMENT each TODO item SEQUENTIALLY, one at a time. For each TODO item:
   1. UPDATE SPEC file TODO item `Status: In Progress`
   2. IMPLEMENT TODO item
   3. WRITE unit tests for the implemented component/function
   4. UPDATE SPEC file TODO item `Status: Done` or `Failed` or any other task completion status
5. WRITE e2e tests after all implementation tasks complete (if applicable)
6. IF an unexpected error/failure occurs, surface it to the user. If you cannot recover from it, stop and ask user feedback. DO NOT ignore the error/failure.
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT implementation, tests, and spec (ONLY the files you changed):
   1. Commit code changes + tests to main repository:
      ```bash
      # Standard git commit for code changes
      git add <changed_files>
      git commit -m "spec(NNN): IMPLEMENT - <title>"
      ```
   2. Capture commit hash and update spec file with hash at end of `## Implement` section
   3. Commit spec file using spec resolver:
      ```bash
      # Source spec resolver (pure bash - no external commands)
      _agp=""
      [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
      AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
      unset _agp
      source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

      # Get commit hash from previous commit
      COMMIT_HASH=$(git rev-parse HEAD)

      # Commit spec changes with hash reference
      commit_spec_changes "<spec_path>" "IMPLEMENT" "<NNN>" "<title> [${COMMIT_HASH:0:7}]"
      ```

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- SURFACE ERRORS FIRST, in their own section.
