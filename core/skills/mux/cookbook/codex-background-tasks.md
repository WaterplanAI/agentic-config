# Codex Background Tasks

Replicate `Task(run_in_background=True)` delegation using `codex exec` workers launched from Bash, with non-blocking orchestration and signal-based completion.

## Goal

- Launch independent worker jobs (`codex exec`) in background.
- Never block orchestrator on worker output.
- Use MUX signals as the only completion channel.
- Prefer push events (`subscribe.py` via socket bus), auto-fallback to file polling.

## Requirements

- `codex` CLI installed and authenticated.
- Run from project root.
- Start a MUX session first:

```bash
eval "$(uv run .claude/skills/mux/tools/session.py "codex-bg")"
```

Expected session outputs include:
- `SESSION_DIR=...`
- `TRACE_ID=...`
- Optional push bus metadata: `SIGNAL_BUS=...`, `SIGNAL_HUB=unix://...`

## Directory Layout

```text
$SESSION_DIR/
  .signals/
  .agents/
  research/
  audits/
```

Codex background bookkeeping:

```text
$SESSION_DIR/.agents/codex/
  worker-<id>.prompt.txt
  worker-<id>.log
  worker-<id>.pid
  worker-<id>.exit
```

## Pattern: Worker + Monitor (Non-blocking)

### 1) Launch workers (fire-and-forget)

```bash
mkdir -p "$SESSION_DIR/.agents/codex" "$SESSION_DIR/research"

launch_worker() {
  id="$1"
  prompt_file="$SESSION_DIR/.agents/codex/worker-$id.prompt.txt"
  log_file="$SESSION_DIR/.agents/codex/worker-$id.log"
  out_file="$SESSION_DIR/research/$id.md"
  sig_file="$SESSION_DIR/.signals/$id.done"
  pid_file="$SESSION_DIR/.agents/codex/worker-$id.pid"
  exit_file="$SESSION_DIR/.agents/codex/worker-$id.exit"

  cat > "$prompt_file" <<EOF
Write findings to: $out_file
Topic: $id
Return concise output.
EOF

  (
    codex exec "$(cat "$prompt_file")" > "$log_file" 2>&1
    ec=$?
    echo "$ec" > "$exit_file"
    if [ "$ec" -eq 0 ]; then
      uv run tools/signal.py "$sig_file" --path "$out_file" --status success --trace-id "$TRACE_ID"
    else
      uv run tools/signal.py "${sig_file%.done}.fail" --path "$out_file" --status fail --error "codex exit $ec" --trace-id "$TRACE_ID"
    fi
  ) &

  echo $! > "$pid_file"
}

launch_worker "research-api"
launch_worker "research-ux"
launch_worker "research-infra"
```

Orchestrator returns immediately after launch.

### 2) Launch monitor (separate background process)

Monitor waits for N worker signals and emits monitor completion signal.

```bash
(
  uv run tools/subscribe.py "$SESSION_DIR" --expected 3 --timeout 900 > "$SESSION_DIR/.agents/codex/monitor.wait.json"
  ec=$?
  if [ "$ec" -eq 0 ]; then
    uv run tools/signal.py "$SESSION_DIR/.signals/monitor.done" \
      --path "$SESSION_DIR/.agents/codex/monitor.wait.json" \
      --status success --trace-id "$TRACE_ID"
  else
    uv run tools/signal.py "$SESSION_DIR/.signals/monitor.fail" \
      --path "$SESSION_DIR/.agents/codex/monitor.wait.json" \
      --status fail --error "subscribe timeout/fail" --trace-id "$TRACE_ID"
  fi
) &
echo $! > "$SESSION_DIR/.agents/codex/monitor.pid"
```

## Orchestrator Contract

- Do:
  - Launch all workers.
  - Launch one monitor for the phase.
  - Continue to next orchestration step.
- Don’t:
  - Wait on worker PIDs (`wait <pid>` in orchestrator path).
  - Read worker logs inline.
  - Use task-output style blocking.

## Equivalence to `Task()` Model

| Task() pattern | Codex background equivalent |
|---|---|
| `Task(..., run_in_background=True)` | `codex exec ... &` |
| worker writes output artifact | worker writes `$SESSION_DIR/<phase>/<id>.md` |
| worker signals completion | `uv run tools/signal.py ...` |
| monitor waits for N completions | `uv run tools/subscribe.py --expected N` |
| orchestrator never blocks | launch-and-continue |

## Failure Handling

- Worker non-zero exit:
  - create `.fail` signal with error metadata.
- Monitor timeout:
  - create `monitor.fail`.
- Orchestrator checks phase status:

```bash
uv run tools/verify.py "$SESSION_DIR" --action summary
```

## Resume

Use pid/exit files to determine what already finished:

```bash
ls "$SESSION_DIR/.agents/codex/"*.exit
ls "$SESSION_DIR/.signals/"*.done "$SESSION_DIR/.signals/"*.fail
```

Only relaunch workers missing both `*.exit` and signal files.

## Notes

- `subscribe.py` is preferred (push socket bus when available, polling fallback otherwise).
- `signal.py --require-bus` can enforce push-only delivery when strict mode is needed.
- This pattern gives subagent-like parallelism in environments without `Task()`.
