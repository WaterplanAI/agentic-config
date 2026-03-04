# AMEND
STAGE: AMEND
GOAL: CAPTURE `FEEDBACK` to AMEND `SPEC` `AI Section`

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. FIND every empty `[ ] FEEDBACK:` block using `rg -n "\\[\\s*\\] FEEDBACK:" SPEC`
2. INTEPRET the feedback all together.
3. REFLECT your understanding and what you will do (CONCISELY).
4. AMEND the corresponding blocks in `# AI Section`.
   1. BE PRECISE AND CONCISE.
   2. PROCESS each feedback block one by one.
   3. AFTER AMENDMENT, MARK each feedback as DONE:
      1. Check the box `[x]`
      2. APPEND `DONE: 1 CONCISE sentence of HOW you proceeded the feedback + line numbers on the amendments`.
5. SUMMARIZE result to user in output (max: 150 words).
6. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (plugin-aware)
   source "${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "AMEND" "<NNN>" "<title>"
   ```

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- DO NOT MODIFY ANY FILE OTHER THAN `SPEC`.