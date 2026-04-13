# SENTINEL
STAGE: SENTINEL
GOAL: Final ruthless validation stage for full workflow.

## Variables
SPEC: required spec path

## Workflow
1. Validate all success criteria with explicit PASS/WARN/FAIL evidence.
2. Reject any implicit or missing evidence.
3. Only PASS settles workflow completion.
4. WARN/FAIL routes to FIX or explicit user escalation.

## Commit contract
- commit stage evidence updates in changed repos
- enforce root-first then spec ordering when both changed
