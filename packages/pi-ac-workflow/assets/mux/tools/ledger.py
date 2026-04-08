#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared mux protocol-state ledger helpers.

This tool owns the authoritative persisted control-plane state for a mux session.
The ledger is stored at:

    <session_dir>/.mux-ledger.json

Phase 003 scope:
- Persist the Phase 002 minimum schema
- Enforce legal control-state transitions
- Persist dispatch/prerequisite/verification/blocker/recovery state atomically
- Append transition history entries atomically with state updates
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

LEDGER_FILE_NAME = ".mux-ledger.json"

ControlState = Literal[
    "LOCK",
    "RESOLVE",
    "DECLARE",
    "DISPATCH",
    "VERIFY",
    "ADVANCE",
    "BLOCK",
    "RECOVER",
]

VerificationStatus = Literal["pending", "pass", "blocked", "fail"]

LEGAL_TRANSITIONS: dict[ControlState, set[ControlState]] = {
    "LOCK": {"RESOLVE"},
    "RESOLVE": {"DECLARE"},
    "DECLARE": {"DISPATCH"},
    "DISPATCH": {"VERIFY"},
    "VERIFY": {"ADVANCE", "BLOCK", "RECOVER"},
    "ADVANCE": set(),
    "BLOCK": {"RESOLVE"},
    "RECOVER": {"RESOLVE"},
}


class DeclaredDispatch(TypedDict):
    worker_type: str
    objective: str
    scope: str
    report_path: str
    signal_path: str
    expected_artifacts: list[str]
    no_nested_subagents: bool


class Prerequisites(TypedDict):
    required: list[str]
    missing: list[str]
    status: str


class Verification(TypedDict):
    status: VerificationStatus
    checked_artifacts: list[str]
    summary_path: str
    verified_at: str


class Blocker(TypedDict):
    active: bool
    reason: str
    missing_prerequisites: list[str]
    opened_at: str
    cleared_at: str


class Recovery(TypedDict):
    required: bool
    trigger: str
    plan: str
    started_at: str
    completed_at: str


class TransitionRecord(TypedDict):
    from_state: str
    to_state: str
    reason: str
    actor: str
    timestamp: str


class ProtocolLedger(TypedDict):
    session_id: str
    phase_id: str
    stage_id: str
    wave_id: str
    control_state: ControlState
    declared_dispatch: DeclaredDispatch
    prerequisites: Prerequisites
    verification: Verification
    blocker: Blocker
    recovery: Recovery
    transition_history: list[TransitionRecord]


class LedgerError(RuntimeError):
    """Base ledger exception."""


class LedgerValidationError(LedgerError):
    """Raised when persisted ledger content is invalid."""


class LedgerTransitionError(LedgerError):
    """Raised when an illegal control-state transition is attempted."""


LedgerMutator = Callable[[ProtocolLedger], None]


def utc_now_iso() -> str:
    """Return an RFC-3339-like UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def resolve_ledger_path(session_dir_or_ledger_path: Path | str) -> Path:
    """Resolve a session directory or explicit ledger file path to ledger path."""
    candidate = Path(session_dir_or_ledger_path)
    if candidate.name == LEDGER_FILE_NAME:
        return candidate
    return candidate / LEDGER_FILE_NAME


def _atomic_write_json(path: Path, payload: dict[str, Any] | ProtocolLedger) -> None:
    """Atomically write JSON data with write-temp-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(str(tmp_path), str(path))


def _default_dispatch() -> DeclaredDispatch:
    return {
        "worker_type": "",
        "objective": "",
        "scope": "",
        "report_path": "",
        "signal_path": "",
        "expected_artifacts": [],
        "no_nested_subagents": True,
    }


def _default_prerequisites() -> Prerequisites:
    return {
        "required": [],
        "missing": [],
        "status": "pending",
    }


def _default_verification() -> Verification:
    return {
        "status": "pending",
        "checked_artifacts": [],
        "summary_path": "",
        "verified_at": "",
    }


def _default_blocker() -> Blocker:
    return {
        "active": False,
        "reason": "",
        "missing_prerequisites": [],
        "opened_at": "",
        "cleared_at": "",
    }


def _default_recovery() -> Recovery:
    return {
        "required": False,
        "trigger": "",
        "plan": "",
        "started_at": "",
        "completed_at": "",
    }


def create_ledger_state(
    *,
    session_id: str,
    phase_id: str,
    stage_id: str,
    wave_id: str,
    actor: str,
) -> ProtocolLedger:
    """Create a new protocol ledger state in LOCK with an initial transition."""
    timestamp = utc_now_iso()
    return {
        "session_id": session_id,
        "phase_id": phase_id,
        "stage_id": stage_id,
        "wave_id": wave_id,
        "control_state": "LOCK",
        "declared_dispatch": _default_dispatch(),
        "prerequisites": _default_prerequisites(),
        "verification": _default_verification(),
        "blocker": _default_blocker(),
        "recovery": _default_recovery(),
        "transition_history": [
            {
                "from_state": "INIT",
                "to_state": "LOCK",
                "reason": "session ledger initialized",
                "actor": actor,
                "timestamp": timestamp,
            }
        ],
    }


def init_ledger(
    session_dir_or_ledger_path: Path | str,
    *,
    session_id: str,
    phase_id: str,
    stage_id: str,
    wave_id: str,
    actor: str = "session.py",
    overwrite: bool = False,
) -> Path:
    """Initialize the protocol ledger file for a session."""
    ledger_path = resolve_ledger_path(session_dir_or_ledger_path)
    if ledger_path.exists() and not overwrite:
        return ledger_path

    state = create_ledger_state(
        session_id=session_id,
        phase_id=phase_id,
        stage_id=stage_id,
        wave_id=wave_id,
        actor=actor,
    )
    _atomic_write_json(ledger_path, state)
    return ledger_path


def _require_str(value: object, *, field: str) -> str:
    if isinstance(value, str):
        return value
    raise LedgerValidationError(f"Invalid ledger field '{field}': expected string")


def _require_bool(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise LedgerValidationError(f"Invalid ledger field '{field}': expected bool")


def _require_list_of_str(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise LedgerValidationError(f"Invalid ledger field '{field}': expected list[str]")
    return cast(list[str], value)


def _validate_control_state(value: object) -> ControlState:
    if value in LEGAL_TRANSITIONS:
        return cast(ControlState, value)
    raise LedgerValidationError(f"Invalid control_state: {value}")


def _normalize_dispatch(raw: object) -> DeclaredDispatch:
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid declared_dispatch: expected object")
    return {
        "worker_type": _require_str(raw.get("worker_type", ""), field="declared_dispatch.worker_type"),
        "objective": _require_str(raw.get("objective", ""), field="declared_dispatch.objective"),
        "scope": _require_str(raw.get("scope", ""), field="declared_dispatch.scope"),
        "report_path": _require_str(raw.get("report_path", ""), field="declared_dispatch.report_path"),
        "signal_path": _require_str(raw.get("signal_path", ""), field="declared_dispatch.signal_path"),
        "expected_artifacts": _require_list_of_str(
            raw.get("expected_artifacts", []),
            field="declared_dispatch.expected_artifacts",
        ),
        "no_nested_subagents": _require_bool(
            raw.get("no_nested_subagents", True),
            field="declared_dispatch.no_nested_subagents",
        ),
    }


def _normalize_prerequisites(raw: object) -> Prerequisites:
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid prerequisites: expected object")
    return {
        "required": _require_list_of_str(raw.get("required", []), field="prerequisites.required"),
        "missing": _require_list_of_str(raw.get("missing", []), field="prerequisites.missing"),
        "status": _require_str(raw.get("status", "pending"), field="prerequisites.status"),
    }


def _normalize_verification(raw: object) -> Verification:
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid verification: expected object")
    status = _require_str(raw.get("status", "pending"), field="verification.status")
    if status not in {"pending", "pass", "blocked", "fail"}:
        raise LedgerValidationError(f"Invalid verification.status: {status}")

    return {
        "status": cast(VerificationStatus, status),
        "checked_artifacts": _require_list_of_str(
            raw.get("checked_artifacts", []),
            field="verification.checked_artifacts",
        ),
        "summary_path": _require_str(raw.get("summary_path", ""), field="verification.summary_path"),
        "verified_at": _require_str(raw.get("verified_at", ""), field="verification.verified_at"),
    }


def _normalize_blocker(raw: object) -> Blocker:
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid blocker: expected object")
    return {
        "active": _require_bool(raw.get("active", False), field="blocker.active"),
        "reason": _require_str(raw.get("reason", ""), field="blocker.reason"),
        "missing_prerequisites": _require_list_of_str(
            raw.get("missing_prerequisites", []),
            field="blocker.missing_prerequisites",
        ),
        "opened_at": _require_str(raw.get("opened_at", ""), field="blocker.opened_at"),
        "cleared_at": _require_str(raw.get("cleared_at", ""), field="blocker.cleared_at"),
    }


def _normalize_recovery(raw: object) -> Recovery:
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid recovery: expected object")
    return {
        "required": _require_bool(raw.get("required", False), field="recovery.required"),
        "trigger": _require_str(raw.get("trigger", ""), field="recovery.trigger"),
        "plan": _require_str(raw.get("plan", ""), field="recovery.plan"),
        "started_at": _require_str(raw.get("started_at", ""), field="recovery.started_at"),
        "completed_at": _require_str(raw.get("completed_at", ""), field="recovery.completed_at"),
    }


def _normalize_transition_history(raw: object) -> list[TransitionRecord]:
    if not isinstance(raw, list):
        raise LedgerValidationError("Invalid transition_history: expected list")

    normalized: list[TransitionRecord] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise LedgerValidationError(f"Invalid transition_history[{idx}]: expected object")
        normalized.append(
            {
                "from_state": _require_str(item.get("from_state", ""), field=f"transition_history[{idx}].from_state"),
                "to_state": _require_str(item.get("to_state", ""), field=f"transition_history[{idx}].to_state"),
                "reason": _require_str(item.get("reason", ""), field=f"transition_history[{idx}].reason"),
                "actor": _require_str(item.get("actor", ""), field=f"transition_history[{idx}].actor"),
                "timestamp": _require_str(item.get("timestamp", ""), field=f"transition_history[{idx}].timestamp"),
            }
        )
    return normalized


def load_ledger(session_dir_or_ledger_path: Path | str) -> ProtocolLedger:
    """Load and validate ledger state from disk."""
    ledger_path = resolve_ledger_path(session_dir_or_ledger_path)
    if not ledger_path.exists():
        raise LedgerValidationError(f"Ledger does not exist: {ledger_path}")

    raw = json.loads(ledger_path.read_text())
    if not isinstance(raw, dict):
        raise LedgerValidationError("Invalid ledger payload: expected object")

    return {
        "session_id": _require_str(raw.get("session_id", ""), field="session_id"),
        "phase_id": _require_str(raw.get("phase_id", ""), field="phase_id"),
        "stage_id": _require_str(raw.get("stage_id", ""), field="stage_id"),
        "wave_id": _require_str(raw.get("wave_id", ""), field="wave_id"),
        "control_state": _validate_control_state(raw.get("control_state", "")),
        "declared_dispatch": _normalize_dispatch(raw.get("declared_dispatch", _default_dispatch())),
        "prerequisites": _normalize_prerequisites(raw.get("prerequisites", _default_prerequisites())),
        "verification": _normalize_verification(raw.get("verification", _default_verification())),
        "blocker": _normalize_blocker(raw.get("blocker", _default_blocker())),
        "recovery": _normalize_recovery(raw.get("recovery", _default_recovery())),
        "transition_history": _normalize_transition_history(raw.get("transition_history", [])),
    }


def save_ledger(session_dir_or_ledger_path: Path | str, state: ProtocolLedger) -> Path:
    """Persist a validated ledger state atomically."""
    ledger_path = resolve_ledger_path(session_dir_or_ledger_path)
    # Validate before writing so malformed state never persists.
    _ = load_ledger_payload(state)
    _atomic_write_json(ledger_path, state)
    return ledger_path


def load_ledger_payload(payload: ProtocolLedger | dict[str, Any]) -> ProtocolLedger:
    """Validate a ledger payload already in memory."""
    return {
        "session_id": _require_str(payload.get("session_id", ""), field="session_id"),
        "phase_id": _require_str(payload.get("phase_id", ""), field="phase_id"),
        "stage_id": _require_str(payload.get("stage_id", ""), field="stage_id"),
        "wave_id": _require_str(payload.get("wave_id", ""), field="wave_id"),
        "control_state": _validate_control_state(payload.get("control_state", "")),
        "declared_dispatch": _normalize_dispatch(payload.get("declared_dispatch", _default_dispatch())),
        "prerequisites": _normalize_prerequisites(payload.get("prerequisites", _default_prerequisites())),
        "verification": _normalize_verification(payload.get("verification", _default_verification())),
        "blocker": _normalize_blocker(payload.get("blocker", _default_blocker())),
        "recovery": _normalize_recovery(payload.get("recovery", _default_recovery())),
        "transition_history": _normalize_transition_history(payload.get("transition_history", [])),
    }


def mutate_ledger(session_dir_or_ledger_path: Path | str, mutator: LedgerMutator) -> ProtocolLedger:
    """Apply a mutator and persist the entire ledger atomically."""
    ledger_path = resolve_ledger_path(session_dir_or_ledger_path)
    state = load_ledger(ledger_path)
    mutator(state)
    validated_state = load_ledger_payload(state)
    _atomic_write_json(ledger_path, validated_state)
    return validated_state


def validate_declared_dispatch(dispatch: DeclaredDispatch | dict[str, Any]) -> tuple[bool, str]:
    """Validate declared dispatch payload against the minimum contract."""
    required_str_fields = [
        "worker_type",
        "objective",
        "scope",
        "report_path",
        "signal_path",
    ]
    for field in required_str_fields:
        value = dispatch.get(field)
        if not isinstance(value, str) or not value.strip():
            return False, f"declared_dispatch.{field} must be a non-empty string"

    expected_artifacts = dispatch.get("expected_artifacts")
    if not isinstance(expected_artifacts, list) or not all(
        isinstance(item, str) and item.strip() for item in expected_artifacts
    ):
        return False, "declared_dispatch.expected_artifacts must be a non-empty list[str]"

    expected = {artifact.strip().lower() for artifact in expected_artifacts}
    if not {"report", "signal", "summary"}.issubset(expected):
        return False, "declared_dispatch.expected_artifacts must include report, signal, and summary"

    if dispatch.get("no_nested_subagents") is not True:
        return False, "declared_dispatch.no_nested_subagents must be true"

    return True, ""


def _append_transition(
    state: ProtocolLedger,
    *,
    from_state: ControlState,
    to_state: ControlState,
    reason: str,
    actor: str,
) -> None:
    state["transition_history"].append(
        {
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "actor": actor,
            "timestamp": utc_now_iso(),
        }
    )


def _assert_transition_preconditions(
    state: ProtocolLedger,
    *,
    from_state: ControlState,
    to_state: ControlState,
) -> None:
    if to_state not in LEGAL_TRANSITIONS[from_state]:
        raise LedgerTransitionError(f"Illegal transition: {from_state} -> {to_state}")

    if from_state == "LOCK" and to_state == "RESOLVE":
        if not state["phase_id"].strip() or not state["stage_id"].strip():
            raise LedgerTransitionError("LOCK -> RESOLVE requires persisted phase_id and stage_id")

    if from_state == "RESOLVE" and to_state == "DECLARE":
        prerequisites = state["prerequisites"]
        status = prerequisites["status"].strip().lower()
        if status not in {"ready", "satisfied", "pass"}:
            raise LedgerTransitionError("RESOLVE -> DECLARE requires prerequisites.status=ready")
        if prerequisites["missing"]:
            raise LedgerTransitionError("RESOLVE -> DECLARE forbidden while prerequisites.missing is non-empty")

    if from_state == "DECLARE" and to_state == "DISPATCH":
        is_valid, error = validate_declared_dispatch(state["declared_dispatch"])
        if not is_valid:
            raise LedgerTransitionError(f"DECLARE -> DISPATCH requires valid declared_dispatch: {error}")

    if from_state == "VERIFY" and to_state == "ADVANCE":
        if state["verification"]["status"] != "pass":
            raise LedgerTransitionError("VERIFY -> ADVANCE requires verification.status=pass")

    if from_state == "VERIFY" and to_state == "BLOCK":
        if not state["blocker"]["active"]:
            raise LedgerTransitionError("VERIFY -> BLOCK requires blocker.active=true")

    if from_state == "VERIFY" and to_state == "RECOVER":
        if not state["recovery"]["required"]:
            raise LedgerTransitionError("VERIFY -> RECOVER requires recovery.required=true")

    if from_state == "BLOCK" and to_state == "RESOLVE":
        blocker = state["blocker"]
        if blocker["active"]:
            raise LedgerTransitionError("BLOCK -> RESOLVE requires blocker.active=false")
        if not blocker["cleared_at"]:
            raise LedgerTransitionError("BLOCK -> RESOLVE requires blocker.cleared_at evidence")

    if from_state == "RECOVER" and to_state == "RESOLVE":
        recovery = state["recovery"]
        if recovery["required"]:
            raise LedgerTransitionError("RECOVER -> RESOLVE requires recovery.required=false")
        if not recovery["completed_at"]:
            raise LedgerTransitionError("RECOVER -> RESOLVE requires recovery.completed_at evidence")


def transition_control_state(
    session_dir_or_ledger_path: Path | str,
    *,
    to_state: ControlState,
    reason: str,
    actor: str,
) -> ProtocolLedger:
    """Transition control_state when legal and persist transition history atomically."""

    def mutator(state: ProtocolLedger) -> None:
        current = state["control_state"]
        _assert_transition_preconditions(state, from_state=current, to_state=to_state)
        state["control_state"] = to_state
        _append_transition(
            state,
            from_state=current,
            to_state=to_state,
            reason=reason,
            actor=actor,
        )

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def set_prerequisites(
    session_dir_or_ledger_path: Path | str,
    *,
    required: Sequence[str],
    missing: Sequence[str],
    status: str | None,
) -> ProtocolLedger:
    """Persist prerequisite evaluation atomically."""
    required_list = [item for item in required if item]
    missing_list = [item for item in missing if item]
    status_value = status or ("blocked" if missing_list else "ready")

    def mutator(state: ProtocolLedger) -> None:
        state["prerequisites"] = {
            "required": required_list,
            "missing": missing_list,
            "status": status_value,
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def set_declared_dispatch(
    session_dir_or_ledger_path: Path | str,
    *,
    worker_type: str,
    objective: str,
    scope: str,
    report_path: str,
    signal_path: str,
    expected_artifacts: Sequence[str],
    no_nested_subagents: bool,
) -> ProtocolLedger:
    """Persist declared dispatch atomically."""
    dispatch: DeclaredDispatch = {
        "worker_type": worker_type,
        "objective": objective,
        "scope": scope,
        "report_path": report_path,
        "signal_path": signal_path,
        "expected_artifacts": [artifact for artifact in expected_artifacts if artifact],
        "no_nested_subagents": no_nested_subagents,
    }

    is_valid, error = validate_declared_dispatch(dispatch)
    if not is_valid:
        raise LedgerValidationError(error)

    def mutator(state: ProtocolLedger) -> None:
        state["declared_dispatch"] = dispatch

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def set_verification(
    session_dir_or_ledger_path: Path | str,
    *,
    status: VerificationStatus,
    checked_artifacts: Sequence[str],
    summary_path: str,
) -> ProtocolLedger:
    """Persist verification evidence atomically."""

    def mutator(state: ProtocolLedger) -> None:
        state["verification"] = {
            "status": status,
            "checked_artifacts": [item for item in checked_artifacts if item],
            "summary_path": summary_path,
            "verified_at": utc_now_iso(),
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def open_blocker(
    session_dir_or_ledger_path: Path | str,
    *,
    reason: str,
    missing_prerequisites: Sequence[str],
) -> ProtocolLedger:
    """Persist blocker state atomically."""

    def mutator(state: ProtocolLedger) -> None:
        state["blocker"] = {
            "active": True,
            "reason": reason,
            "missing_prerequisites": [item for item in missing_prerequisites if item],
            "opened_at": utc_now_iso(),
            "cleared_at": "",
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def clear_blocker(
    session_dir_or_ledger_path: Path | str,
    *,
    reason: str,
) -> ProtocolLedger:
    """Persist blocker clearance evidence atomically."""

    def mutator(state: ProtocolLedger) -> None:
        previous_reason = state["blocker"]["reason"]
        merged_reason = reason if not previous_reason else f"{previous_reason}; {reason}"
        state["blocker"] = {
            "active": False,
            "reason": merged_reason,
            "missing_prerequisites": [],
            "opened_at": state["blocker"]["opened_at"],
            "cleared_at": utc_now_iso(),
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def start_recovery(
    session_dir_or_ledger_path: Path | str,
    *,
    trigger: str,
    plan: str,
) -> ProtocolLedger:
    """Persist recovery-start evidence atomically."""

    def mutator(state: ProtocolLedger) -> None:
        state["recovery"] = {
            "required": True,
            "trigger": trigger,
            "plan": plan,
            "started_at": utc_now_iso(),
            "completed_at": "",
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def complete_recovery(
    session_dir_or_ledger_path: Path | str,
    *,
    completion_note: str,
) -> ProtocolLedger:
    """Persist recovery completion evidence atomically."""

    def mutator(state: ProtocolLedger) -> None:
        previous_plan = state["recovery"]["plan"]
        merged_plan = completion_note if not previous_plan else f"{previous_plan}; {completion_note}"
        state["recovery"] = {
            "required": False,
            "trigger": state["recovery"]["trigger"],
            "plan": merged_plan,
            "started_at": state["recovery"]["started_at"],
            "completed_at": utc_now_iso(),
        }

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def apply_verification_gate(
    session_dir_or_ledger_path: Path | str,
    *,
    verification_status: Literal["pass", "blocked", "fail"],
    checked_artifacts: Sequence[str],
    summary_path: str,
    actor: str,
    reason: str,
    blocker_reason: str = "",
    missing_prerequisites: Sequence[str] = (),
    recovery_trigger: str = "",
    recovery_plan: str = "",
) -> ProtocolLedger:
    """Apply DISPATCH->VERIFY plus terminal ADVANCE|BLOCK|RECOVER atomically."""

    def mutator(state: ProtocolLedger) -> None:
        from_state = state["control_state"]
        if from_state != "DISPATCH":
            raise LedgerTransitionError(
                f"Verification gate requires DISPATCH state, found: {from_state}"
            )

        _assert_transition_preconditions(
            state,
            from_state="DISPATCH",
            to_state="VERIFY",
        )
        state["control_state"] = "VERIFY"
        _append_transition(
            state,
            from_state="DISPATCH",
            to_state="VERIFY",
            reason="verification gate started",
            actor=actor,
        )

        state["verification"] = {
            "status": cast(VerificationStatus, verification_status),
            "checked_artifacts": [item for item in checked_artifacts if item],
            "summary_path": summary_path,
            "verified_at": utc_now_iso(),
        }

        if verification_status == "pass":
            _assert_transition_preconditions(
                state,
                from_state="VERIFY",
                to_state="ADVANCE",
            )
            state["control_state"] = "ADVANCE"
            _append_transition(
                state,
                from_state="VERIFY",
                to_state="ADVANCE",
                reason=reason,
                actor=actor,
            )
            return

        if verification_status == "blocked":
            state["blocker"] = {
                "active": True,
                "reason": blocker_reason or reason,
                "missing_prerequisites": [item for item in missing_prerequisites if item],
                "opened_at": utc_now_iso(),
                "cleared_at": "",
            }
            _assert_transition_preconditions(
                state,
                from_state="VERIFY",
                to_state="BLOCK",
            )
            state["control_state"] = "BLOCK"
            _append_transition(
                state,
                from_state="VERIFY",
                to_state="BLOCK",
                reason=reason,
                actor=actor,
            )
            return

        state["recovery"] = {
            "required": True,
            "trigger": recovery_trigger or reason,
            "plan": recovery_plan or "repair protocol state before resume",
            "started_at": utc_now_iso(),
            "completed_at": "",
        }
        _assert_transition_preconditions(
            state,
            from_state="VERIFY",
            to_state="RECOVER",
        )
        state["control_state"] = "RECOVER"
        _append_transition(
            state,
            from_state="VERIFY",
            to_state="RECOVER",
            reason=reason,
            actor=actor,
        )

    return mutate_ledger(session_dir_or_ledger_path, mutator)


def _print_state(state: ProtocolLedger) -> None:
    print(json.dumps(state, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage mux protocol-state ledger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize ledger")
    init_parser.add_argument("session_dir", help="Session directory path")
    init_parser.add_argument("--session-id", default="", help="Session identifier")
    init_parser.add_argument("--phase-id", default="phase-unknown", help="Phase identifier")
    init_parser.add_argument("--stage-id", default="stage-unknown", help="Stage identifier")
    init_parser.add_argument("--wave-id", default="wave-unknown", help="Wave identifier")
    init_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing ledger")

    show_parser = subparsers.add_parser("show", help="Show ledger")
    show_parser.add_argument("session_dir", help="Session directory path")

    transition_parser = subparsers.add_parser("transition", help="Transition control state")
    transition_parser.add_argument("session_dir", help="Session directory path")
    transition_parser.add_argument("--to", required=True, choices=sorted(LEGAL_TRANSITIONS.keys()))
    transition_parser.add_argument("--reason", default="state transition")
    transition_parser.add_argument("--actor", default="ledger.py")

    prereq_parser = subparsers.add_parser("prerequisites", help="Set prerequisites")
    prereq_parser.add_argument("session_dir", help="Session directory path")
    prereq_parser.add_argument("--required", action="append", default=[])
    prereq_parser.add_argument("--missing", action="append", default=[])
    prereq_parser.add_argument("--status", default=None)

    declare_parser = subparsers.add_parser("declare", help="Set declared dispatch")
    declare_parser.add_argument("session_dir", help="Session directory path")
    declare_parser.add_argument("--worker-type", required=True)
    declare_parser.add_argument("--objective", required=True)
    declare_parser.add_argument("--scope", required=True)
    declare_parser.add_argument("--report-path", required=True)
    declare_parser.add_argument("--signal-path", required=True)
    declare_parser.add_argument("--expected-artifact", action="append", required=True)
    declare_parser.add_argument("--allow-nested-subagents", action="store_true")

    blocker_open_parser = subparsers.add_parser("blocker-open", help="Open blocker")
    blocker_open_parser.add_argument("session_dir", help="Session directory path")
    blocker_open_parser.add_argument("--reason", required=True)
    blocker_open_parser.add_argument("--missing", action="append", default=[])

    blocker_clear_parser = subparsers.add_parser("blocker-clear", help="Clear blocker")
    blocker_clear_parser.add_argument("session_dir", help="Session directory path")
    blocker_clear_parser.add_argument("--reason", default="blocker cleared")

    recovery_start_parser = subparsers.add_parser("recovery-start", help="Start recovery")
    recovery_start_parser.add_argument("session_dir", help="Session directory path")
    recovery_start_parser.add_argument("--trigger", required=True)
    recovery_start_parser.add_argument("--plan", required=True)

    recovery_complete_parser = subparsers.add_parser("recovery-complete", help="Complete recovery")
    recovery_complete_parser.add_argument("session_dir", help="Session directory path")
    recovery_complete_parser.add_argument("--note", default="recovery complete")

    verification_parser = subparsers.add_parser("verification", help="Record verification")
    verification_parser.add_argument("session_dir", help="Session directory path")
    verification_parser.add_argument("--status", required=True, choices=["pending", "pass", "blocked", "fail"])
    verification_parser.add_argument("--checked-artifact", action="append", default=[])
    verification_parser.add_argument("--summary-path", default="")

    args = parser.parse_args()

    try:
        if args.command == "init":
            session_dir = Path(args.session_dir)
            session_id = args.session_id or session_dir.name
            ledger_path = init_ledger(
                session_dir,
                session_id=session_id,
                phase_id=args.phase_id,
                stage_id=args.stage_id,
                wave_id=args.wave_id,
                actor="ledger.py",
                overwrite=args.overwrite,
            )
            print(str(ledger_path))
            return 0

        if args.command == "show":
            _print_state(load_ledger(args.session_dir))
            return 0

        if args.command == "transition":
            state = transition_control_state(
                args.session_dir,
                to_state=cast(ControlState, args.to),
                reason=args.reason,
                actor=args.actor,
            )
            _print_state(state)
            return 0

        if args.command == "prerequisites":
            state = set_prerequisites(
                args.session_dir,
                required=args.required,
                missing=args.missing,
                status=args.status,
            )
            _print_state(state)
            return 0

        if args.command == "declare":
            state = set_declared_dispatch(
                args.session_dir,
                worker_type=args.worker_type,
                objective=args.objective,
                scope=args.scope,
                report_path=args.report_path,
                signal_path=args.signal_path,
                expected_artifacts=args.expected_artifact,
                no_nested_subagents=not args.allow_nested_subagents,
            )
            _print_state(state)
            return 0

        if args.command == "blocker-open":
            state = open_blocker(
                args.session_dir,
                reason=args.reason,
                missing_prerequisites=args.missing,
            )
            _print_state(state)
            return 0

        if args.command == "blocker-clear":
            state = clear_blocker(
                args.session_dir,
                reason=args.reason,
            )
            _print_state(state)
            return 0

        if args.command == "recovery-start":
            state = start_recovery(
                args.session_dir,
                trigger=args.trigger,
                plan=args.plan,
            )
            _print_state(state)
            return 0

        if args.command == "recovery-complete":
            state = complete_recovery(
                args.session_dir,
                completion_note=args.note,
            )
            _print_state(state)
            return 0

        if args.command == "verification":
            state = set_verification(
                args.session_dir,
                status=cast(VerificationStatus, args.status),
                checked_artifacts=args.checked_artifact,
                summary_path=args.summary_path,
            )
            _print_state(state)
            return 0

    except (LedgerError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
