# CREATE
STAGE: CREATE
GOAL: Create a new spec file in `.specs/specs/...` with the canonical template.

## Variables
SPEC: optional explicit target path

## Workflow
1. Resolve target path (explicit input wins).
2. Create the spec from `_template.md`.
3. Populate Human section from user request only.
4. Keep AI section scaffolded but unfilled.

## Commit contract
- repo_scope: `spec-only`
- commit spec repo changes with resolver
- do not create a root-repo commit unless root files changed
