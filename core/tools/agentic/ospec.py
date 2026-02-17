#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
OSpec — Orchestrated Spec (Layer 2): sequences spec.py executor calls per-stage.

Calls `uv run spec.py STAGE SPEC` for each stage in the configured sequence,
parses JSON output, routes on exit codes, and produces a stage manifest.
Never executes work directly.

Usage:
    uv run core/tools/agentic/ospec.py full specs/001-feature.md
    uv run core/tools/agentic/ospec.py lean specs/001-feature.md
    uv run core/tools/agentic/ospec.py leanest specs/001-feature.md --max-depth 5

Exit codes:
    0  - all stages passed
    1  - unrecoverable failure
    2  - depth limit exceeded (passthrough, never absorbed)
    12 - partial success (some stages passed, others failed)
    20 - interrupted
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Import shared library (same package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_PARTIAL_SUCCESS,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    NON_ABSORBABLE_EXIT_CODES,
    emit_error,
    emit_manifest,
    format_manifest,
    format_stage_result,
    get_project_root,
    load_stage_config,
)
from lib.observability import Timer, emit_event, run_streaming, signal_completion, write_live_report

# -- Constants ----------------------------------------------------------------

VALID_MODIFIERS = ("full", "lean", "leanest")
CONFIG_NAME = "ospec"


# -- Stage execution ----------------------------------------------------------


def run_stage(
    executor_path: Path,
    stage_name: str,
    spec_path: str,
    model: str,
    max_depth: int,
    extra_args: list[str],
    cwd: str | None,
) -> tuple[int, dict | None]:
    """Execute a single stage via the executor.

    Returns:
        Tuple of (exit_code, parsed_json_output_or_None).
    """
    cmd: list[str] = [
        "uv", "run", str(executor_path),
        stage_name, spec_path,
        "--model", model,
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if extra_args:
        cmd.extend(extra_args)
    if cwd:
        cmd.extend(["--cwd", cwd])

    try:
        exit_code, stdout = run_streaming(cmd, timeout=600, label=f"ospec:{stage_name}")
    except subprocess.TimeoutExpired:
        emit_event("L2", f"ospec:{stage_name}", "TIMEOUT", detail="600s limit")
        return EXIT_TIMEOUT, None
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED, None

    # Parse JSON output if available
    parsed: dict | None = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            emit_event("L2", f"ospec:{stage_name}", "WARNING", detail="JSON parse failed")

    return exit_code, parsed


def execute_stages(
    executor_path: Path,
    stages: list[dict],
    spec_path: str,
    max_depth: int,
    extra_args: list[str],
    cwd: str | None,
    session_dir: Path | None = None,
) -> tuple[int, list[dict]]:
    """Execute all stages sequentially with retry logic.

    Returns:
        Tuple of (overall_exit_code, stage_results).
    """
    results: list[dict] = []
    total_stages = len(stages)

    for stage_idx, stage_config in enumerate(stages):
        stage_name = stage_config["name"]
        model = stage_config.get("model", "medium-tier")
        max_retries = stage_config.get("retry", 0)
        required = stage_config.get("required", True)
        counter = f"stage {stage_idx + 1}/{total_stages}"

        emit_event("L2", f"ospec:{stage_name}", "STARTING", detail=counter)
        write_live_report(session_dir, "L2", f"ospec:{stage_name}", "STARTING", detail=counter)

        with Timer() as t:
            exit_code, output = run_stage(
                executor_path, stage_name, spec_path, model, max_depth, extra_args, cwd
            )

        # Non-absorbable exit codes propagate immediately
        if exit_code in NON_ABSORBABLE_EXIT_CODES:
            emit_event("L2", f"ospec:{stage_name}", f"NON-ABSORBABLE:exit={exit_code}", elapsed_ms=t.elapsed_ms, detail=counter)
            signal_completion(session_dir, "L2", f"ospec-{stage_name}", "fail", elapsed_seconds=t.elapsed_seconds)
            results.append(format_stage_result(
                stage_name, "failed", exit_code,
                error=f"Non-absorbable exit code: {exit_code}"
            ))
            return exit_code, results

        # Retry logic (R-15: iterate N times, not just once)
        for attempt in range(max_retries):
            if exit_code not in (EXIT_FAILURE,):
                break
            emit_event("L2", f"ospec:{stage_name}", f"RETRY:{attempt + 1}/{max_retries}", detail=counter)
            with Timer() as t:
                exit_code, output = run_stage(
                    executor_path, stage_name, spec_path, model, max_depth, extra_args, cwd
                )
                if exit_code in NON_ABSORBABLE_EXIT_CODES:
                    results.append(format_stage_result(
                        stage_name, "failed", exit_code,
                        error=f"Non-absorbable exit code on retry: {exit_code}"
                    ))
                    return exit_code, results

        # Record result
        if exit_code == EXIT_SUCCESS:
            emit_event("L2", f"ospec:{stage_name}", "COMPLETE", elapsed_ms=t.elapsed_ms, detail=counter)
            artifact = output.get("result_file") if output else None
            results.append(format_stage_result(stage_name, "success", exit_code, artifact=artifact))
            signal_completion(session_dir, "L2", f"ospec-{stage_name}", "done", artifact_path=artifact, elapsed_seconds=t.elapsed_seconds)
        else:
            emit_event("L2", f"ospec:{stage_name}", f"FAILED:exit={exit_code}", elapsed_ms=t.elapsed_ms, detail=counter)
            error_msg = output.get("error") if output else f"exit code {exit_code}"
            results.append(format_stage_result(stage_name, "failed", exit_code, error=str(error_msg)))
            signal_completion(session_dir, "L2", f"ospec-{stage_name}", "fail", elapsed_seconds=t.elapsed_seconds)

            if required:
                return EXIT_FAILURE, results

        write_live_report(session_dir, "L2", f"ospec:{stage_name}", "COMPLETE" if exit_code == EXIT_SUCCESS else "FAILED", elapsed_seconds=t.elapsed_seconds, detail=counter)

    # Determine overall exit code
    failed_count = sum(1 for r in results if r["exit_code"] != EXIT_SUCCESS)
    if failed_count == 0:
        signal_completion(session_dir, "L2", "ospec", "done")
        return EXIT_SUCCESS, results
    if failed_count < len(results):
        signal_completion(session_dir, "L2", "ospec", "partial")
        return EXIT_PARTIAL_SUCCESS, results
    signal_completion(session_dir, "L2", "ospec", "fail")
    return EXIT_FAILURE, results


# -- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Layer 2 orchestrator: sequences spec.py executor calls per-stage"
    )
    parser.add_argument(
        "modifier",
        choices=VALID_MODIFIERS,
        metavar="MODIFIER",
        help=f"Stage sequence modifier: {', '.join(VALID_MODIFIERS)}",
    )
    parser.add_argument(
        "spec",
        metavar="SPEC",
        help="Path to the spec file",
    )
    parser.add_argument(
        "extra",
        nargs="*",
        default=[],
        metavar="EXTRA",
        help="Additional arguments passed through to each executor call",
    )
    parser.add_argument(
        "--max-depth",
        dest="max_depth",
        type=int,
        default=3,
        help="Maximum nesting depth allowed (default: 3)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for spawned agents",
    )
    parser.add_argument(
        "--session-dir",
        dest="session_dir",
        default=None,
        help="Session directory for signals and live report",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Load stage config
    try:
        config = load_stage_config(CONFIG_NAME, script_dir)
    except FileNotFoundError as e:
        emit_error("CONFIG_NOT_FOUND", str(e))
        return EXIT_FAILURE
    except json.JSONDecodeError as e:
        emit_error("CONFIG_INVALID", f"Invalid JSON in config: {e}")
        return EXIT_FAILURE

    # Resolve modifier -> stages
    modifier_config = config.get("modifiers", {}).get(args.modifier)
    if not modifier_config:
        emit_error("INVALID_MODIFIER", f"Modifier '{args.modifier}' not in config")
        return EXIT_FAILURE
    stages = modifier_config["stages"]

    # Resolve executor path
    executor_relative = Path(config["executor"])
    try:
        root = get_project_root(script_dir)
    except FileNotFoundError as e:
        emit_error("PROJECT_ROOT_NOT_FOUND", str(e))
        return EXIT_FAILURE

    executor_path = root / executor_relative
    if not executor_path.is_file():
        emit_error("EXECUTOR_NOT_FOUND", f"Executor not found: {executor_path}")
        return EXIT_FAILURE

    session_dir = Path(args.session_dir) if args.session_dir else None

    # Execute stages
    exit_code, results = execute_stages(
        executor_path=executor_path,
        stages=stages,
        spec_path=args.spec,
        max_depth=args.max_depth,
        extra_args=args.extra,
        cwd=args.cwd,
        session_dir=session_dir,
    )

    # Output manifest
    manifest = format_manifest(CONFIG_NAME, results, exit_code)
    emit_manifest(manifest)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
