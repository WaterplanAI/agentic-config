# REVIEW
STAGE: REVIEW
GOAL: Judge implementation against plan and success criteria.

## Variables
SPEC: required spec path

## Workflow
1. Compare implementation evidence with plan/tasks and success criteria.
2. Assign explicit grade: PASS, WARN, or FAIL.
3. Document exact findings and required fixes.
4. Only PASS can advance to TEST/SENTINEL/SELF_VALIDATION.

## Commit contract
- review updates in spec are `spec-only` commits
- if root review artifacts changed too, use `root+spec` with root-first ordering
