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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import allow, ask, deny, fail_close, get_category_decision, load_config

# Patterns that are SAFE (skip blocking)
SAFE_PATTERNS = [
    re.compile(r"\bnpm\s+(install|ci)\s*$"),
    re.compile(r"\bnpm\s+(install|ci)\s+--"),
    re.compile(r"\bpip\s+install\s+(-r\s|--requirement\s|-e\s|--editable\s|\.\s*$)"),
    re.compile(r"\buv\s+sync\b"),
    re.compile(r"\buv\s+pip\s+install\s+(-r\s|--requirement\s|-e\s|--editable\s|\.\s*$)"),
    re.compile(r"\buv\s+pip\s+compile\b"),
]


def _apply_decision(config: dict, category: str, reason: str) -> None:
    """Apply the configured decision for a supply_chain category."""
    decision = get_category_decision(config, "supply_chain", category)
    if decision == "deny":
        deny(f"BLOCKED: {reason}. Supply-chain-guardian.")
    elif decision == "ask":
        ask(f"{reason} -- confirm to proceed?")
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
    if not re.search(r"\bpip\s+install\b", command):
        return None
    for safe in SAFE_PATTERNS:
        if safe.search(command):
            return None
    return "pip install of direct package (use requirements.txt instead)"


def _is_uv_add_blocked(command: str, uv_add_allowlist: set[str]) -> str | None:
    match = re.search(r"\buv\s+add\s+(\S+)", command)
    if not match:
        return None
    package = match.group(1)
    if package.startswith("-"):
        return None
    if package in uv_add_allowlist:
        return None
    return f"uv add with unapproved package '{package}' (not in allowlist)"


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


def _extract_first_package_arg(args: list[str]) -> str | None:
    """Return the first non-flag argument from a command tail."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return None


def _is_npm_install_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    """Check for npm install <package> (not bare npm install / npm ci)."""
    match = re.search(r"\bnpm\s+install\s+(.*)", command)
    if not match:
        return None
    package = _extract_first_package_arg(_split_args(match.group(1)))
    if not package or _is_allowlisted(package, npm_install_allowlist):
        return None
    return f"npm install with unapproved package '{package}' (not in allowlist)"


def _is_pnpm_add_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    match = re.search(r"\bpnpm\s+add\s+(.*)", command)
    if not match:
        return None
    package = _extract_first_package_arg(_split_args(match.group(1)))
    if not package or _is_allowlisted(package, npm_install_allowlist):
        return None
    return f"pnpm add with unapproved package '{package}' (not in allowlist)"


def _is_yarn_add_blocked(command: str, yarn_add_allowlist: set[str]) -> str | None:
    """Check for yarn add <package>."""
    match = re.search(r"\byarn\s+add\s+(.*)", command)
    if not match:
        return None
    package = _extract_first_package_arg(_split_args(match.group(1)))
    if not package or _is_allowlisted(package, yarn_add_allowlist):
        return None
    return f"yarn add with unapproved package '{package}' (not in allowlist)"


def _is_bun_add_blocked(command: str, npm_install_allowlist: set[str]) -> str | None:
    match = re.search(r"\bbun\s+add\s+(.*)", command)
    if not match:
        return None
    package = _extract_first_package_arg(_split_args(match.group(1)))
    if not package or _is_allowlisted(package, npm_install_allowlist):
        return None
    return f"bun add with unapproved package '{package}' (not in allowlist)"


@fail_close
def main() -> None:
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name != "Bash":
        allow()
        return

    command = tool_input.get("command", "")

    # Fast path: safe patterns always allowed
    for safe in SAFE_PATTERNS:
        if safe.search(command):
            allow()
            return

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

    # Check each supply chain risk
    checks: list[tuple[str | None, str]] = [
        (_is_npx_blocked(command, npx_allowlist), "npx-packages"),
        (_is_npm_exec_blocked(command, npx_allowlist), "npx-packages"),
        (_is_pnpm_dlx_blocked(command, npx_allowlist), "npx-packages"),
        (_is_yarn_dlx_blocked(command, npx_allowlist), "npx-packages"),
        (_is_bunx_blocked(command, npx_allowlist), "npx-packages"),
        (_is_uvx_blocked(command, npx_allowlist), "npx-packages"),
        (_is_uv_tool_run_blocked(command, npx_allowlist), "npx-packages"),
        (_is_pip_blocked(command), "pip-direct"),
        (_is_uv_add_blocked(command, uv_add_allowlist), "uv-add"),
        (_is_uv_pip_blocked(command), "uv-pip-direct"),
        (_is_uv_run_with_blocked(command), "uv-pip-direct"),
        (_is_npm_install_blocked(command, npm_install_allowlist), "npm-install"),
        (_is_pnpm_add_blocked(command, npm_install_allowlist), "npm-install"),
        (_is_yarn_add_blocked(command, yarn_add_allowlist), "yarn-add"),
        (_is_bun_add_blocked(command, npm_install_allowlist), "npm-install"),
    ]
    for reason, category in checks:
        if reason:
            _apply_decision(config, category, reason)
            return

    allow()


if __name__ == "__main__":
    main()
