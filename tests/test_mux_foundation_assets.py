#!/usr/bin/env python3
"""Smoke and deterministic tests for generated mux foundation assets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUX_TOOLS_ROOT = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "tools"
PI_MUX_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux" / "SKILL.md"
PI_MUX_OSPEC_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-ospec" / "SKILL.md"
PI_MUX_ROADMAP_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-roadmap" / "SKILL.md"
PI_MUX_SUBAGENT_SKILL = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "skills" / "ac-workflow-mux-subagent" / "SKILL.md"
CLAUDE_MUX_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux" / "SKILL.md"
CLAUDE_MUX_OSPEC_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-ospec" / "SKILL.md"
CLAUDE_MUX_ROADMAP_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-roadmap" / "SKILL.md"
CLAUDE_MUX_SUBAGENT_SKILL = PROJECT_ROOT / "plugins" / "ac-workflow" / "skills" / "mux-subagent" / "SKILL.md"
LEDGER_FILE_NAME = ".mux-ledger.json"


def run_python_script(script_path: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a generated Python helper and capture its output."""
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_output_value(stdout: str, key: str) -> str:
    """Extract a `KEY=value` line from helper stdout."""
    prefix = f"{key}="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"Missing {key} in output: {stdout}")


def parse_session_dir(stdout: str) -> str:
    """Extract the relative session directory from session.py output."""
    return parse_output_value(stdout, "SESSION_DIR")


def parse_json_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse JSON payload from a subprocess stdout stream."""
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:  # pragma: no cover - assertion helper path
        raise AssertionError(
            f"Expected JSON output.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from error

    if not isinstance(payload, dict):
        raise AssertionError(f"Expected JSON object, got: {type(payload)!r}")
    return payload


def run_ledger_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ledger.py helper."""
    return run_python_script(MUX_TOOLS_ROOT / "ledger.py", *args, cwd=cwd)


def read_ledger(workspace: Path, session_dir_rel: str) -> dict[str, Any]:
    """Read persisted mux protocol ledger from a session."""
    ledger_path = workspace / session_dir_rel / LEDGER_FILE_NAME
    return json.loads(ledger_path.read_text())


def create_workspace(tmp_path: Path) -> Path:
    """Create isolated workspace with a .git root."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    return workspace


def create_session(workspace: Path, topic_slug: str) -> str:
    """Create mux session and return relative session directory path."""
    result = run_python_script(
        MUX_TOOLS_ROOT / "session.py",
        topic_slug,
        "--base",
        "tmp/mux-smoke",
        "--phase-id",
        "it005",
        "--stage-id",
        "phase-003",
        "--wave-id",
        "wave-004",
        cwd=workspace,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return parse_session_dir(result.stdout)


def create_strict_session(workspace: Path, topic_slug: str, session_key: str) -> subprocess.CompletedProcess[str]:
    """Create strict mux session bootstrap output for activation/cleanup tests."""
    result = run_python_script(
        MUX_TOOLS_ROOT / "session.py",
        topic_slug,
        "--base",
        "tmp/mux-smoke",
        "--phase-id",
        "it005",
        "--stage-id",
        "phase-004",
        "--wave-id",
        "strict-runtime",
        "--strict-runtime",
        "--session-key",
        session_key,
        cwd=workspace,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def configure_dispatch_state(
    workspace: Path,
    session_dir_rel: str,
    report_rel: str,
    signal_rel: str,
) -> None:
    """Drive ledger state into DISPATCH with valid prerequisites + declared dispatch."""
    prerequisites_result = run_ledger_script(
        "prerequisites",
        session_dir_rel,
        "--required",
        "phase-target",
        "--status",
        "ready",
        cwd=workspace,
    )
    assert prerequisites_result.returncode == 0, prerequisites_result.stdout + prerequisites_result.stderr

    transition_to_resolve = run_ledger_script(
        "transition",
        session_dir_rel,
        "--to",
        "RESOLVE",
        "--reason",
        "phase target persisted",
        cwd=workspace,
    )
    assert transition_to_resolve.returncode == 0, transition_to_resolve.stdout + transition_to_resolve.stderr

    transition_to_declare = run_ledger_script(
        "transition",
        session_dir_rel,
        "--to",
        "DECLARE",
        "--reason",
        "prerequisites evaluated",
        cwd=workspace,
    )
    assert transition_to_declare.returncode == 0, transition_to_declare.stdout + transition_to_declare.stderr

    declare_result = run_ledger_script(
        "declare",
        session_dir_rel,
        "--worker-type",
        "worker",
        "--objective",
        "implement approved bounded change",
        "--scope",
        "phase-003 approved files only",
        "--report-path",
        report_rel,
        "--signal-path",
        signal_rel,
        "--expected-artifact",
        "report",
        "--expected-artifact",
        "signal",
        "--expected-artifact",
        "summary",
        cwd=workspace,
    )
    assert declare_result.returncode == 0, declare_result.stdout + declare_result.stderr

    transition_to_dispatch = run_ledger_script(
        "transition",
        session_dir_rel,
        "--to",
        "DISPATCH",
        "--reason",
        "declared dispatch validated",
        cwd=workspace,
    )
    assert transition_to_dispatch.returncode == 0, transition_to_dispatch.stdout + transition_to_dispatch.stderr


def write_worker_report(path: Path) -> None:
    """Write markdown report with an Executive Summary section."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Worker Report\n\n"
        "## Table of Contents\n"
        "- Item\n\n"
        "## Executive Summary\n"
        "- **Status**: pass\n"
        "- **Files**: reports/worker.md\n\n"
        "### Next Steps\n"
        "- **Recommended action**: continue\n"
        "- **Dependencies**: none\n"
        "- **Routing hint**: writer\n"
    )


def emit_success_signal(workspace: Path, signal_rel: str, report_rel: str) -> None:
    """Emit deterministic success signal for a report artifact."""
    signal_result = run_python_script(
        MUX_TOOLS_ROOT / "signal.py",
        signal_rel,
        "--path",
        report_rel,
        "--status",
        "success",
        cwd=workspace,
    )
    assert signal_result.returncode == 0, signal_result.stdout + signal_result.stderr


def emit_summary_evidence(workspace: Path, report_rel: str, summary_evidence_rel: str) -> None:
    """Emit machine-readable summary evidence for a report artifact."""
    summary_result = run_python_script(
        MUX_TOOLS_ROOT / "extract-summary.py",
        report_rel,
        "--evidence",
        "--evidence-path",
        summary_evidence_rel,
        cwd=workspace,
    )
    assert summary_result.returncode == 0, summary_result.stdout + summary_result.stderr


def run_verify_gate(
    workspace: Path,
    session_dir_rel: str,
    *,
    summary_evidence_rel: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run verify.py gate action with optional summary evidence path."""
    args: list[str] = [session_dir_rel, "--action", "gate"]
    if summary_evidence_rel is not None:
        args.extend(["--summary-evidence", summary_evidence_rel])
    return run_python_script(
        MUX_TOOLS_ROOT / "verify.py",
        *args,
        cwd=workspace,
    )


def test_generated_mux_claude_frontmatter_survives_generation() -> None:
    """The canonical generator should preserve mux-specific Claude frontmatter extras."""
    mux_text = CLAUDE_MUX_SKILL.read_text()
    assert "hooks:" in mux_text
    assert "matcher: Read|Write|Edit|NotebookEdit|Grep|Glob|WebSearch|WebFetch|TaskOutput|Skill|Bash|Task" in mux_text
    assert "${CLAUDE_PLUGIN_ROOT}/skills/mux/hooks/mux-orchestrator-guard.py" in mux_text

    mux_ospec_text = CLAUDE_MUX_OSPEC_SKILL.read_text()
    assert "argument-hint:" in mux_ospec_text
    assert "requires-skills:" in mux_ospec_text
    assert "- spec" in mux_ospec_text

    mux_roadmap_text = CLAUDE_MUX_ROADMAP_SKILL.read_text()
    assert "**Modes:**" in mux_roadmap_text
    assert "`start` - New session." in mux_roadmap_text
    assert "`continue` - Resume session." in mux_roadmap_text

    subagent_text = CLAUDE_MUX_SUBAGENT_SKILL.read_text()
    assert "hooks:" in subagent_text
    assert "matcher: TaskOutput" in subagent_text
    assert "${CLAUDE_PLUGIN_ROOT}/mux/subagent-hooks/mux-subagent-guard.py" in subagent_text


def test_generated_pi_mux_foundation_assets_exist() -> None:
    """The pi workflow package should ship mux foundation assets and skill family."""
    protocol_files = [
        "subagent.md",
        "foundation.md",
        "guardrail-policy.md",
        "strict-happy-path-transcript.md",
        "strict-blocker-path-transcript.md",
        "strict-regression-checklist.md",
    ]

    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "README.md").exists()
    assert (MUX_TOOLS_ROOT / "session.py").exists()
    assert (MUX_TOOLS_ROOT / "ledger.py").exists()
    assert (MUX_TOOLS_ROOT / "signal.py").exists()
    assert (MUX_TOOLS_ROOT / "verify.py").exists()
    assert PI_MUX_SKILL.exists()
    assert PI_MUX_OSPEC_SKILL.exists()
    assert PI_MUX_ROADMAP_SKILL.exists()
    assert PI_MUX_SUBAGENT_SKILL.exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "index.ts").exists()
    assert (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "strict-mux-runtime" / "index.js").exists()

    package_protocol_root = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "protocol"
    plugin_protocol_root = PROJECT_ROOT / "plugins" / "ac-workflow" / "mux" / "protocol"
    for protocol_file in protocol_files:
        assert (package_protocol_root / protocol_file).exists()
        assert (plugin_protocol_root / protocol_file).exists()

    subagent_text = PI_MUX_SUBAGENT_SKILL.read_text()
    assert "../../assets/mux/tools/signal.py" in subagent_text
    assert "../../assets/mux/protocol/subagent.md" in subagent_text
    assert "binding runtime contract" in subagent_text
    assert "data-plane only" in subagent_text
    assert "Do not launch nested `subagent` calls" in subagent_text
    assert "control-plane bridge tools or `report_parent`" in subagent_text


def test_generated_pi_mux_orchestrators_reference_shared_foundation() -> None:
    """Generated pi mux orchestrators should preserve mux semantics while routing through pimux."""
    mux_text = PI_MUX_SKILL.read_text()
    assert "allowed-tools:" in mux_text
    assert "  - pimux" in mux_text
    assert "  - Read" not in mux_text
    assert "  - Bash" not in mux_text
    assert "  - subagent" not in mux_text
    assert "binding runtime contract" in mux_text
    assert "current session is a `pimux`-only control plane" in mux_text
    assert "The first real move is to spawn the authoritative `pimux` child coordinator." in mux_text
    assert "The first observable parent tool call must be `pimux spawn`." in mux_text
    assert "Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`" in mux_text
    assert "The parent does not use repo `Read`, `Bash`, `Edit`, `Write`, `NotebookEdit`, `Grep`, `Glob`, `web_search`" in mux_text
    assert "../../assets/mux/protocol/foundation.md" in mux_text
    assert "coordinator -> subagent" in mux_text
    assert "--strict-runtime --session-key <key>" in mux_text

    mux_ospec_text = PI_MUX_OSPEC_SKILL.read_text()
    assert "argument-hint: '[modifier] [spec_path|inline_prompt]'" in mux_ospec_text
    assert "  - pimux" in mux_ospec_text
    assert "  - Read" not in mux_ospec_text
    assert "  - Bash" not in mux_ospec_text
    assert "  - subagent" not in mux_ospec_text
    assert "binding runtime contract" in mux_ospec_text
    assert "current session is a `pimux`-only cross-stage orchestrator" in mux_ospec_text
    assert "Do not read, grep, or inspect repo files in the parent" in mux_ospec_text
    assert "The first real move is to spawn the authoritative stage-owning `pimux` child." in mux_ospec_text
    assert "The first observable parent tool call must be `pimux spawn`." in mux_ospec_text
    assert "Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`" in mux_ospec_text
    assert "no-spec invocation starts at Stage `000 CREATE`" in mux_ospec_text
    assert "inline prompt without a spec path" in mux_ospec_text
    assert "route to `BLOCK`" in mux_ospec_text

    mux_roadmap_text = PI_MUX_ROADMAP_SKILL.read_text()
    assert "  - pimux" in mux_roadmap_text
    assert "  - Read" not in mux_roadmap_text
    assert "  - Bash" not in mux_roadmap_text
    assert "  - subagent" not in mux_roadmap_text
    assert "binding runtime contract" in mux_roadmap_text
    assert "current session is a `pimux`-only roadmap orchestrator" in mux_roadmap_text
    assert "Do not inspect roadmap files, phase docs, or repo targets in the parent before spawn." in mux_roadmap_text
    assert "The first observable parent tool call must be `pimux spawn`." in mux_roadmap_text
    assert "Before the first child exists, the parent must not call `Read`, `Bash`, `Edit`, `Write`" in mux_roadmap_text
    assert "For explicit `mux-roadmap` requests, lock this default hierarchy:" in mux_roadmap_text
    assert "direct phase-owning `/mux-ospec` child" in mux_roadmap_text
    assert "direct stage-owning `pimux` child" in mux_roadmap_text
    assert "Do not collapse or bypass these ownership layers by default." in mux_roadmap_text
    assert "inline prompt without a path" in mux_roadmap_text
    assert "No silent fallback to non-`pimux` runtime for explicit mux-roadmap execution." in mux_roadmap_text


def test_generated_pi_mux_foundation_docs_reflect_post_it005_release_boundary() -> None:
    """Generated shared mux docs should reflect the shipped post-IT005 release boundary."""
    foundation_text = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "protocol" / "foundation.md").read_text()
    assert "Phase 005 hardens `mux-ospec` as the canonical strict consumer." in foundation_text
    assert "Phase 006 aligns sibling `mux` / `mux-roadmap` surfaces to the strict control-plane contract" in foundation_text
    assert "Phase 007 ships the guardrail-policy split plus transcript/checklist protocol artifacts for deterministic strict-flow documentation." in foundation_text
    assert "later phases still own transcripts/checklists and final release-surface alignment" not in foundation_text
    assert "Later release-surface closeout still owns final packaging/reporting reconciliation work outside this shared foundation." not in foundation_text
    assert "Package/roadmap release-surface bookkeeping consumes this shared foundation" in foundation_text

    mux_assets_readme = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "README.md").read_text()
    assert "Phase 004/005/006 now ship the runtime seam plus strict control-plane consumption across `mux-ospec`, `mux`, and `mux-roadmap`." in mux_assets_readme
    assert "Phase 007 now ships guardrail-policy and transcript/checklist protocol artifacts under `assets/mux/protocol/`." in mux_assets_readme
    assert "Later IT005 phases still own transcript/checklist artifacts and final release-surface closeout." not in mux_assets_readme


def test_generated_pi_mux_protocol_artifacts_cover_phase_007_contract() -> None:
    """Generated protocol artifacts should document strict happy/blocker semantics honestly."""
    protocol_root = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "assets" / "mux" / "protocol"

    subagent_text = (protocol_root / "subagent.md").read_text()
    assert "data-plane" in subagent_text
    assert "final textual response exactly `0`" in subagent_text
    assert "control-plane bridge tools or `report_parent`" in subagent_text

    guardrail_text = (protocol_root / "guardrail-policy.md").read_text()
    assert "Guardrail layer matrix" in guardrail_text
    assert "Strict runtime" in guardrail_text
    assert "Hook guard" in guardrail_text
    assert "Worker protocol prose" in guardrail_text

    happy_transcript = (protocol_root / "strict-happy-path-transcript.md").read_text()
    assert "--strict-runtime" in happy_transcript
    assert "--session-key phase-007-happy-key" in happy_transcript
    assert "REPORT_PATH=tmp/mux/phase-007/reports/strict-happy-runtime-worker.md" in happy_transcript
    assert 'SIGNAL_PATH="${SESSION_DIR}/.signals/strict-happy-runtime-worker.done"' in happy_transcript
    assert 'SUMMARY_EVIDENCE_PATH="${SESSION_DIR}/research/strict-happy-runtime-summary-evidence.json"' in happy_transcript
    assert 'extract-summary.py "$REPORT_PATH"' in happy_transcript
    assert "--evidence" in happy_transcript
    assert '--evidence-path "$SUMMARY_EVIDENCE_PATH"' in happy_transcript
    assert 'verify.py "$SESSION_DIR"' in happy_transcript
    assert "--action gate" in happy_transcript
    assert '--summary-evidence "$SUMMARY_EVIDENCE_PATH"' in happy_transcript
    assert '"gate_status": "advance"' in happy_transcript
    assert '"control_state": "ADVANCE"' in happy_transcript

    blocker_transcript = (protocol_root / "strict-blocker-path-transcript.md").read_text()
    assert "--strict-runtime" in blocker_transcript
    assert "--session-key phase-007-blocker-key" in blocker_transcript
    assert "REPORT_PATH=tmp/mux/phase-007/reports/strict-blocker-runtime-worker.md" in blocker_transcript
    assert 'SIGNAL_PATH="${SESSION_DIR}/.signals/strict-blocker-runtime-worker.done"' in blocker_transcript
    assert (
        'MISSING_SUMMARY_EVIDENCE_PATH="${SESSION_DIR}/research/strict-blocker-runtime-summary-evidence.json"'
        in blocker_transcript
    )
    assert 'verify.py "$SESSION_DIR"' in blocker_transcript
    assert "--action gate" in blocker_transcript
    assert '--summary-evidence "$MISSING_SUMMARY_EVIDENCE_PATH"' in blocker_transcript
    assert '"gate_status": "block"' in blocker_transcript
    assert '"control_state": "BLOCK"' in blocker_transcript
    assert "ERROR: Illegal transition: BLOCK -> ADVANCE" in blocker_transcript

    checklist_text = (protocol_root / "strict-regression-checklist.md").read_text()
    assert "**A01**" in checklist_text
    assert "**B01**" in checklist_text
    assert "**B02**" in checklist_text
    assert "**B03**" in checklist_text
    assert "**C02**" in checklist_text
    assert "**F03**" in checklist_text
    assert "project-root-relative report/signal/summary paths." in checklist_text
    assert "extract-summary.py --evidence --evidence-path <path>" in checklist_text
    assert "verify.py --action gate --summary-evidence <path>" in checklist_text
    assert "session.py --strict-runtime --session-key <key>" in checklist_text
    assert "**H01**" in checklist_text
    assert "**H05**" in checklist_text
    assert "Prompt Matrix — Explicit Strict Invocation Cases" in checklist_text
    assert "MUX_OSPEC_ACK" in checklist_text
    assert "gate_status: block" in checklist_text
    assert "control_state: RECOVER" in checklist_text
    assert "**R01**" in checklist_text
    assert "**R05**" in checklist_text
    assert "`ADVANCE` is reachable only via a passed gate with valid report + signal + summary evidence." in checklist_text


def test_generated_mux_tools_support_session_signal_and_summary_flow(tmp_path: Path) -> None:
    """Generated mux helpers should keep the original smoke flow compatible."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="phase-007-smoke")

    session_dir = workspace / session_dir_rel
    assert session_dir.exists()
    assert (session_dir / ".signals").exists()

    report_rel = "reports/worker.md"
    report_path = workspace / report_rel
    write_worker_report(report_path)

    signal_rel = f"{session_dir_rel}/.signals/worker.done"
    signal_result = run_python_script(
        MUX_TOOLS_ROOT / "signal.py",
        signal_rel,
        "--path",
        report_rel,
        "--status",
        "success",
        cwd=workspace,
    )
    assert signal_result.returncode == 0, signal_result.stdout + signal_result.stderr
    assert (workspace / signal_rel).exists()

    verify_result = run_python_script(
        MUX_TOOLS_ROOT / "verify.py",
        session_dir_rel,
        "--action",
        "summary",
        cwd=workspace,
    )
    assert verify_result.returncode == 0, verify_result.stdout + verify_result.stderr
    assert "completed: 1" in verify_result.stdout
    assert "failed: 0" in verify_result.stdout

    check_result = run_python_script(
        MUX_TOOLS_ROOT / "check-signals.py",
        session_dir_rel,
        "--expected",
        "1",
        cwd=workspace,
    )
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert '"status": "complete"' in check_result.stdout

    summary_result = run_python_script(
        MUX_TOOLS_ROOT / "extract-summary.py",
        report_rel,
        cwd=workspace,
    )
    assert summary_result.returncode == 0, summary_result.stdout + summary_result.stderr
    assert "## Executive Summary" in summary_result.stdout
    assert "**Status**: pass" in summary_result.stdout


def test_session_initializes_mux_protocol_ledger(tmp_path: Path) -> None:
    """session.py should initialize the authoritative protocol ledger file."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="ledger-init")

    ledger = read_ledger(workspace, session_dir_rel)
    required_keys = {
        "session_id",
        "phase_id",
        "stage_id",
        "wave_id",
        "control_state",
        "declared_dispatch",
        "prerequisites",
        "verification",
        "blocker",
        "recovery",
        "transition_history",
    }
    assert required_keys.issubset(ledger)
    assert ledger["control_state"] == "LOCK"
    assert ledger["phase_id"] == "it005"
    assert ledger["stage_id"] == "phase-003"
    assert ledger["wave_id"] == "wave-004"

    transition_history = ledger["transition_history"]
    assert isinstance(transition_history, list)
    assert transition_history
    first_transition = transition_history[0]
    assert first_transition["from"] == "INIT"
    assert first_transition["to"] == "LOCK"


def test_session_strict_runtime_writes_activation_artifacts(tmp_path: Path) -> None:
    """session.py should write explicit strict-runtime artifacts only when requested."""
    workspace = create_workspace(tmp_path)
    session_key = "phase-004-strict-session"
    result = create_strict_session(workspace, topic_slug="strict-runtime-artifacts", session_key=session_key)

    session_dir_rel = parse_session_dir(result.stdout)
    strict_runtime_file_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_FILE")
    strict_runtime_registry_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_REGISTRY")
    strict_runtime_hash = parse_output_value(result.stdout, "STRICT_RUNTIME_SESSION_KEY_HASH")

    assert parse_output_value(result.stdout, "STRICT_RUNTIME") == "true"
    assert strict_runtime_hash == hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:24]

    activation_file = workspace / strict_runtime_file_rel
    registry_file = workspace / strict_runtime_registry_rel
    assert activation_file.exists()
    assert registry_file.exists()

    activation_payload = json.loads(activation_file.read_text())
    registry_payload = json.loads(registry_file.read_text())
    assert activation_payload == registry_payload
    assert activation_payload["mode"] == "strict"
    assert activation_payload["session_key"] == session_key
    assert activation_payload["session_key_hash"] == strict_runtime_hash
    assert activation_payload["session_dir"] == session_dir_rel
    assert activation_payload["ledger_path"] == f"{session_dir_rel}/{LEDGER_FILE_NAME}"
    assert activation_payload["activation_file"] == strict_runtime_file_rel
    assert activation_payload["registry_path"] == strict_runtime_registry_rel
    assert activation_payload["allowed_write_roots"] == [".specs"]
    assert session_dir_rel not in activation_payload["allowed_write_roots"]
    assert "outputs/session/mux-runtime" not in activation_payload["allowed_write_roots"]


def test_deactivate_removes_strict_runtime_artifacts(tmp_path: Path) -> None:
    """deactivate.py should remove strict-runtime activation artifacts by session key."""
    workspace = create_workspace(tmp_path)
    session_key = "phase-004-deactivate-session"
    result = create_strict_session(workspace, topic_slug="strict-runtime-deactivate", session_key=session_key)

    strict_runtime_file_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_FILE")
    strict_runtime_registry_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_REGISTRY")
    activation_file = workspace / strict_runtime_file_rel
    registry_file = workspace / strict_runtime_registry_rel
    assert activation_file.exists()
    assert registry_file.exists()

    deactivate_result = run_python_script(
        MUX_TOOLS_ROOT / "deactivate.py",
        "--session-key",
        session_key,
        cwd=workspace,
    )
    assert deactivate_result.returncode == 0, deactivate_result.stdout + deactivate_result.stderr
    assert parse_output_value(deactivate_result.stdout, "STRICT_RUNTIME_DEACTIVATED") == "true"
    assert not activation_file.exists()
    assert not registry_file.exists()


def test_deactivate_skips_activation_cleanup_when_registry_payload_is_tampered(tmp_path: Path) -> None:
    """deactivate.py should fail closed when registry activation_file points outside strict artifacts."""
    workspace = create_workspace(tmp_path)
    session_key = "phase-004-deactivate-tampered-session"
    result = create_strict_session(workspace, topic_slug="strict-runtime-deactivate-tampered", session_key=session_key)

    strict_runtime_file_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_FILE")
    strict_runtime_registry_rel = parse_output_value(result.stdout, "STRICT_RUNTIME_REGISTRY")
    activation_file = workspace / strict_runtime_file_rel
    registry_file = workspace / strict_runtime_registry_rel
    protected_file = workspace / "do-not-delete.txt"
    protected_file.write_text("preserve\n")

    assert activation_file.exists()
    assert registry_file.exists()
    assert protected_file.exists()

    tampered_registry_payload = json.loads(registry_file.read_text())
    tampered_registry_payload["activation_file"] = "do-not-delete.txt"
    registry_file.write_text(json.dumps(tampered_registry_payload, indent=2, sort_keys=True) + "\n")

    deactivate_result = run_python_script(
        MUX_TOOLS_ROOT / "deactivate.py",
        "--session-key",
        session_key,
        cwd=workspace,
    )
    assert deactivate_result.returncode == 0, deactivate_result.stdout + deactivate_result.stderr
    assert parse_output_value(deactivate_result.stdout, "STRICT_RUNTIME_DEACTIVATED") == "true"
    assert protected_file.exists()
    assert activation_file.exists()
    assert not registry_file.exists()


def test_mux_ledger_accepts_legal_flow_and_rejects_illegal_transition(tmp_path: Path) -> None:
    """Ledger should accept legal state flow and reject illegal jumps."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="legal-illegal-transitions")

    report_rel = "reports/legal-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/legal-worker.done"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)

    signal_result = run_python_script(
        MUX_TOOLS_ROOT / "signal.py",
        signal_rel,
        "--path",
        report_rel,
        "--status",
        "success",
        cwd=workspace,
    )
    assert signal_result.returncode == 0, signal_result.stdout + signal_result.stderr

    summary_evidence_rel = f"{session_dir_rel}/research/legal-summary-evidence.json"
    summary_result = run_python_script(
        MUX_TOOLS_ROOT / "extract-summary.py",
        report_rel,
        "--evidence",
        "--evidence-path",
        summary_evidence_rel,
        cwd=workspace,
    )
    assert summary_result.returncode == 0, summary_result.stdout + summary_result.stderr

    gate_result = run_python_script(
        MUX_TOOLS_ROOT / "verify.py",
        session_dir_rel,
        "--action",
        "gate",
        "--summary-evidence",
        summary_evidence_rel,
        cwd=workspace,
    )
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr
    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "advance"
    assert gate_payload["checked_artifacts"] == [
        report_rel,
        signal_rel,
        summary_evidence_rel,
    ]

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "ADVANCE"
    transitions = [
        (entry["from"], entry["to"])
        for entry in ledger["transition_history"]
    ]
    assert transitions == [
        ("INIT", "LOCK"),
        ("LOCK", "RESOLVE"),
        ("RESOLVE", "DECLARE"),
        ("DECLARE", "DISPATCH"),
        ("DISPATCH", "VERIFY"),
        ("VERIFY", "ADVANCE"),
    ]

    illegal_transition = run_ledger_script(
        "transition",
        session_dir_rel,
        "--to",
        "DECLARE",
        "--reason",
        "attempt invalid backtrack",
        cwd=workspace,
    )
    assert illegal_transition.returncode == 1
    assert "Illegal transition" in illegal_transition.stderr

    ledger_after_illegal = read_ledger(workspace, session_dir_rel)
    assert ledger_after_illegal["control_state"] == "ADVANCE"


def test_mux_ledger_blocker_and_recovery_bookkeeping(tmp_path: Path) -> None:
    """Blocker and recovery payloads should persist deterministic evidence."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="blocker-recovery-bookkeeping")

    blocker_open_result = run_ledger_script(
        "blocker-open",
        session_dir_rel,
        "--reason",
        "missing prerequisite artifact",
        "--missing",
        "research/required.md",
        cwd=workspace,
    )
    assert blocker_open_result.returncode == 0, blocker_open_result.stdout + blocker_open_result.stderr

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["blocker"]["active"] is True
    assert ledger["blocker"]["reason"] == "missing prerequisite artifact"
    assert ledger["blocker"]["missing_prerequisites"] == ["research/required.md"]
    assert ledger["blocker"]["opened_at"]

    blocker_clear_result = run_ledger_script(
        "blocker-clear",
        session_dir_rel,
        "--reason",
        "prerequisite artifact restored",
        cwd=workspace,
    )
    assert blocker_clear_result.returncode == 0, blocker_clear_result.stdout + blocker_clear_result.stderr

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["blocker"]["active"] is False
    assert ledger["blocker"]["cleared_at"]
    assert "prerequisite artifact restored" in ledger["blocker"]["reason"]

    recovery_start_result = run_ledger_script(
        "recovery-start",
        session_dir_rel,
        "--trigger",
        "protocol violation detected",
        "--plan",
        "rerun verify after redeclare",
        cwd=workspace,
    )
    assert recovery_start_result.returncode == 0, recovery_start_result.stdout + recovery_start_result.stderr

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["recovery"]["required"] is True
    assert ledger["recovery"]["trigger"] == "protocol violation detected"
    assert ledger["recovery"]["plan"] == "rerun verify after redeclare"
    assert ledger["recovery"]["started_at"]

    recovery_complete_result = run_ledger_script(
        "recovery-complete",
        session_dir_rel,
        "--note",
        "recovery evidence persisted",
        cwd=workspace,
    )
    assert recovery_complete_result.returncode == 0, recovery_complete_result.stdout + recovery_complete_result.stderr

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["recovery"]["required"] is False
    assert ledger["recovery"]["completed_at"]
    assert "recovery evidence persisted" in ledger["recovery"]["plan"]


def test_verify_gate_rejects_missing_summary_evidence(tmp_path: Path) -> None:
    """Gate should block when report/signal exists but summary evidence is missing."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="missing-summary-evidence")

    report_rel = "reports/missing-summary-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/missing-summary-worker.done"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)

    signal_result = run_python_script(
        MUX_TOOLS_ROOT / "signal.py",
        signal_rel,
        "--path",
        report_rel,
        "--status",
        "success",
        cwd=workspace,
    )
    assert signal_result.returncode == 0, signal_result.stdout + signal_result.stderr

    missing_summary_evidence_rel = f"{session_dir_rel}/research/summary-missing.json"
    gate_result = run_python_script(
        MUX_TOOLS_ROOT / "verify.py",
        session_dir_rel,
        "--action",
        "gate",
        "--summary-evidence",
        missing_summary_evidence_rel,
        cwd=workspace,
    )
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "block"

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "BLOCK"
    assert ledger["verification"]["status"] == "blocked"
    assert ledger["blocker"]["active"] is True

    transitions = [
        (entry["from"], entry["to"])
        for entry in ledger["transition_history"]
    ]
    assert ("DISPATCH", "VERIFY") in transitions
    assert ("VERIFY", "BLOCK") in transitions


def test_verify_gate_recovers_on_invalid_declared_dispatch(tmp_path: Path) -> None:
    """Gate should move to RECOVER when declared dispatch payload is invalid."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="invalid-declared-dispatch")

    report_rel = "reports/invalid-dispatch-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/invalid-dispatch-worker.done"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    ledger_path = workspace / session_dir_rel / LEDGER_FILE_NAME
    ledger_payload = json.loads(ledger_path.read_text())
    declared_dispatch = ledger_payload["declared_dispatch"]
    assert isinstance(declared_dispatch, dict)
    declared_dispatch["objective"] = ""
    ledger_path.write_text(json.dumps(ledger_payload, indent=2, sort_keys=True) + "\n")

    gate_result = run_verify_gate(workspace, session_dir_rel)
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "recover"
    assert "declared_dispatch.objective" in gate_payload["reason"]

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "RECOVER"
    assert ledger["verification"]["status"] == "fail"


def test_verify_gate_blocks_on_missing_report_artifact(tmp_path: Path) -> None:
    """Gate should BLOCK when report evidence is missing."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="missing-report-artifact")

    report_rel = "reports/missing-report-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/missing-report-worker.done"
    summary_evidence_rel = f"{session_dir_rel}/research/missing-report-summary.json"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)
    emit_success_signal(workspace, signal_rel, report_rel)
    emit_summary_evidence(workspace, report_rel, summary_evidence_rel)

    report_path.unlink()

    gate_result = run_verify_gate(
        workspace,
        session_dir_rel,
        summary_evidence_rel=summary_evidence_rel,
    )
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "block"
    assert f"missing report artifact: {report_rel}" in gate_payload["missing_evidence"]

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "BLOCK"
    assert ledger["verification"]["status"] == "blocked"
    assert ledger["verification"]["checked_artifacts"] == [
        signal_rel,
        summary_evidence_rel,
    ]


def test_verify_gate_blocks_on_missing_signal_artifact(tmp_path: Path) -> None:
    """Gate should BLOCK when signal evidence is missing."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="missing-signal-artifact")

    report_rel = "reports/missing-signal-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/missing-signal-worker.done"
    summary_evidence_rel = f"{session_dir_rel}/research/missing-signal-summary.json"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)
    emit_summary_evidence(workspace, report_rel, summary_evidence_rel)

    gate_result = run_verify_gate(
        workspace,
        session_dir_rel,
        summary_evidence_rel=summary_evidence_rel,
    )
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "block"
    assert f"missing signal artifact: {signal_rel}" in gate_payload["missing_evidence"]

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "BLOCK"
    assert ledger["verification"]["status"] == "blocked"
    assert ledger["verification"]["checked_artifacts"] == [
        report_rel,
        summary_evidence_rel,
    ]


def test_verify_gate_recovers_on_inconsistent_summary_metadata(tmp_path: Path) -> None:
    """Gate should RECOVER when summary evidence metadata is stale for the same report path."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="inconsistent-summary-evidence")

    report_rel = "reports/inconsistent-summary-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/inconsistent-summary-worker.done"
    summary_evidence_rel = f"{session_dir_rel}/research/inconsistent-summary.json"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)
    emit_success_signal(workspace, signal_rel, report_rel)
    emit_summary_evidence(workspace, report_rel, summary_evidence_rel)

    report_path.write_text(report_path.read_text() + "\nUpdated after summary extraction.\n")

    gate_result = run_verify_gate(
        workspace,
        session_dir_rel,
        summary_evidence_rel=summary_evidence_rel,
    )
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "recover"
    assert gate_payload["checked_artifacts"] == [
        report_rel,
        signal_rel,
        summary_evidence_rel,
    ]
    assert any(
        "summary evidence" in issue and "does not match report artifact" in issue
        for issue in gate_payload["inconsistent_evidence"]
    )

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "RECOVER"
    assert ledger["verification"]["status"] == "fail"


def test_mux_ledger_fails_closed_when_required_sections_missing(tmp_path: Path) -> None:
    """Ledger load should fail closed when a required top-level section is missing."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="missing-ledger-section")

    ledger_path = workspace / session_dir_rel / LEDGER_FILE_NAME
    ledger_payload = json.loads(ledger_path.read_text())
    del ledger_payload["verification"]
    ledger_path.write_text(json.dumps(ledger_payload, indent=2, sort_keys=True) + "\n")

    show_result = run_ledger_script("show", session_dir_rel, cwd=workspace)
    assert show_result.returncode == 1
    assert "Missing required ledger field(s): verification" in show_result.stderr


def test_mux_ledger_fails_closed_when_required_identifier_missing(tmp_path: Path) -> None:
    """Ledger load should fail closed when a required identifier is missing."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="missing-ledger-identifier")

    ledger_path = workspace / session_dir_rel / LEDGER_FILE_NAME
    ledger_payload = json.loads(ledger_path.read_text())
    del ledger_payload["stage_id"]
    ledger_path.write_text(json.dumps(ledger_payload, indent=2, sort_keys=True) + "\n")

    show_result = run_ledger_script("show", session_dir_rel, cwd=workspace)
    assert show_result.returncode == 1
    assert "Missing required ledger field(s): stage_id" in show_result.stderr


def test_mux_ledger_rejects_illegal_advancement_from_advance_state(tmp_path: Path) -> None:
    """Ledger should reject illegal ADVANCE->ADVANCE transition explicitly."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="illegal-advancement-from-advance")

    report_rel = "reports/illegal-adv-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/illegal-adv-worker.done"
    summary_evidence_rel = f"{session_dir_rel}/research/illegal-adv-summary.json"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)
    emit_success_signal(workspace, signal_rel, report_rel)
    emit_summary_evidence(workspace, report_rel, summary_evidence_rel)

    gate_result = run_verify_gate(
        workspace,
        session_dir_rel,
        summary_evidence_rel=summary_evidence_rel,
    )
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "ADVANCE"

    illegal_advancement = run_ledger_script(
        "transition",
        session_dir_rel,
        "--to",
        "ADVANCE",
        "--reason",
        "attempt bypass: ADVANCE->ADVANCE",
        cwd=workspace,
    )
    assert illegal_advancement.returncode == 1
    assert "Illegal transition" in illegal_advancement.stderr

    ledger_after = read_ledger(workspace, session_dir_rel)
    assert ledger_after["control_state"] == "ADVANCE"


def test_mux_ledger_blocker_path_never_silently_bypasses(tmp_path: Path) -> None:
    """Blocker path should never silently bypass; missing evidence always routes to BLOCK."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="blocker-never-bypasses")

    report_rel = "reports/blocker-bypass-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/blocker-bypass-worker.done"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    report_path = workspace / report_rel
    write_worker_report(report_path)
    emit_success_signal(workspace, signal_rel, report_rel)

    blocker_open_result = run_ledger_script(
        "blocker-open",
        session_dir_rel,
        "--reason",
        "missing prerequisite artifact",
        "--missing",
        "research/required.md",
        cwd=workspace,
    )
    assert blocker_open_result.returncode == 0, blocker_open_result.stdout + blocker_open_result.stderr

    gate_result = run_verify_gate(workspace, session_dir_rel)
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "block"

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "BLOCK"
    assert ledger["blocker"]["active"] is True


def test_mux_ledger_recovery_path_never_silent_fallback(tmp_path: Path) -> None:
    """Recovery path should never silently fall back; protocol violations always route to RECOVER."""
    workspace = create_workspace(tmp_path)
    session_dir_rel = create_session(workspace, topic_slug="recovery-never-fallback")

    report_rel = "reports/recovery-fallback-worker.md"
    signal_rel = f"{session_dir_rel}/.signals/recovery-fallback-worker.done"
    configure_dispatch_state(workspace, session_dir_rel, report_rel, signal_rel)

    ledger_path = workspace / session_dir_rel / LEDGER_FILE_NAME
    ledger_payload = json.loads(ledger_path.read_text())
    assert "declared_dispatch" in ledger_payload
    ledger_payload["declared_dispatch"]["objective"] = ""
    ledger_path.write_text(json.dumps(ledger_payload, indent=2, sort_keys=True) + "\n")

    gate_result = run_verify_gate(workspace, session_dir_rel)
    assert gate_result.returncode == 1, gate_result.stdout + gate_result.stderr

    gate_payload = parse_json_stdout(gate_result)
    assert gate_payload["gate_status"] == "recover"
    assert "declared_dispatch.objective" in gate_payload["reason"]

    ledger = read_ledger(workspace, session_dir_rel)
    assert ledger["control_state"] == "RECOVER"
    assert ledger["recovery"]["required"] is True
