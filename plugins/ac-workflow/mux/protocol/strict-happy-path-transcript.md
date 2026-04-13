# strict happy-path transcript

Representative strict-flow transcript for `DECLARE -> DISPATCH -> VERIFY -> ADVANCE`.

## Scenario
- Objective: worker updates approved mux docs inside declared scope.
- Expected artifacts: report, signal, summary evidence.
- Session mode: strict runtime activated for the current pi session key.

## Transcript

### 1) Strict session bootstrap
```bash
SESSION_OUT=$(uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/session.py strict-happy-path \
  --base tmp/mux/phase-007-transcripts \
  --phase-id it005 \
  --stage-id phase-007 \
  --wave-id strict-happy \
  --strict-runtime \
  --session-key phase-007-happy-key)
SESSION_DIR=$(printf '%s\n' "$SESSION_OUT" | awk -F= '/^SESSION_DIR=/{print $2}')
REPORT_PATH=tmp/mux/phase-007/reports/strict-happy-runtime-worker.md
SIGNAL_PATH="${SESSION_DIR}/.signals/strict-happy-runtime-worker.done"
SUMMARY_EVIDENCE_PATH="${SESSION_DIR}/research/strict-happy-runtime-summary-evidence.json"
```

Observed output excerpt:
```text
STRICT_RUNTIME=true
STRICT_RUNTIME_FILE=<session_dir>/.mux-runtime.json
STRICT_RUNTIME_REGISTRY=outputs/session/mux-runtime/<session-key-hash>.json
```

### 2) Coordinator declares bounded dispatch and enters DISPATCH
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

### 3) Worker stays data-plane only
```bash
# Worker writes report to REPORT_PATH (includes Executive Summary + Next Steps)
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/signal.py "$SIGNAL_PATH" --path "$REPORT_PATH" --status success
```

Worker terminal response:
```text
0
```

### 4) Coordinator extracts summary evidence and runs strict gate
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/extract-summary.py "$REPORT_PATH" \
  --evidence \
  --evidence-path "$SUMMARY_EVIDENCE_PATH"
uv run ${CLAUDE_PLUGIN_ROOT}/mux/tools/verify.py "$SESSION_DIR" \
  --action gate \
  --summary-evidence "$SUMMARY_EVIDENCE_PATH"
```

Observed `verify.py` output excerpt:
```json
{
  "gate_status": "advance",
  "control_state": "ADVANCE",
  "verification_status": "pass",
  "checked_artifacts": [
    "tmp/mux/phase-007/reports/strict-happy-runtime-worker.md",
    "tmp/mux/phase-007-transcripts/<session-id>/.signals/strict-happy-runtime-worker.done",
    "tmp/mux/phase-007-transcripts/<session-id>/research/strict-happy-runtime-summary-evidence.json"
  ]
}
```

## Expected transition sequence
`LOCK -> RESOLVE -> DECLARE -> DISPATCH -> VERIFY -> ADVANCE`

## Closeout boundary note
- Worker communication remains report/signal artifacts + final `0` only.
- Worker does not call control-plane bridge tools or `report_parent`.
- Coordinator settles success only after gate evidence reaches `ADVANCE`.
