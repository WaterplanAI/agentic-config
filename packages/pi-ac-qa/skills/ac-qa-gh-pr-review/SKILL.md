---
name: ac-qa-gh-pr-review
description: "Reviews pull requests through a bounded shared worker-wave review flow, consolidated reporting, and user-confirmed `gh pr review` actions."
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - AskUserQuestion
  - subagent
---

# PR Review - pi adaptation

Review a pull request with a bounded shared worker-wave on top of the shipped `@agentic-config/pi-compat` orchestration helpers.

## Current shipped boundary

This pi wrapper now ships, but it stays inside the bounded IT003 contract:
- use exactly one fixed review-worker wave through `subagent`
- use the shared `pi-compat` worker protocol and result helpers for worker outputs
- keep PR metadata fetch, final markdown synthesis, and any `gh pr review` action in the coordinator skill
- keep review posting user-confirmed and serial through `AskUserQuestion`
- do **not** introduce nested workers, `subagent.chain`, mux/session state, or package-local orchestration helpers
- if the local checkout does not match the PR head, continue honestly in diff-first mode and report any execution limitation instead of pretending local commands validated the PR head

## Arguments

- `pr_ref` (required): PR URL, `owner/repo#123`, or any `gh pr view`-compatible PR reference
- `expected_changes` (optional): brief description of the intended change; if omitted, compare the diff against the PR title/body only
- `report_path` (optional): explicit final report path; default to `tmp/gh-pr-review/<date>-<uuid>/PR-<number>-<uuid>.md`

## Required references

Read these when needed:
- `node_modules/@agentic-config/pi-compat/assets/orchestration/protocol/worker.md`
- `node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js`
- `node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js`

## Pre-flight

1. Verify `gh` CLI is available and authenticated:
   ```bash
   gh --version
   gh auth status
   ```
   - If either step fails: STOP and explain what is missing.

2. Verify the current directory is inside the repo being reviewed:
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   ```
   - If this fails: STOP. This skill needs a local repo so the workers can inspect the actual codebase and run bounded local validation when that is honest.

3. Resolve runtime paths and report defaults:
   ```bash
   DATE_PREFIX=$(date +%Y-%m-%d)
   UUID_VALUE=$(uuidgen | tr 'A-Z' 'a-z')
   RUN_ROOT="$REPO_ROOT/tmp/gh-pr-review/$DATE_PREFIX-$UUID_VALUE"
   mkdir -p "$RUN_ROOT/reports" "$RUN_ROOT/results"
   ```

4. Fetch PR metadata and review inputs before launching workers:
   ```bash
   gh pr view "$PR_REF" \
     --json number,url,title,body,author,state,baseRefName,headRefName,headRefOid,files,additions,deletions,commits \
     > "$RUN_ROOT/pr.json"

   gh pr view "$PR_REF" --json comments,reviews > "$RUN_ROOT/feedback.json"
   gh pr diff "$PR_REF" > "$RUN_ROOT/pr.diff"

   set +e
   gh pr checks "$PR_REF" > "$RUN_ROOT/checks.txt" 2>&1
   CHECKS_EXIT=$?
   set -e
   ```
   - Record `CHECKS_EXIT`, but do **not** stop only because checks are failing. Failing CI is review evidence, not a fetch failure.

5. Derive machine-readable coordinator facts from `pr.json`.
   - Use a short `python3` snippet when shell parsing becomes brittle.
   - Extract at least:
     - PR number
     - PR title
     - PR URL
     - base branch
     - head branch
     - head commit SHA (`headRefOid`)
     - changed file paths
   - Write the changed-file list to `$RUN_ROOT/changed-files.txt`.

6. Resolve the default report path when `$REPORT_PATH` was not provided:
   ```bash
   REPORT_PATH="${REPORT_PATH:-$RUN_ROOT/PR-$PR_NUMBER-$UUID_VALUE.md}"
   COMMENT_PATH="$RUN_ROOT/github-review-comment.md"
   ```

7. Check whether the local checkout actually matches the PR head:
   ```bash
   LOCAL_HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)
   LOCAL_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)
   ```
   - If `LOCAL_HEAD` equals the PR `headRefOid`, record `CHECKOUT_MODE=head-aligned`.
   - Otherwise record `CHECKOUT_MODE=diff-only`.
   - In `diff-only` mode:
     - do **not** auto-checkout the PR
     - do **not** claim that local tests or linters validated the PR head
     - tell the code-quality and test workers to treat execution limits as explicit review evidence, usually `warn`

## Fixed review-worker wave

Use one bounded worker wave with these ordered workers:

1. `expected-changes`
2. `security-review`
3. `code-quality-review`
4. `test-review`
5. `logic-review`

Create one report/result pair per worker:
- `reports/01_expected_changes.md` + `results/01-expected.json`
- `reports/02_security.md` + `results/02-security.json`
- `reports/03_code_quality.md` + `results/03-quality.json`
- `reports/04_tests.md` + `results/04-tests.json`
- `reports/05_logic_bugs.md` + `results/05-logic.json`

## Worker contract

Every worker task must explicitly tell the worker to:
1. read `node_modules/@agentic-config/pi-compat/assets/orchestration/protocol/worker.md`
2. stay non-interactive and never launch nested subagents
3. keep writes limited to its assigned report path and result path
4. read the coordinator artifacts it needs from:
   - `$RUN_ROOT/pr.json`
   - `$RUN_ROOT/feedback.json`
   - `$RUN_ROOT/pr.diff`
   - `$RUN_ROOT/checks.txt`
   - `$RUN_ROOT/changed-files.txt`
5. inspect the local repo only as far as the assigned scope requires
6. write a substantive markdown report first
7. call:
   ```bash
   node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js \
     --result-path "$RESULT_PATH" \
     --worker-id "$WORKER_ID" \
     --status "$STATUS" \
     --summary "$SUMMARY" \
     --report-path "$REPORT_PATH" \
     --target "$TARGET"
   ```
8. return a concise completion message after the result file exists

### Worker status rules
Use the result status to encode review significance honestly:
- `success` — completed the assigned review scope with no blocking issue
- `warn` — completed the scope but found non-blocking concerns or hit a non-authoritative execution limitation
- `fail` — found a blocking review issue or could not complete the scope honestly

## Worker scope details

### 1. Expected changes validation
Target: `expected-changes`

Inputs and expectations:
- Compare the PR diff against `expected_changes` when provided.
- If no explicit `expected_changes` brief was provided, compare against the PR title/body and say that no external expectation brief was available.
- Identify:
  - missing expected changes
  - unexpected or out-of-scope changes
  - alignment score (`1-10`) with short justification

Required report sections:
- Scope basis used (`expected_changes` vs PR title/body only)
- Alignment summary
- Missing expected changes
- Unexpected changes
- Recommendation impact

### 2. Security review
Target: `security`

Check the diff and affected files for:
- hardcoded secrets or credentials
- injection risks
- auth / permission regressions
- insecure dependency or shell usage changes
- data exposure or trust-boundary regressions

Required report sections:
- Blocking findings
- Non-blocking concerns
- Files inspected
- Recommendation impact

### 3. Code quality review
Target: `code-quality`

Check project conventions and changed-file quality.

Rules:
- Inspect the changed files and nearby local context.
- If `CHECKOUT_MODE=head-aligned`, run the narrowest repo-native lint and type-check commands you can justify for the changed files.
- If `CHECKOUT_MODE=diff-only`, do **not** pretend local commands validate the PR head. You may still inspect configs and current files for context, but any command-based conclusion must be labeled limited and should normally produce `warn` rather than `success`.
- Report only issues that appear introduced or exposed by this PR.

Required report sections:
- Commands run
- Execution mode (`head-aligned` or `diff-only`)
- New code-quality issues
- Type/lint findings
- Recommendation impact

### 4. Test discovery and execution
Target: `tests`

Rules:
- Discover the narrowest authoritative test surface suggested by the diff.
- Prefer targeted repo-native commands over broad whole-repo runs.
- If `CHECKOUT_MODE=head-aligned`, run the relevant commands and record exact outputs.
- If `CHECKOUT_MODE=diff-only`, do not claim authoritative execution against the PR head. Report the limitation, any discoverable relevant tests, and the exact commands a human should run after checking out the PR.

Required report sections:
- Discovered relevant tests
- Commands run or deferred
- Execution mode (`head-aligned` or `diff-only`)
- Failures or limitations
- Recommendation impact

### 5. Logic and bug risk review
Target: `logic-bug-risk`

Review the logic changes critically:
- intent vs implementation
- edge cases
- state transitions
- control flow and early returns
- data-flow correctness
- regression risk and downstream contract changes

Required report sections:
- Logic correctness findings
- Bug risks
- Impact assessment
- Recommendation impact

## Launch the worker wave

Use exactly one synchronous `subagent.parallel` call when the five workers are independent, which they should be in this phase because they only write to disjoint report/result files.

Prefer the `worker` agent.

Each worker task should include:
- the shared worker protocol path
- the exact assigned report path and result path
- the coordinator artifact paths under `$RUN_ROOT`
- the current `CHECKOUT_MODE`
- the worker-specific scope above
- the instruction to avoid nested subagents and user prompts

## Summarize the worker results

After all workers return, summarize the ordered result set:

```bash
set +e
node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js \
  --result "$RUN_ROOT/results/01-expected.json" \
  --result "$RUN_ROOT/results/02-security.json" \
  --result "$RUN_ROOT/results/03-quality.json" \
  --result "$RUN_ROOT/results/04-tests.json" \
  --result "$RUN_ROOT/results/05-logic.json" \
  --fail-on-missing \
  --fail-on-status fail \
  --format json \
  > "$RUN_ROOT/summary.json"
SUMMARY_EXIT=$?
set -e
```

Interpretation rules:
- missing result files or malformed summary output are fatal: STOP
- `SUMMARY_EXIT=0` means no worker reported `fail`
- `SUMMARY_EXIT=1` means at least one worker reported `fail`; continue to final synthesis because blocking review findings are still valid review output
- before final synthesis, read every worker report with `warn` or `fail`

## Final synthesis

The coordinator owns the final review report.

Create the final markdown report at `$REPORT_PATH`.

Include at least:

```markdown
# PR Review: #{PR_NUMBER}

**URL**: {PR_URL}
**Title**: {PR_TITLE}
**Author**: {AUTHOR}
**Branch**: {HEAD} -> {BASE}
**Review Session**: {UUID}
**Date**: {TIMESTAMP}
**Checkout Mode**: {head-aligned|diff-only}

---

## Executive Summary

{APPROVE | REQUEST_CHANGES | COMMENT}

## Worker Wave Summary

- Totals by status from `summary.json`
- Any missing or limited evidence
- CI/check status summary from `checks.txt`

## Detailed Findings

### Expected Changes
{from worker 1}

### Security
{from worker 2}

### Code Quality
{from worker 3}

### Test Results
{from worker 4}

### Logic & Bug Risk
{from worker 5}

## Recommendation

- APPROVE when no worker reported `fail` and the evidence supports merge readiness
- REQUEST_CHANGES when any worker reported a blocking issue
- COMMENT when only `warn` results or non-blocking concerns remain

## Recommended Review Message

{copy-paste-ready review body}

## Next Steps

{actionable follow-ups}
```

Also write the concise review-ready message to `$COMMENT_PATH`.

### Recommendation rules
- Any worker `fail` should normally produce `REQUEST_CHANGES` unless the coordinator can prove the failure was purely infrastructural and non-review-significant.
- `diff-only` mode cannot justify an unconditional approval when test or lint execution was a required part of the evidence but could not be run authoritatively.
- Be explicit when the recommendation is limited by checkout alignment or missing local execution.

## Optional review action

Keep review posting serial and user-confirmed.

1. Show the exact command that would run.
2. Use `AskUserQuestion` to offer only the actions that are honest for the current result:
   - keep report only
   - post comment
   - request changes
   - approve (only when the evidence truly supports approval)
3. If the user chooses a posting action, run the corresponding command with `$COMMENT_PATH`.

Representative commands:
```bash
gh pr review "$PR_REF" --comment --body-file "$COMMENT_PATH"
gh pr review "$PR_REF" --request-changes --body-file "$COMMENT_PATH"
gh pr review "$PR_REF" --approve --body-file "$COMMENT_PATH"
```

If the user chooses not to post, stop after writing the report and comment files.

## Final user-facing output

Report clearly:
- PR number and title
- final recommendation
- checkout mode
- final report path
- review comment path
- any blocking issues
- whether a review action was executed or left pending

## Error handling

| Condition | Action |
|---|---|
| `gh` unavailable or unauthenticated | STOP |
| not inside a git repo | STOP |
| PR metadata or diff fetch fails | STOP |
| `gh pr checks` reports failing checks | continue and treat as review evidence |
| local checkout does not match PR head | continue in `diff-only` mode and report the limitation honestly |
| worker result file missing | STOP |
| worker reports `warn` | continue and surface explicitly |
| worker reports `fail` | continue to synthesis and normally recommend `REQUEST_CHANGES` |
| user declines posting | keep report only |

## Non-goals

This skill does **not** ship:
- nested review workers
- generic orchestration sessions
- automatic PR checkout or branch switching
- generic PR-host automation beyond this review flow
- browser or Playwright behavior
