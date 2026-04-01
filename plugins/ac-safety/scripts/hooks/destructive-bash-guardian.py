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
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, load_config, resolve_path

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

# gh CLI read-only subcommands: excluded from external-visibility blocking
_GH_READ_ONLY = r"(?:list|view|status|checks|diff|download|checkout)\b"


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


# File-reading commands that can expose credential file contents
_FILE_READER_COMMANDS: tuple[str, ...] = (
    "cat", "head", "tail", "less", "more", "od", "xxd", "hexdump",
    "strings", "base64", "openssl", "sed", "awk", "grep", "sort",
    "tee", "cp", "scp", "tar", "zip", "rsync", "mv", "ln", "diff",
    "nl", "cut", "paste", "fold", "fmt", "rev", "pr", "dd", "install",
)
_FILE_READER_COMMAND_SET = set(_FILE_READER_COMMANDS)
_FILE_READERS = r"(?:" + "|".join(re.escape(command) for command in _FILE_READER_COMMANDS) + r")"

# Credential paths: (regex_suffix, description)
# Kept in sync with safety.default.yaml credential_guardian.blocked_prefixes
_CREDENTIAL_PATHS: list[tuple[str, str]] = [
    (r"~/.ssh/", "SSH directory"),
    (r"~/.aws/", "AWS directory"),
    (r"/\.ssh/", "SSH directory (absolute)"),
    (r"/\.aws/", "AWS directory (absolute)"),
    (r"~/.config/gh/", "GitHub CLI config"),
    (r"/\.config/gh/", "GitHub CLI config (absolute)"),
    (r"~/.config/gcloud/", "GCP credentials"),
    (r"/\.config/gcloud/", "GCP credentials (absolute)"),
    (r"~/.azure/", "Azure credentials"),
    (r"/\.azure/", "Azure credentials (absolute)"),
    (r"~/.kube/", "Kubernetes config"),
    (r"/\.kube/", "Kubernetes config (absolute)"),
    (r"~/.gnupg/", "GnuPG directory"),
    (r"/\.gnupg/", "GnuPG directory (absolute)"),
    (r"~/.terraform\.d/", "Terraform credentials"),
    (r"/\.terraform\.d/", "Terraform credentials (absolute)"),
    (r"~/.npmrc\b", "npmrc"),
    (r"/\.npmrc\b", "npmrc (absolute)"),
    (r"~/.netrc\b", "netrc"),
    (r"/\.netrc\b", "netrc (absolute)"),
    (r"~/.docker/", "Docker config"),
    (r"/\.docker/", "Docker config (absolute)"),
    (r"~/Library/", "macOS Library directory"),
    (r"/Library/", "macOS Library directory (absolute)"),
    (r"~/.claude/debug/", "Claude debug directory"),
    (r"/\.claude/debug/", "Claude debug directory (absolute)"),
    (r"~/.claude/\.claude\.json\b", "Claude API tokens"),
    (r"/\.claude/\.claude\.json\b", "Claude API tokens (absolute)"),
]


def _credential_read_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Build credential-read patterns for all file-reading commands."""
    patterns: list[tuple[re.Pattern[str], str, str]] = []
    for path_re, description in _CREDENTIAL_PATHS:
        patterns.append((
            re.compile(r"\b" + _FILE_READERS + r"\s+.*" + path_re),
            f"file reader accessing {description}",
            "credential-reads",
        ))
    return patterns


def _split_args(command: str) -> list[str]:
    """Split a shell command into argv, falling back on whitespace."""
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _extract_command_name(args: list[str]) -> tuple[str, list[str]]:
    """Return the invoked command name and its trailing args.

    Skips common shell wrappers such as ``env`` and leading environment
    assignments so ``env FOO=1 cat ~/.*/id_rsa`` still resolves to ``cat``.
    """
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", arg):
            idx += 1
            continue
        if arg in {"env", "command", "builtin", "exec", "sudo"}:
            idx += 1
            continue
        return arg, args[idx + 1:]
    return "", []


def _strip_assignment_prefix(arg: str) -> str:
    """Strip option-style assignment prefixes such as ``if=`` from an arg."""
    if "=" not in arg:
        return arg
    _, value = arg.split("=", 1)
    return value or arg


def _is_hidden_dir_wildcard_arg(arg: str) -> bool:
    """Return True for HOME-relative wildcard scans over hidden directories.

    Examples: ``~/.*/id_rsa``, ``$HOME/.[a-z]*/config``, ``/home/u/.*/``,
    and option forms such as ``if=~/.*/id_rsa``.
    These shell globs can expand into credential directories such as ``~/.ssh``
    and ``~/.aws`` even without naming them explicitly.
    """
    home = os.path.expanduser("~")
    prefixes = ("~/", "$HOME/", "${HOME}/", home.rstrip("/") + "/")
    normalized = _strip_assignment_prefix(arg).rstrip("/")
    for prefix in prefixes:
        if not normalized.startswith(prefix):
            continue
        relative = normalized[len(prefix):]
        first_segment = relative.split("/", 1)[0]
        return first_segment.startswith(".") and any(token in first_segment for token in ("*", "?", "[", "{"))
    return False


def _has_hidden_dir_glob_credential_read(command: str) -> bool:
    """Return True when a file-reader scans wildcard hidden dirs under HOME."""
    args = _split_args(command)
    if not args:
        return False
    command_name, trailing_args = _extract_command_name(args)
    if command_name not in _FILE_READER_COMMAND_SET:
        return False
    return any(_is_hidden_dir_wildcard_arg(arg) for arg in trailing_args)


# Map: (compiled_pattern, reason, category)
# Category names match safety.yaml destructive_bash.categories keys
PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # -- file-destruction --
    # NOTE: rm patterns match broadly (no hard-coded project exclusions).
    # Post-match filtering in main() checks allowed_project_roots from config.
    (re.compile(_BIN + r"\brm\s+(-[^\s]*)*\s*-[rR].*(" + re.escape(os.path.expanduser("~")) + r"[/\s]|~/|/Users/\w+/)"), "rm -r targeting home or user directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"/\S"), "rm -rf targeting absolute path", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"~/"), "rm -rf targeting home subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"~" + _OPT_QUOTE + _END), "rm -rf targeting entire home directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"\.\." + _END), "rm -rf targeting parent directory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + r"\.\./"), "rm -rf targeting parent-relative path", "file-destruction"),
    # $HOME / ${HOME} variable expansion (combined -rf flags)
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$HOME" + _END), "rm -rf targeting $HOME", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$\{HOME\}" + _END), "rm -rf targeting ${HOME}", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$HOME/"), "rm -rf targeting $HOME subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF + _OPT_QUOTE + r"\$\{HOME\}/"), "rm -rf targeting ${HOME} subdirectory", "file-destruction"),
    # Split flags: rm -r -f ~ / rm -f -r ~
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"/\S"), "rm with split flags targeting absolute path", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + r"~/"), "rm with split flags targeting home subdirectory", "file-destruction"),
    (re.compile(_BIN + r"\brm\s+" + _RM_RF_SPLIT + _OPT_QUOTE + r"~" + _OPT_QUOTE + _END), "rm with split flags targeting entire home directory", "file-destruction"),
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
    # Force push via refspec: git push <remote> +<ref>:<ref>
    (re.compile(r"\bgit\s+push\s+\S+\s+\+"), "git push with + refspec (force push via refspec)", "git-destructive"),
    # Delete remote branch via empty refspec: git push <remote> :<branch>
    (re.compile(r"\bgit\s+push\s+\S+\s+:"), "git push with : refspec (delete remote branch)", "git-destructive"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard", "git-destructive"),
    (re.compile(r"\bgit\s+clean\s+(-[^\s]*)*-[fd]"), "git clean -f/-d", "git-destructive"),
    (re.compile(r"\bgit\s+stash\s+clear\b"), "git stash clear", "git-destructive"),
    (re.compile(r"\bgit\s+reflog\s+expire\b"), "git reflog expire", "git-destructive"),
    (re.compile(r"\bgit\s+gc\s+.*--prune=now"), "git gc --prune=now", "git-destructive"),
    (re.compile(r"\bgit\s+filter-branch\b"), "git filter-branch", "git-destructive"),
    (re.compile(r"\bgit\s+push\s+\S+\s+--delete\b"), "git push --delete (remote branch deletion)", "git-destructive"),
    (re.compile(r"\bgit\s+checkout\s+\.\s*$"), "git checkout . (discard all changes)", "git-destructive"),
    (re.compile(r"\bgit\s+restore\s+\.\s*$"), "git restore . (discard all changes)", "git-destructive"),
    # gh repo delete is irreversible — categorized as git-destructive, not external-visibility
    (re.compile(r"\bgh\s+repo\s+delete\b"), "gh repo delete (irreversible repository deletion)", "git-destructive"),
    # -- credential-reads --
    # Any file-reading or file-copying command accessing credential paths is blocked.
    # _FILE_READERS covers: cat, head, tail, less, more, od, xxd, hexdump,
    # strings, base64, openssl, sed, awk, grep, sort, tee, cp, scp,
    # diff, nl, cut, paste, fold, fmt, rev, pr, dd, install
    *_credential_read_patterns(),
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
    (re.compile(_BIN + r"\bterraform\s+apply\b"), "terraform apply (can implicitly destroy resources)", "iac-destruction"),
    (re.compile(_BIN + r"\bpulumi\s+destroy\b"), "pulumi destroy", "iac-destruction"),
    (re.compile(_BIN + r"\bpulumi\s+up\b"), "pulumi up (can implicitly destroy resources)", "iac-destruction"),
    # npx pattern handles optional flags between npx and cdk (e.g. npx --yes cdk deploy)
    (re.compile(_BIN + r"\bnpx\s+(?:--?\S+\s+)*cdk\s+(deploy|destroy|bootstrap|watch)\b"), "cdk deploy/destroy/bootstrap/watch via npx (can implicitly destroy resources)", "iac-destruction"),
    (re.compile(_BIN + r"\bcdk\s+(deploy|destroy|bootstrap|watch)\b"), "cdk deploy/destroy/bootstrap/watch (can implicitly destroy resources)", "iac-destruction"),
    # -- privilege-escalation --
    (re.compile(_BIN + r"\bsudo(\s|$)"), "sudo (privilege escalation)", "privilege-escalation"),
    (re.compile(_BIN + r"\bsu(\s|$)"), "su (privilege escalation)", "privilege-escalation"),
    (re.compile(_BIN + r"\bdoas(\s|$)"), "doas (privilege escalation)", "privilege-escalation"),
    # -- credential-reads (gh secrets — more restrictive than external-visibility) --
    (re.compile(r"\bgh\s+secret\s+(?!list\b)\w+"), "gh secret write/delete (credential operation)", "credential-reads"),
    # -- external-visibility --
    # ORDERING INVARIANT: git-destructive patterns must precede external-visibility
    # to ensure force-push detection fires first. Negative lookahead covers both
    # --force and -f shorthand as defense-in-depth.
    (re.compile(r"\bgit\s+push\b(?!.*(?:--force(?!-with-lease)\b|-[a-eg-zA-Z]*f\b))"), "git push (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+pr\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh pr write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+issue\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh issue write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+workflow\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh workflow operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+release\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh release operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+repo\s+(?!" + _GH_READ_ONLY + r"|clone\b)\w+"), "gh repo write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+label\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh label write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+variable\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh variable write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+environment\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh environment write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+ruleset\s+(?!" + _GH_READ_ONLY + r")\w+"), "gh ruleset write operation (visible to teammates)", "external-visibility"),
    (re.compile(r"\bgh\s+api\s+.*-X\s*(?:POST|PUT|DELETE|PATCH)\b"), "gh api write operation (visible to teammates)", "external-visibility"),
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


def _normalize_rm_target(arg: str) -> str | None:
    """Normalize a candidate rm target into a resolved path when possible."""
    cleaned = arg.replace('"', "").replace("'", "").strip("`()")
    cleaned = cleaned.replace("${HOME}", os.path.expanduser("~"))
    cleaned = cleaned.replace("$HOME", os.path.expanduser("~"))
    if cleaned.startswith(("/", "~")):
        return resolve_path(cleaned)
    return None


def _extract_rm_targets(command: str) -> list[str]:
    """Extract target paths from an rm command for project-root checks.

    Returns resolved absolute paths found after rm flags.
    Only extracts paths that start with /, ~, $HOME, or ${HOME}.
    """
    args = _split_args(command)
    if not args:
        return []

    command_name, trailing_args = _extract_command_name(args)
    if os.path.basename(command_name) != "rm":
        return []

    targets: list[str] = []
    past_flags = False
    for arg in trailing_args:
        if arg == "--":
            past_flags = True
            continue
        if not past_flags and arg.startswith("-"):
            continue
        normalized = _normalize_rm_target(arg)
        if normalized:
            targets.append(normalized)
    return targets


def _is_within_allowed_roots(targets: list[str], allowed_roots: list[str]) -> bool:
    """Check if ALL extracted targets are within allowed project roots."""
    if not targets:
        return False
    for target in targets:
        in_root = False
        for root in allowed_roots:
            resolved_root = resolve_path(root.rstrip("/"))
            if target.startswith(resolved_root + "/") or target == resolved_root:
                in_root = True
                break
        if not in_root:
            return False
    return True


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
    allowed_project_roots: list[str] = config.get("allowed_project_roots", ["~/projects/"])

    if _has_hidden_dir_glob_credential_read(command):
        decision = get_category_decision(config, "destructive_bash", "credential-reads")
        reason = "file reader scanning wildcard hidden directory under home"
        if decision == "deny":
            deny(f"BLOCKED: {reason}. Command denied by destructive-bash-guardian.")
        elif decision == "ask":
            ask(f"{reason} -- confirm to proceed?")
        else:
            allow()
        return

    for pattern, reason, category in PATTERNS:
        if pattern.search(command):
            # For file-destruction patterns (rm commands), check if the target
            # is within allowed project roots. If so, allow it.
            if category == "file-destruction" and "rm" in reason.lower():
                targets = _extract_rm_targets(command)
                if targets and _is_within_allowed_roots(targets, allowed_project_roots):
                    allow()
                    return

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
