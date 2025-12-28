---
name: dry-run
description: Simulates command execution in dry-run mode without file modifications. Sets dry_run flag, executes command with read-only constraint, then resets flag. Useful for testing workflows safely. Triggers on keywords: dry run, simulate, test command, preview changes, safe mode, no write
project-agnostic: true
allowed-tools:
  - Bash
  - Write
  - Read
---

# Dry Run Skill

Executes any command or skill in simulation mode, preventing all file modifications except session state.

## Usage

```
/dry-run <any command or prompt>
```

Examples:
- `/dry-run /po_spec path/to/spec.md` - Preview full spec workflow
- `/dry-run /spec IMPLEMENT path/to/spec.md` - Test implementation without changes
- `/dry-run why did you implement X this way?` - Normal chat (no files affected)

## Workflow

### Step 1: Initialize Session Status

First, find the Claude Code PID to scope the session:

```bash
# Find Claude PID by tracing process tree
find_claude_pid() {
  local pid=$$
  for i in {1..10}; do
    local info=$(ps -o pid=,ppid=,comm= -p $pid 2>/dev/null)
    [[ -z "$info" ]] && break
    local current_pid=$(echo "$info" | awk '{print $1}')
    local ppid=$(echo "$info" | awk '{print $2}')
    local comm=$(echo "$info" | awk '{print $3}')
    if [[ "$comm" == *"claude"* ]]; then
      echo "$current_pid"
      return
    fi
    pid=$ppid
  done
}

CLAUDE_PID=$(find_claude_pid)
SESSION_DIR="outputs/session/${CLAUDE_PID:-shared}"
mkdir -p "$SESSION_DIR"
```

Check if `$SESSION_DIR/status.yml` exists. If not, create with initial schema:

```yaml
dry_run: false
```

### Step 2: Set Dry-Run Mode

Update `$SESSION_DIR/status.yml`:

```yaml
dry_run: true
```

This signals to THIS session's file operations that writes are prohibited.
Other Claude sessions (different PIDs) are not affected.

### Step 3: Execute Delegated Command

Execute the provided command/prompt EXACTLY as given. All behavior remains normal EXCEPT:

CRITICAL CONSTRAINTS:
- NO file modifications allowed (Read, Grep, Glob, LSP, Bash read-only commands OK)
- ONLY exception: `$SESSION_DIR/status.yml` can be modified
- If command requires file writes, DESCRIBE what WOULD be changed instead
- For chat-only prompts (no file operations needed), respond normally

### Step 4: Reset Dry-Run Mode

After execution completes (success or failure), reset state in `$SESSION_DIR/status.yml`:

```yaml
dry_run: false
```

### Step 5: Report Results

Provide summary:
- What was executed
- What file changes WOULD have occurred (if any)
- Verification that dry_run mode is reset

## Implementation Notes

The skill acts as a wrapper:
1. It does NOT interpret or execute the delegated work itself
2. It sets the flag, then lets normal AI behavior handle the prompt
3. The dry_run flag is checked by pretooluse hook (hard enforcement at tool level)
4. After completion, it ensures cleanup

## State Schema

`outputs/session/<claude_pid>/status.yml`:
```yaml
dry_run: bool  # true = prevent file writes, false = normal mode
```

Session isolation by Claude PID ensures parallel agents don't interfere with each other.
Future extensions may add additional session state fields.
