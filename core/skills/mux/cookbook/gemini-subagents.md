# Gemini CLI Sub-Agents (Shell-Native MUX)

This guide documents how to implement **E2E Autonomous Agent Fleets** using the Gemini CLI and MUX Protocol in a "Shell-Native" environment.

This pattern is required when high-level abstractions like the `Task` tool are unavailable, or when you need raw process control over your agent fleet.

## Architecture

In Shell-Native mode, we replace the `Task()` tool with direct process management:

| Component | Abstract (Task Tool) | Shell-Native Implementation |
|-----------|----------------------|-----------------------------|
| **Delegator** | `Task(subagent=...)` | `uv run exec-worker.py ... &` |
| **Worker** | Subagent Instance | `gemini -p "PROMPT"` process |
| **Signaling** | Implicit Return | `exec-worker.py` writes `.done`/`.fail` |
| **Monitoring** | `await task` | `uv run subscribe.py --expected N` |

## Prerequisites

Ensure you have the MUX tools available in your path (typically `.claude/skills/mux/tools/`):
*   `session.py`: Initializes the MUX session and signal bus.
*   `exec-worker.py`: Wrapper that runs a command and emits MUX signals.
*   `subscribe.py`: Blocks until a specific number of signals are received.

## Workflow

### 1. Initialize Session
Start a new MUX session to generate a unique ID and start the signal bus (optional but recommended for speed).

```bash
# Set session name
TOPIC="research-fleet-01"
# Run session tool
uv run .claude/skills/mux/tools/session.py "$TOPIC"
# Capture the output directory (usually tmp/mux/YYYYMMDD-HHMM-topic)
SESSION_DIR="tmp/mux/..." 
```

### 2. Define the Fleet
Construct the commands for your fleet. Use `exec-worker.py` to wrap the actual agent command.

**Syntax:**
```bash
uv run .claude/skills/mux/tools/exec-worker.py 
  --command "gemini -p 'Your Prompt Here'" 
  --signal-path "$SESSION_DIR/.signals/worker-id.done" 
  --output-path "outputs/worker-id.md" 
  --log-path "outputs/logs/worker-id.log" &
```

*   `--command`: The actual work. Can be `gemini -p`, `python script.py`, or any shell command.
*   `--signal-path`: MUST be inside `$SESSION_DIR/.signals/`.
*   `--output-path`: The primary artifact the worker is expected to produce.
*   `&`: Crucial! Runs the worker in the background.

### 3. Launch & Monitor
Launch all workers in the background, then immediately start the monitor in the foreground.

```bash
# Launch 3 workers
uv run .../exec-worker.py ... &
uv run .../exec-worker.py ... &
uv run .../exec-worker.py ... &

# Wait for 3 completions
uv run .claude/skills/mux/tools/subscribe.py "$SESSION_DIR" --expected 3 --timeout 300
```

## complete-fleet.sh Template

Save this script as a reusable template for launching fleets.

```bash
#!/bin/bash
set -e

# Configuration
TOPIC="autonomous-research"
TOOLS_DIR=".claude/skills/mux/tools"
OUTPUT_DIR="outputs/$TOPIC"

# 1. Initialize Session
echo "Initializing MUX Session..."
uv run "$TOOLS_DIR/session.py" "$TOPIC"
# Extract session path (assumes session.py outputs SESSION_DIR=... to stdout)
# In practice, you might need to parse it or just predict the path:
SESSION_ID="$(date +%Y%m%d)-$(date +%H%M)-$TOPIC"
SESSION_DIR="tmp/mux/$SESSION_ID" # Approximate path structure
mkdir -p "$OUTPUT_DIR" "$OUTPUT_DIR/logs"

echo "Session: $SESSION_DIR"

# 2. Launch Workers
echo "Launching Fleet..."

# Worker A: Research
uv run "$TOOLS_DIR/exec-worker.py" 
  --command "gemini -p 'Research Feature A and save to $OUTPUT_DIR/feature_a.md'" 
  --signal-path "$SESSION_DIR/.signals/worker_a.done" 
  --output-path "$OUTPUT_DIR/feature_a.md" 
  --log-path "$OUTPUT_DIR/logs/worker_a.log" &

# Worker B: Audit
uv run "$TOOLS_DIR/exec-worker.py" 
  --command "gemini -p 'Audit code security and save to $OUTPUT_DIR/audit.md'" 
  --signal-path "$SESSION_DIR/.signals/worker_b.done" 
  --output-path "$OUTPUT_DIR/audit.md" 
  --log-path "$OUTPUT_DIR/logs/worker_b.log" &

# 3. Monitor
echo "Waiting for fleet completion..."
uv run "$TOOLS_DIR/subscribe.py" "$SESSION_DIR" --expected 2 --timeout 600

echo "Fleet execution complete."
```

## Troubleshooting

*   **Timeout:** If `subscribe.py` times out, check the logs in `log-path`.
*   **Permissions:** Ensure `gemini` executable is in the PATH of the background process.
*   **Failures:** If a worker fails (non-zero exit), `exec-worker.py` writes a `.fail` signal. `subscribe.py` counts these towards the expected total but reports the failure status.
