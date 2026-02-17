#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Researcher tool: thin wrapper around spawn.py for domain-specific research.

Specializes the generic spawn primitive for research execution.
Resolves domain-specific system prompts (researcher-{domain}.md) and
delegates to spawn.py with medium-tier model defaults.

Usage:
    uv run core/tools/agentic/researcher.py --domain market --topic "Feature X" --output findings.md
    uv run core/tools/agentic/researcher.py --domain ux --topic "Feature X" --output findings.md
    uv run core/tools/agentic/researcher.py --domain tech --topic "Feature X" --output findings.md
    uv run core/tools/agentic/researcher.py --domain market --topic "Feature X" --output findings.md --model high-tier

Exit codes:
    0 - success (from spawn.py)
    1 - failure (from spawn.py or local error)
    2 - depth limit exceeded (from spawn.py)
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import EXIT_FAILURE, EXIT_INTERRUPTED, EXIT_SUCCESS, SPAWN_SCRIPT_RELATIVE
from lib.observability import Timer, emit_event

# -- Constants ----------------------------------------------------------------

VALID_DOMAINS = ("market", "ux", "tech")

DEFAULT_MODEL = "medium-tier"

PROMPT_DIR_RELATIVE = Path("core", "prompts", "executors")


# -- Path resolution ----------------------------------------------------------


def find_project_root(start: Path) -> Path | None:
    """Walk up from start to find the project root containing spawn.py marker."""
    current = start
    while current != current.parent:
        if (current / SPAWN_SCRIPT_RELATIVE).is_file():
            return current
        current = current.parent
    return None


def resolve_system_prompt(script_dir: Path, domain: str) -> Path:
    """Resolve the researcher-{domain}.md system prompt file path.

    Searches from the script's own directory upward to find the project root.
    Falls back to CWD-based resolution if script location doesn't work.

    Raises:
        FileNotFoundError: If the system prompt cannot be found.
    """
    filename = f"researcher-{domain}.md"
    relative = PROMPT_DIR_RELATIVE / filename

    # Try from script location first
    root = find_project_root(script_dir)
    if root is not None:
        candidate = root / relative
        if candidate.is_file():
            return candidate

    # Fallback: try from CWD
    root = find_project_root(Path.cwd())
    if root is not None:
        candidate = root / relative
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Cannot find {relative}. "
        "Run from within the agentic-config project tree."
    )


def resolve_spawn_script(script_dir: Path) -> Path:
    """Resolve the spawn.py script path.

    Raises:
        FileNotFoundError: If spawn.py cannot be found.
    """
    root = find_project_root(script_dir)
    if root is not None:
        candidate = root / SPAWN_SCRIPT_RELATIVE
        if candidate.is_file():
            return candidate

    root = find_project_root(Path.cwd())
    if root is not None:
        candidate = root / SPAWN_SCRIPT_RELATIVE
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Cannot find {SPAWN_SCRIPT_RELATIVE}. "
        "Run from within the agentic-config project tree."
    )


# -- Prompt construction -------------------------------------------------------


def build_agent_prompt(domain: str, topic: str, output: str) -> str:
    """Construct the agent prompt for domain-specific research."""
    return (
        f"Research domain: {domain}\n"
        f"Topic: {topic}\n"
        f"Write findings to: {output}"
    )


# -- CLI -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for researcher tool."""
    parser = argparse.ArgumentParser(
        description="Run domain-specific research via a spawned Claude agent"
    )
    parser.add_argument(
        "--domain",
        required=True,
        # choices=VALID_DOMAINS removed -- enables custom domains (fail at prompt resolution if invalid)
        help=f"Research domain (built-in: {', '.join(VALID_DOMAINS)}; custom domains supported if prompt file exists)",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Research subject / topic to investigate",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write research findings (e.g., session/research/market-findings.md)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model tier or raw model ID. "
            "Tiers: low-tier, medium-tier, high-tier. "
            f"Default: {DEFAULT_MODEL}."
        ),
    )
    parser.add_argument(
        "--max-depth",
        dest="max_depth",
        type=int,
        default=3,
        help="Maximum nesting depth allowed (default: 3)",
    )
    parser.add_argument(
        "--current-depth",
        dest="current_depth",
        type=int,
        default=None,
        help="Current nesting depth (auto-detected from env if omitted)",
    )
    parser.add_argument(
        "--output-format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (shell key=value) or json (default: text)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for the spawned agent (default: current directory)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Resolve paths
    try:
        system_prompt_path = resolve_system_prompt(script_dir, args.domain)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    try:
        spawn_path = resolve_spawn_script(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    # Determine model tier
    model = args.model if args.model else DEFAULT_MODEL

    # Build agent prompt
    prompt = build_agent_prompt(args.domain, args.topic, args.output)

    # Construct spawn.py subprocess command
    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(system_prompt_path),
        "--model", model,
        "--output-format", args.output_format,
        "--max-depth", str(args.max_depth),
    ]

    if args.current_depth is not None:
        cmd.extend(["--current-depth", str(args.current_depth)])

    if args.cwd:
        cmd.extend(["--cwd", args.cwd])

    # Execute spawn.py, inheriting stdin/stdout/stderr
    emit_event("L1", f"researcher:{args.domain}", "STARTING")
    try:
        with Timer() as t:
            result = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        emit_event("L1", f"researcher:{args.domain}", "INTERRUPTED")
        return EXIT_INTERRUPTED
    except Exception as e:
        print(f"ERROR: Failed to execute spawn.py: {e}", file=sys.stderr)
        emit_event("L1", f"researcher:{args.domain}", "FAILED")
        return EXIT_FAILURE

    status = "COMPLETE" if result.returncode == EXIT_SUCCESS else f"FAILED:exit={result.returncode}"
    emit_event("L1", f"researcher:{args.domain}", status, elapsed_ms=t.elapsed_ms)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
