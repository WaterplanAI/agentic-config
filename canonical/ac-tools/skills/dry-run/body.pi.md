# Dry Run

Executes any command or prompt in simulation mode, preventing file modifications except for the session status file.

## Compatibility Note

This pi wrapper preserves the original dry-run workflow. Runtime enforcement comes from the package-local `dry-run-guard.py` registration via `@agentic-config/pi-compat`; if that guard is unavailable, still follow the same no-write constraints manually.

## Usage

```text
/skill:ac-tools-dry-run <any command or prompt>
```

Examples:
- `/skill:ac-tools-dry-run /skill:ac-workflow-spec IMPLEMENT path/to/spec.md` - Preview the implementation flow without writing files
- `/skill:ac-tools-dry-run /skill:ac-workflow-mux-ospec path/to/spec.md` - Preview a larger workflow without committing changes
- `/skill:ac-tools-dry-run explain why the current plan uses packaged assets` - Normal chat with no file modifications

## Workflow

### Step 1: Initialize Session Status

Resolve the session status path using the same priority as the dry-run hook:
1. prefer `CLAUDE_SESSION_ID` when it is available
2. otherwise fall back to compat PID tracing
3. use the shared path only as a legacy last resort

```bash
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID=$(python3 - <<'PY'
import os
import subprocess

pid = os.getpid()
for _ in range(10):
    result = subprocess.run(
        ["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    line = result.stdout.strip()
    if not line:
        break

    parts = line.split()
    if len(parts) >= 3:
        current_pid, ppid, comm = int(parts[0]), int(parts[1]), parts[2]
        if "claude" in comm.lower():
            print(current_pid)
            break
        pid = ppid
    else:
        break
else:
    print("shared")
PY
)
fi

[ -n "$SESSION_ID" ] || SESSION_ID="shared"
STATUS_DIR="outputs/session/${SESSION_ID}"
STATUS_FILE="${STATUS_DIR}/status.yml"
mkdir -p "$STATUS_DIR"
```

If `${STATUS_FILE}` does not exist, create it with:

```yaml
dry_run: false
```

### Step 2: Set Dry-Run Mode

Update `${STATUS_FILE}` to:

```yaml
dry_run: true
```

This signals to this session's file operations that writes are prohibited. Other sessions with different session IDs are not affected.

### Step 3: Execute Delegated Command

Execute the provided command or prompt exactly as given. All behavior remains normal except:

- No file modifications are allowed
- The only write exception is `${STATUS_FILE}`
- If the delegated work requires file writes, describe what would change instead of performing the write
- For chat-only prompts, respond normally

### Step 4: Reset Dry-Run Mode

After execution completes, whether it succeeds or fails, reset `${STATUS_FILE}` to:

```yaml
dry_run: false
```

### Step 5: Report Results

Summarize:
- what was executed
- what file changes would have occurred, if any
- confirmation that dry-run mode was reset

## Implementation Notes

The skill acts as a wrapper:
1. It does not reinterpret the delegated work
2. It sets the status flag, then lets the normal workflow continue
3. The dry-run flag is enforced by the package-local pre-tool hook when available
4. It must always clean up the status flag afterward

## State Schema

`outputs/session/<session_id>/status.yml`:

```yaml
dry_run: bool
```
