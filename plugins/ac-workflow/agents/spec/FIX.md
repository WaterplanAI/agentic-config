# FIX
STAGE: FIX
GOAL: Resolve REVIEW/TEST/SENTINEL/SELF_VALIDATION issues until PASS or escalation.

## Variables
SPEC: required spec path

## Workflow
1. Address only verified findings.
2. Re-run required checks after fixes.
3. Update spec `## Implement` and test evidence with what changed.
4. If retry budget is exhausted, escalate to user with explicit blocker details.

## Commit contract
- commit every changed repo
- if both root and spec changed: root first, spec second
- emit `repo_scope`, `root_commit`, `spec_commit`
