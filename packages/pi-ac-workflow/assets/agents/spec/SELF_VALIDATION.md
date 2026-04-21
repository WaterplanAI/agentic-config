# SELF_VALIDATION
STAGE: SELF_VALIDATION
GOAL: Final validation stage for lean and leanest workflows.

## Variables
SPEC: required spec path

## Workflow
1. Validate implementation against success criteria and gate evidence.
2. Assign explicit PASS/WARN/FAIL result.
3. Only PASS completes workflow.
4. WARN/FAIL routes to FIX or user escalation.

## Commit contract
- commit changed repos with repo-scoped evidence
- when both repos changed: root commit first, spec commit second
