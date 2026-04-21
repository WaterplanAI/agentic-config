# strict blocker-path transcript

Representative strict-flow transcript for a real `BLOCK` outcome from current shipped gate behavior.

## Scenario
- Objective/scope declaration is valid.
- Worker writes report and success signal correctly.
- Summary evidence artifact is missing at gate time.
- Result must be `BLOCK` (not `ADVANCE`, not manual fallback).

## Transcript

### 1) Strict session bootstrap
```bash
SESSION_OUT=$(uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/session.py strict-blocker-path \
  --base tmp/mux/phase-007-transcripts \
  --phase-id it005 \
  --stage-id phase-007 \
  --wave-id strict-blocker \
  --strict-runtime \
  --session-key phase-007-blocker-key)
SESSION_DIR=$(printf '%s\n' "$SESSION_OUT" | awk -F= '/^SESSION_DIR=/{print $2}')
REPORT_PATH=tmp/mux/phase-007/reports/strict-blocker-runtime-worker.md
SIGNAL_PATH="${SESSION_DIR}/.signals/strict-blocker-runtime-worker.done"
MISSING_SUMMARY_EVIDENCE_PATH="${SESSION_DIR}/research/strict-blocker-runtime-summary-evidence.json"
```

Observed output excerpt:
```text
STRICT_RUNTIME=true
```

### 2) Coordinator reaches DISPATCH with valid declared dispatch
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py prerequisites "$SESSION_DIR" --required approved-plan --status ready
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py transition "$SESSION_DIR" --to RESOLVE --reason "approved plan loaded"
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py transition "$SESSION_DIR" --to DECLARE --reason "prerequisites satisfied"
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py declare "$SESSION_DIR" \
  --worker-type protocol-writer \
  --objective "align mux protocol docs" \
  --scope "phase-007 approved canonical files" \
  --report-path "$REPORT_PATH" \
  --signal-path "$SIGNAL_PATH" \
  --expected-artifact report \
  --expected-artifact signal \
  --expected-artifact summary
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py transition "$SESSION_DIR" --to DISPATCH --reason "worker dispatched"
```

### 3) Worker completes data-plane actions only
```bash
# Worker writes report to REPORT_PATH (includes Executive Summary + Next Steps)
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py "$SIGNAL_PATH" --path "$REPORT_PATH" --status success
```

Worker terminal response:
```text
0
```

### 4) Gate runs without summary evidence artifact
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/verify.py "$SESSION_DIR" \
  --action gate \
  --summary-evidence "$MISSING_SUMMARY_EVIDENCE_PATH"
```

Observed `verify.py` output excerpt:
```json
{
  "gate_status": "block",
  "control_state": "BLOCK",
  "verification_status": "blocked",
  "checked_artifacts": [
    "tmp/mux/phase-007/reports/strict-blocker-runtime-worker.md",
    "tmp/mux/phase-007-transcripts/<session-id>/.signals/strict-blocker-runtime-worker.done"
  ],
  "missing_evidence": [
    "missing summary evidence artifact: tmp/mux/phase-007-transcripts/<session-id>/research/strict-blocker-runtime-summary-evidence.json"
  ]
}
```

### 5) Manual fallback to ADVANCE is rejected
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/ledger.py transition "$SESSION_DIR" --to ADVANCE --reason "manual fallback attempt"
```

Observed output excerpt:
```text
ERROR: Illegal transition: BLOCK -> ADVANCE
```

## Expected transition sequence
`LOCK -> RESOLVE -> DECLARE -> DISPATCH -> VERIFY -> BLOCK`

## Recovery note
After the missing summary evidence artifact is produced, recovery proceeds through legal transitions (`BLOCK -> RESOLVE -> DECLARE -> DISPATCH -> VERIFY`) before any later `ADVANCE`.
