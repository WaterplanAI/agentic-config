"""Shared constants and utilities for agentic tool composition hierarchy.

All layers (0-4) import from this module for consistent exit codes,
output formatting, path resolution, signal writing, and config loading.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Exit Codes ---------------------------------------------------------------
# From composition-hierarchy.md Section 5

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_DEPTH_EXCEEDED = 2
EXIT_HUMAN_INPUT = 3
EXIT_NEEDS_REFINEMENT = 10
EXIT_NEEDS_ESCALATION = 11
EXIT_PARTIAL_SUCCESS = 12
EXIT_INTERRUPTED = 20
EXIT_TIMEOUT = 21

EXIT_CODE_NAMES: dict[int, str] = {
    EXIT_SUCCESS: "SUCCESS",
    EXIT_FAILURE: "FAILURE",
    EXIT_DEPTH_EXCEEDED: "DEPTH_EXCEEDED",
    EXIT_HUMAN_INPUT: "HUMAN_INPUT",
    EXIT_NEEDS_REFINEMENT: "NEEDS_REFINEMENT",
    EXIT_NEEDS_ESCALATION: "NEEDS_ESCALATION",
    EXIT_PARTIAL_SUCCESS: "PARTIAL_SUCCESS",
    EXIT_INTERRUPTED: "INTERRUPTED",
    EXIT_TIMEOUT: "TIMEOUT",
}

# Exit codes that must NEVER be absorbed by any layer
NON_ABSORBABLE_EXIT_CODES = frozenset(
    {EXIT_DEPTH_EXCEEDED, EXIT_INTERRUPTED, EXIT_TIMEOUT}
)

# -- Depth tracking -----------------------------------------------------------

DEPTH_ENV_VAR = "AGENTIC_SPAWN_DEPTH"


def get_current_depth() -> int:
    """Read current spawn depth from environment."""
    env_depth = os.environ.get(DEPTH_ENV_VAR)
    if env_depth is not None:
        try:
            return int(env_depth)
        except ValueError:
            pass
    return 0


# -- Path resolution ----------------------------------------------------------

SPAWN_SCRIPT_RELATIVE = Path("core", "tools", "agentic", "spawn.py")


def find_project_root(start: Path, marker: Path) -> Path | None:
    """Walk up from start to find directory containing marker file."""
    current = start.resolve()
    while current != current.parent:
        if (current / marker).is_file():
            return current
        current = current.parent
    return None


def resolve_project_file(relative_path: Path, script_dir: Path | None = None) -> Path:
    """Resolve a project-relative file path.

    Tries script directory first, then CWD.

    Raises:
        FileNotFoundError: If file cannot be found.
    """
    # Need a marker to find project root. Use spawn.py as universal marker.
    marker = SPAWN_SCRIPT_RELATIVE

    if script_dir is not None:
        root = find_project_root(script_dir, marker)
        if root is not None:
            candidate = root / relative_path
            if candidate.is_file():
                return candidate

    root = find_project_root(Path.cwd(), marker)
    if root is not None:
        candidate = root / relative_path
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Cannot find {relative_path}. Run from within the agentic-config project tree."
    )


def get_project_root(script_dir: Path | None = None) -> Path:
    """Get the project root directory.

    Raises:
        FileNotFoundError: If project root cannot be found.
    """
    marker = SPAWN_SCRIPT_RELATIVE

    if script_dir is not None:
        root = find_project_root(script_dir, marker)
        if root is not None:
            return root

    root = find_project_root(Path.cwd(), marker)
    if root is not None:
        return root

    raise FileNotFoundError(
        "Cannot find project root. Run from within the agentic-config project tree."
    )


# -- Output formatting --------------------------------------------------------


def format_stage_result(
    name: str,
    status: str,
    exit_code: int,
    artifact: str | None = None,
    error: str | None = None,
) -> dict:
    """Format a single stage result for manifest output."""
    result: dict = {
        "name": name,
        "status": status,
        "exit_code": exit_code,
    }
    if artifact:
        result["artifact"] = artifact
    if error:
        result["error"] = error
    return result


def format_manifest(orchestrator: str, stages: list[dict], exit_code: int) -> dict:
    """Format orchestrator manifest output (Section 3: L2 to L3 contract)."""
    total = len(stages)
    passed = sum(1 for s in stages if s["exit_code"] == EXIT_SUCCESS)
    failed = total - passed
    return {
        "orchestrator": orchestrator,
        "stages": stages,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "exit_code": exit_code,
        },
    }


def emit_manifest(manifest: dict) -> None:
    """Write manifest JSON to stdout."""
    print(json.dumps(manifest, indent=2))


def emit_error(code: str, message: str, details: str = "") -> None:
    """Write structured error to stderr."""
    error: dict = {
        "status": "error",
        "error": {"code": code, "message": message},
    }
    if details:
        error["error"]["details"] = details
    print(json.dumps(error), file=sys.stderr)


def emit_progress(stage: str, status: str) -> None:
    """Write human-readable progress to stderr."""
    print(f"[{stage}] {status}", file=sys.stderr)


# -- Signal file protocol -----------------------------------------------------
# From composition-hierarchy.md Section 5


def write_signal(
    session_dir: Path,
    layer: str,
    name: str,
    status: str,
    artifact_path: str | None = None,
    artifact_size: int | None = None,
    trace_id: str | None = None,
) -> Path:
    """Write a signal file atomically.

    Path: <session-dir>/.signals/<layer>-<name>.<status>
    """
    signals_dir = session_dir / ".signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    signal_path = signals_dir / f"{layer}-{name}.{status}"

    content_lines = [
        f"path: {artifact_path or 'none'}",
        f"size: {artifact_size or 0}",
        f"status: {status}",
        f"created_at: {datetime.now(timezone.utc).isoformat()}",
        f"trace_id: {trace_id or os.urandom(8).hex()}",
        f"layer: {layer}",
        f"name: {name}",
        "version: 1",
    ]
    content = "\n".join(content_lines) + "\n"

    # Atomic write: temp file + os.replace
    tmp_path = signals_dir / f".{name}.tmp.{os.getpid()}"
    tmp_path.write_text(content, encoding="utf-8")
    try:
        os.replace(tmp_path, signal_path)
    except OSError:
        shutil.copy2(str(tmp_path), str(signal_path))
        tmp_path.unlink(missing_ok=True)

    return signal_path


# -- Config loading -----------------------------------------------------------


def load_stage_config(config_name: str, script_dir: Path | None = None) -> dict:
    """Load stage configuration from core/tools/agentic/config/<name>.json.

    Raises:
        FileNotFoundError: If config file not found.
        json.JSONDecodeError: If config is invalid JSON.
    """
    config_relative = Path("core", "tools", "agentic", "config", f"{config_name}.json")
    config_path = resolve_project_file(config_relative, script_dir)
    return json.loads(config_path.read_text(encoding="utf-8"))


# -- Shared validation helpers ------------------------------------------------

VALID_STAGE_NAMES = frozenset({"RESEARCH", "PLAN", "IMPLEMENT", "VALIDATE", "TEST"})
VALID_PERMISSION_MODES = frozenset({"acceptEdits", "plan", "bypassPermissions"})


def _check_type(
    warnings: list[str], path: str, val: object, expected_type: type
) -> bool:
    """Check type and warn if mismatch. Returns True if type matches."""
    if isinstance(val, bool) and expected_type is int:
        # bool is subclass of int in Python; reject bools when int expected
        warnings.append(f"{path} must be {expected_type.__name__}, got bool")
        return False
    if not isinstance(val, expected_type):
        warnings.append(
            f"{path} must be {expected_type.__name__}, got {type(val).__name__}"
        )
        return False
    return True


def _check_str(
    warnings: list[str], path: str, val: object, allow_empty: bool = False
) -> None:
    """Check string type and optionally non-empty."""
    if not _check_type(warnings, path, val, str):
        return
    assert isinstance(val, str)  # for type narrowing
    if not allow_empty and not val:
        warnings.append(f"{path} must be non-empty string")


def _check_int_range(
    warnings: list[str], path: str, val: object, min_val: int, max_val: int
) -> None:
    """Check integer type and range [min_val, max_val]."""
    if not _check_type(warnings, path, val, int):
        return
    assert isinstance(val, int)  # for type narrowing
    if not (min_val <= val <= max_val):
        warnings.append(f"{path} must be int {min_val}-{max_val}, got {val}")


def _check_bool_field(warnings: list[str], path: str, val: object) -> None:
    """Check boolean type."""
    if not isinstance(val, bool):
        warnings.append(f"{path} must be bool, got {type(val).__name__}")


def _check_model(warnings: list[str], path: str, val: object) -> None:
    """Check model tier name or claude-* model ID."""
    if not _check_type(warnings, path, val, str):
        return
    assert isinstance(val, str)  # for type narrowing
    if val not in VALID_MODEL_TIERS and not val.startswith("claude-"):
        warnings.append(f"{path} must be tier name or claude-* model ID, got '{val}'")


def _check_enum(
    warnings: list[str], path: str, val: object, allowed: frozenset[str]
) -> None:
    """Check value is in allowed set."""
    if not _check_type(warnings, path, val, str):
        return
    assert isinstance(val, str)  # for type narrowing
    if val not in allowed:
        warnings.append(f"{path} must be one of {sorted(allowed)}, got '{val}'")


def _check_nullable_str(warnings: list[str], path: str, val: object) -> None:
    """Check value is string or null."""
    if val is not None and not isinstance(val, str):
        warnings.append(f"{path} must be string or null, got {type(val).__name__}")


# -- Campaign config ----------------------------------------------------------

VALID_MODEL_TIERS = frozenset({"low-tier", "medium-tier", "high-tier"})


def validate_campaign_config(config: dict) -> list[str]:
    """Validate campaign config structure, types, and ranges.

    Returns list of warning strings. Empty list means valid.
    Warnings (not errors) for forward-compatibility with future config keys.
    """
    warnings: list[str] = []
    known_sections = {"research", "planning", "execution", "validation"}

    # Unknown top-level keys: warn, don't error (forward-compatible)
    for key in config:
        if key not in known_sections:
            warnings.append(f"Unknown top-level key: '{key}' (will be ignored)")

    # -- research section --
    if "research" in config:
        r = config["research"]
        if not isinstance(r, dict):
            warnings.append("research must be a dict")
        else:
            if "enabled" in r:
                _check_bool_field(warnings, "research.enabled", r["enabled"])
            if "domains" in r:
                if not isinstance(r["domains"], list) or not all(
                    isinstance(d, str) and d for d in r["domains"]
                ):
                    warnings.append(
                        "research.domains must be list of non-empty strings"
                    )
            if "max_rounds" in r:
                if not isinstance(r["max_rounds"], int) or not (
                    1 <= r["max_rounds"] <= 5
                ):
                    warnings.append("research.max_rounds must be int 1-5")
            if "timeout_per_worker" in r:
                if not isinstance(r["timeout_per_worker"], int) or not (
                    60 <= r["timeout_per_worker"] <= 1800
                ):
                    warnings.append("research.timeout_per_worker must be int 60-1800")
            if "timeout_overall" in r:
                if (
                    not isinstance(r["timeout_overall"], int)
                    or r["timeout_overall"] > 3600
                ):
                    warnings.append("research.timeout_overall must be int <= 3600")
                if (
                    "timeout_per_worker" in r
                    and isinstance(r["timeout_overall"], int)
                    and isinstance(r["timeout_per_worker"], int)
                ):
                    if r["timeout_overall"] < r["timeout_per_worker"]:
                        warnings.append(
                            "research.timeout_overall must be >= timeout_per_worker"
                        )
            for mk in ("model", "consolidation_model"):
                if mk in r:
                    _check_model(warnings, f"research.{mk}", r[mk])
            # Warn on unknown nested keys
            known_research = {
                "enabled",
                "domains",
                "max_rounds",
                "model",
                "consolidation_model",
                "timeout_per_worker",
                "timeout_overall",
            }
            for k in r:
                if k not in known_research:
                    warnings.append(f"Unknown key research.{k} (will be ignored)")

    # -- planning section --
    if "planning" in config:
        p = config["planning"]
        if not isinstance(p, dict):
            warnings.append("planning must be a dict")
        else:
            if "enabled" in p:
                _check_bool_field(warnings, "planning.enabled", p["enabled"])
            if "ceo_review" in p:
                _check_bool_field(warnings, "planning.ceo_review", p["ceo_review"])
            for mk in ("roadmap_model", "decompose_model"):
                if mk in p:
                    _check_model(warnings, f"planning.{mk}", p[mk])
            known_planning = {
                "enabled",
                "roadmap_model",
                "decompose_model",
                "ceo_review",
            }
            for k in p:
                if k not in known_planning:
                    warnings.append(f"Unknown key planning.{k} (will be ignored)")

    # -- execution section --
    if "execution" in config:
        e = config["execution"]
        if not isinstance(e, dict):
            warnings.append("execution must be a dict")
        else:
            if "enabled" in e:
                _check_bool_field(warnings, "execution.enabled", e["enabled"])
            if "max_depth" in e:
                if not isinstance(e["max_depth"], int) or e["max_depth"] < 3:
                    warnings.append("execution.max_depth must be int >= 3")
            if "timeout" in e:
                if not isinstance(e["timeout"], int) or not (
                    300 <= e["timeout"] <= 7200
                ):
                    warnings.append("execution.timeout must be int 300-7200")
            known_execution = {"enabled", "max_depth", "timeout"}
            for k in e:
                if k not in known_execution:
                    warnings.append(f"Unknown key execution.{k} (will be ignored)")

    # -- validation section --
    if "validation" in config:
        v = config["validation"]
        if not isinstance(v, dict):
            warnings.append("validation must be a dict")
        else:
            if "enabled" in v:
                _check_bool_field(warnings, "validation.enabled", v["enabled"])
            if "max_heal_cycles" in v:
                if not isinstance(v["max_heal_cycles"], int) or not (
                    0 <= v["max_heal_cycles"] <= 5
                ):
                    warnings.append("validation.max_heal_cycles must be int 0-5")
            if "evaluator_model" in v:
                _check_model(
                    warnings, "validation.evaluator_model", v["evaluator_model"]
                )
            known_validation = {"enabled", "max_heal_cycles", "evaluator_model"}
            for k in v:
                if k not in known_validation:
                    warnings.append(f"Unknown key validation.{k} (will be ignored)")

    return warnings


def load_campaign_config(config_path: Path) -> dict:
    """Load and validate campaign config from JSON file.

    Raises:
        FileNotFoundError: Config file not found.
        json.JSONDecodeError: Invalid JSON.
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")

    config: dict = json.loads(config_path.read_text(encoding="utf-8"))

    warnings = validate_campaign_config(config)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    return config


def merge_config(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values take precedence.

    - Nested dicts merge recursively.
    - Lists, scalars, and new keys replace (no list merging).
    - Preserves base keys not in override.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def resolve_campaign_config(config: dict, cli_args: argparse.Namespace) -> dict:
    """Apply CLI argument overrides to config. Precedence: CLI > config > defaults.

    Maps the 3 existing campaign.py CLI args to config structure:
    - cli_args.max_depth -> config["execution"]["max_depth"]
    - cli_args.max_research_rounds -> config["research"]["max_rounds"]
    - cli_args.max_heal_cycles -> config["validation"]["max_heal_cycles"]

    Other config values (models, timeouts, enabled flags) are consumed
    directly by campaign.py internal logic, NOT passed via CLI args.
    """
    if getattr(cli_args, "max_depth", None) is not None:
        config.setdefault("execution", {})["max_depth"] = cli_args.max_depth

    if getattr(cli_args, "max_research_rounds", None) is not None:
        config.setdefault("research", {})["max_rounds"] = cli_args.max_research_rounds

    if getattr(cli_args, "max_heal_cycles", None) is not None:
        config.setdefault("validation", {})["max_heal_cycles"] = (
            cli_args.max_heal_cycles
        )

    return config


# -- L0 spawn config ----------------------------------------------------------


def validate_l0_config(config: dict) -> list[str]:
    """Validate L0 spawn.py config structure.

    Returns list of warning strings. Empty list means valid.
    Warnings (not errors) for forward-compatibility with future config keys.
    """
    warnings: list[str] = []
    known_keys = {
        "model",
        "max_depth",
        "current_depth",
        "output_format",
        "system_prompt",
        "allowed_tools",
        "cwd",
        "permission_mode",
        "session_dir",
        "signal_name",
        "trace_id",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown L0 key: '{key}' (will be ignored)")

    # model: valid tier or claude-*
    if "model" in config:
        _check_model(warnings, "L0.model", config["model"])

    # max_depth: int 1-10
    if "max_depth" in config:
        _check_int_range(warnings, "L0.max_depth", config["max_depth"], 1, 10)

    # output_format: string
    if "output_format" in config:
        _check_str(warnings, "L0.output_format", config["output_format"])

    # permission_mode: enum
    if "permission_mode" in config:
        _check_enum(
            warnings,
            "L0.permission_mode",
            config["permission_mode"],
            VALID_PERMISSION_MODES,
        )

    # allowed_tools: array of strings or null
    if "allowed_tools" in config:
        val = config["allowed_tools"]
        if val is not None:
            if not isinstance(val, list):
                warnings.append("L0.allowed_tools must be list of strings or null")
            else:
                for idx, item in enumerate(val):
                    if not isinstance(item, str) or not item:
                        warnings.append(
                            f"L0.allowed_tools[{idx}] must be non-empty string"
                        )

    # Nullable strings: current_depth, system_prompt, cwd, session_dir, signal_name, trace_id
    for key in (
        "current_depth",
        "system_prompt",
        "cwd",
        "session_dir",
        "signal_name",
        "trace_id",
    ):
        if key in config:
            _check_nullable_str(warnings, f"L0.{key}", config[key])

    return warnings


# -- L1 executor config -------------------------------------------------------


def validate_l1_config(config: dict) -> list[str]:
    """Validate L1 executor config structure (spec.py, researcher.py).

    Returns list of warning strings. Empty list means valid.
    """
    warnings: list[str] = []
    known_keys = {
        "model",
        "max_depth",
        "output_format",
        "cwd",
        "enabled",
        "stage_model_defaults",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown L1 key: '{key}' (will be ignored)")

    # model: valid tier or claude-*
    if "model" in config:
        _check_model(warnings, "L1.model", config["model"])

    # max_depth: int 1-10
    if "max_depth" in config:
        _check_int_range(warnings, "L1.max_depth", config["max_depth"], 1, 10)

    # output_format: string
    if "output_format" in config:
        _check_str(warnings, "L1.output_format", config["output_format"])

    # cwd: string or null
    if "cwd" in config:
        _check_nullable_str(warnings, "L1.cwd", config["cwd"])

    # enabled: bool
    if "enabled" in config:
        _check_bool_field(warnings, "L1.enabled", config["enabled"])

    # stage_model_defaults: dict of string keys to valid model tiers
    if "stage_model_defaults" in config:
        smd = config["stage_model_defaults"]
        if not isinstance(smd, dict):
            warnings.append("L1.stage_model_defaults must be dict")
        else:
            for stage_name, model_val in smd.items():
                if not isinstance(stage_name, str):
                    warnings.append(
                        f"L1.stage_model_defaults key must be string, got {type(stage_name).__name__}"
                    )
                _check_model(
                    warnings, f"L1.stage_model_defaults.{stage_name}", model_val
                )

    return warnings


# -- L2 ospec config ----------------------------------------------------------


def validate_l2_ospec_config(config: dict) -> list[str]:
    """Validate L2 ospec orchestrator config structure.

    Returns list of warning strings. Empty list means valid.
    """
    warnings: list[str] = []
    known_keys = {
        "name",
        "description",
        "executor",
        "modifier",
        "stages",
        "session_dir",
        "max_depth",
        "cwd",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown L2-ospec key: '{key}' (will be ignored)")

    # executor: non-empty string
    if "executor" in config:
        _check_str(warnings, "L2-ospec.executor", config["executor"])

    # modifier: string (validated at runtime by orchestrator)
    if "modifier" in config:
        _check_str(warnings, "L2-ospec.modifier", config["modifier"])

    # max_depth: int 1-10
    if "max_depth" in config:
        _check_int_range(warnings, "L2-ospec.max_depth", config["max_depth"], 1, 10)

    # session_dir, cwd: nullable strings
    for key in ("session_dir", "cwd"):
        if key in config:
            _check_nullable_str(warnings, f"L2-ospec.{key}", config[key])

    # stages: array of stage objects
    if "stages" in config:
        stages = config["stages"]
        if not isinstance(stages, list):
            warnings.append("L2-ospec.stages must be list")
        else:
            known_stage_keys = {"name", "model", "retry", "required", "timeout"}
            for idx, stage in enumerate(stages):
                prefix = f"L2-ospec.stages[{idx}]"
                if not isinstance(stage, dict):
                    warnings.append(f"{prefix} must be dict")
                    continue
                # Unknown stage keys
                for sk in stage:
                    if sk not in known_stage_keys:
                        warnings.append(
                            f"Unknown {prefix} key: '{sk}' (will be ignored)"
                        )
                # name: must be valid stage name
                if "name" in stage:
                    _check_enum(
                        warnings, f"{prefix}.name", stage["name"], VALID_STAGE_NAMES
                    )
                # model: valid tier or claude-*
                if "model" in stage:
                    _check_model(warnings, f"{prefix}.model", stage["model"])
                # retry: int 0-5
                if "retry" in stage:
                    _check_int_range(warnings, f"{prefix}.retry", stage["retry"], 0, 5)
                # required: bool
                if "required" in stage:
                    _check_bool_field(warnings, f"{prefix}.required", stage["required"])
                # timeout: int 60-3600
                if "timeout" in stage:
                    _check_int_range(
                        warnings, f"{prefix}.timeout", stage["timeout"], 60, 3600
                    )

    return warnings


# -- L2 oresearch config ------------------------------------------------------


def validate_l2_oresearch_config(config: dict) -> list[str]:
    """Validate L2 oresearch orchestrator config structure.

    Returns list of warning strings. Empty list means valid.
    """
    warnings: list[str] = []
    known_keys = {
        "name",
        "description",
        "executor",
        "workers",
        "consolidation_model",
        "timeout_per_worker",
        "timeout_overall",
        "max_concurrency",
        "session_dir",
        "max_depth",
        "round_number",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown L2-oresearch key: '{key}' (will be ignored)")

    # executor: non-empty string
    if "executor" in config:
        _check_str(warnings, "L2-oresearch.executor", config["executor"])

    # consolidation_model: valid tier or claude-*
    if "consolidation_model" in config:
        _check_model(
            warnings, "L2-oresearch.consolidation_model", config["consolidation_model"]
        )

    # timeout_per_worker: int 60-1800
    if "timeout_per_worker" in config:
        _check_int_range(
            warnings,
            "L2-oresearch.timeout_per_worker",
            config["timeout_per_worker"],
            60,
            1800,
        )

    # timeout_overall: int >= timeout_per_worker, <= 3600
    if "timeout_overall" in config:
        _check_int_range(
            warnings,
            "L2-oresearch.timeout_overall",
            config["timeout_overall"],
            60,
            3600,
        )

    # Cross-field: timeout_overall >= timeout_per_worker
    if "timeout_overall" in config and "timeout_per_worker" in config:
        to = config["timeout_overall"]
        tpw = config["timeout_per_worker"]
        if isinstance(to, int) and isinstance(tpw, int) and to < tpw:
            warnings.append(
                "L2-oresearch.timeout_overall must be >= timeout_per_worker"
            )

    # max_concurrency: int 1-8
    if "max_concurrency" in config:
        _check_int_range(
            warnings, "L2-oresearch.max_concurrency", config["max_concurrency"], 1, 8
        )

    # max_depth: int 1-10
    if "max_depth" in config:
        _check_int_range(warnings, "L2-oresearch.max_depth", config["max_depth"], 1, 10)

    # round_number: int >= 1
    if "round_number" in config:
        _check_int_range(
            warnings, "L2-oresearch.round_number", config["round_number"], 1, 100
        )

    # session_dir: nullable string
    if "session_dir" in config:
        _check_nullable_str(warnings, "L2-oresearch.session_dir", config["session_dir"])

    # workers: array of worker objects
    if "workers" in config:
        workers = config["workers"]
        if not isinstance(workers, list):
            warnings.append("L2-oresearch.workers must be list")
        else:
            known_worker_keys = {"domain", "model", "focus", "enabled"}
            seen_domains: set[str] = set()
            for idx, worker in enumerate(workers):
                prefix = f"L2-oresearch.workers[{idx}]"
                if not isinstance(worker, dict):
                    warnings.append(f"{prefix} must be dict")
                    continue
                # Unknown worker keys
                for wk in worker:
                    if wk not in known_worker_keys:
                        warnings.append(
                            f"Unknown {prefix} key: '{wk}' (will be ignored)"
                        )
                # domain: non-empty string
                if "domain" in worker:
                    _check_str(warnings, f"{prefix}.domain", worker["domain"])
                    if isinstance(worker["domain"], str) and worker["domain"]:
                        if worker["domain"] in seen_domains:
                            warnings.append(
                                f"{prefix}.domain '{worker['domain']}' is duplicate"
                            )
                        seen_domains.add(worker["domain"])
                # model: valid tier or claude-*
                if "model" in worker:
                    _check_model(warnings, f"{prefix}.model", worker["model"])
                # focus: string or null
                if "focus" in worker:
                    _check_nullable_str(warnings, f"{prefix}.focus", worker["focus"])
                # enabled: bool
                if "enabled" in worker:
                    _check_bool_field(warnings, f"{prefix}.enabled", worker["enabled"])

    return warnings


# -- L3 coordinator config ----------------------------------------------------


def validate_l3_config(config: dict) -> list[str]:
    """Validate L3 coordinator config structure.

    Returns list of warning strings. Empty list means valid.
    Includes DAG validation for phases[].depends_on.
    """
    warnings: list[str] = []
    known_keys = {
        "name",
        "description",
        "phases",
        "max_depth",
        "cwd",
        "session_dir",
        "checkpoint_enabled",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown L3 key: '{key}' (will be ignored)")

    # name: non-empty string
    if "name" in config:
        _check_str(warnings, "L3.name", config["name"])

    # description: string
    if "description" in config:
        _check_str(warnings, "L3.description", config["description"], allow_empty=True)

    # max_depth: int 1-10
    if "max_depth" in config:
        _check_int_range(warnings, "L3.max_depth", config["max_depth"], 1, 10)

    # cwd, session_dir: nullable strings
    for key in ("cwd", "session_dir"):
        if key in config:
            _check_nullable_str(warnings, f"L3.{key}", config[key])

    # checkpoint_enabled: bool
    if "checkpoint_enabled" in config:
        _check_bool_field(
            warnings, "L3.checkpoint_enabled", config["checkpoint_enabled"]
        )

    # phases: array of phase objects with DAG validation
    if "phases" in config:
        phases = config["phases"]
        if not isinstance(phases, list):
            warnings.append("L3.phases must be list")
        else:
            known_phase_keys = {
                "name",
                "orchestrator",
                "modifier",
                "target",
                "depends_on",
                "retry",
                "timeout",
                "required",
            }
            seen_names: list[str] = []
            for idx, phase in enumerate(phases):
                prefix = f"L3.phases[{idx}]"
                if not isinstance(phase, dict):
                    warnings.append(f"{prefix} must be dict")
                    continue
                # Unknown phase keys
                for pk in phase:
                    if pk not in known_phase_keys:
                        warnings.append(
                            f"Unknown {prefix} key: '{pk}' (will be ignored)"
                        )
                # name: required non-empty string
                phase_name = phase.get("name")
                if phase_name is None:
                    warnings.append(f"{prefix}.name is required")
                else:
                    _check_str(warnings, f"{prefix}.name", phase_name)
                    if isinstance(phase_name, str) and phase_name:
                        if phase_name in seen_names:
                            warnings.append(
                                f"{prefix}.name '{phase_name}' is duplicate"
                            )
                        seen_names.append(phase_name)
                # orchestrator: non-empty string
                if "orchestrator" in phase:
                    _check_str(
                        warnings, f"{prefix}.orchestrator", phase["orchestrator"]
                    )
                # modifier: string
                if "modifier" in phase:
                    _check_str(warnings, f"{prefix}.modifier", phase["modifier"])
                # target: string
                if "target" in phase:
                    _check_str(warnings, f"{prefix}.target", phase["target"])
                # retry: int 0-5
                if "retry" in phase:
                    _check_int_range(warnings, f"{prefix}.retry", phase["retry"], 0, 5)
                # timeout: int 300-7200
                if "timeout" in phase:
                    _check_int_range(
                        warnings, f"{prefix}.timeout", phase["timeout"], 300, 7200
                    )
                # required: bool
                if "required" in phase:
                    _check_bool_field(warnings, f"{prefix}.required", phase["required"])
                # depends_on: DAG validation
                if "depends_on" in phase:
                    deps = phase["depends_on"]
                    if not isinstance(deps, list):
                        warnings.append(f"{prefix}.depends_on must be list")
                    else:
                        for dep_idx, dep in enumerate(deps):
                            if not isinstance(dep, str) or not dep:
                                warnings.append(
                                    f"{prefix}.depends_on[{dep_idx}] must be non-empty string"
                                )
                            elif dep not in seen_names:
                                warnings.append(
                                    f"{prefix}.depends_on references '{dep}' "
                                    f"which does not appear earlier in phases array"
                                )
                            elif isinstance(phase_name, str) and dep == phase_name:
                                warnings.append(
                                    f"{prefix}.depends_on self-references '{dep}'"
                                )

    return warnings


# -- Template bundle config ---------------------------------------------------


def validate_template_bundle(config: dict) -> list[str]:
    """Validate template bundle format.

    Returns list of warning strings. Empty list means valid.
    Validates each layer section with its layer-specific validator.
    """
    warnings: list[str] = []
    known_keys = {
        "$schema",
        "template_name",
        "template_version",
        "description",
        "min_stack_version",
        "layers",
    }

    # Unknown top-level keys
    for key in config:
        if key not in known_keys:
            warnings.append(f"Unknown template key: '{key}' (will be ignored)")

    # template_name: required non-empty string
    if "template_name" not in config:
        warnings.append("template.template_name is required")
    else:
        _check_str(warnings, "template.template_name", config["template_name"])

    # template_version: string matching \d+\.\d+
    if "template_version" in config:
        tv = config["template_version"]
        if not isinstance(tv, str):
            warnings.append(
                f"template.template_version must be string, got {type(tv).__name__}"
            )
        else:
            import re

            if not re.fullmatch(r"\d+\.\d+", tv):
                warnings.append(
                    f"template.template_version must match '\\d+.\\d+', got '{tv}'"
                )

    # description: string
    if "description" in config:
        _check_str(
            warnings, "template.description", config["description"], allow_empty=True
        )

    # min_stack_version: string or null
    if "min_stack_version" in config:
        _check_nullable_str(
            warnings, "template.min_stack_version", config["min_stack_version"]
        )

    # layers: dict with valid layer keys
    if "layers" in config:
        layers = config["layers"]
        if not isinstance(layers, dict):
            warnings.append("template.layers must be dict")
        else:
            valid_layer_keys = {"L0", "L1", "L2", "L3", "L4"}
            for lk in layers:
                if lk not in valid_layer_keys:
                    warnings.append(
                        f"Unknown template.layers key: '{lk}' (will be ignored)"
                    )

            # L0: validate with validate_l0_config
            if "L0" in layers:
                l0 = layers["L0"]
                if not isinstance(l0, dict):
                    warnings.append("template.layers.L0 must be dict")
                else:
                    for w in validate_l0_config(l0):
                        warnings.append(f"template.layers.{w}")

            # L1: sub-keys spec, researcher -- each validated by validate_l1_config
            if "L1" in layers:
                l1 = layers["L1"]
                if not isinstance(l1, dict):
                    warnings.append("template.layers.L1 must be dict")
                else:
                    valid_l1_keys = {"spec", "researcher"}
                    for k in l1:
                        if k not in valid_l1_keys:
                            warnings.append(
                                f"Unknown template.layers.L1 key: '{k}' (will be ignored)"
                            )
                    for sub_key in ("spec", "researcher"):
                        if sub_key in l1:
                            if not isinstance(l1[sub_key], dict):
                                warnings.append(
                                    f"template.layers.L1.{sub_key} must be dict"
                                )
                            else:
                                for w in validate_l1_config(l1[sub_key]):
                                    warnings.append(f"template.layers.L1.{sub_key}.{w}")

            # L2: sub-keys ospec, oresearch
            if "L2" in layers:
                l2 = layers["L2"]
                if not isinstance(l2, dict):
                    warnings.append("template.layers.L2 must be dict")
                else:
                    valid_l2_keys = {"ospec", "oresearch"}
                    for k in l2:
                        if k not in valid_l2_keys:
                            warnings.append(
                                f"Unknown template.layers.L2 key: '{k}' (will be ignored)"
                            )
                    if "ospec" in l2:
                        if not isinstance(l2["ospec"], dict):
                            warnings.append("template.layers.L2.ospec must be dict")
                        else:
                            for w in validate_l2_ospec_config(l2["ospec"]):
                                warnings.append(f"template.layers.L2.ospec.{w}")
                    if "oresearch" in l2:
                        if not isinstance(l2["oresearch"], dict):
                            warnings.append("template.layers.L2.oresearch must be dict")
                        else:
                            for w in validate_l2_oresearch_config(l2["oresearch"]):
                                warnings.append(f"template.layers.L2.oresearch.{w}")

            # L3: validate with validate_l3_config
            if "L3" in layers:
                l3 = layers["L3"]
                if not isinstance(l3, dict):
                    warnings.append("template.layers.L3 must be dict")
                else:
                    for w in validate_l3_config(l3):
                        warnings.append(f"template.layers.{w}")

            # L4: validate with validate_campaign_config
            if "L4" in layers:
                l4 = layers["L4"]
                if not isinstance(l4, dict):
                    warnings.append("template.layers.L4 must be dict")
                else:
                    for w in validate_campaign_config(l4):
                        warnings.append(f"template.layers.L4.{w}")

    return warnings


def load_template(name_or_path: str, script_dir: Path | None = None) -> dict:
    """Load and validate a template bundle by name or path.

    If name_or_path ends with '.json', treats it as a direct path.
    Otherwise, resolves from core/tools/agentic/config/templates/<name>.json.

    Returns the validated template dict.

    Raises:
        FileNotFoundError: Template file not found.
        json.JSONDecodeError: Invalid JSON.
    """
    if name_or_path.endswith(".json"):
        template_path = Path(name_or_path)
    else:
        template_relative = Path(
            "core", "tools", "agentic", "config", "templates", f"{name_or_path}.json"
        )
        template_path = resolve_project_file(template_relative, script_dir)

    if not template_path.is_file():
        raise FileNotFoundError(f"Template not found: {template_path}")

    config: dict = json.loads(template_path.read_text(encoding="utf-8"))

    warnings = validate_template_bundle(config)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    return config


def resolve_layer_config(
    template: dict, layer: str, sub_key: str | None = None
) -> dict:
    """Extract layer-specific config from a template bundle.

    Args:
        template: Validated template bundle dict.
        layer: Layer key ("L0", "L1", "L2", "L3", "L4").
        sub_key: Optional sub-key for L1 ("spec", "researcher") or
                 L2 ("ospec", "oresearch").

    Returns:
        Layer config dict (empty dict if layer not present).
    """
    layers = template.get("layers", {})
    if not isinstance(layers, dict):
        return {}

    layer_config = layers.get(layer, {})
    if not isinstance(layer_config, dict):
        return {}

    if sub_key is not None:
        sub_config = layer_config.get(sub_key, {})
        return sub_config if isinstance(sub_config, dict) else {}

    return layer_config
