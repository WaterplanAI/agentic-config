# TEST
STAGE: TEST
GOAL: Validate implementation quality gates with explicit PASS/WARN/FAIL outcome.

## Variables
SPEC: required spec path

## Workflow
1. Run required lint/type/test commands for touched surfaces.
2. Record exact commands and outcomes in spec evidence section.
3. Grade gate result: PASS, WARN, or FAIL.
4. WARN/FAIL must route to FIX; never advance directly.

## Commit contract
- commit updated evidence/spec changes
- commit root test/report changes when present
- include repo-scoped commit metadata in stage outputs
