## Tasks
VALIDATE SPEC PLAN will successfully ACHIEVE Objectives and Details, ALIGNED with Research.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. RE-READ SPEC.
2. EVALUATE if AFTER implementing `# AI Section > ## Plan`, the SPEC implementation will successfully ACHIEVE Objectives and Details, ALIGNED with Research.
3. REFLECT your understanding and what you will do (CONCISELY).
4. CAREFULLY EVALUATE `# AI Section > ## Plan` AGAINST other SPEC sections.
   1. RESEARCH affected files-lines and logic involved to ACHIEVE GOAL.
5. IF `# AI Section > ## Plan ### FEEDBACK` already exists:
   1. CAREFULLY evaluate whether the FEEDBACK is correctly captured in the SPEC.
6. APPEND the output in section `# AI Section > ## Plan ### FEEDBACK`.
   1. IF FEEDBACK already exists, DO NOT DELETE IT. Rather, APPEND NEW FEEDBACK ONLY.
   2. APPEND each feedback in a new line, with format `- [ ] FEEDBACK: <feedback>`. Use file:line references, even if referencing the same SPEC file.
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (plugin-aware)
   source "${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "VALIDATE" "<NNN>" "<title>"
   ```

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- SURFACE ERRORS FIRST, in their own section.
