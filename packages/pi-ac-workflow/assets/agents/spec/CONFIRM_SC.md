# CONFIRM_SC
STAGE: CONFIRM_SC
GOAL: Enforce user approval gate for success criteria before PLAN.

## Variables
SPEC: required spec path

## Workflow
1. Present current `## Success Criteria` to user.
2. Ask for explicit approve/refine decision.
3. If refine requested, update criteria and re-ask.
4. Do not run PLAN until approval is explicit.

## Commit contract
- repo_scope: `spec-only` unless root files changed
- commit any spec edits caused by refinement
