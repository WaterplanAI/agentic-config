#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: blocks destructive bash commands.

Config-driven per-category decisions via safety.yaml (destructive_bash section).
Default decision: DENY. Fail-close on errors.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, load_config

# Optional path prefix for system binaries (covers /bin/rm, /usr/bin/rm,
# /usr/local/bin/rm, /usr/local/sbin/rm, etc.)
_BIN = r"(?:(?:/usr(?:/local)?)?/s?bin/)?"

# End-of-target anchor: whitespace, EOL, or shell metacharacters
_END = r"""(\s|$|[);\x60|&"'])"""

# Optional quote prefix: matches 0 or 1 leading quote (single or double)
_OPT_QUOTE = r"""["']?"""

# rm flags pattern: matches combined flags like -rf or split flags like -r -f / -f -r
# Also handles POSIX -- end-of-options separator
_RM_RF = r"(-[^\s]*\s+)*-rf\s+(?:--\s+)?"
_RM_RF_SPLIT = r"(-[^\s]*\s+)*(-[^\s]*[rR][^\s]*\s+(-[^\s]*\s+)*-[^\s]*f[^\s]*|-[^\s]*f[^\s]*\s+(-[^\s]*\s+)*-[^\s]*[rR][^\s]*)\s+(?:--\s+)?"

# Shells (for herestring, source, eval -- contexts where only shells make sense)
_SHELL_RE = r"(?:sh|bash|zsh|dash)"
# Executors (for pipe-to, process substitution, download-then-execute -- any interpreter)
_EXEC_RE = r"(?:sh|bash|zsh|dash|python[23]?|perl|ruby|node)"


def _rce_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Build remote-code-execution patterns using shared shell/exec constants."""
    return [
        # Pipe-to-exec: curl ... | [env|exec] [/usr/bin/]<executor>
        (re.compile(r"\bcurl\b.*\|\s*(?:env\s+|exec\s+)?" + _BIN + _EXEC_RE + r"\b"), "curl piped to shell/interpreter (remote code execution)", "remote-code-execution"),
        # Pipe-to-exec: wget ... | [env|exec] [/usr/bin/]<executor>
        (re.compile(r"\bwget\b.*\|\s*(?:env\s+|exec\s+)?" + _BIN + _EXEC_RE + r"\b"), "wget piped to shell/interpreter (remote code execution)", "remote-code-execution"),
        # Reverse pattern: <executor> -c "$(curl ...)" or <executor> -c "$(wget ...)"
        (re.compile(r"(?:env\s+|exec\s+)?" + _BIN + _EXEC_RE + r"\s+-c\s+.*\$\(\s*(?:curl|wget)\b"), "shell/interpreter -c with curl/wget subshell (remote code execution)", "remote-code-execution"),
        # Process substitution: <executor> <(curl ...) or <executor> <(wget ...)
        (re.compile(r"(?:env\s+|exec\s+)?" + _BIN + _EXEC_RE + r"\s+<\(\s*(?:curl|wget)\b"), "shell/interpreter with process substitution (remote code execution)", "remote-code-execution"),
        # eval with curl/wget subshell: eval $(curl ...) or eval $(wget ...)
        (re.compile(r"\beval\s+.*\$\(\s*(?:curl|wget)\b"), "eval with curl/wget subshell (remote code execution)", "remote-code-execution"),
        # source / . with process substitution: source <(curl ...) or . <(curl ...)
        (re.compile(r"(?:\bsource|\.\s)\s*<\(\s*(?:curl|wget)\b"), "source with process substitution (remote code execution)", "remote-code-execution"),
        # HIGH-001: download-to-file-then-execute: curl -o/wget -O/> redirect, then exec
        (re.compile(r"\b(?:curl|wget)\b.*(?:-o\s*|-O\s*|>\s*)\S+.*[;&|]+\s*(?:(?:" + _EXEC_RE + r"|source|\.)\s|chmod\s)"), "download-to-file then execute (remote code execution)", "remote-code-execution"),
        # HIGH-002: bare command substitution with curl/wget at command position
        (re.compile(r"\$\(\s*(?:curl|wget)\b"), "bare command substitution with curl/wget (remote code execution)", "remote-code-execution"),
        (re.compile(r"`\s*(?:curl|wget)\b"), "bare backtick substitution with curl/wget (remote code execution)", "remote-code-execution"),
        # MEDIUM-001: xargs laundering to shell/interpreter
        (re.compile(r"\bxargs\s+.*" + _EXEC_RE + r"\b"), "xargs invoking shell/interpreter (remote code execution)", "remote-code-execution"),
        # MEDIUM-002: herestring delivery to shell
        (re.compile(_SHELL_RE + r"\s+<<<"), "shell with herestring input (remote code execution)", "remote-code-execution"),
    ]


# Map: (compiled_pattern, reason, category)
# Category names match safety.yaml destructive_bash.categories keys
PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # -- file-destruction --
    (re.compile(_BIN + r"\brm\s+(-[^\s]*)*\s*-[rR].*(" + re.escape(os.path.expanduser("~")) + r"[/\s]|~/|/Users/\w+/(?!projects/))"), "rm -r targeting home or outside project", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"/(?!Users/\w+/projects/)"), "rm -rf targeting system or non-project path", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"~/(?!projects/)"), "rm -rf targeting home subdirectory outside project", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"~" + _END), "rm -rf targeting entire home directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"\.\." + _END), "rm -rf targeting parent directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"\.\./"), "rm -rf targeting parent-relative path", "file-destruction"),
    # $HOME / ${HOME} variable expansion (combined -rf flags)
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$HOME" + _END), "rm -rf targeting $HOME", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$\{HOME\}" + _END), "rm -rf targeting ${HOME}", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$HOME/"), "rm -rf targeting $HOME subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$\{HOME\}/"), "rm -rf targeting ${HOME} subdirectory", "file-destruction"),
    # Split flags: rm -r -f ~ / rm -f -r ~
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"/(?!Users/\w+/projects/)"), "rm with split flags targeting system path", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"~/(?!projects/)"), "rm with split flags targeting home subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"~" + _END), "rm with split flags targeting entire home directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"\.\." + _END), "rm with split flags targeting parent directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"\.\./"), "rm with split flags targeting parent-relative path", "file-destruction"),
    # $HOME / ${HOME} variable expansion (split flags)
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + _OPT_QUOTE + r"\$HOME" + _END), "rm with split flags targeting $HOME", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + _OPT_QUOTE + r"\$\{HOME\}" + _END), "rm with split flags targeting ${HOME}", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + _OPT_QUOTE + r"\$HOME/"), "rm with split flags targeting $HOME subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + _OPT_QUOTE + r"\$\{HOME\}/"), "rm with split flags targeting ${HOME} subdirectory", "file-destruction"),
    # find -delete / find -exec rm (recursive deletion)
    (re.compile(r"\bfind\s+.*\s+-delete\b"), "find with -delete (recursive deletion)", "file-destruction"),
    (re.compile(r"\bfind\s+.*\s+-exec\s+" + _BIN + r"rm\b"), "find with -exec rm (recursive deletion)", "file-destruction"),
    # xargs rm (indirect deletion)
    (re.compile(r"\bxargs\s+.*" + _BIN + r"rm\b"), "xargs rm (indirect deletion)", "file-destruction"),
    # -- aws-destructive --
    (re.compile(r"\baws\s+s3\s+rb\b"), "aws s3 rb (bucket removal)", "aws-destructive"),
    (re.compile(r"\baws\s+s3\s+rm\s+.*--recursive\b"), "aws s3 rm --recursive", "aws-destructive"),
    (re.compile(r"\baws\s+cloudformation\s+delete-stack\b"), "aws cloudformation delete-stack", "aws-destructive"),
    (re.compile(r"\baws\s+lambda\s+delete-function\b"), "aws lambda delete-function", "aws-destructive"),
    (re.compile(r"\baws\s+dynamodb\s+delete-table\b"), "aws dynamodb delete-table", "aws-destructive"),
    (re.compile(r"\baws\s+rds\s+delete-db-instance\b"), "aws rds delete-db-instance", "aws-destructive"),
    (re.compile(r"\baws\s+rds\s+delete-db-cluster\b"), "aws rds delete-db-cluster", "aws-destructive"),
    (re.compile(r"\baws\s+ec2\s+terminate-instances\b"), "aws ec2 terminate-instances", "aws-destructive"),
    (re.compile(r"\baws\s+iam\s+delete-(role|user|policy|group)\b"), "aws iam delete operation", "aws-destructive"),
    (re.compile(r"\baws\s+iam\s+attach-role-policy\b"), "aws iam attach-role-policy (privilege escalation)", "aws-destructive"),
    (re.compile(r"\baws\s+secretsmanager\s+delete-secret\b"), "aws secretsmanager delete-secret", "aws-destructive"),
    (re.compile(r"\baws\s+eks\s+delete-cluster\b"), "aws eks delete-cluster", "aws-destructive"),
    (re.compile(r"\baws\s+ecr\s+delete-repository\b"), "aws ecr delete-repository", "aws-destructive"),
    # -- git-destructive --
    (re.compile(r"\bgit\s+push\s+.*--force(?!-with-lease)\b"), "git push --force (use --force-with-lease)", "git-destructive"),
    (re.compile(r"\bgit\s+push\s+(-[^\s]*\s+)*-[a-eg-zA-Z]*f\b"), "git push -f (force push, combined flags)", "git-destructive"),
    (re.compile(r"\bgit\s+push\s+.+\s+-[a-eg-zA-Z]*f\b"), "git push <args> -f (force push, trailing)", "git-destructive"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard", "git-destructive"),
    (re.compile(r"\bgit\s+clean\s+(-[^\s]*)*-[fd]"), "git clean -f/-d", "git-destructive"),
    (re.compile(r"\bgit\s+stash\s+clear\b"), "git stash clear", "git-destructive"),
    (re.compile(r"\bgit\s+reflog\s+expire\b"), "git reflog expire", "git-destructive"),
    (re.compile(r"\bgit\s+gc\s+.*--prune=now"), "git gc --prune=now", "git-destructive"),
    (re.compile(r"\bgit\s+filter-branch\b"), "git filter-branch", "git-destructive"),
    (re.compile(r"\bgit\s+push\s+\S+\s+--delete\b"), "git push --delete (remote branch deletion)", "git-destructive"),
    (re.compile(r"\bgit\s+checkout\s+\.\s*$"), "git checkout . (discard all changes)", "git-destructive"),
    (re.compile(r"\bgit\s+restore\s+\.\s*$"), "git restore . (discard all changes)", "git-destructive"),
    # -- credential-reads --
    (re.compile(r"\bcat\s+.*~/.ssh/"), "cat reading SSH directory", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.aws/"), "cat reading AWS directory", "credential-reads"),
    (re.compile(r"\bcat\s+.*/\.ssh/"), "cat reading SSH directory (absolute)", "credential-reads"),
    (re.compile(r"\bcat\s+.*/\.aws/"), "cat reading AWS directory (absolute)", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.config/gh/"), "cat reading GitHub CLI config", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.config/gcloud/"), "cat reading GCP credentials", "credential-reads"),
    (re.compile(r"\bcat\s+.*/\.config/gcloud/"), "cat reading GCP credentials (absolute)", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.azure/"), "cat reading Azure credentials", "credential-reads"),
    (re.compile(r"\bcat\s+.*/\.azure/"), "cat reading Azure credentials (absolute)", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.kube/"), "cat reading Kubernetes config", "credential-reads"),
    (re.compile(r"\bcat\s+.*/\.kube/"), "cat reading Kubernetes config (absolute)", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.terraform\.d/"), "cat reading Terraform credentials", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.npmrc\b"), "cat reading npmrc", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.netrc\b"), "cat reading netrc", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.docker/"), "cat reading Docker config", "credential-reads"),
    (re.compile(r"\bcat\s+.*~/.claude/\.claude\.json\b"), "cat reading Claude API tokens", "credential-reads"),
    (re.compile(r"\bsecurity\s+(find|dump)-.*keychain"), "macOS Keychain access", "credential-reads"),
    # -- data-exfiltration --
    (re.compile(r"\bcurl\s+.*-X\s*POST\b"), "curl POST (potential exfiltration)", "data-exfiltration"),
    (re.compile(r"\bcurl\s+.*--data\b"), "curl --data (potential exfiltration)", "data-exfiltration"),
    (re.compile(r"\bcurl\s+.*-d\s"), "curl -d (potential exfiltration)", "data-exfiltration"),
    (re.compile(r"\bwget\s+.*--post"), "wget POST (potential exfiltration)", "data-exfiltration"),
    (re.compile(r"\bnslookup\s+.*\$\("), "DNS exfiltration attempt", "data-exfiltration"),
    (re.compile(r"\bdig\s+.*\$\("), "DNS exfiltration attempt", "data-exfiltration"),
    # -- process-destruction --
    (re.compile(_BIN + r"\bkill\s+-9\s+-1\b"), "kill all user processes", "process-destruction"),
    (re.compile(_BIN + r"\bkillall\s+-9\b"), "killall -9", "process-destruction"),
    (re.compile(_BIN + r"\bpkill\s+-9\b"), "pkill -9", "process-destruction"),
    (re.compile(_BIN + r"\bpkill\s+-u\s"), "pkill by user (mass kill)", "process-destruction"),
    # -- permission-abuse --
    (re.compile(_BIN + r"\bchmod\s+(-[^\s]+\s+)*777\b"), "chmod 777", "permission-abuse"),
    (re.compile(_BIN + r"\bchmod\s+-[Rr].*777"), "recursive chmod 777", "permission-abuse"),
    # -- persistence --
    (re.compile(r"\bcrontab\b"), "crontab modification", "persistence"),
    (re.compile(r"LaunchAgents"), "LaunchAgent persistence", "persistence"),
    (re.compile(r"\bnohup\s+"), "nohup background process", "persistence"),
    # -- system-level --
    (re.compile(r"\bmkfs\."), "filesystem format", "system-level"),
    (re.compile(r"\bdd\s+.*of=/dev/"), "dd to device", "system-level"),
    (re.compile(r":\(\)\{.*\|.*&.*\};:"), "fork bomb", "system-level"),
    # -- iac-destruction --
    (re.compile(_BIN + r"\bterraform\s+destroy\b"), "terraform destroy", "iac-destruction"),
    (re.compile(_BIN + r"\bpulumi\s+destroy\b"), "pulumi destroy", "iac-destruction"),
    # -- docker-destruction --
    (re.compile(_BIN + r"\bdocker\s+system\s+prune\s+-a\b"), "docker system prune -a", "docker-destruction"),
    (re.compile(_BIN + r"\bdocker\s+volume\s+prune\b"), "docker volume prune", "docker-destruction"),
    # -- npm-publish --
    (re.compile(r"\bnpm\s+publish\b"), "npm publish", "npm-publish"),
    (re.compile(r"\bnpm\s+unpublish\b"), "npm unpublish", "npm-publish"),
    # -- remote-code-execution --
    # Reusable fragments for RCE patterns:
    #   _SHELL_RE: shells only (for eval, source, herestring -- shell-only contexts)
    #   _EXEC_RE:  shells + interpreters (for pipe-to, process subst, download-exec)
    *_rce_patterns(),
]


@fail_close
def main() -> None:
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name != "Bash":
        allow()
        return

    command = tool_input.get("command", "")
    config = load_config()

    for pattern, reason, category in PATTERNS:
        if pattern.search(command):
            decision = get_category_decision(config, "destructive_bash", category)
            if decision == "deny":
                deny(f"BLOCKED: {reason}. Command denied by destructive-bash-guardian.")
            elif decision == "ask":
                ask(f"{reason} -- confirm to proceed?")
            # else: allow (fall through)
            else:
                allow()
            return

    allow()


if __name__ == "__main__":
    main()
