# Worker protocol

This protocol applies to any worker launched by a consumer skill through `@agentic-config/pi-compat/assets/orchestration/`.

## Required inputs from the coordinator
The coordinator must assign each worker:
- `worker_id`
- `target`
- `report_path`
- `result_path`
- explicit scope boundaries
- explicit completion criteria

## Mandatory worker rules
1. Read the coordinator inputs before changing anything.
2. Stay inside the assigned scope.
3. Do not launch nested subagents.
4. Do not prompt the user.
5. Write substantive findings or execution evidence to `report_path`.
6. Write normalized result metadata to `result_path` with `tools/write-result.js`.
7. Return a concise completion response after the report and result files exist.

## Status semantics
- `success` — completed the requested scope with no blocking issue
- `warn` — completed the requested scope but surfaced a non-fatal issue the coordinator must evaluate explicitly
- `fail` — could not complete the requested scope or hit a blocking issue

A missing result file is treated as failure by the coordinator.

## Minimal completion sequence
1. Produce the worker report at `report_path`.
2. Run:

```bash
node node_modules/@agentic-config/pi-compat/assets/orchestration/tools/write-result.js \
  --result-path "$RESULT_PATH" \
  --worker-id "$WORKER_ID" \
  --status "$STATUS" \
  --summary "$SUMMARY" \
  --report-path "$REPORT_PATH" \
  --target "$TARGET"
```

3. Return a brief completion note such as:

```text
Completed worker scope. Report and result files are written.
```

## Notes for worker authors
- Put detailed evidence in the report file, not in the tool response.
- Keep summaries concise and decision-relevant.
- Prefer `warn` over `success` when the coordinator should re-check something but may still continue.
- Use `fail` when the coordinator must treat the wave as incomplete unless it explicitly retries or re-scopes the worker.
