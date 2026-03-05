## Tasks
VALIDATE SPEC PLAN
1. COMPLIES with agents/spec/PLAN.md EXACT instructions.
2. Will successfully ACHIEVE Objectives and Details, ALIGNED with Research.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. RE-READ SPEC.
2. EVALUATE if SPEC COMPLIES with agents/spec/PLAN.md EXACT instructions.
3. EVALUATE if AFTER implementing `# AI Section > ## Plan`, the SPEC implementation will successfully ACHIEVE Objectives and Details, ALIGNED with Research.
4. REFLECT your understanding and what you will do (CONCISELY).
5. CAREFULLY EVALUATE `# AI Section > ## Plan` AGAINST
  1. ALL other SPEC sections.
   1. RESEARCH affected files-lines and logic involved to ACHIEVE GOAL.
  2. agents/spec/PLAN.md EXACT instructions
6. AMEND EVERY necessary detailed in `# AI Section > ## Plan` that does not align with `## Tasks` (L1) requirement
  - INCLUDES EXACT format requested in PLAN.md, making the diff EXACT (MAX. ACCURACY), reordering TASKS so that they make sense and are sequentially implemented, among EVERY other gap with regards to main `## Tasks` (L1)
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (plugin-aware)
   source "${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "VALIDATE_INLINE" "<NNN>" "<title>"
   ```

## Behavior

- RE-READ project `CLAUDE.md` (AGENTS.md).
