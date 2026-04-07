# FIX
STAGE: FIX
GOAL: FIX EXACT step by step PLAN to achieve `SPEC` Objectives aligned with Details, Research & Strategy.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. READ `# AI Section > ## Review` and PREPARE to IMPLEMENT `# AI Section > ## Review > ### Feedback`.
2. REFLECT your understanding and what you will do (CONCISELY).
3. APPEND EXACT TASKs list in `# AI Section > ## Plan > ### Post-Fixes` (MIRROR @agents/spec/PLAN.md guidelines).
4. APPEND TODO list in `# AI Section > ## Implement > ### Post-Fixes` (MIRROR @agents/spec/IMPLEMENT.md guidelines).
5. IMPLEMENT each TODO item, one at a time.
	1. PROGRESSIVELY UPDATE progress for each TODO appending the status (`Status: In Progress/Done/Failed`) right below the TODO item.
6. IF an unexpected error/failure occurs, surface it to the user. If you cannot recover from it, stop and ask user feedback. DO NOT ignore the error/failure.
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (plugin-aware)
   source "${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "FIX" "<NNN>" "<title>"
   ```

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- SURFACE ERRORS FIRST, in their own section.