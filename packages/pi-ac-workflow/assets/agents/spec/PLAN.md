# PLAN
STAGE: PLAN
GOAL: Produce an explicit ordered implementation plan that can be executed without inference.

## Variables
SPEC: required spec path

## Workflow
1. Translate approved success criteria into ordered tasks.
2. Enumerate exact files/surfaces to edit and validation commands.
3. Include fail-closed routing (what happens on WARN/FAIL).
4. Include mandatory stage commit expectations for IMPLEMENT onward.

## Commit contract
- repo_scope: `spec-only` unless root files changed
- commit changed repos; if both changed, root commit first then spec commit
