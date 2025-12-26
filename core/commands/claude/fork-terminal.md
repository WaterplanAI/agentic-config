---
description: Open new kitty terminal session with optional command and prime prompt
argument-hint: [path] [cmd] [tab|window] [prime_prompt]
project-agnostic: true
allowed-tools:
  - Bash
---

# Fork Terminal

Open a new kitty terminal tab or window, cd to specified path, and optionally run a command with initial context.

## BEHAVIOR

1. PARSE arguments:
   - PATH=$1 (optional, default: /tmp/claude/<uuid>): directory to cd into
   - CMD=$2 (optional, default: "claude"): command to run after cd
   - MODE=$3 (optional, default: "window"): "tab" or "window"
   - PRIME_PROMPT=$4+ (optional): initial context to prime claude with

2. VALIDATE:
   - Generate UUID if PATH is empty/unset
   - Set default PATH to /tmp/claude/<uuid> if not provided
   - CRITICAL: Validate PATH is not a dangerous system directory:
     - REJECT if PATH is exactly: /, /bin, /usr, /etc, /System, /sbin, /Library
     - REJECT if PATH is subdirectory of: /bin/*, /usr/*, /etc/*, /System/*, /sbin/*, /Library/*
     - Exit with error message if validation fails
   - Create directory if PATH does not exist (mkdir -p)
   - Exit with error if directory creation fails
   - If MODE is not "tab" or "window", default to "window"

3. BUILD osascript command:
   - Activate kitty
   - Open new tab (cmd+t) or window (cmd+n) based on MODE
   - Add delay 0.5 for UI sync
   - Type: `cd {WORK_PATH} && clear && {CMD}`
   - Press return

4. HANDLE prime_prompt:
   - If PRIME_PROMPT provided and CMD is "claude":
     - Check if cload is available (command -v cload)
     - If available: use `cd {WORK_PATH} && clear && cload {PRIME_PROMPT} | claude`
     - Otherwise: just run `cd {WORK_PATH} && clear && {CMD}` (user must paste prompt)
   - If PRIME_PROMPT provided but CMD is not "claude":
     - Warn user that prime_prompt only works with claude command
     - Run without prime_prompt

5. EXECUTE osascript command

## SAFETY

### Default Behavior

When invoked WITHOUT arguments:
- Generates unique UUID (8 chars, lowercase)
- Creates isolated directory: /tmp/claude/<uuid>
- Opens new terminal window in that directory
- Runs default command: "claude"

Example: `/fork-terminal` creates `/tmp/claude/a3f8e2c1/` and runs `claude`

### PATH Validation Rules

The command validates PATH before execution to prevent dangerous operations:

| Path | Action | Reason |
|------|--------|--------|
| Empty/unset | Use /tmp/claude/<uuid> | Safe default with isolation |
| / | REJECT | System root - dangerous |
| /bin, /usr, /etc, /System, /sbin, /Library | REJECT | System directories - dangerous |
| /bin/*, /usr/*, /etc/*, /System/*, /sbin/*, /Library/* | REJECT | System files - dangerous |
| Non-existent valid path | CREATE | Safe to create if not system dir |
| Existing valid path | USE | Safe to use |

### Safe Invocation Examples

```bash
/fork-terminal                                    # Safe: uses /tmp/claude/<uuid>
/fork-terminal /tmp/my-workspace                  # Safe: valid tmp directory
/fork-terminal ~/projects/my-app                  # Safe: user home directory
/fork-terminal /                                  # REJECTED: system root
```

## EXAMPLE OSASCRIPT STRUCTURE

```bash
osascript -e 'tell application "kitty" to activate' \
  -e 'tell application "System Events" to tell process "kitty" to keystroke "t" using command down' \
  -e 'delay 0.5' \
  -e 'tell application "System Events" to tell process "kitty" to keystroke "cd /path && clear && claude"' \
  -e 'tell application "System Events" to keystroke return'
```

## VARIABLES

# Generate UUID if WORK_PATH not provided
UUID=$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)
DEFAULT_PATH="/tmp/claude/${UUID}"
WORK_PATH=${1:-$DEFAULT_PATH}

# Validate WORK_PATH is not dangerous
# (validation logic per spec details section 2)

case "$WORK_PATH" in
  /|/bin|/usr|/etc|/System|/sbin|/Library|/var|/private|/opt)
    echo "ERROR: Refusing to execute in dangerous system directory: $WORK_PATH" >&2
    exit 1
    ;;
  /bin/*|/usr/*|/etc/*|/System/*|/sbin/*|/Library/*|/var/*|/private/*|/opt/*)
    echo "ERROR: Refusing to execute in dangerous system directory: $WORK_PATH" >&2
    exit 1
    ;;
esac

# Create directory if it doesn't exist
if [ ! -d "$WORK_PATH" ]; then
  echo "Creating directory: $WORK_PATH"
  mkdir -p "$WORK_PATH" || {
    echo "ERROR: Failed to create directory: $WORK_PATH" >&2
    exit 1
  }
fi

CMD=$2 (default: "claude")
MODE=$3 (default: "window")
PRIME_PROMPT=$4+
