#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: blocks Read/Grep/Glob access to credential files.

Config-driven via safety.yaml (credential_guardian section).
Default decision: DENY. Fail-close on errors.
"""

import json
import os
import re
import sys

# Import shared library via sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, is_in_prefixes, load_config, resolve_path

READ_TOOLS = {"Read", "Grep", "Glob"}


def _candidate_path(base_path: str, candidate: str) -> str | None:
    """Build a path candidate from a base path and possibly relative pattern."""
    if not candidate:
        return None
    if candidate.startswith(("/", "~/")):
        return candidate
    if not base_path:
        return candidate
    return os.path.join(base_path, candidate)


def _strip_glob_wildcards(path: str) -> str:
    """Extract the concrete directory prefix from a path that may contain glob wildcards."""
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if any(c in part for c in ("*", "?", "[", "{")):
            break
        parts.append(part)
    return "/".join(parts) if parts else path


# Blocked directory segments that should trigger blocking even when embedded in glob patterns.
# These are concrete names (no wildcards) that indicate sensitive directories.
_BLOCKED_SEGMENTS = {
    ".ssh", ".aws", ".config/gcloud", ".config/gh", ".azure", ".kube",
    ".docker", ".gnupg", ".terraform.d",
    "Library/Keychains", "Library/LaunchAgents",
    ".claude/debug", ".claude/.claude.json",
}


def _extract_blocked_segments_from_pattern(base_path: str, pattern: str) -> list[str]:
    """Extract synthetic paths from a glob pattern that contains blocked directory segments.

    When a pattern like '**/.ssh/*' is combined with base_path '~', wildcard stripping
    loses the '.ssh' component. This function recovers it by scanning the pattern for
    known blocked directory segments and synthesising paths to check.
    """
    results: list[str] = []
    if not pattern:
        return results
    # When base_path is empty, use CWD as the effective base
    if not base_path:
        base_path = os.getcwd()
    # Normalise pattern separators
    norm_pattern = pattern.replace("\\", "/")
    home = os.path.expanduser("~")
    real_base = os.path.realpath(os.path.expanduser(base_path))
    for segment in _BLOCKED_SEGMENTS:
        if segment in norm_pattern:
            # Build a synthetic path: base_path / segment
            candidate = os.path.join(base_path, segment)
            results.append(candidate)
            # If base_path is an ancestor of home (e.g. "/"), also generate
            # a home-relative candidate so blocked-prefix checks succeed.
            base_with_sep = real_base.rstrip("/") + "/"
            if home.startswith(base_with_sep) or home == real_base:
                home_candidate = os.path.join(home, segment)
                if home_candidate != os.path.realpath(os.path.expanduser(candidate)):
                    results.append(home_candidate)
    return results


def _extract_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Extract file-system path candidates from tool input."""
    raw_paths: list[str] = []
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            raw_paths.append(file_path)
    elif tool_name == "Grep":
        base_path = tool_input.get("path", "")
        if base_path:
            raw_paths.append(base_path)
        glob_pattern = tool_input.get("glob", "")
        candidate_path = _candidate_path(base_path, glob_pattern)
        if candidate_path:
            # Check both the full candidate and its concrete prefix (without wildcards)
            raw_paths.append(candidate_path)
            concrete = _strip_glob_wildcards(candidate_path)
            if concrete and concrete != candidate_path:
                raw_paths.append(concrete)
        # Also check for blocked segments hidden behind wildcards
        raw_paths.extend(_extract_blocked_segments_from_pattern(base_path, glob_pattern))
    elif tool_name == "Glob":
        base_path = tool_input.get("path", "")
        if base_path:
            raw_paths.append(base_path)
        pattern = tool_input.get("pattern", "")
        candidate_path = _candidate_path(base_path, pattern)
        if candidate_path:
            raw_paths.append(candidate_path)
            concrete = _strip_glob_wildcards(candidate_path)
            if concrete and concrete != candidate_path:
                raw_paths.append(concrete)
        # Also check for blocked segments hidden behind wildcards
        raw_paths.extend(_extract_blocked_segments_from_pattern(base_path, pattern))

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(raw_paths))


def _categorize_block(prefix: str) -> str:
    """Map a blocked prefix to its credential category."""
    p = prefix.rstrip("/").lower()
    if ".ssh" in p:
        return "ssh-keys"
    if any(s in p for s in (".aws", ".docker", ".config/gh", ".config/gcloud", ".azure", ".kube", ".terraform")):
        return "cloud-credentials"
    if ".gnupg" in p:
        return "cloud-credentials"
    if "library" in p:
        return "browser-credentials"
    if ".claude" in p:
        return "app-tokens"
    return "cloud-credentials"


def _is_blocked(
    path: str,
    blocked_prefixes: list[str],
    blocked_filenames: list[str],
    blocked_extensions: list[str],
    allowed_project_roots: list[str],
    allowed_claude_files: list[str],
) -> tuple[str | None, str]:
    """Returns (block_reason, category) or (None, '') if allowed."""
    resolved = resolve_path(path)

    # Always-blocked absolute prefixes (use is_in_prefixes logic for consistency)
    for prefix in blocked_prefixes:
        real_prefix = os.path.realpath(os.path.expanduser(prefix.rstrip("/")))
        if resolved.startswith(real_prefix + "/") or resolved == real_prefix:
            # Exception for explicitly allowed claude files
            if any(resolved == os.path.realpath(os.path.expanduser(f)) for f in allowed_claude_files):
                return None, ""
            category = _categorize_block(prefix)
            return f"Access to {prefix} is blocked (credential protection)", category

    # Blocked filenames: block outside project roots; inside home but outside project roots too
    basename = os.path.basename(resolved)
    home = os.path.expanduser("~")
    if basename in blocked_filenames:
        in_project = is_in_prefixes(path, allowed_project_roots + ["/private/tmp/", "/tmp/"])
        if in_project:
            pass  # Allow credential-named files inside project roots
        elif resolved.startswith(home + "/"):
            return f"Access to {basename} is blocked (credential file)", "app-tokens"
        else:
            return f"Access to {basename} outside project dirs is blocked (credential file)", "app-tokens"

    # Outside project roots: block sensitive extensions and .env
    if not is_in_prefixes(path, allowed_project_roots + ["/private/tmp/", "/tmp/"]):
        _, ext = os.path.splitext(resolved)
        if ext.lower() in blocked_extensions:
            return f"Access to {ext} files outside project dirs is blocked", "ssh-keys"
        if re.search(r"(^|/)\.env(\..+)?$", os.path.basename(resolved)):
            return "Access to .env files outside project dirs is blocked", "env-files"

    return None, ""


@fail_close
def main() -> None:
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name not in READ_TOOLS:
        allow()
        return

    config = load_config()
    cg = config.get("credential_guardian", {})
    if not isinstance(cg, dict):
        cg = {}

    blocked_prefixes: list[str] = cg.get("blocked_prefixes", [
        "~/.aws/", "~/.ssh/", "~/.config/gcloud/", "~/.config/gh/", "~/.azure/", "~/.kube/",
        "~/.docker/", "~/.gnupg/", "~/.terraform.d/",
        "~/Library/", "~/.claude/debug/", "~/.claude/.claude.json",
    ])
    blocked_filenames: list[str] = cg.get("blocked_filenames", [
        ".npmrc", ".netrc", ".pypirc", ".git-credentials", ".vault-token",
    ])
    blocked_extensions: list[str] = cg.get("blocked_extensions", [".pem", ".key", ".p12", ".pfx"])
    allowed_project_roots: list[str] = config.get("allowed_project_roots", ["~/projects/"])
    allowed_claude_files: list[str] = cg.get("allowed_claude_files", [
        "~/.claude/settings.json", "~/.claude/settings.local.json", "~/.claude/CLAUDE.md",
    ])

    # Detect broad recursive scans that could reach credential directories.
    # When base_path is HOME or an ancestor of HOME and the pattern contains **,
    # the scan could enumerate ~/.ssh, ~/.aws, etc.
    base_path = ""
    pattern = ""
    if tool_name == "Glob":
        base_path = tool_input.get("path", "")
        pattern = tool_input.get("pattern", "")
    elif tool_name == "Grep":
        base_path = tool_input.get("path", "")
        pattern = tool_input.get("glob", "")

    # When base_path is empty/falsy, the tool resolves from CWD.
    # Substitute CWD so broad-scan and blocked-segment checks still fire.
    if not base_path and (tool_name in ("Glob", "Grep")):
        base_path = os.getcwd()
        # Propagate the effective base_path into tool_input so _extract_paths
        # also benefits from the substitution.
        if tool_name == "Glob":
            tool_input = {**tool_input, "path": base_path}
        elif tool_name == "Grep":
            tool_input = {**tool_input, "path": base_path}

    if base_path and pattern and "**" in pattern:
        resolved_base = os.path.realpath(os.path.expanduser(base_path))
        home = os.path.realpath(os.path.expanduser("~"))
        # Check if base_path is HOME or an ancestor of HOME
        is_home_or_ancestor = (
            resolved_base == home
            or home.startswith(resolved_base.rstrip("/") + "/")
        )
        if is_home_or_ancestor and not is_in_prefixes(base_path, allowed_project_roots):
            reason = f"Recursive scan from {base_path} could reach credential directories"
            category = "broad-scan"
            decision = get_category_decision(config, "credential_guardian", category)
            if decision == "deny":
                deny(f"BLOCKED: {reason}")
            elif decision == "ask":
                ask(f"{reason} -- confirm to proceed?")
            else:
                allow()
            return

    paths = _extract_paths(tool_name, tool_input)
    for path in paths:
        reason, category = _is_blocked(path, blocked_prefixes, blocked_filenames, blocked_extensions, allowed_project_roots, allowed_claude_files)
        if reason:
            # Default to deny if category not found (fail-close)
            decision = get_category_decision(config, "credential_guardian", category) if category else "deny"
            if decision == "deny":
                deny(f"BLOCKED: {reason}")
            elif decision == "ask":
                ask(f"{reason} -- confirm to proceed?")
            else:
                allow()
            return

    allow()


if __name__ == "__main__":
    main()
