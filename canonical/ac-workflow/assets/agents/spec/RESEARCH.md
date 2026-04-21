# RESEARCH
STAGE: RESEARCH
GOAL: Gather evidence needed to execute later stages safely.

## Variables
SPEC: required spec path

## Workflow
1. Read human objective, constraints, and current AI section.
2. Append concrete findings under `## Research`.
3. Include risks, dependencies, and unknowns.
4. If success criteria are missing, draft candidate criteria section.

## Commit contract
- repo_scope: usually `spec-only`
- commit spec repo updates with resolver
- if root docs/tools were changed, set repo_scope `root+spec` and commit root first, spec second
