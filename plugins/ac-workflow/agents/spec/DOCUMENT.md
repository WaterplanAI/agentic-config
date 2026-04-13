# DOCUMENT
STAGE: DOCUMENT
GOAL: Update docs to match implemented behavior and validated workflow.

## Variables
SPEC: required spec path

## Workflow
1. Update only docs affected by implemented change.
2. Keep wording concise, explicit, and ordered.
3. Update spec `## Updated Doc` with changed files and summary.

## Commit contract
- if root docs changed: root repo commit is required
- if spec changed: spec repo commit is required
- if both changed: root first, spec second
- report `repo_scope`, `root_commit`, `spec_commit`
