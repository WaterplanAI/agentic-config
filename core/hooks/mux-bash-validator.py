#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# ARCHIVED: Superseded by skill-scoped hooks in mux.md and mux-subagent.md frontmatter.
# Kept for reference only. Not registered in settings.json.
# See: .claude/skills/mux/cookbook/hooks.md for current architecture.
"""ARCHIVED - Superseded by skill-scoped hooks.

Original purpose: MUX Compliance: Whitelist Bash commands during MUX skill execution.

Exit Code Strategy:
- SDK reads JSON response from stdout only
- Exit code 0: Hook executed successfully (SDK reads permissionDecision from JSON)
- Exit code 2: Hook failed (fail-closed, SDK blocks regardless of JSON)
"""
import json
import os
import re
import sys

FORBIDDEN_COMMANDS = ["gh", "git", "npm", "npx", "cdk", "grep", "rg", "cat", "head", "tail", "curl", "wget", "python", "node"]
ALLOWED_PATTERNS = [
    r"^mkdir\s+-p\s+",
    r"^uv\s+run\s+tools/",
    r"^ls\s+"
]

def is_mux_active() -> bool:
    """Check if MUX skill is active via session marker or env var."""
    if os.environ.get("MUX_ACTIVE") == "1":
        return True
    # Future: Check outputs/session/{pid}/mux-active marker
    return False

def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})

        # If MUX not active, allow (exit 0)
        if not is_mux_active():
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}))
            sys.exit(0)

        if tool_name == "Bash":
            cmd = tool_input.get("command", "")

            # Check forbidden commands
            for forbidden in FORBIDDEN_COMMANDS:
                if forbidden in cmd:
                    print(json.dumps({
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"MUX VIOLATION: Bash '{forbidden}' forbidden. Delegate to agent."
                        }
                    }))
                    sys.exit(0)

            # Check allowed patterns
            if not any(re.match(pattern, cmd.strip()) for pattern in ALLOWED_PATTERNS):
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"MUX VIOLATION: Bash command not in allowlist: {cmd[:50]}..."
                    }
                }))
                sys.exit(0)

        # Otherwise allow (exit 0)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}))
        sys.exit(0)
    except Exception as e:
        # Fail-closed: Exit 2 blocks execution regardless of JSON
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Hook error (fail-closed): {e}"
            }
        }), file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
