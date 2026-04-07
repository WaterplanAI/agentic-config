# Shared worker-wave orchestration helpers

This asset root is the IT003 shared runtime foundation for the last repo-solvable deferred pi ports.

## Scope
- Build bounded synchronous worker waves on top of the runtime `subagent` tool.
- Standardize worker result files so later skills do not need to parse free-form subagent responses.
- Keep serial preflight, user approvals, branch/bootstrap logic, and final synthesis in the consumer skill.

## Layout
- `protocol/worker.md` — worker contract for any skill-owned subagent launched through this shared surface
- `tools/write-result.js` — writes normalized worker-result JSON to the coordinator-assigned path
- `tools/summarize-results.js` — validates and summarizes an ordered set of worker-result files

## Coordinator contract
The consumer skill remains the coordinator.

Coordinator responsibilities:
- create disjoint report/result paths before launching workers
- provide each worker with its `worker_id`, `target`, `report_path`, and `result_path`
- keep workers inside one synchronous `subagent` single or parallel wave
- serialize work whenever write ownership overlaps
- decide whether `warn` results are acceptable for the current wave
- own final synthesis after reading worker reports and the ordered result summary

## Worker contract
Workers must follow `./protocol/worker.md`.

In practice that means every worker:
- stays non-interactive
- does not launch nested subagents
- writes substantive output to its assigned report path
- calls `write-result.js` after the report is written
- returns a concise completion response while treating the result file as the authoritative machine-readable status surface

## Result file shape
`write-result.js` writes deterministic JSON with the required fields:
- `worker_id`
- `status` (`success`, `warn`, or `fail`)
- `summary`
- `report_path`
- `target`

Example:

```json
{
  "worker_id": "frontend-env",
  "status": "warn",
  "summary": "frontend install completed with peer dependency warnings",
  "report_path": "tmp/worktree/reports/frontend.md",
  "target": "trees/abc123-feature/services/web"
}
```

## Tool usage
### Worker-side result write

```bash
node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js \
  --result-path "$RESULT_PATH" \
  --worker-id "$WORKER_ID" \
  --status "success" \
  --summary "backend environment configured" \
  --report-path "$REPORT_PATH" \
  --target "$TARGET"
```

### Coordinator-side ordered summary

```bash
node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/summarize-results.js \
  --result tmp/worktree/results/01-backend.json \
  --result tmp/worktree/results/02-frontend.json \
  --result tmp/worktree/results/03-worker-tools.json \
  --fail-on-missing \
  --fail-on-status fail
```

Use `--format json` when the coordinator wants machine-readable ordered summary output.

## Representative consumption
### `ac-git-worktree`
The shipped `@agentic-config/pi-ac-git` worktree skill uses this shared surface for the parallel environment-setup wave only.

Keep these steps in the skill coordinator:
- `.worktree.yml` discovery
- branch/bootstrap flow
- asset wiring and `direnv allow`
- final commit and user summary

### `ac-qa-gh-pr-review`
The shipped `@agentic-config/pi-ac-qa` gh-pr-review skill uses this shared surface for the fixed review-worker fan-out plus result collection.

Keep these steps in the skill coordinator:
- PR metadata fetch
- final markdown synthesis
- user-confirmed `gh pr review` action

## Explicitly out of scope
This asset root does not provide:
- a new end-user orchestration tool
- nested workers
- `subagent.chain` abstractions
- background session or signal orchestration
- generic skill-to-skill invocation runtime
- review posting semantics
- browser, MCP, or Playwright behavior
