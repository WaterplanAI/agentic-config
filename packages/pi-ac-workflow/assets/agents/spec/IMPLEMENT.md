# IMPLEMENT
STAGE: IMPLEMENT
GOAL: Apply approved plan changes exactly and record execution evidence.

## Variables
SPEC: required spec path

## Workflow
1. Execute planned tasks in order.
2. Update `## Implement` with task status and evidence.
3. Run required checks for touched surfaces.
4. Record changed files and resulting commit hashes.

## Commit contract (mandatory)
- if root files changed: create root repo commit
- if spec files changed: create spec repo commit via resolver
- when both changed: root commit first, spec commit second
- report metadata fields: `repo_scope`, `root_commit`, `spec_commit`
