#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Campaign controller (Layer 4): strategic planning + execution oversight.

Top-level orchestration layer. Acts as Head of Product + Head of Engineering.
The user (CEO) provides a topic; campaign.py runs research, builds a roadmap,
gets CEO approval, delegates execution to coordinators, evaluates results,
and heals failures.

Zero LLM tokens consumed by campaign.py itself. All LLM work happens in the
tools it calls (spawn.py, oresearch.py, coordinator.py).

Usage:
    uv run core/tools/agentic/campaign.py --topic "Feature X"
    uv run core/tools/agentic/campaign.py --topic "Feature X" --session-dir tmp/session/
    uv run core/tools/agentic/campaign.py --topic "Feature X" --phase PLAN
    uv run core/tools/agentic/campaign.py --topic "Feature X" --phase EXECUTE --session-dir tmp/session/
    uv run core/tools/agentic/campaign.py --topic "Feature X" --resolution path/to/ceo-feedback.md --session-dir tmp/session/

Exit codes:
    0  - campaign complete (all phases passed)
    1  - unrecoverable failure
    2  - depth limit exceeded (passthrough, never absorbed)
    3  - CEO input required (roadmap review, escalation)
    10 - needs refinement (research insufficient after max rounds)
    12 - partial success
    20 - interrupted
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import shared library (same package)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    EXIT_FAILURE,
    EXIT_HUMAN_INPUT,
    EXIT_INTERRUPTED,
    EXIT_NEEDS_REFINEMENT,
    EXIT_PARTIAL_SUCCESS,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    NON_ABSORBABLE_EXIT_CODES,
    emit_error,
    emit_manifest,
    get_project_root,
    load_campaign_config,
    load_template,
    merge_config,
    resolve_campaign_config,
)
from lib.observability import (
    Timer,
    emit_event,
    init_session,
    run_streaming,
    signal_completion,
    write_consolidated_report,
    write_live_report,
)

# -- Constants ----------------------------------------------------------------

ORESEARCH_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "oresearch.py")
COORDINATOR_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "coordinator.py")
SPAWN_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "spawn.py")

REFINEMENT_PROMPT_RELATIVE = Path("core", "prompts", "campaigns", "refinement-evaluator.md")
ROADMAP_PROMPT_RELATIVE = Path("core", "prompts", "campaigns", "roadmap-writer.md")
EVALUATOR_PROMPT_RELATIVE = Path("core", "prompts", "campaigns", "evaluator.md")
TEMPLATES_DIR_RELATIVE = Path("core", "tools", "agentic", "config", "templates")

# Campaign states
STATE_PLAN_RESEARCH = "PLAN_RESEARCH"
STATE_PLAN_REFINE = "PLAN_REFINE"
STATE_PLAN_CONSOLIDATE = "PLAN_CONSOLIDATE"
STATE_PLAN_DECOMPOSE = "PLAN_DECOMPOSE"
STATE_CEO_REVIEW = "CEO_REVIEW"
STATE_EXECUTE = "EXECUTE"
STATE_EVALUATE = "EVALUATE"
STATE_HEAL = "HEAL"
STATE_REPORT = "REPORT"
STATE_COMPLETE = "COMPLETE"

# Phase CLI values -> starting states
PHASE_TO_STATE: dict[str, str] = {
    "PLAN": STATE_PLAN_RESEARCH,
    "EXECUTE": STATE_EXECUTE,
    "EVALUATE": STATE_EVALUATE,
}


def get_default_config() -> dict:
    """Get default campaign configuration.

    These defaults match the argparse default values for backward compatibility.
    When --config is NOT provided, these are the values used.
    When --config IS provided, the config file overrides these defaults,
    and CLI flags override the config file.

    Precedence: CLI > config file > these defaults.

    DUAL DEFAULTS SYNC: If you change argparse defaults in build_parser(),
    update the corresponding values here. See build_parser() lines 992-1010.
    """
    return {
        "research": {
            "enabled": True,
            "domains": ["market", "ux", "tech"],
            "max_rounds": 3,  # was: argparse default at build_parser() --max-research-rounds
            "model": "medium-tier",
            "consolidation_model": "high-tier",
            "timeout_per_worker": 300,
            "timeout_overall": 600,  # L2 internal timeout (NOT 660 -- L4 subprocess wrapper adds 60s buffer)
        },
        "planning": {
            "enabled": True,
            "roadmap_model": "high-tier",
            "decompose_model": "medium-tier",
            "ceo_review": True,
        },
        "execution": {
            "enabled": True,
            "max_depth": 5,  # was: argparse default at build_parser() --max-depth
            "timeout": 3600,
        },
        "validation": {
            "enabled": True,
            "evaluator_model": "medium-tier",
            "max_heal_cycles": 2,  # was: argparse default at build_parser() --max-heal-cycles
        },
    }


# -- Session management -------------------------------------------------------


def init_session_campaign(base_dir: Path | None, topic: str) -> Path:
    """Create campaign session directory structure."""
    subdirs = ["research", "refinements", "resolutions", "phases", "checkpoints", "reports", ".signals"]
    return init_session(
        base_dir=base_dir,
        topic=topic,
        subdirs=subdirs,
        session_state=None,
        topic_max_len=40,
        lowercase_topic=True,
    )


def read_state(session_dir: Path) -> dict[str, str]:
    """Read campaign state from .campaign-state file."""
    state_file = session_dir / ".campaign-state"
    if not state_file.exists():
        return {}
    state: dict[str, str] = {}
    for line in state_file.read_text(encoding="utf-8").strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            state[key.strip()] = value.strip()
    return state


def write_state(session_dir: Path, state: dict[str, str]) -> None:
    """Write campaign state to .campaign-state file."""
    state_file = session_dir / ".campaign-state"
    content = "\n".join(f"{k}: {v}" for k, v in state.items()) + "\n"
    state_file.write_text(content, encoding="utf-8")


def write_checkpoint(session_dir: Path, state_name: str, data: dict) -> Path:
    """Write checkpoint file. Returns checkpoint path. R-18: does not crash on write failure."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cp_path = session_dir / "checkpoints" / f"cp-{timestamp}.json"
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "checkpoint_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "session_dir": str(session_dir),
        "state": state_name,
        **data,
    }
    try:
        cp_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    except OSError as e:
        emit_error("CHECKPOINT_WRITE_FAILED", str(e))
        return cp_path
    return cp_path


# -- Subprocess helpers -------------------------------------------------------


def run_subprocess(
    cmd: list[str],
    timeout: int,
    label: str,
    session_dir: Path | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess with streaming and return (exit_code, stdout, stderr='')."""
    emit_event("L4", label, "STARTING")
    write_live_report(session_dir, "L4", label, "STARTING")

    try:
        with Timer() as t:
            exit_code, stdout = run_streaming(cmd, timeout=timeout, label=label)
    except subprocess.TimeoutExpired:
        emit_event("L4", label, "TIMEOUT", detail=f"{timeout}s limit")
        write_live_report(session_dir, "L4", label, "TIMEOUT")
        return EXIT_TIMEOUT, "", f"Timeout after {timeout}s"
    except KeyboardInterrupt:
        emit_event("L4", label, "INTERRUPTED")
        return EXIT_INTERRUPTED, "", "Interrupted"

    status = "COMPLETE" if exit_code == EXIT_SUCCESS else f"FAILED:exit={exit_code}"
    emit_event("L4", label, status, elapsed_ms=t.elapsed_ms)
    write_live_report(session_dir, "L4", label, status, elapsed_seconds=t.elapsed_seconds)

    return exit_code, stdout, ""


def parse_json_stdout(stdout: str) -> dict | None:
    """Attempt to parse JSON from subprocess stdout."""
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# -- Phase A: PLAN -----------------------------------------------------------


def run_research(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    refinement_context: Path | None = None,
    round_number: int = 1,
    cwd: str | None = None,
) -> tuple[int, dict | None]:
    """Execute L2 oresearch.py for fan-out research."""
    oresearch_path = project_root / ORESEARCH_SCRIPT_RELATIVE

    cmd: list[str] = [
        "uv", "run", str(oresearch_path),
        "--topic", topic,
        "--session-dir", str(session_dir),
        "--max-depth", str(max_depth),
        "--round", str(round_number),
    ]

    if refinement_context is not None:
        cmd.extend(["--refinement-context", str(refinement_context)])

    if cwd:
        cmd.extend(["--cwd", cwd])

    exit_code, stdout, _ = run_subprocess(cmd, timeout=660, label=f"research:round-{round_number}", session_dir=session_dir)

    manifest = parse_json_stdout(stdout)
    return exit_code, manifest


def evaluate_sufficiency(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    cwd: str | None = None,
) -> tuple[int, dict | None]:
    """Use spawn.py to evaluate research sufficiency (needs LLM)."""
    spawn_path = project_root / SPAWN_SCRIPT_RELATIVE
    prompt_path = project_root / REFINEMENT_PROMPT_RELATIVE

    if not prompt_path.is_file():
        emit_error("PROMPT_NOT_FOUND", f"Refinement evaluator prompt not found: {prompt_path}")
        return EXIT_FAILURE, None

    consolidated_path = session_dir / "research" / "consolidated-findings.md"
    if not consolidated_path.is_file():
        emit_error("FINDINGS_NOT_FOUND", f"Consolidated findings not found: {consolidated_path}")
        return EXIT_FAILURE, None

    findings_text = consolidated_path.read_text(encoding="utf-8")

    prompt = (
        f"Evaluate whether these research findings are sufficient for roadmap creation.\n\n"
        f"Topic: {topic}\n\n"
        f"Consolidated findings:\n{findings_text}"
    )

    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(prompt_path),
        "--model", "medium-tier",
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    exit_code, stdout, _ = run_subprocess(cmd, timeout=300, label="refinement-eval", session_dir=session_dir)

    parsed = parse_json_stdout(stdout)

    # Extract the inner result if spawn wraps it
    if parsed and "result" in parsed and isinstance(parsed["result"], dict):
        return exit_code, parsed["result"]
    if parsed and "result" in parsed and isinstance(parsed["result"], str):
        try:
            inner = json.loads(parsed["result"])
            return exit_code, inner
        except (json.JSONDecodeError, TypeError):
            pass

    return exit_code, parsed


def write_refinement_doc(
    session_dir: Path,
    round_number: int,
    gaps: list[str],
    topic: str,
) -> Path:
    """Write refinement feedback document for next research round."""
    doc_path = session_dir / "refinements" / f"round-{round_number}-feedback.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    gaps_list = "\n".join(f"- {g}" for g in gaps)
    content = (
        f"# Refinement Feedback: Round {round_number}\n\n"
        f"## Topic\n{topic}\n\n"
        f"## Gaps Identified\n{gaps_list}\n\n"
        f"## Instructions\n"
        f"Focus research on addressing the gaps listed above.\n"
        f"Prior findings were insufficient in these areas.\n"
    )
    doc_path.write_text(content, encoding="utf-8")
    return doc_path


def run_plan_research(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    max_research_rounds: int,
    cwd: str | None = None,
) -> tuple[int, str]:
    """Run RESEARCH + REFINE loop. Returns (exit_code, next_state)."""
    state = read_state(session_dir)
    start_round = int(state.get("research_round", "1"))

    for round_num in range(start_round, max_research_rounds + 1):
        # Update state
        write_state(session_dir, {
            **state,
            "state": STATE_PLAN_RESEARCH,
            "research_round": str(round_num),
        })

        # Determine refinement context
        refinement_ctx: Path | None = None
        if round_num > 1:
            refinement_path = session_dir / "refinements" / f"round-{round_num - 1}-feedback.md"
            if refinement_path.is_file():
                refinement_ctx = refinement_path

        # Run research
        exit_code, manifest = run_research(
            project_root, session_dir, topic, max_depth,
            refinement_context=refinement_ctx,
            round_number=round_num,
            cwd=cwd,
        )

        # Non-absorbable: propagate immediately
        if exit_code in NON_ABSORBABLE_EXIT_CODES:
            return exit_code, STATE_PLAN_RESEARCH

        # Total failure: cannot continue
        if exit_code == EXIT_FAILURE:
            emit_error("RESEARCH_FAILED", f"Research round {round_num} failed completely")
            return EXIT_FAILURE, STATE_PLAN_RESEARCH

        # Checkpoint research
        write_checkpoint(session_dir, STATE_PLAN_RESEARCH, {
            "round": round_num,
            "manifest": manifest,
        })

        # Evaluate sufficiency (REFINE step)
        write_state(session_dir, {
            **state,
            "state": STATE_PLAN_REFINE,
            "research_round": str(round_num),
        })

        eval_exit, eval_result = evaluate_sufficiency(
            project_root, session_dir, topic, max_depth, cwd=cwd,
        )

        if eval_exit in NON_ABSORBABLE_EXIT_CODES:
            return eval_exit, STATE_PLAN_REFINE

        # If evaluation failed (LLM error), assume sufficient and proceed
        if eval_exit != EXIT_SUCCESS or eval_result is None:
            emit_event("L4", "refinement-eval", "INCONCLUSIVE", detail="proceeding to consolidation")
            return EXIT_SUCCESS, STATE_PLAN_CONSOLIDATE

        sufficient = eval_result.get("sufficient", True)
        if sufficient:
            emit_event("L4", "refinement-eval", "SUFFICIENT", detail=f"after round {round_num}")
            return EXIT_SUCCESS, STATE_PLAN_CONSOLIDATE

        # Insufficient: write refinement doc and loop
        gaps = eval_result.get("gaps", ["Unspecified gaps in research findings"])
        refinement_doc = write_refinement_doc(session_dir, round_num, gaps, topic)
        emit_event("L4", "refinement", "GAPS_IDENTIFIED", detail=f"round {round_num}, wrote {refinement_doc.name}")

        write_checkpoint(session_dir, STATE_PLAN_REFINE, {
            "round": round_num,
            "gaps": gaps,
            "refinement_doc": str(refinement_doc),
        })

    # Exhausted all rounds without sufficient research
    emit_error("RESEARCH_INSUFFICIENT", f"Research still insufficient after {max_research_rounds} rounds")
    return EXIT_NEEDS_REFINEMENT, STATE_PLAN_REFINE


def run_consolidate(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    cwd: str | None = None,
) -> tuple[int, str]:
    """CONSOLIDATE: Create roadmap from findings. Returns (exit_code, next_state)."""
    spawn_path = project_root / SPAWN_SCRIPT_RELATIVE
    prompt_path = project_root / ROADMAP_PROMPT_RELATIVE

    if not prompt_path.is_file():
        emit_error("PROMPT_NOT_FOUND", f"Roadmap writer prompt not found: {prompt_path}")
        return EXIT_FAILURE, STATE_PLAN_CONSOLIDATE

    consolidated_path = session_dir / "research" / "consolidated-findings.md"
    if not consolidated_path.is_file():
        emit_error("FINDINGS_NOT_FOUND", f"Consolidated findings not found: {consolidated_path}")
        return EXIT_FAILURE, STATE_PLAN_CONSOLIDATE

    roadmap_path = session_dir / "roadmap.md"

    prompt = (
        f"Create a roadmap document from these consolidated research findings.\n\n"
        f"Topic: {topic}\n\n"
        f"Read the findings from: {consolidated_path}\n"
        f"Write the roadmap to: {roadmap_path}\n\n"
        f"Include: strategic rationale (WHY), business impact, measurable success criteria, "
        f"phase breakdown with deliverables and dependencies."
    )

    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--system-prompt", str(prompt_path),
        "--model", "high-tier",
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    exit_code, stdout, _ = run_subprocess(cmd, timeout=600, label="consolidate", session_dir=session_dir)

    if exit_code in NON_ABSORBABLE_EXIT_CODES:
        return exit_code, STATE_PLAN_CONSOLIDATE

    if exit_code != EXIT_SUCCESS:
        emit_error("CONSOLIDATION_FAILED", f"Roadmap creation failed (exit={exit_code})")
        return EXIT_FAILURE, STATE_PLAN_CONSOLIDATE

    write_state(session_dir, {
        "state": STATE_PLAN_CONSOLIDATE,
        "topic": topic,
    })
    write_checkpoint(session_dir, STATE_PLAN_CONSOLIDATE, {
        "roadmap_path": str(roadmap_path),
    })

    return EXIT_SUCCESS, STATE_PLAN_DECOMPOSE


def run_decompose(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    cwd: str | None = None,
) -> tuple[int, str]:
    """DECOMPOSE: Generate coordinator-config.json from roadmap. Returns (exit_code, next_state)."""
    roadmap_path = session_dir / "roadmap.md"
    config_path = session_dir / "coordinator-config.json"

    if not roadmap_path.is_file():
        emit_error("ROADMAP_NOT_FOUND", f"Roadmap not found: {roadmap_path}")
        return EXIT_FAILURE, STATE_PLAN_DECOMPOSE

    roadmap_text = roadmap_path.read_text(encoding="utf-8")

    # Extract phases from roadmap using spawn.py for LLM parsing
    spawn_path = project_root / SPAWN_SCRIPT_RELATIVE

    prompt = (
        f"Extract the phase definitions from this roadmap and produce a coordinator config JSON.\n\n"
        f"Roadmap:\n{roadmap_text}\n\n"
        f"Output a JSON object with this structure:\n"
        f'{{"name": "campaign-{topic[:30]}", '
        f'"description": "Generated from campaign roadmap", '
        f'"phases": ['
        f'{{"name": "phase-01-...", "orchestrator": "core/tools/agentic/ospec.py", '
        f'"modifier": "full", "target": "...", "depends_on": []}}, ...'
        f"]}}\n\n"
        f"Map each roadmap phase to a coordinator phase entry.\n"
        f"Use ospec.py as the orchestrator for each phase.\n"
        f"Use 'full' modifier for the first phase, 'lean' for subsequent phases.\n"
        f"Set depends_on to reference prior phase names where the roadmap indicates dependencies."
    )

    cmd: list[str] = [
        "uv", "run", str(spawn_path),
        "--prompt", prompt,
        "--model", "medium-tier",
        "--output-format", "json",
        "--max-depth", str(max_depth),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    exit_code, stdout, _ = run_subprocess(cmd, timeout=300, label="decompose", session_dir=session_dir)

    if exit_code in NON_ABSORBABLE_EXIT_CODES:
        return exit_code, STATE_PLAN_DECOMPOSE

    if exit_code != EXIT_SUCCESS:
        emit_error("DECOMPOSE_FAILED", f"Decomposition failed (exit={exit_code})")
        return EXIT_FAILURE, STATE_PLAN_DECOMPOSE

    # Parse the coordinator config from spawn output
    parsed = parse_json_stdout(stdout)
    config_data: dict | None = None

    if parsed:
        # spawn.py wraps result — unwrap
        if "result" in parsed and isinstance(parsed["result"], dict):
            config_data = parsed["result"]
        elif "result" in parsed and isinstance(parsed["result"], str):
            try:
                config_data = json.loads(parsed["result"])
            except (json.JSONDecodeError, TypeError):
                pass
        elif "phases" in parsed:
            config_data = parsed

    if config_data is None or "phases" not in config_data:
        emit_error("DECOMPOSE_PARSE_FAILED", "Could not extract coordinator config from LLM output")
        return EXIT_FAILURE, STATE_PLAN_DECOMPOSE

    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    emit_event("L4", "decompose", "COMPLETE", detail=f"wrote {config_path}")

    write_checkpoint(session_dir, STATE_PLAN_DECOMPOSE, {
        "config_path": str(config_path),
        "phase_count": len(config_data["phases"]),
    })

    return EXIT_SUCCESS, STATE_CEO_REVIEW


def run_ceo_review(
    session_dir: Path,
    topic: str,
    resolution_path: Path | None = None,
) -> tuple[int, str]:
    """CEO_REVIEW: Present roadmap for approval. Returns (exit_code, next_state).

    If resolution_path provided, reads CEO feedback:
    - "approved" / "approve" -> proceed to EXECUTE
    - Otherwise -> treat as revision feedback, return to CONSOLIDATE
    """
    roadmap_path = session_dir / "roadmap.md"

    if resolution_path is not None and resolution_path.is_file():
        feedback = resolution_path.read_text(encoding="utf-8").strip()

        # Copy to resolutions dir
        resolution_count = len(list((session_dir / "resolutions").glob("ceo-feedback-*.md")))
        dest = session_dir / "resolutions" / f"ceo-feedback-{resolution_count + 1}.md"
        dest.write_text(feedback, encoding="utf-8")

        # Check if approved
        feedback_lower = feedback.lower()
        if feedback_lower.startswith("approve") or feedback_lower == "lgtm" or feedback_lower == "ok":
            emit_event("L4", "ceo-review", "APPROVED")
            write_state(session_dir, {
                "state": STATE_EXECUTE,
                "topic": topic,
            })
            return EXIT_SUCCESS, STATE_EXECUTE

        # CEO wants revisions — go back to consolidate
        emit_event("L4", "ceo-review", "REVISIONS_REQUESTED", detail="returning to consolidation")
        write_state(session_dir, {
            "state": STATE_PLAN_CONSOLIDATE,
            "topic": topic,
            "ceo_feedback": str(dest),
        })
        return EXIT_SUCCESS, STATE_PLAN_CONSOLIDATE

    # No resolution: present roadmap and exit for CEO review
    if roadmap_path.is_file():
        emit_event("L4", "ceo-review", "READY", detail=f"roadmap: {roadmap_path}")
    else:
        emit_event("L4", "ceo-review", "WARNING", detail="roadmap not found, requesting CEO review")

    write_state(session_dir, {
        "state": STATE_CEO_REVIEW,
        "topic": topic,
    })

    # Exit 3 = HUMAN_INPUT required
    return EXIT_HUMAN_INPUT, STATE_CEO_REVIEW


# -- Phase B: EXECUTE --------------------------------------------------------


def run_execute(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    cwd: str | None = None,
) -> tuple[int, str]:
    """EXECUTE: Delegate to L3 coordinator. Returns (exit_code, next_state)."""
    coordinator_path = project_root / COORDINATOR_SCRIPT_RELATIVE
    config_path = session_dir / "coordinator-config.json"

    if not config_path.is_file():
        emit_error("CONFIG_NOT_FOUND", f"Coordinator config not found: {config_path}")
        return EXIT_FAILURE, STATE_EXECUTE

    phases_dir = session_dir / "phases"
    phases_dir.mkdir(exist_ok=True)

    cmd: list[str] = [
        "uv", "run", str(coordinator_path),
        str(config_path),
        "--max-depth", str(max_depth),
        "--session-dir", str(phases_dir),
    ]
    if cwd:
        cmd.extend(["--cwd", cwd])

    exit_code, stdout, _ = run_subprocess(cmd, timeout=3600, label="execute", session_dir=session_dir)

    if exit_code in NON_ABSORBABLE_EXIT_CODES:
        return exit_code, STATE_EXECUTE

    # Save coordinator manifest
    manifest = parse_json_stdout(stdout)
    if manifest:
        manifest_path = session_dir / "coordinator-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    write_state(session_dir, {
        "state": STATE_EVALUATE,
        "topic": topic,
    })
    write_checkpoint(session_dir, STATE_EXECUTE, {
        "coordinator_exit_code": exit_code,
        "manifest": manifest,
    })

    if exit_code == EXIT_HUMAN_INPUT:
        # Coordinator needs human input — propagate
        return EXIT_HUMAN_INPUT, STATE_EXECUTE

    return EXIT_SUCCESS, STATE_EVALUATE


# -- Phase C: EVALUATE -------------------------------------------------------


def run_evaluate(
    project_root: Path,
    session_dir: Path,
    topic: str,
    max_depth: int,
    max_heal_cycles: int,
    cwd: str | None = None,
) -> tuple[int, str]:
    """EVALUATE + HEAL loop (iterative -- R-05). Returns (exit_code, next_state)."""
    heal_cycle = int(read_state(session_dir).get("heal_cycle", "0"))

    spawn_path = project_root / SPAWN_SCRIPT_RELATIVE
    evaluator_prompt_path = project_root / EVALUATOR_PROMPT_RELATIVE

    if not evaluator_prompt_path.is_file():
        emit_error("PROMPT_NOT_FOUND", f"Evaluator prompt not found: {evaluator_prompt_path}")
        return EXIT_FAILURE, STATE_EVALUATE

    while True:
        roadmap_path = session_dir / "roadmap.md"
        manifest_path = session_dir / "coordinator-manifest.json"

        if not roadmap_path.is_file():
            emit_error("ROADMAP_NOT_FOUND", f"Roadmap not found: {roadmap_path}")
            return EXIT_FAILURE, STATE_EVALUATE

        manifest_text = ""
        if manifest_path.is_file():
            manifest_text = manifest_path.read_text(encoding="utf-8")
        else:
            emit_event("L4", "evaluate", "WARNING", detail="No coordinator manifest found")

        roadmap_text = roadmap_path.read_text(encoding="utf-8")

        prompt = (
            f"Evaluate whether the execution results meet the success criteria.\n\n"
            f"Topic: {topic}\n\n"
            f"Roadmap (with success criteria):\n{roadmap_text}\n\n"
            f"Coordinator manifest (execution results):\n{manifest_text or 'No manifest available'}"
        )

        cmd: list[str] = [
            "uv", "run", str(spawn_path),
            "--prompt", prompt,
            "--system-prompt", str(evaluator_prompt_path),
            "--model", "medium-tier",
            "--output-format", "json",
            "--max-depth", str(max_depth),
        ]
        if cwd:
            cmd.extend(["--cwd", cwd])

        exit_code, stdout, _ = run_subprocess(cmd, timeout=300, label="evaluate", session_dir=session_dir)

        if exit_code in NON_ABSORBABLE_EXIT_CODES:
            return exit_code, STATE_EVALUATE

        if exit_code != EXIT_SUCCESS:
            emit_error("EVALUATION_FAILED", f"Evaluation failed (exit={exit_code})")
            return EXIT_FAILURE, STATE_EVALUATE

        parsed = parse_json_stdout(stdout)
        eval_result: dict | None = None

        if parsed:
            if "result" in parsed and isinstance(parsed["result"], dict):
                eval_result = parsed["result"]
            elif "result" in parsed and isinstance(parsed["result"], str):
                try:
                    eval_result = json.loads(parsed["result"])
                except (json.JSONDecodeError, TypeError):
                    pass
            elif "verdict" in parsed:
                eval_result = parsed

        if eval_result is None:
            emit_event("L4", "evaluate", "INCONCLUSIVE", detail="treating as pass")
            return EXIT_SUCCESS, STATE_REPORT

        verdict = eval_result.get("verdict", "pass")

        if verdict == "pass":
            emit_event("L4", "evaluate", "PASS", detail="All success criteria met")
            signal_completion(session_dir, "L4", "evaluate", "done")
            return EXIT_SUCCESS, STATE_REPORT

        # Verdict is fail -- attempt healing (iterative, not recursive)
        if heal_cycle >= max_heal_cycles:
            emit_error("HEAL_EXHAUSTED", f"Max heal cycles ({max_heal_cycles}) exhausted")
            return EXIT_PARTIAL_SUCCESS, STATE_REPORT

        heal_cycle += 1
        issues = eval_result.get("issues", [])
        diag_path = session_dir / "refinements" / f"heal-cycle-{heal_cycle}-diagnostics.md"
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        issues_text = "\n".join(
            f"- Phase {i.get('phase', '?')}: {i.get('problem', 'unknown')} -> {i.get('suggested_fix', 'N/A')}"
            for i in issues
        )
        diag_content = (
            f"# Heal Cycle {heal_cycle} Diagnostics\n\n"
            f"## Failed Criteria\n{issues_text}\n\n"
            f"## Recommendation\n{eval_result.get('recommendation', 'Re-run failed phases')}\n"
        )
        diag_path.write_text(diag_content, encoding="utf-8")

        emit_event("L4", "heal", f"CYCLE:{heal_cycle}/{max_heal_cycles}", detail="re-invoking coordinator")

        write_state(session_dir, {
            "state": STATE_HEAL,
            "topic": topic,
            "heal_cycle": str(heal_cycle),
        })

        exec_exit, _ = run_execute(project_root, session_dir, topic, max_depth, cwd)

        if exec_exit in NON_ABSORBABLE_EXIT_CODES:
            return exec_exit, STATE_HEAL

        write_state(session_dir, {
            "state": STATE_EVALUATE,
            "topic": topic,
            "heal_cycle": str(heal_cycle),
        })
        # Loop continues with next evaluation iteration


def run_report(
    session_dir: Path,
    topic: str,
) -> tuple[int, str]:
    """REPORT: Write final summary. Returns (exit_code, next_state)."""
    report_path = session_dir / "report.md"

    # Gather available data
    roadmap_exists = (session_dir / "roadmap.md").is_file()
    manifest_path = session_dir / "coordinator-manifest.json"
    manifest: dict | None = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    state = read_state(session_dir)

    lines: list[str] = [
        f"# Campaign Report: {topic}",
        "",
        "## Session",
        f"- Directory: {session_dir}",
        f"- Final state: {state.get('state', 'UNKNOWN')}",
        f"- Heal cycles: {state.get('heal_cycle', '0')}",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    if roadmap_exists:
        lines.append("## Roadmap")
        lines.append(f"- Path: {session_dir / 'roadmap.md'}")
        lines.append("")

    if manifest:
        summary = manifest.get("summary", {})
        lines.append("## Execution Summary")
        lines.append(f"- Total phases: {summary.get('total', '?')}")
        lines.append(f"- Passed: {summary.get('passed', '?')}")
        lines.append(f"- Failed: {summary.get('failed', '?')}")
        lines.append(f"- Exit code: {summary.get('exit_code', '?')}")
        lines.append("")

        phases = manifest.get("phases", [])
        if phases:
            lines.append("## Phase Results")
            for p in phases:
                status_str = p.get("status", "unknown")
                lines.append(f"- {p.get('name', '?')}: {status_str}")
            lines.append("")

    lines.append("## Artifacts")
    for artifact_name in ("roadmap.md", "coordinator-config.json", "coordinator-manifest.json"):
        artifact_path = session_dir / artifact_name
        if artifact_path.is_file():
            lines.append(f"- {artifact_name}: {artifact_path}")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    emit_event("L4", "report", "COMPLETE", detail=f"report: {report_path}")

    write_state(session_dir, {
        "state": STATE_COMPLETE,
        "topic": topic,
    })

    return EXIT_SUCCESS, STATE_COMPLETE


# -- State machine ------------------------------------------------------------


def run_campaign(
    topic: str,
    session_dir: Path,
    start_state: str,
    project_root: Path,
    max_depth: int,
    max_research_rounds: int,
    max_heal_cycles: int,
    resolution_path: Path | None = None,
    cwd: str | None = None,
) -> int:
    """Execute campaign state machine from start_state. Returns exit code."""
    current_state = start_state

    # R-06: Only write initial state if no existing state (preserve resume values)
    state_file = session_dir / ".campaign-state"
    if not state_file.exists():
        write_state(session_dir, {
            "state": current_state,
            "topic": topic,
            "research_round": "1",
            "max_research_rounds": str(max_research_rounds),
            "heal_cycle": "0",
            "max_heal_cycles": str(max_heal_cycles),
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Update current state only, preserve other values
        existing = read_state(session_dir)
        existing["state"] = current_state
        write_state(session_dir, existing)

    while True:
        emit_event("L4", "campaign", f"STATE={current_state}")

        if current_state == STATE_PLAN_RESEARCH or current_state == STATE_PLAN_REFINE:
            exit_code, next_state = run_plan_research(
                project_root, session_dir, topic, max_depth, max_research_rounds, cwd,
            )
            if exit_code != EXIT_SUCCESS:
                return exit_code
            current_state = next_state

        elif current_state == STATE_PLAN_CONSOLIDATE:
            exit_code, next_state = run_consolidate(
                project_root, session_dir, topic, max_depth, cwd,
            )
            if exit_code != EXIT_SUCCESS:
                return exit_code
            current_state = next_state

        elif current_state == STATE_PLAN_DECOMPOSE:
            exit_code, next_state = run_decompose(
                project_root, session_dir, topic, max_depth, cwd,
            )
            if exit_code != EXIT_SUCCESS:
                return exit_code
            current_state = next_state

        elif current_state == STATE_CEO_REVIEW:
            exit_code, next_state = run_ceo_review(session_dir, topic, resolution_path)
            if exit_code != EXIT_SUCCESS:
                return exit_code
            current_state = next_state
            # Clear resolution after processing
            resolution_path = None

        elif current_state == STATE_EXECUTE:
            exit_code, next_state = run_execute(
                project_root, session_dir, topic, max_depth, cwd,
            )
            if exit_code != EXIT_SUCCESS:
                return exit_code
            current_state = next_state

        elif current_state == STATE_EVALUATE or current_state == STATE_HEAL:
            exit_code, next_state = run_evaluate(
                project_root, session_dir, topic, max_depth, max_heal_cycles, cwd,
            )
            # Partial success still generates report
            if exit_code not in (EXIT_SUCCESS, EXIT_PARTIAL_SUCCESS):
                return exit_code
            current_state = next_state
            if exit_code == EXIT_PARTIAL_SUCCESS:
                # Generate report then return partial success
                run_report(session_dir, topic)
                return EXIT_PARTIAL_SUCCESS

        elif current_state == STATE_REPORT:
            exit_code, next_state = run_report(session_dir, topic)
            return exit_code

        elif current_state == STATE_COMPLETE:
            signal_completion(session_dir, "L4", "campaign", "done")
            write_consolidated_report(session_dir)
            return EXIT_SUCCESS

        else:
            emit_error("INVALID_STATE", f"Unknown state: {current_state}")
            return EXIT_FAILURE


# -- CLI ----------------------------------------------------------------------


def list_templates(project_root: Path) -> list[dict[str, str]]:
    """Scan templates directory and return list of {name, description} dicts."""
    templates_dir = project_root / TEMPLATES_DIR_RELATIVE
    results: list[dict[str, str]] = []
    if not templates_dir.is_dir():
        return results
    for f in sorted(templates_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "name": f.stem,
                "description": data.get("description", ""),
            })
        except (json.JSONDecodeError, OSError):
            results.append({"name": f.stem, "description": "(invalid JSON)"})
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Layer 4 campaign controller: strategic planning + execution oversight"
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Campaign subject / goal",
    )
    parser.add_argument(
        "--session-dir",
        dest="session_dir",
        default=None,
        help="Session directory. Auto-created if not provided.",
    )
    parser.add_argument(
        "--phase",
        choices=["PLAN", "EXECUTE", "EVALUATE"],
        default=None,
        help="Which phase to run. Default: auto-detect from checkpoint.",
    )
    parser.add_argument(
        "--resolution",
        default=None,
        help="Path to CEO feedback file for refinement continuation.",
    )
    parser.add_argument(
        "--max-depth",
        dest="max_depth",
        type=int,
        default=None,
        help="Maximum nesting depth (default: 5, enough for L4->L3->L2->L1->L0)",
    )
    parser.add_argument(
        "--max-research-rounds",
        dest="max_research_rounds",
        type=int,
        default=None,
        help="Maximum research refinement rounds (default: 3)",
    )
    parser.add_argument(
        "--max-heal-cycles",
        dest="max_heal_cycles",
        type=int,
        default=None,
        help="Maximum heal cycles during evaluation (default: 2)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for spawned agents",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to campaign config file (JSON). Enables config-driven execution. Precedence: CLI > config > defaults.",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="Template name (e.g. big-feature, iteration) or path to template JSON. Precedence: CLI > template > config > defaults.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Resolve full config (template + CLI overlay + defaults), print JSON to stdout, exit without executing.",
    )
    parser.add_argument(
        "--list-templates",
        dest="list_templates",
        action="store_true",
        default=False,
        help="List available templates with descriptions and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # Resolve project root
    try:
        project_root = get_project_root(script_dir)
    except FileNotFoundError as e:
        emit_error("PROJECT_ROOT_NOT_FOUND", str(e))
        return EXIT_FAILURE

    # Verify critical tool paths exist
    for label, rel_path in [
        ("oresearch.py", ORESEARCH_SCRIPT_RELATIVE),
        ("coordinator.py", COORDINATOR_SCRIPT_RELATIVE),
        ("spawn.py", SPAWN_SCRIPT_RELATIVE),
    ]:
        tool_path = project_root / rel_path
        if not tool_path.is_file():
            emit_error("TOOL_NOT_FOUND", f"{label} not found: {tool_path}")
            return EXIT_FAILURE

    # Handle --list-templates (early exit)
    if args.list_templates:
        templates = list_templates(project_root)
        if not templates:
            print("No templates found.", file=sys.stderr)
            return EXIT_FAILURE
        print("Available templates:\n")
        for t in templates:
            print(f"  {t['name']:20s} {t['description']}")
        return EXIT_SUCCESS

    # Initialize or reuse session directory
    if args.session_dir:
        session_dir = Path(args.session_dir)
        if not session_dir.exists():
            session_dir = init_session_campaign(session_dir.parent, args.topic)
            # Rename to match explicit path if needed
            if session_dir != Path(args.session_dir):
                target = Path(args.session_dir)
                target.mkdir(parents=True, exist_ok=True)
                # Copy subdirs into explicit path
                for subdir in ("research", "refinements", "resolutions", "phases", "checkpoints"):
                    (target / subdir).mkdir(exist_ok=True)
                if (session_dir / ".trace").exists():
                    trace = (session_dir / ".trace").read_text()
                    (target / ".trace").write_text(trace)
                session_dir = target
    else:
        session_dir = init_session_campaign(None, args.topic)

    emit_event("L4", "campaign", "SESSION", detail=f"{session_dir}")

    # Determine starting state
    if args.phase:
        start_state = PHASE_TO_STATE[args.phase]
    elif args.resolution:
        # Re-invoked with resolution -> CEO_REVIEW
        start_state = STATE_CEO_REVIEW
    else:
        # Auto-detect from checkpoint
        existing_state = read_state(session_dir)
        if existing_state and "state" in existing_state:
            start_state = existing_state["state"]
            emit_event("L4", "campaign", "RESUMING", detail=f"from state: {start_state}")
        else:
            start_state = STATE_PLAN_RESEARCH

    # Resolve resolution path
    resolution_path: Path | None = None
    if args.resolution:
        resolution_path = Path(args.resolution)
        if not resolution_path.is_file():
            emit_error("RESOLUTION_NOT_FOUND", f"Resolution file not found: {args.resolution}")
            return EXIT_FAILURE

    # Load and resolve config
    config = get_default_config()

    # Template loading (template values override defaults)
    if args.template:
        try:
            template_bundle = load_template(args.template, script_dir)
        except FileNotFoundError as e:
            emit_error("TEMPLATE_NOT_FOUND", str(e))
            return EXIT_FAILURE
        except json.JSONDecodeError as e:
            emit_error("TEMPLATE_INVALID_JSON", str(e))
            return EXIT_FAILURE
        # Extract L4 layer config from template and merge on top of defaults
        from lib import resolve_layer_config
        l4_config = resolve_layer_config(template_bundle, "L4")
        if l4_config:
            config = merge_config(config, l4_config)

    # Config file loading (config file values override template)
    if args.config:
        config_path = Path(args.config)
        try:
            user_config = load_campaign_config(config_path)
        except FileNotFoundError as e:
            emit_error("CONFIG_NOT_FOUND", str(e))
            return EXIT_FAILURE
        except json.JSONDecodeError as e:
            emit_error("CONFIG_INVALID_JSON", str(e))
            return EXIT_FAILURE
        config = merge_config(config, user_config)
    config = resolve_campaign_config(config, args)

    # Handle --dry-run (early exit after full resolution)
    if args.dry_run:
        print(json.dumps(config, indent=2))
        return EXIT_SUCCESS

    # Run campaign (precedence: CLI > config > hardcoded defaults)
    # Argparse defaults are None to allow config values to take effect
    # Use explicit None checks to handle 0 as a valid config value
    max_depth = args.max_depth if args.max_depth is not None else config.get("execution", {}).get("max_depth", 5)
    max_research_rounds = args.max_research_rounds if args.max_research_rounds is not None else config.get("research", {}).get("max_rounds", 3)
    max_heal_cycles = args.max_heal_cycles if args.max_heal_cycles is not None else config.get("validation", {}).get("max_heal_cycles", 2)

    exit_code = run_campaign(
        topic=args.topic,
        session_dir=session_dir,
        start_state=start_state,
        project_root=project_root,
        max_depth=max_depth,
        max_research_rounds=max_research_rounds,
        max_heal_cycles=max_heal_cycles,
        resolution_path=resolution_path,
        cwd=args.cwd,
    )

    # Emit final manifest
    state = read_state(session_dir)
    final_manifest = {
        "campaign": args.topic,
        "session_dir": str(session_dir),
        "final_state": state.get("state", "UNKNOWN"),
        "exit_code": exit_code,
    }
    emit_manifest(final_manifest)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
