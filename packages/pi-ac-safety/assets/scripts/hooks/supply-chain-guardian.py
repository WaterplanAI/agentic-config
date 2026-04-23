#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PreToolUse hook: blocks unapproved package installations.

Config-driven via safety.yaml (supply_chain section).
Default category decisions: ASK. Fail-close on errors.
"""

import json
import os
import re
import shlex
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, build_permission_decision_metadata, deny, fail_close, get_category_decision, load_config

# Patterns that are SAFE (skip blocking).
# These are applied per-segment (after splitting on shell operators).
# Patterns must be tight -- they should not match when extra package args follow.
#
# Path restrictions for -r/--requirement and -e/--editable:
#   - Requirement files: relative paths only (no :// schemes, no absolute paths starting
#     with / or ~). Safe examples: requirements.txt, requirements/dev.txt, ./req.txt
#   - Editable installs: only . or .[extras] (current directory editable install)
_SAFE_REQ_PATH = r"(?![/~]|\.\.|\S*://)[^\s]+"  # relative path, no URL scheme, no absolute, no ../
_SAFE_EDITABLE = r"\.(?:\[\S+\])?"  # . or .[extras]

SAFE_PATTERNS = [
    re.compile(r"\bnpm\s+(install|ci|i)\s*$"),
    re.compile(
        r"\bnpm\s+(install|ci|i)\s+--(legacy-peer-deps|prefer-offline|no-audit"
        r"|ignore-scripts|frozen-lockfile|no-optional|no-save|production)\s*$"
    ),
    # pip install from requirements (relative path) / editable (. only) / current-dir only
    re.compile(
        r"\bpip3?\s+install\s+"
        r"((?:-r|--requirement)[=\s]" + _SAFE_REQ_PATH +
        r"|(?:-e|--editable)[=\s]" + _SAFE_EDITABLE +
        r"|\.)\s*$"
    ),
    re.compile(r"\buv\s+sync\s*$"),
    # uv pip install from requirements (relative path) / editable (. only) / current-dir only
    re.compile(
        r"\buv\s+pip\s+install\s+"
        r"((?:-r|--requirement)[=\s]" + _SAFE_REQ_PATH +
        r"|(?:-e|--editable)[=\s]" + _SAFE_EDITABLE +
        r"|\.)\s*$"
    ),
    re.compile(r"\buv\s+pip\s+compile\b"),
]


def _apply_decision(config: dict, category: str, reason: str, metadata: dict | None = None) -> None:
    """Apply the configured decision for a supply_chain category."""
    decision = get_category_decision(config, "supply_chain", category)
    if decision == "deny":
        deny(f"BLOCKED: {reason}. Supply-chain-guardian.")
    elif decision == "ask":
        ask(f"{reason} -- confirm to proceed?", metadata=metadata)
    else:
        allow()


def _strip_version(package: str) -> str:
    """Strip version suffix from a package name.

    Scoped packages (e.g., @scope/pkg@1.0) have a leading '@', so
    only strip version when there is more than one '@'.
    Unscoped packages (e.g., pkg@1.0) always strip the trailing @version.
    """
    if package.startswith("@"):
        # Scoped: @scope/pkg or @scope/pkg@version
        if package.count("@") > 1:
            return re.sub(r"@[\w./-]+$", "", package)
        return package
    # Unscoped: pkg or pkg@version
    return re.sub(r"@[\w./-]+$", "", package)


def _split_args(segment: str) -> list[str]:
    """Split a shell segment into arguments, falling back on whitespace."""
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _extract_option_values(args: list[str], option_names: set[str]) -> list[str]:
    """Extract option values for flags like --with pkg or --with=pkg."""
    values: list[str] = []
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg in option_names and idx + 1 < len(args):
            values.append(args[idx + 1])
            idx += 2
            continue
        for option_name in option_names:
            prefix = f"{option_name}="
            if arg.startswith(prefix):
                values.append(arg[len(prefix):])
                break
        idx += 1
    return values


def _extract_package_from_runner_args(args: list[str], package_flags: set[str]) -> str | None:
    """Extract the package executed by a transient package runner."""
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--":
            # POSIX end-of-options: next non-flag arg is the package/command
            idx += 1
            while idx < len(args):
                if not args[idx].startswith("-"):
                    return args[idx]
                idx += 1
            return None
        if arg in package_flags and idx + 1 < len(args):
            return args[idx + 1]
        for package_flag in package_flags:
            prefix = f"{package_flag}="
            if arg.startswith(prefix):
                return arg[len(prefix):]
        if arg.startswith("-"):
            idx += 1
            continue
        return arg
    return None


def _is_allowlisted(package: str, allowlist: set[str]) -> bool:
    return _strip_version(package) in allowlist


def _is_npx_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\bnpx\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), {"--package", "-p"})
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"npx with unapproved package '{package}' (not in allowlist)"


def _is_npm_exec_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\bnpm\s+exec\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), {"--package"})
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"npm exec with unapproved package '{package}' (not in allowlist)"


def _is_pnpm_dlx_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\bpnpm\s+dlx\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), set())
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"pnpm dlx with unapproved package '{package}' (not in allowlist)"


def _is_yarn_dlx_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\byarn\s+dlx\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), set())
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"yarn dlx with unapproved package '{package}' (not in allowlist)"


def _is_bunx_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\bbunx\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), {"--package", "-p"})
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"bunx with unapproved package '{package}' (not in allowlist)"


def _is_uvx_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\buvx\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), {"--with", "--from"})
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"uvx with unapproved package '{package}' (not in allowlist)"


def _is_uv_tool_run_blocked(command: str, npx_allowlist: set[str]) -> str | None:
    match = re.search(r"\buv\s+tool\s+run\s+(.*)", command)
    if not match:
        return None
    package = _extract_package_from_runner_args(_split_args(match.group(1)), {"--from"})
    if not package or _is_allowlisted(package, npx_allowlist):
        return None
    return f"uv tool run with unapproved package '{package}' (not in allowlist)"


def _is_pip_blocked(command: str) -> str | None:
    if not re.search(r"\bpip3?\s+install\b", command):
        return None
    for safe in SAFE_PATTERNS:
        if safe.search(command):
            return None
    return "pip install of direct package (use requirements.txt instead)"


def _is_uv_add_blocked(command: str, uv_add_allowlist: set[str]) -> str | None:
    """Validates ALL package arguments -- if ANY is not allowlisted, block."""
    match = re.search(r"\buv\s+add\s+(.*)", command)
    if not match:
        return None

    # Flags that do NOT consume a following value
    _UV_ADD_BARE_FLAGS = {"--dev", "--no-sync", "--frozen", "--locked", "--editable"}
    # Flags that consume the next token as their value
    _UV_ADD_VALUE_FLAGS = {"--group", "--optional", "--extra", "--tag", "--branch", "--rev"}

    args = _split_args(match.group(1))
    packages: list[str] = []
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--":
            # POSIX end-of-options: remaining non-flag args are all packages
            idx += 1
            while idx < len(args):
                if not args[idx].startswith("-"):
                    packages.append(args[idx])
                idx += 1
            break
        if arg in _UV_ADD_BARE_FLAGS:
            idx += 1
            continue
        if arg in _UV_ADD_VALUE_FLAGS:
            idx += 2  # skip flag + its value
            continue
        # Handle --flag=value forms for value flags
        for vf in _UV_ADD_VALUE_FLAGS:
            if arg.startswith(f"{vf}="):
                break
        else:
            # Not a known flag form; check if it's an unknown flag
            if arg.startswith("-"):
                idx += 1
                continue
            # Positional arg is a package
            packages.append(arg)
        idx += 1

    if not packages:
        return None
    for pkg in packages:
        if pkg not in uv_add_allowlist:
            return f"uv add with unapproved package '{pkg}' (not in allowlist)"
    return None


def _is_uv_pip_blocked(command: str) -> str | None:
    if not re.search(r"\buv\s+pip\s+install\b", command):
        return None
    for safe in SAFE_PATTERNS:
        if safe.search(command):
            return None
    return "uv pip install of direct package (use requirements.txt or uv sync)"


def _is_uv_run_with_blocked(command: str) -> str | None:
    match = re.search(r"\buv\s+run\s+(.*)", command)
    if not match:
        return None
    with_values = _extract_option_values(_split_args(match.group(1)), {"--with"})
    if not with_values:
        return None
    package = with_values[0]
    return f"uv run --with introduces transient package '{package}'"


def _extract_all_package_args(args: list[str]) -> list[str]:
    """Return all non-flag arguments from a command tail."""
    return [arg for arg in args if not arg.startswith("-")]



def _dedupe_packages(packages: list[str]) -> list[str]:
    """Normalize package names for persistence allowlists."""
    seen: set[str] = set()
    normalized: list[str] = []
    for package in packages:
        stripped = _strip_version(package)
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized



def _extract_npx_packages(segment: str) -> list[str]:
    """Return exact transient packages that can be allowlisted."""
    extractors: list[tuple[str, set[str]]] = [
        (r"\bnpx\s+(.*)", {"--package", "-p"}),
        (r"\bnpm\s+exec\s+(.*)", {"--package"}),
        (r"\bpnpm\s+dlx\s+(.*)", set()),
        (r"\byarn\s+dlx\s+(.*)", set()),
        (r"\bbunx\s+(.*)", {"--package", "-p"}),
        (r"\buvx\s+(.*)", {"--with", "--from"}),
        (r"\buv\s+tool\s+run\s+(.*)", {"--from"}),
    ]
    for pattern, package_flags in extractors:
        match = re.search(pattern, segment)
        if not match:
            continue
        package = _extract_package_from_runner_args(_split_args(match.group(1)), package_flags)
        return _dedupe_packages([package] if package else [])
    return []



def _extract_uv_add_packages(command: str) -> list[str]:
    """Extract package args from `uv add` for persistence allowlists."""
    match = re.search(r"\buv\s+add\s+(.*)", command)
    if not match:
        return []

    bare_flags = {"--dev", "--no-sync", "--frozen", "--locked", "--editable"}
    value_flags = {"--group", "--optional", "--extra", "--tag", "--branch", "--rev"}
    args = _split_args(match.group(1))
    packages: list[str] = []
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--":
            idx += 1
            while idx < len(args):
                if not args[idx].startswith("-"):
                    packages.append(args[idx])
                idx += 1
            break
        if arg in bare_flags:
            idx += 1
            continue
        if arg in value_flags:
            idx += 2
            continue
        if any(arg.startswith(f"{flag}=") for flag in value_flags):
            idx += 1
            continue
        if arg.startswith("-"):
            idx += 1
            continue
        packages.append(arg)
        idx += 1
    return _dedupe_packages(packages)



def _extract_install_packages(command: str, pattern: str) -> list[str]:
    """Extract package args for add/install-style commands."""
    match = re.search(pattern, command)
    if not match:
        return []
    return _dedupe_packages(_extract_all_package_args(_split_args(match.group(1))))



def _build_persistence_metadata(segment: str, category: str) -> dict[str, Any] | None:
    """Return narrow allowlist persistence metadata for selected categories."""
    allowlist_key_by_category = {
        "npx-packages": "npx_allowlist",
        "uv-add": "uv_add_allowlist",
        "npm-install": "npm_install_allowlist",
        "yarn-add": "yarn_add_allowlist",
    }
    allowlist_key = allowlist_key_by_category.get(category)
    if allowlist_key is None:
        return None

    if category == "npx-packages":
        packages = _extract_npx_packages(segment)
    elif category == "uv-add":
        packages = _extract_uv_add_packages(segment)
    elif category == "npm-install":
        packages = (
            _extract_install_packages(segment, r"\bnpm\s+(?:install|i)\s+(.*)")
            or _extract_install_packages(segment, r"\bpnpm\s+add\s+(.*)")
            or _extract_install_packages(segment, r"\bbun\s+add\s+(.*)")
        )
    else:
        packages = _extract_install_packages(segment, r"\byarn\s+add\s+(.*)")

    if not packages:
        return None

    patch = {
        "supply_chain": {
            allowlist_key: packages,
        }
    }
    return build_permission_decision_metadata(
        allow_key=f"supply-chain:{category}:{','.join(packages)}",
        project_patch=patch,
        user_patch=patch,
    )


def _is_npm_install_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    """Check for npm install/i <package> (not bare npm install / npm ci).

    Validates ALL package arguments -- if ANY is not allowlisted, block.
    """
    match = re.search(r"\bnpm\s+(?:install|i)\s+(.*)", command)
    if not match:
        return None
    packages = _extract_all_package_args(_split_args(match.group(1)))
    if not packages:
        return None
    for pkg in packages:
        if not _is_allowlisted(pkg, npm_install_allowlist):
            return f"npm install with unapproved package '{pkg}' (not in allowlist)"
    return None


def _is_pnpm_add_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    """Validates ALL package arguments -- if ANY is not allowlisted, block."""
    match = re.search(r"\bpnpm\s+add\s+(.*)", command)
    if not match:
        return None
    packages = _extract_all_package_args(_split_args(match.group(1)))
    if not packages:
        return None
    for pkg in packages:
        if not _is_allowlisted(pkg, npm_install_allowlist):
            return f"pnpm add with unapproved package '{pkg}' (not in allowlist)"
    return None


def _is_yarn_add_blocked(command: str, yarn_add_allowlist: set[str]) -> str | None:
    """Check for yarn add <package>.

    Validates ALL package arguments -- if ANY is not allowlisted, block.
    """
    match = re.search(r"\byarn\s+add\s+(.*)", command)
    if not match:
        return None
    packages = _extract_all_package_args(_split_args(match.group(1)))
    if not packages:
        return None
    for pkg in packages:
        if not _is_allowlisted(pkg, yarn_add_allowlist):
            return f"yarn add with unapproved package '{pkg}' (not in allowlist)"
    return None


def _is_bun_add_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    """Validates ALL package arguments -- if ANY is not allowlisted, block."""
    match = re.search(r"\bbun\s+add\s+(.*)", command)
    if not match:
        return None
    packages = _extract_all_package_args(_split_args(match.group(1)))
    if not packages:
        return None
    for pkg in packages:
        if not _is_allowlisted(pkg, npm_install_allowlist):
            return f"bun add with unapproved package '{pkg}' (not in allowlist)"
    return None


def _split_shell_segments(command: str) -> list[str]:
    """Split a command string on shell operators (&&, ||, ;, |) into segments.

    Each segment is stripped of leading/trailing whitespace. Pipe (|) is
    included because piped commands are independently dangerous (e.g.,
    ``safe-cmd | npm install evil``).
    """
    # Split on &&, ||, ;, | (but not || as part of &&)
    # Order matters: match && and || before single & and |
    segments = re.split(r"\s*(?:&&|\|\||[;|])\s*", command)
    return [s.strip() for s in segments if s.strip()]


# xargs laundering: xargs piped to a package manager install command
_XARGS_PKG_MANAGER_RE = re.compile(
    r"\bxargs\s+.*(?:npm\s+(?:install|i)|pip3?\s+install|uv\s+add|yarn\s+add|pnpm\s+add|bun\s+add)\b"
)


def _check_segment(
    segment: str,
    npx_allowlist: set[str],
    uv_add_allowlist: set[str],
    npm_install_allowlist: set[str],
    yarn_add_allowlist: set[str],
) -> tuple[str | None, str]:
    """Check a single command segment for supply chain risks.

    Returns (reason, category) or (None, '') if safe.
    """
    # xargs laundering to package managers (e.g. echo evil | xargs npm install)
    # Must run BEFORE safe-pattern fast-path: safe patterns use \b not ^,
    # so "xargs npm install" matches the safe pattern for bare "npm install".
    if _XARGS_PKG_MANAGER_RE.search(segment):
        return "xargs piped to package manager install (supply chain risk)", "npm-install"

    # Safe pattern fast-path: only safe if the ENTIRE segment matches
    for safe in SAFE_PATTERNS:
        if safe.search(segment):
            return None, ""

    checks: list[tuple[str | None, str]] = [
        (_is_npx_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_npm_exec_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_pnpm_dlx_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_yarn_dlx_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_bunx_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_uvx_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_uv_tool_run_blocked(segment, npx_allowlist), "npx-packages"),
        (_is_pip_blocked(segment), "pip-direct"),
        (_is_uv_add_blocked(segment, uv_add_allowlist), "uv-add"),
        (_is_uv_pip_blocked(segment), "uv-pip-direct"),
        (_is_uv_run_with_blocked(segment), "uv-pip-direct"),
        (_is_npm_install_blocked(segment, npm_install_allowlist), "npm-install"),
        (_is_pnpm_add_blocked(segment, npm_install_allowlist), "npm-install"),
        (_is_yarn_add_blocked(segment, yarn_add_allowlist), "yarn-add"),
        (_is_bun_add_blocked(segment, npm_install_allowlist), "npm-install"),
    ]
    for reason, category in checks:
        if reason:
            return reason, category
    return None, ""


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
    sc = config.get("supply_chain", {})
    if not isinstance(sc, dict):
        sc = {}

    npx_allowlist = set(sc.get("npx_allowlist", [
        "@playwright/mcp", "ts-node", "cdk", "aws-cdk", "jest", "tsx", "tsc", "prettier", "eslint",
    ]))
    uv_add_allowlist = set(sc.get("uv_add_allowlist", []))
    npm_install_allowlist = set(sc.get("npm_install_allowlist", []))
    yarn_add_allowlist = set(sc.get("yarn_add_allowlist", []))

    # Split on shell operators and check EACH segment independently.
    # This prevents chaining bypasses (safe-cmd && evil-cmd).
    segments = _split_shell_segments(command)
    for segment in segments:
        reason, category = _check_segment(
            segment, npx_allowlist, uv_add_allowlist,
            npm_install_allowlist, yarn_add_allowlist,
        )
        if reason:
            _apply_decision(config, category, reason, metadata=_build_persistence_metadata(segment, category))
            return

    allow()


if __name__ == "__main__":
    main()
