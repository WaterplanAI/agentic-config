## Tasks
REVIEW SPEC was successfully implemented according to plan, complying with Objectives.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. MANDATORILY RE-READ FILES. They might have been modified by other entities.
2. REFLECT your understanding and what you will do (CONCISELY).
3. Compare EACH Task in `# AI Section > ## Plan` with the actual implementation.
   1. EVALUATE if TASK was implemented EXACTLY as planned.
      1. READ the SPEC TASK, READ the affected FILE, READ git history.
   2. EVALUATE test coverage:
      1. Were unit tests written for each component/function?
      2. Were e2e tests written for feature validation (if applicable)?
      3. Do tests adequately cover the implementation?
   3. DOCUMENT ANY deviations, referencing SPECIFIC files:lines.
      1. IF deviations negagtively AFFECT achieving SPEC GOAL => APPEND `- [ ] FEEDBACK` block in `# AI Section > ## Review > ### Feedback`
      2. IF deviations DO NOT AFFECT achieving SPEC GOAL => JUSTIFY why.
4. RE-EVALUATE ACTUAL status AFTER `IMPLEMENT` stage. Answer: WAS THE GOAL of SPEC achieved? WRITE a CLEAR `Yes/No` answer with 1 line justification. Propose Next steps.
5. APPEND the output in section `# AI Section > ## Review`.
6. SUMMARIZE result to user in output (max: 150 words).
7. COMMIT using spec resolver:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "REVIEW" "<NNN>" "<title>"
   ```

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- SURFACE ERRORS FIRST, in their own section.
- You can ONLY edit SPEC.
