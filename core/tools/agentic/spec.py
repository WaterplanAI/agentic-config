#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Spec tool: thin wrapper around spawn.py for the /spec workflow.

Specializes the generic spawn primitive for spec stage execution.
Resolves the spec.md command definition as the system prompt and
delegates to spawn.py with stage-appropriate model defaults.

Usage:
    uv run core/tools/agentic/spec.py RESEARCH specs/2026/02/branch/001-feature.md
    uv run core/tools/agentic/spec.py PLAN specs/2026/02/branch/001-feature.md --focus "auth module"
    uv run core/tools/agentic/spec.py IMPLEMENT specs/2026/02/branch/001-feature.md --model high-tier
    uv run core/tools/agentic/spec.py RESEARCH specs/001.md --max-depth 3

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
from lib import EXIT_FAILURE, EXIT_INTERRUPTED, EXIT_SUCCESS
from lib.observability import Timer, emit_event

# -- Constants ----------------------------------------------------------------

VALID_STAGES = ("RESEARCH", "PLAN", "IMPLEMENT")

# Stage -> default model tier
STAGE_MODEL_DEFAULTS: dict[str, str] = {
    "RESEARCH": "medium-tier",
    "PLAN": "medium-tier",
    "IMPLEMENT": "high-tier",
}

SPEC_COMMAND_RELATIVE = Path("core", "commands", "claude", "spec.md")
SPAWN_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "spawn.py")


# -- Path resolution ----------------------------------------------------------


def find_project_root(start: Path) -> Path | None:
    """Walk up from start to find the project root containing core/commands/claude/spec.md."""
    current = start
    while current != current.parent:
        if (current / SPEC_COMMAND_RELATIVE).is_file():
            return current
        current = current.parent
    return None


def resolve_spec_command(script_dir: Path) -> Path:
    """Resolve the spec.md command file path.

    Searches from the script's own directory upward to find the project root.
    Falls back to CWD-based resolution if script location doesn't work.

    Raises:
        FileNotFoundError: If spec.md cannot be found.
    """
    # Try from script location first
    root = find_project_root(script_dir)
    if root is not None:
        return root / SPEC_COMMAND_RELATIVE

    # Fallback: try from CWD
    root = find_project_root(Path.cwd())
    if root is not None:
        return root / SPEC_COMMAND_RELATIVE

    raise FileNotFoundError(
        f"Cannot find {SPEC_COMMAND_RELATIVE}. "
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


def build_agent_prompt(stage: str, spec: str, extra: list[str] | None) -> str:
    """Construct the agent prompt: /spec {STAGE} {SPEC} {extra}."""
    parts = ["/spec", stage, spec]
    if extra:
        parts.extend(extra)
    return " ".join(parts)


# -- CLI -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for spec tool."""
    parser = argparse.ArgumentParser(
        description="Run a /spec workflow stage via a spawned Claude agent"
    )
    parser.add_argument(
        "stage",
        choices=VALID_STAGES,
        metavar="STAGE",
        help=f"Spec stage to execute: {', '.join(VALID_STAGES)}",
    )
    parser.add_argument(
        "spec",
        metavar="SPEC",
        help="Path to the spec file (e.g., specs/2026/02/branch/001-feature.md)",
    )
    parser.add_argument(
        "extra",
        nargs="*",
        default=[],
        metavar="EXTRA",
        help="Additional arguments passed through to the agent prompt",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model tier or raw model ID. "
            "Tiers: low-tier, medium-tier, high-tier. "
            "Default: medium-tier for RESEARCH/PLAN, high-tier for IMPLEMENT."
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
        spec_command_path = resolve_spec_command(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    try:
        spawn_path = resolve_spawn_script(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    # Determine model tier
    model = args.model if args.model else STAGE_MODEL_DEFAULTS[args.stage]

    # Build agent prompt
    prompt = build_agent_prompt(args.stage, args.spec, args.extra)

    # Construct spawn.py subprocess command
    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(spec_command_path),
        "--model", model,
        "--output-format", args.output_format,
        "--max-depth", str(args.max_depth),
    ]

    if args.current_depth is not None:
        cmd.extend(["--current-depth", str(args.current_depth)])

    if args.cwd:
        cmd.extend(["--cwd", args.cwd])

    # Execute spawn.py, inheriting stdin/stdout/stderr
    emit_event("L1", f"spec:{args.stage}", "STARTING")
    try:
        with Timer() as t:
            result = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        emit_event("L1", f"spec:{args.stage}", "INTERRUPTED")
        return EXIT_INTERRUPTED
    except Exception as e:
        print(f"ERROR: Failed to execute spawn.py: {e}", file=sys.stderr)
        emit_event("L1", f"spec:{args.stage}", "FAILED")
        return EXIT_FAILURE

    status = "COMPLETE" if result.returncode == EXIT_SUCCESS else f"FAILED:exit={result.returncode}"
    emit_event("L1", f"spec:{args.stage}", status, elapsed_ms=t.elapsed_ms)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
