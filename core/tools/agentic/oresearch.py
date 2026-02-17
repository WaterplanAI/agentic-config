#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
OResearch — Orchestrated Research (Layer 2): fan-out research across domains.

Spawns parallel researcher.py workers (one per domain), waits for completion,
then consolidates findings via spawn.py. Produces a research manifest (JSON).

Unlike ospec.py (sequential), oresearch.py runs workers IN PARALLEL (independent
domains) then consolidates. Supports refinement rounds from L4.

Usage:
    uv run core/tools/agentic/oresearch.py --topic "Feature X" --session-dir tmp/session/
    uv run core/tools/agentic/oresearch.py --topic "Feature X" --session-dir tmp/session/ --domains market,tech
    uv run core/tools/agentic/oresearch.py --topic "Feature X" --session-dir tmp/session/ --refinement-context path/to/refinement.md
    uv run core/tools/agentic/oresearch.py --topic "Feature X" --session-dir tmp/session/ --max-depth 5

Exit codes:
    0  - all workers passed + consolidation succeeded
    1  - unrecoverable failure
    2  - depth limit exceeded (passthrough, never absorbed)
    12 - partial success (some workers passed, others failed)
    20 - interrupted
"""

import argparse
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Import shared library (same package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    EXIT_DEPTH_EXCEEDED,
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_PARTIAL_SUCCESS,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    emit_error,
    emit_manifest,
    get_project_root,
    load_stage_config,
    resolve_project_file,
)
from lib.observability import Timer, emit_event, run_streaming, signal_completion, write_live_report

# -- Constants ----------------------------------------------------------------

CONFIG_NAME = "oresearch"
CONSOLIDATOR_PROMPT_RELATIVE = Path("core", "prompts", "executors", "researcher-consolidator.md")
SPAWN_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "spawn.py")


# -- Worker execution --------------------------------------------------------


def run_worker(
    executor_path: Path,
    domain: str,
    topic: str,
    output_path: Path,
    model: str,
    max_depth: int,
    timeout: int,
    refinement_context: str | None,
    cwd: str | None,
    session_dir: Path | None = None,
    worker_counter: str = "",
    worker_config: dict | None = None,
) -> dict:
    """Execute a single researcher.py worker as a subprocess.

    Returns:
        Worker result dict with domain, status, exit_code, artifact, and error.
    """
    # Build effective_topic with all modifications before constructing cmd
    effective_topic = topic
    if refinement_context:
        effective_topic += f"\n\nRefinement context:\n{refinement_context}"

    # Append focus from worker config if present (was dead field in oresearch.json)
    if worker_config and worker_config.get("focus"):
        effective_topic += f"\n\nResearch focus: {worker_config['focus']}"

    cmd: list[str] = [
        "uv", "run", str(executor_path),
        "--domain", domain,
        "--topic", effective_topic,
        "--output", str(output_path),
        "--model", model,
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    emit_event("L2", f"worker:{domain}", "STARTING", detail=worker_counter)
    write_live_report(session_dir, "L2", f"worker:{domain}", "STARTING", detail=worker_counter)

    with Timer() as t:
        try:
            exit_code, stdout = run_streaming(cmd, timeout=timeout, label=f"worker:{domain}")
        except subprocess.TimeoutExpired:
            emit_event("L2", f"worker:{domain}", "TIMEOUT", detail=f"{timeout}s limit")
            signal_completion(session_dir, "L2", f"worker-{domain}", "fail", elapsed_seconds=t.elapsed_seconds)
            return {
                "domain": domain,
                "status": "failed",
                "exit_code": EXIT_TIMEOUT,
                "error": "timeout",
            }
        except KeyboardInterrupt:
            signal_completion(session_dir, "L2", f"worker-{domain}", "fail")
            return {
                "domain": domain,
                "status": "failed",
                "exit_code": EXIT_INTERRUPTED,
                "error": "interrupted",
            }

    if exit_code == EXIT_SUCCESS:
        emit_event("L2", f"worker:{domain}", "COMPLETE", elapsed_ms=t.elapsed_ms, detail=worker_counter)
        signal_completion(session_dir, "L2", f"worker-{domain}", "done", artifact_path=str(output_path), elapsed_seconds=t.elapsed_seconds)
        write_live_report(session_dir, "L2", f"worker:{domain}", "COMPLETE", elapsed_seconds=t.elapsed_seconds, detail=worker_counter)
        return {
            "domain": domain,
            "status": "success",
            "exit_code": exit_code,
            "artifact": str(output_path),
            "elapsed_seconds": t.elapsed_seconds,
        }

    emit_event("L2", f"worker:{domain}", f"FAILED:exit={exit_code}", elapsed_ms=t.elapsed_ms, detail=worker_counter)
    signal_completion(session_dir, "L2", f"worker-{domain}", "fail", elapsed_seconds=t.elapsed_seconds)
    write_live_report(session_dir, "L2", f"worker:{domain}", "FAILED", elapsed_seconds=t.elapsed_seconds, detail=worker_counter)
    error_msg = f"exit code {exit_code}"
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict) and "error" in parsed:
                error_msg = str(parsed["error"])
        except json.JSONDecodeError:
            pass

    return {
        "domain": domain,
        "status": "failed",
        "exit_code": exit_code,
        "error": error_msg,
        "elapsed_seconds": t.elapsed_seconds,
    }


def execute_workers(
    executor_path: Path,
    workers: list[dict],
    topic: str,
    session_dir: Path,
    max_depth: int,
    timeout_per_worker: int,
    timeout_overall: int,
    refinement_context: str | None,
    cwd: str | None,
    max_concurrency: int = 4,
) -> tuple[int, list[dict]]:
    """Execute all workers in parallel.

    Returns:
        Tuple of (overall_exit_code, worker_results).
    """
    research_dir = session_dir / "research"
    research_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    interrupted = threading.Event()
    total_workers = len(workers)

    with ThreadPoolExecutor(max_workers=min(len(workers), max_concurrency)) as executor:
        future_to_domain: dict = {}
        for worker_idx, worker_config in enumerate(workers):
            domain = worker_config["domain"]
            model = worker_config.get("model", "medium-tier")
            output_path = research_dir / f"{domain}-findings.md"
            counter = f"worker {worker_idx + 1}/{total_workers}"

            future = executor.submit(
                run_worker,
                executor_path=executor_path,
                domain=domain,
                topic=topic,
                output_path=output_path,
                model=model,
                max_depth=max_depth,
                timeout=timeout_per_worker,
                refinement_context=refinement_context,
                cwd=cwd,
                session_dir=session_dir,
                worker_counter=counter,
                worker_config=worker_config,
            )
            future_to_domain[future] = domain

        try:
            for future in as_completed(future_to_domain, timeout=timeout_overall):
                worker_result = future.result()
                results.append(worker_result)
        except TimeoutError:
            emit_event("L2", "oresearch", f"OVERALL_TIMEOUT:{timeout_overall}s")
            # R-14: Cancel running futures
            executor.shutdown(wait=False, cancel_futures=True)
            # Collect completed results
            for f in future_to_domain:
                if f.done():
                    try:
                        results.append(f.result())
                    except Exception:
                        domain = future_to_domain[f]
                        results.append({
                            "domain": domain,
                            "status": "failed",
                            "exit_code": EXIT_TIMEOUT,
                            "error": "exception during collection",
                        })
                else:
                    domain = future_to_domain[f]
                    results.append({
                        "domain": domain,
                        "status": "failed",
                        "exit_code": EXIT_TIMEOUT,
                        "error": "overall timeout",
                    })
        except KeyboardInterrupt:
            interrupted.set()
            executor.shutdown(wait=False, cancel_futures=True)

    if interrupted.is_set():
        return EXIT_INTERRUPTED, results

    # Check for non-absorbable exit codes
    for r in results:
        if r["exit_code"] == EXIT_DEPTH_EXCEEDED:
            return EXIT_DEPTH_EXCEEDED, results
        if r["exit_code"] == EXIT_INTERRUPTED:
            return EXIT_INTERRUPTED, results
        if r["exit_code"] == EXIT_TIMEOUT:
            return EXIT_TIMEOUT, results

    # Determine overall exit code
    failed_count = sum(1 for r in results if r["exit_code"] != EXIT_SUCCESS)
    if failed_count == 0:
        return EXIT_SUCCESS, results
    if failed_count < len(results):
        return EXIT_PARTIAL_SUCCESS, results
    return EXIT_FAILURE, results


# -- Consolidation -----------------------------------------------------------


def run_consolidation(
    spawn_path: Path,
    consolidator_prompt_path: Path,
    finding_files: list[str],
    consolidated_output: Path,
    topic: str,
    model: str,
    max_depth: int,
    cwd: str | None,
    session_dir: Path | None = None,
) -> tuple[int, str | None]:
    """Run the consolidator agent via spawn.py.

    Returns:
        Tuple of (exit_code, error_message_or_None).
    """
    findings_list = "\n".join(f"- {f}" for f in finding_files)
    prompt = (
        f"Consolidate these research findings into a unified document.\n\n"
        f"Topic: {topic}\n\n"
        f"Findings files:\n{findings_list}\n\n"
        f"Write consolidated output to: {consolidated_output}"
    )

    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(consolidator_prompt_path),
        "--model", model,
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    emit_event("L2", "consolidation", "STARTING")
    write_live_report(session_dir, "L2", "consolidation", "STARTING")

    with Timer() as t:
        try:
            exit_code, _stdout = run_streaming(cmd, timeout=600, label="consolidation")
        except subprocess.TimeoutExpired:
            emit_event("L2", "consolidation", "TIMEOUT", detail="600s limit")
            signal_completion(session_dir, "L2", "consolidation", "fail")
            return EXIT_TIMEOUT, "consolidation timeout"
        except KeyboardInterrupt:
            signal_completion(session_dir, "L2", "consolidation", "fail")
            return EXIT_INTERRUPTED, "interrupted"

    if exit_code == EXIT_SUCCESS:
        emit_event("L2", "consolidation", "COMPLETE", elapsed_ms=t.elapsed_ms)
        signal_completion(session_dir, "L2", "consolidation", "done", artifact_path=str(consolidated_output), elapsed_seconds=t.elapsed_seconds)
        write_live_report(session_dir, "L2", "consolidation", "COMPLETE", elapsed_seconds=t.elapsed_seconds)
        return EXIT_SUCCESS, None

    emit_event("L2", "consolidation", f"FAILED:exit={exit_code}", elapsed_ms=t.elapsed_ms)
    signal_completion(session_dir, "L2", "consolidation", "fail", elapsed_seconds=t.elapsed_seconds)

    # Non-absorbable codes propagate
    if exit_code == EXIT_DEPTH_EXCEEDED:
        return EXIT_DEPTH_EXCEEDED, "depth limit exceeded"
    if exit_code == EXIT_INTERRUPTED:
        return EXIT_INTERRUPTED, "interrupted"

    return exit_code, f"consolidation exit code {exit_code}"


# -- Manifest formatting -----------------------------------------------------


def format_research_manifest(
    worker_results: list[dict],
    consolidated_path: str | None,
    exit_code: int,
    round_number: int,
) -> dict:
    """Format the oresearch manifest for stdout."""
    total = len(worker_results)
    passed = sum(1 for r in worker_results if r["exit_code"] == EXIT_SUCCESS)
    failed = total - passed

    manifest: dict = {
        "orchestrator": CONFIG_NAME,
        "round": round_number,
        "workers": worker_results,
    }
    if consolidated_path:
        manifest["consolidated"] = consolidated_path
    manifest["summary"] = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "exit_code": exit_code,
    }
    return manifest


# -- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Layer 2 orchestrator: fan-out research across domains in parallel"
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Research subject / topic to investigate",
    )
    parser.add_argument(
        "--session-dir",
        dest="session_dir",
        required=True,
        help="Directory for research artifacts (findings, consolidated)",
    )
    parser.add_argument(
        "--domains",
        default=None,
        help="Comma-separated subset of domains to research (default: all from config)",
    )
    parser.add_argument(
        "--refinement-context",
        dest="refinement_context",
        default=None,
        help="Path to refinement doc from L4 for focused re-research",
    )
    parser.add_argument(
        "--max-depth",
        dest="max_depth",
        type=int,
        default=3,
        help="Maximum nesting depth for spawn.py calls (default: 3)",
    )
    parser.add_argument(
        "--consolidation-model",
        dest="consolidation_model",
        default=None,
        help="Model tier for consolidator agent (default: from config, typically high-tier)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for spawned agents",
    )
    parser.add_argument(
        "--round",
        dest="round_number",
        type=int,
        default=1,
        help="Research round number for manifest tracking (default: 1)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Load config
    try:
        config = load_stage_config(CONFIG_NAME, script_dir)
    except FileNotFoundError as e:
        emit_error("CONFIG_NOT_FOUND", str(e))
        return EXIT_FAILURE
    except json.JSONDecodeError as e:
        emit_error("CONFIG_INVALID", f"Invalid JSON in config: {e}")
        return EXIT_FAILURE

    # Resolve executor path
    try:
        root = get_project_root(script_dir)
    except FileNotFoundError as e:
        emit_error("PROJECT_ROOT_NOT_FOUND", str(e))
        return EXIT_FAILURE

    executor_path = root / Path(config["executor"])
    if not executor_path.is_file():
        emit_error("EXECUTOR_NOT_FOUND", f"Executor not found: {executor_path}")
        return EXIT_FAILURE

    # Resolve consolidator prompt
    try:
        consolidator_prompt_path = resolve_project_file(
            CONSOLIDATOR_PROMPT_RELATIVE, script_dir
        )
    except FileNotFoundError as e:
        emit_error("CONSOLIDATOR_PROMPT_NOT_FOUND", str(e))
        return EXIT_FAILURE

    # Resolve spawn.py
    spawn_path = root / SPAWN_SCRIPT_RELATIVE
    if not spawn_path.is_file():
        emit_error("SPAWN_NOT_FOUND", f"spawn.py not found: {spawn_path}")
        return EXIT_FAILURE

    # Filter workers by --domains if specified
    all_workers: list[dict] = config["workers"]
    if args.domains:
        requested = {d.strip() for d in args.domains.split(",")}
        available = {w["domain"] for w in all_workers}
        unknown = requested - available
        if unknown:
            emit_error(
                "UNKNOWN_DOMAINS",
                f"Unknown domains: {', '.join(sorted(unknown))}. "
                f"Available: {', '.join(sorted(available))}",
            )
            return EXIT_FAILURE
        workers = [w for w in all_workers if w["domain"] in requested]
    else:
        workers = all_workers

    if not workers:
        emit_error("NO_WORKERS", "No workers to execute")
        return EXIT_FAILURE

    # Read refinement context if provided
    refinement_text: str | None = None
    if args.refinement_context:
        refinement_path = Path(args.refinement_context)
        if not refinement_path.is_file():
            emit_error(
                "REFINEMENT_NOT_FOUND",
                f"Refinement context not found: {args.refinement_context}",
            )
            return EXIT_FAILURE
        refinement_text = refinement_path.read_text(encoding="utf-8")

    session_dir = Path(args.session_dir)
    timeout_per_worker = config.get("timeout_per_worker", 300)
    timeout_overall = config.get("timeout_overall", 600)
    max_concurrency = config.get("max_concurrency", 4)

    # Execute workers in parallel
    worker_exit_code, worker_results = execute_workers(
        executor_path=executor_path,
        workers=workers,
        topic=args.topic,
        session_dir=session_dir,
        max_depth=args.max_depth,
        timeout_per_worker=timeout_per_worker,
        timeout_overall=timeout_overall,
        refinement_context=refinement_text,
        cwd=args.cwd,
        max_concurrency=max_concurrency,
    )

    # Non-absorbable exit codes propagate immediately
    if worker_exit_code in (EXIT_DEPTH_EXCEEDED, EXIT_INTERRUPTED):
        manifest = format_research_manifest(
            worker_results, None, worker_exit_code, args.round_number
        )
        emit_manifest(manifest)
        return worker_exit_code

    # All workers failed — no consolidation possible
    successful_artifacts = [
        r["artifact"] for r in worker_results
        if r["exit_code"] == EXIT_SUCCESS and "artifact" in r
    ]

    if not successful_artifacts:
        manifest = format_research_manifest(
            worker_results, None, EXIT_FAILURE, args.round_number
        )
        emit_manifest(manifest)
        return EXIT_FAILURE

    # Run consolidation on successful findings
    consolidation_model = (
        args.consolidation_model or config.get("consolidation_model", "high-tier")
    )
    consolidated_output = session_dir / "research" / "consolidated-findings.md"

    consolidation_exit, consolidation_error = run_consolidation(
        spawn_path=spawn_path,
        consolidator_prompt_path=consolidator_prompt_path,
        finding_files=successful_artifacts,
        consolidated_output=consolidated_output,
        topic=args.topic,
        model=consolidation_model,
        max_depth=args.max_depth,
        cwd=args.cwd,
        session_dir=session_dir,
    )

    # Non-absorbable codes from consolidation
    if consolidation_exit in (EXIT_DEPTH_EXCEEDED, EXIT_INTERRUPTED):
        manifest = format_research_manifest(
            worker_results, None, consolidation_exit, args.round_number
        )
        emit_manifest(manifest)
        return consolidation_exit

    # Determine final exit code
    if consolidation_exit != EXIT_SUCCESS:
        # Workers partially passed but consolidation failed
        final_exit = EXIT_PARTIAL_SUCCESS if worker_exit_code == EXIT_SUCCESS else worker_exit_code
    else:
        final_exit = worker_exit_code  # EXIT_SUCCESS or EXIT_PARTIAL_SUCCESS

    consolidated_str = str(consolidated_output) if consolidation_exit == EXIT_SUCCESS else None
    signal_completion(session_dir, "L2", "oresearch", "done" if final_exit == EXIT_SUCCESS else "partial" if final_exit == EXIT_PARTIAL_SUCCESS else "fail")
    manifest = format_research_manifest(
        worker_results, consolidated_str, final_exit, args.round_number
    )
    emit_manifest(manifest)

    return final_exit


if __name__ == "__main__":
    sys.exit(main())
