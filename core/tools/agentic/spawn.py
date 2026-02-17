#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "claude-agent-sdk>=0.1.0",
# ]
# ///
"""
Spawn tool: universal primitive for depth-N agent nesting.

Wraps the Claude Code SDK to spawn specialized agent sessions as isolated
subprocess invocations. Handles depth tracking, model tier mapping,
structured output, and environment inheritance.

Usage:
    uv run core/tools/agentic/spawn.py --prompt "Do X" --model medium-tier
    uv run core/tools/agentic/spawn.py --prompt "Do X" --system-prompt agents/researcher.md
    uv run core/tools/agentic/spawn.py --prompt "Do X" --allowed-tools "Bash,Read,Grep,Glob"
    uv run core/tools/agentic/spawn.py --prompt "Do X" --output-format json
    uv run core/tools/agentic/spawn.py --prompt "Do X" --max-depth 3 --current-depth 1
    uv run core/tools/agentic/spawn.py --prompt "Do X" --cwd /path/to/project

Output (stdout):
    SPAWN_STATUS=success
    SPAWN_DEPTH=1
    SPAWN_MODEL=medium-tier
    SPAWN_RESULT_FILE=/path/to/result.json

Exit codes:
    0 - success
    1 - failure
    2 - depth limit exceeded
"""

import argparse
import asyncio
import atexit
import json
import os
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

# Import shared library (same package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_SUCCESS,
    EXIT_DEPTH_EXCEEDED,
    DEPTH_ENV_VAR,
)
from lib.observability import Timer, build_child_env_with_trace, emit_event, get_trace_id, signal_completion

# -- Constants ----------------------------------------------------------------

MODEL_TIER_MAP: dict[str, str] = {
    "low-tier": "claude-haiku-4-5-20251001",
    "medium-tier": "claude-sonnet-4-5-20250929",
    "high-tier": "claude-opus-4-6",
}

# -- Temp file tracking (R-08) -----------------------------------------------

_temp_files: set[str] = set()


def _cleanup_temps() -> None:
    """Remove tracked temp files on exit."""
    for f in _temp_files:
        try:
            os.unlink(f)
        except OSError:
            pass


atexit.register(_cleanup_temps)


# -- Pure functions -----------------------------------------------------------


def resolve_model(model_arg: str) -> str:
    """Map tier name to model ID, or pass through raw model IDs."""
    return MODEL_TIER_MAP.get(model_arg, model_arg)


def resolve_depth(current_depth_arg: int | None) -> int:
    """Resolve current depth from CLI arg or environment variable.

    Priority: explicit --current-depth > AGENTIC_SPAWN_DEPTH env > 0
    """
    if current_depth_arg is not None:
        return current_depth_arg
    env_depth = os.environ.get(DEPTH_ENV_VAR)
    if env_depth is not None:
        try:
            return int(env_depth)
        except ValueError:
            pass
    return 0


def check_depth_limit(current_depth: int, max_depth: int) -> str | None:
    """Return error message if depth limit exceeded, None otherwise."""
    if current_depth >= max_depth:
        return (
            f"Depth limit exceeded: current_depth={current_depth} "
            f">= max_depth={max_depth}. "
            f"Refusing to spawn to prevent runaway nesting."
        )
    return None


def read_system_prompt(path: str) -> str:
    """Read system prompt from file path."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    return resolved.read_text(encoding="utf-8")


def parse_allowed_tools(tools_str: str) -> list[str]:
    """Parse comma-separated tool names into list."""
    return [t.strip() for t in tools_str.split(",") if t.strip()]




def format_shell_output(
    status: str,
    depth: int,
    model: str,
    result_file: str | None = None,
    error: str | None = None,
) -> str:
    """Format structured output for shell consumption."""
    lines = [
        f"SPAWN_STATUS={status}",
        f"SPAWN_DEPTH={depth}",
        f"SPAWN_MODEL={model}",
    ]
    if result_file:
        lines.append(f"SPAWN_RESULT_FILE={result_file}")
    if error:
        lines.append(f"SPAWN_ERROR={error}")
    return "\n".join(lines)


def emit_error(code: str, message: str, details: str = "") -> None:
    """Write structured error to stderr."""
    error = {
        "status": "error",
        "error": {"code": code, "message": message},
    }
    if details:
        error["error"]["details"] = details  # type: ignore[index]
    print(json.dumps(error), file=sys.stderr)


# -- Core logic ---------------------------------------------------------------


async def run_agent(
    prompt: str,
    model_id: str,
    system_prompt: str | None,
    allowed_tools: list[str] | None,
    output_format_json: bool,
    cwd: str | None,
    current_depth: int,
) -> tuple[str, dict | None, str | None]:
    """Execute agent session via Claude SDK.

    Returns:
        Tuple of (result_text, structured_output, error_message).
        On success error_message is None.
    """
    # Set depth and trace for child processes (R-07: use build_child_env_with_trace pattern)
    _child_env = build_child_env_with_trace(current_depth, get_trace_id())
    os.environ[DEPTH_ENV_VAR] = _child_env[DEPTH_ENV_VAR]
    if "AGENTIC_TRACE_ID" in _child_env:
        os.environ["AGENTIC_TRACE_ID"] = _child_env["AGENTIC_TRACE_ID"]

    options_kwargs: dict = {}

    if allowed_tools:
        options_kwargs["allowed_tools"] = allowed_tools

    if model_id:
        options_kwargs["model"] = model_id

    if cwd:
        options_kwargs["cwd"] = cwd

    if system_prompt:
        options_kwargs["system_prompt"] = system_prompt

    options_kwargs["permission_mode"] = "acceptEdits"

    if output_format_json:
        options_kwargs["output_format"] = {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                    "data": {},
                },
            },
        }

    options = ClaudeAgentOptions(**options_kwargs)

    result_text = ""
    structured_output = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            if message.is_error:
                return "", None, f"Agent returned error: {message.result}"
            result_text = message.result or ""
            structured_output = message.structured_output

    return result_text, structured_output, None


# -- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for spawn tool."""
    parser = argparse.ArgumentParser(
        description="Spawn a specialized Claude agent session (depth-N nesting primitive)"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Prompt to send to the agent",
    )
    parser.add_argument(
        "--model",
        default="medium-tier",
        help=(
            "Model tier or raw model ID. "
            "Tiers: low-tier, medium-tier, high-tier. "
            "(default: medium-tier)"
        ),
    )
    parser.add_argument(
        "--system-prompt",
        dest="system_prompt",
        help="Path to system prompt file (read and injected as system prompt)",
    )
    parser.add_argument(
        "--allowed-tools",
        dest="allowed_tools",
        help="Comma-separated list of allowed tools (e.g., 'Bash,Read,Grep,Glob')",
    )
    parser.add_argument(
        "--output-format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (shell key=value) or json (default: text)",
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
        help=(
            "Current nesting depth. "
            f"Auto-detected from {DEPTH_ENV_VAR} env var if omitted. (default: 0)"
        ),
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for the spawned agent (default: current directory)",
    )
    parser.add_argument(
        "--session-dir",
        dest="session_dir",
        default=None,
        help="Session directory for signal writing (optional)",
    )
    parser.add_argument(
        "--signal-name",
        dest="signal_name",
        default=None,
        help="Signal name for L0 signal file (optional, requires --session-dir)",
    )
    parser.add_argument(
        "--trace-id",
        dest="trace_id",
        default=None,
        help="Trace ID for observability (optional, auto-detected if not provided)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve depth
    current_depth = resolve_depth(args.current_depth)

    # Check depth limit
    depth_error = check_depth_limit(current_depth, args.max_depth)
    if depth_error:
        emit_error("DEPTH_EXCEEDED", depth_error)
        if args.output_format == "json":
            print(json.dumps({"status": "error", "error": depth_error}))
        else:
            print(
                format_shell_output(
                    status="error",
                    depth=current_depth,
                    model=args.model,
                    error="depth_limit_exceeded",
                )
            )
        return EXIT_DEPTH_EXCEEDED

    # Resolve model
    model_id = resolve_model(args.model)

    # Read system prompt if provided
    system_prompt: str | None = None
    if args.system_prompt:
        try:
            system_prompt = read_system_prompt(args.system_prompt)
        except FileNotFoundError as e:
            emit_error("FILE_NOT_FOUND", str(e))
            return EXIT_FAILURE

    # Parse allowed tools
    allowed_tools: list[str] | None = None
    if args.allowed_tools:
        allowed_tools = parse_allowed_tools(args.allowed_tools)

    # Run agent
    current_depth_val = current_depth
    emit_event("L0", f"spawn:{args.model}", "STARTING", depth=current_depth_val)
    try:
        with Timer() as t:
            result_text, structured_output, error = asyncio.run(
                run_agent(
                    prompt=args.prompt,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    allowed_tools=allowed_tools,
                    output_format_json=(args.output_format == "json"),
                    cwd=args.cwd,
                    current_depth=current_depth,
                )
            )
    except KeyboardInterrupt:
        emit_error("INTERRUPTED", "Agent session interrupted by user")
        emit_event("L0", f"spawn:{args.model}", "INTERRUPTED", depth=current_depth_val)
        return EXIT_INTERRUPTED
    except (OSError, RuntimeError) as e:
        emit_error("SPAWN_FAILED", str(e), details=type(e).__name__)
        emit_event("L0", f"spawn:{args.model}", "FAILED", depth=current_depth_val)
        return EXIT_FAILURE

    emit_event("L0", f"spawn:{args.model}", "COMPLETE", elapsed_ms=t.elapsed_ms, depth=current_depth_val)

    if error:
        emit_error("AGENT_ERROR", error)
        if args.output_format == "json":
            print(json.dumps({"status": "error", "error": error}))
        else:
            print(
                format_shell_output(
                    status="error",
                    depth=current_depth,
                    model=args.model,
                    error=error,
                )
            )
        return EXIT_FAILURE

    # Write result to temp file for structured access
    result_file: str | None = None
    if structured_output is not None or result_text:
        result_data = structured_output if structured_output is not None else result_text
        fd, result_file = tempfile.mkstemp(suffix=".json", prefix="spawn-result-")
        _temp_files.add(result_file)
        with os.fdopen(fd, "w") as f:
            json.dump(result_data, f, indent=2)

    # Write L0 signal if session_dir and signal_name provided
    if args.session_dir and args.signal_name:
        session_path = Path(args.session_dir)
        trace_id_val = args.trace_id or get_trace_id()
        signal_completion(
            session_dir=session_path,
            layer="L0",
            name=args.signal_name,
            status="success",
            artifact_path=result_file,
            trace_id=trace_id_val,
            elapsed_seconds=t.elapsed_seconds,
        )

    # Output
    if args.output_format == "json":
        output = {
            "status": "success",
            "depth": current_depth,
            "model": args.model,
            "model_id": model_id,
            "elapsed_seconds": t.elapsed_seconds,
        }
        if result_file:
            output["result_file"] = result_file
        if structured_output is not None:
            output["result"] = structured_output
        else:
            output["result"] = result_text
        print(json.dumps(output, indent=2))
    else:
        print(
            format_shell_output(
                status="success",
                depth=current_depth,
                model=args.model,
                result_file=result_file,
            )
        )

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
