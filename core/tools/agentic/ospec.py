#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
OSpec tool: thin wrapper around spawn.py for the /mux-ospec orchestrated workflow.

Specializes the generic spawn primitive for orchestrated spec workflow execution.
Resolves the mux-ospec SKILL.md as the system prompt and delegates to spawn.py
with modifier-appropriate model defaults. Since mux-ospec is an orchestrator,
full and lean modifiers default to high-tier.

Usage:
    uv run core/tools/agentic/ospec.py full specs/2026/02/branch/001-feature.md
    uv run core/tools/agentic/ospec.py lean specs/2026/02/branch/001-feature.md --extra-context "auth module"
    uv run core/tools/agentic/ospec.py leanest specs/2026/02/branch/001-feature.md --model medium-tier
    uv run core/tools/agentic/ospec.py full specs/001.md --max-depth 3

Exit codes:
    0 - success (from spawn.py)
    1 - failure (from spawn.py or local error)
    2 - depth limit exceeded (from spawn.py)
"""

import argparse
import subprocess
import sys
from pathlib import Path

# -- Constants ----------------------------------------------------------------

VALID_MODIFIERS = ("full", "lean", "leanest")

# Modifier -> default model tier
# full/lean orchestrate many stages -> high-tier; leanest is lighter -> medium-tier.
MODIFIER_MODEL_DEFAULTS: dict[str, str] = {
    "full": "high-tier",
    "lean": "high-tier",
    "leanest": "medium-tier",
}

OSPEC_SKILL_RELATIVE = Path(".claude", "skills", "mux-ospec", "SKILL.md")
SPAWN_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "spawn.py")

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


# -- Path resolution ----------------------------------------------------------


def find_project_root(start: Path) -> Path | None:
    """Walk up from start to find the project root containing .claude/skills/mux-ospec/SKILL.md."""
    current = start
    while current != current.parent:
        if (current / OSPEC_SKILL_RELATIVE).is_file():
            return current
        current = current.parent
    return None


def resolve_ospec_skill(script_dir: Path) -> Path:
    """Resolve the mux-ospec SKILL.md file path.

    Searches from the script's own directory upward to find the project root.
    Falls back to CWD-based resolution if script location doesn't work.

    Raises:
        FileNotFoundError: If SKILL.md cannot be found.
    """
    # Try from script location first
    root = find_project_root(script_dir)
    if root is not None:
        return root / OSPEC_SKILL_RELATIVE

    # Fallback: try from CWD
    root = find_project_root(Path.cwd())
    if root is not None:
        return root / OSPEC_SKILL_RELATIVE

    raise FileNotFoundError(
        f"Cannot find {OSPEC_SKILL_RELATIVE}. "
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


def build_agent_prompt(modifier: str, spec: str, extra: list[str] | None) -> str:
    """Construct the agent prompt: /mux-ospec {MODIFIER} {SPEC} {extra}."""
    parts = ["/mux-ospec", modifier, spec]
    if extra:
        parts.extend(extra)
    return " ".join(parts)


# -- CLI -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for ospec tool."""
    parser = argparse.ArgumentParser(
        description="Run a /mux-ospec orchestrated workflow via a spawned Claude agent"
    )
    parser.add_argument(
        "modifier",
        choices=VALID_MODIFIERS,
        metavar="MODIFIER",
        help=f"Workflow modifier: {', '.join(VALID_MODIFIERS)}",
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
            "Default: high-tier for full/lean, medium-tier for leanest."
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
        ospec_skill_path = resolve_ospec_skill(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    try:
        spawn_path = resolve_spawn_script(script_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_FAILURE

    # Determine model tier
    model = args.model if args.model else MODIFIER_MODEL_DEFAULTS[args.modifier]

    # Build agent prompt
    prompt = build_agent_prompt(args.modifier, args.spec, args.extra)

    # Construct spawn.py subprocess command
    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(ospec_skill_path),
        "--model", model,
        "--output-format", args.output_format,
        "--max-depth", str(args.max_depth),
    ]

    if args.current_depth is not None:
        cmd.extend(["--current-depth", str(args.current_depth)])

    if args.cwd:
        cmd.extend(["--cwd", args.cwd])

    # Execute spawn.py, inheriting stdin/stdout/stderr
    try:
        result = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as e:
        print(f"ERROR: Failed to execute spawn.py: {e}", file=sys.stderr)
        return EXIT_FAILURE

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
