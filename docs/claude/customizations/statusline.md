# Claude Code Statusline Configuration

Custom statusline scripts display contextual information in the Claude Code interface.

Inspired by [Pure](https://github.com/sindresorhus/pure) prompt.

## Configuration

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

The script receives JSON input via stdin containing workspace and session data.

## JSON Input Structure

```json
{
  "workspace": {
    "current_dir": "/path/to/project"
  },
  "model": {
    "display_name": "Claude Opus 4.5"
  },
  "transcript_path": "/path/to/transcript.jsonl"
}
```

## Example Script

A Pure-style statusline with git integration, context tracking, and color coding:

```bash
#!/bin/bash

# Pure prompt-style status line for Claude Code
# Colors matching Pure's theme: blue for path, color 242 for git, cyan for arrows

# Read JSON input
input=$(cat)

# Extract data from JSON
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
model_name=$(echo "$input" | jq -r '.model.display_name')

# Extract token information from transcript file
transcript_path=$(echo "$input" | jq -r '.transcript_path // ""')
tokens_used=0
tokens_total=200000

if [[ -n "$transcript_path" ]] && [[ -f "$transcript_path" ]]; then
    # Get context from last main chain (non-sidechain) assistant message
    # The input_tokens field already includes full conversation context
    tokens_used=$(tac "$transcript_path" 2>/dev/null | while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            is_main_chain=$(echo "$line" | jq -r 'if .isSidechain == true then "false" else "true" end' 2>/dev/null)
            has_usage=$(echo "$line" | jq -r 'if .message.usage then "true" else "false" end' 2>/dev/null)

            if [[ "$is_main_chain" == "true" && "$has_usage" == "true" ]]; then
                echo "$line" | jq -r '
                    (.message.usage.input_tokens // 0) +
                    (.message.usage.cache_read_input_tokens // 0) +
                    (.message.usage.cache_creation_input_tokens // 0)
                ' 2>/dev/null
                break
            fi
        fi
    done)

    # Default to 0 if extraction failed
    tokens_used=${tokens_used:-0}
fi

# Format path with ~ for home directory (like Pure's %~)
if [[ "$current_dir" == "$HOME"* ]]; then
    display_path="~${current_dir#$HOME}"
else
    display_path="$current_dir"
fi

# Human-readable time function
human_time_to_var() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))

    local result=""
    [[ $days -gt 0 ]] && result="${days}d "
    [[ $hours -gt 0 ]] && result="${result}${hours}h "
    [[ $minutes -gt 0 ]] && result="${result}${minutes}m "
    [[ $secs -gt 0 ]] && result="${result}${secs}s"

    [[ -z "$result" ]] && result="0s"

    echo "${result% }"
}

# Get system uptime in human readable format
if [[ -f /proc/uptime ]]; then
    # Linux
    uptime_seconds=$(awk '{print int($1)}' /proc/uptime)
elif command -v uptime &> /dev/null; then
    # macOS - parse uptime command output
    uptime_output=$(uptime)
    if [[ $uptime_output =~ ([0-9]+)\ day ]]; then
        days=${BASH_REMATCH[1]}
        uptime_seconds=$((days * 86400))
    elif [[ $uptime_output =~ ([0-9]+):([0-9]+) ]]; then
        hours=${BASH_REMATCH[1]}
        minutes=${BASH_REMATCH[2]}
        uptime_seconds=$((hours * 3600 + minutes * 60))
    else
        uptime_seconds=0
    fi
else
    uptime_seconds=0
fi
human_uptime=$(human_time_to_var "$uptime_seconds")

# Get git information and push/pull arrows
git_info=""
git_arrows=""
if git -C "$current_dir" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$current_dir" branch --show-current 2>/dev/null || echo "HEAD")

    # Check git status (dirty/clean)
    if git -C "$current_dir" diff --quiet && git -C "$current_dir" diff --cached --quiet 2>/dev/null; then
        # Clean - Bright white
        git_info=$(printf " \033[38;5;255mon %s\033[0m" "$branch")
    else
        # Dirty - Brightest red
        git_info=$(printf " \033[38;5;196mon %s*\033[0m" "$branch")
    fi

    # Check for push/pull arrows
    upstream=$(git -C "$current_dir" rev-parse --abbrev-ref @{u} 2>/dev/null)
    if [[ -n "$upstream" ]]; then
        counts=$(git -C "$current_dir" rev-list --left-right --count HEAD..."@{u}" 2>/dev/null || echo "0	0")
        ahead=$(echo "$counts" | cut -f1)
        behind=$(echo "$counts" | cut -f2)

        arrows=""
        [[ "$ahead" -gt 0 ]] && arrows="${arrows}⇡${ahead}"
        [[ "$behind" -gt 0 ]] && arrows="${arrows}⇣${behind}"

        if [[ -n "$arrows" ]]; then
            git_arrows=$(printf " \033[38;5;87m%s\033[0m" "$arrows")
        fi
    fi
fi

# SSH/Container detection
ssh_info=""
if [[ -n "$SSH_CONNECTION" ]] || [[ -n "$SSH_CLIENT" ]] || [[ -n "$SSH_TTY" ]] ||
   [[ -f /.dockerenv ]] || [[ -n "$CONTAINER" ]] || [[ -n "$KUBERNETES_SERVICE_HOST" ]]; then
    username=$(whoami)
    hostname=$(hostname -s)
    ssh_info=$(printf " \033[38;5;242m%s@%s\033[0m" "$username" "$hostname")
fi

# Format context information
context_info=""
if [[ $tokens_used -gt 0 ]] && [[ $tokens_total -gt 0 ]]; then
    tokens_remaining=$((tokens_total - tokens_used))
    pct_remaining=$((tokens_remaining * 100 / tokens_total))

    # Format tokens in k (thousands)
    used_k=$((tokens_used / 1000))
    total_k=$((tokens_total / 1000))

    # Color based on percentage remaining
    if [[ $pct_remaining -gt 60 ]]; then
        # Brightest lime green - plenty of context (>60%)
        context_color="\033[38;5;154m"
    elif [[ $pct_remaining -gt 30 ]]; then
        # Brightest yellow - getting low (30-60%)
        context_color="\033[38;5;227m"
    else
        # Brightest red/pink - critical (<30%)
        context_color="\033[38;5;197m"
    fi

    # Format: "32k/200k (84%)" (used/total with % remaining)
    context_info=$(printf "${context_color}%dk/%dk (%d%%)\033[0m" "$used_k" "$total_k" "$pct_remaining")
fi

# Build the status line with components on separate lines:
# 1. pwd
# 2. git (branch, changes)
# 3. model
# 4. ctx

# 1. pwd - Pure white
printf "\033[38;5;231m%s\033[0m\n" "$display_path"

# 2. git (branch, changes)
if [[ -n "$git_info" ]] || [[ -n "$git_arrows" ]]; then
    printf "%s%s\n" "$git_arrows" "$git_info"
else
    printf "\n"
fi

# 3. model - Brightest magenta
printf "\033[38;5;201m%s\033[0m\n" "$model_name"

# 4. ctx
if [[ -n "$context_info" ]]; then
    printf "%s\n" "$context_info"
else
    printf "\n"
fi
```

## Display Output

The script outputs 4 lines:

1. **Path** - Working directory with ~ expansion (white)
2. **Git** - Branch name with dirty indicator (*) and push/pull arrows (white/red + cyan)
3. **Model** - Current model name (magenta)
4. **Context** - Token usage with color-coded percentage (green/yellow/red)

## Dependencies

- `jq` - JSON parsing
- `git` - Repository information
- Standard Unix utilities (`tac`, `awk`, `cut`)

## Context Color Coding

| Remaining | Color | Meaning |
|-----------|-------|---------|
| > 60% | Green | Plenty of context |
| 30-60% | Yellow | Getting low |
| < 30% | Red | Critical |
