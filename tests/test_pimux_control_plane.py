#!/usr/bin/env python3
"""Behavior checks for pimux control-plane lock helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTROL_PLANE_RUNTIME = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "control-plane.ts"

NODE_RUNTIME_EVAL = """
import { pathToFileURL } from "node:url";

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const runtime = await import(pathToFileURL(helperPath).href);
const writeJson = (value) => process.stdout.write(JSON.stringify(value ?? null));

if (payload.action === "parse") {
  writeJson(runtime.parseExplicitControlPlaneTrigger(payload.text));
  process.exit(0);
}

if (payload.action === "extract_spec_path") {
  writeJson(runtime.extractSpecPathFromUserInput(payload.text));
  process.exit(0);
}

if (payload.action === "resolve_pending_spec_path") {
  writeJson(runtime.resolvePendingControlPlaneSpecPath(payload.lock, payload.text));
  process.exit(0);
}

if (payload.action === "prepare_spawn") {
  writeJson(await runtime.prepareControlPlaneSpawn(payload.lock, payload.prompt));
  process.exit(0);
}

if (payload.action === "build_lock") {
  writeJson(runtime.buildControlPlaneLock(payload.trigger, payload.previousActiveTools));
  process.exit(0);
}

if (payload.action === "evaluate") {
  writeJson(runtime.evaluateControlPlaneToolCall(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "update_tool_result") {
  writeJson(runtime.updateControlPlaneLockForToolResult(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "child_activity") {
  writeJson(runtime.updateControlPlaneLockForChildActivity(payload.lock, payload.event, payload.now));
  process.exit(0);
}

if (payload.action === "terminal_settlement") {
  writeJson(runtime.updateControlPlaneLockForTerminalSettlement(payload.lock, payload.event, payload.now));
  process.exit(0);
}

throw new Error(`Unsupported action: ${payload.action}`);
""".strip()


def run_runtime(payload: dict[str, Any], cwd: Path = PROJECT_ROOT) -> Any:
    """Execute the control-plane helper through Node and parse JSON output."""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            NODE_RUNTIME_EVAL,
            str(CONTROL_PLANE_RUNTIME),
            json.dumps(payload),
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Node control-plane helper execution failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def create_branch_spec_workspace(tmp_path: Path, branch_name: str = "pi-adoption-it001") -> Path:
    """Create an isolated git workspace with existing branch-local spec history."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    init_result = subprocess.run(
        ["git", "init"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    checkout_result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checkout_result.returncode == 0, checkout_result.stdout + checkout_result.stderr

    spec_dir = workspace / ".specs" / "specs" / "2026" / "04" / branch_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "007-existing-spec.md").write_text("# Existing spec\n")
    return workspace


def spawn_post_lock(spawned_at: str = "2026-04-17T10:00:00Z") -> dict[str, Any]:
    """Create a post-spawn mux-ospec lock at a fixed timestamp for pacing tests."""
    pre_spawn = run_runtime(
        {
            "action": "build_lock",
            "trigger": {
                "mode": "mux-ospec",
                "source": "skill-command",
                "specPath": ".specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
                "requiresSpecPath": False,
            },
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    return run_runtime(
        {
            "action": "update_tool_result",
            "lock": pre_spawn,
            "event": {
                "toolName": "pimux",
                "details": {"action": "spawn", "agent": {"agentId": "mux-ospec-stage-001"}},
                "isError": False,
            },
            "now": spawned_at,
        }
    )


def test_parse_skill_command_extracts_mux_ospec_path() -> None:
    """Explicit skill command invocations should bind mux-ospec and capture the path."""
    parsed = run_runtime(
        {
            "action": "parse",
            "text": "/skill:mux-ospec full .specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
        }
    )
    assert parsed == {
        "mode": "mux-ospec",
        "source": "skill-command",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/007-consolidate-mux-naming-and-enforce-ospec-workflow.md",
        "requiresSpecPath": False,
    }


def test_parse_embedded_skill_trigger_auto_derives_spec_path_from_inline_prompt(tmp_path: Path) -> None:
    """Embedded mux-ospec prompts should derive the next branch-local spec path without AskUserQuestion."""
    workspace = create_branch_spec_workspace(tmp_path)
    parsed = run_runtime(
        {
            "action": "parse",
            "text": (
                '<skill name="mux-ospec" location="/tmp/mux-ospec/SKILL.md">'
                "Use tmux-backed spec stage orchestration."
                "</skill>\n\nfull\nInline prompt auto spec paths for mux ospec and mux roadmap"
            ),
        },
        cwd=workspace,
    )
    assert parsed == {
        "mode": "mux-ospec",
        "source": "embedded-skill",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md",
        "requiresSpecPath": False,
    }


def test_parse_mux_roadmap_inline_prompt_auto_derives_spec_path(tmp_path: Path) -> None:
    """Explicit mux-roadmap prompts should also mirror the current-branch spec-path pattern."""
    workspace = create_branch_spec_workspace(tmp_path)
    parsed = run_runtime(
        {
            "action": "parse",
            "text": "/mux-roadmap Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    assert parsed == {
        "mode": "mux-roadmap",
        "source": "alias-command",
        "specPath": ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-roadmap.md",
        "requiresSpecPath": False,
    }


def test_extract_spec_path_from_follow_up_answer_finds_path_token() -> None:
    """A later user answer should be enough to resolve the pending mux-ospec path."""
    path_text = "Use this spec: .specs/specs/2026/04/pi-adoption-it001/006-make-pimux-the-pi-mux-runtime.md"
    extracted = run_runtime({"action": "extract_spec_path", "text": path_text})
    assert extracted == ".specs/specs/2026/04/pi-adoption-it001/006-make-pimux-the-pi-mux-runtime.md"


def test_pending_mux_ospec_lock_accepts_follow_up_inline_prompt(tmp_path: Path) -> None:
    """A pending mux-ospec lock should resolve from a later inline prompt, not only from an explicit path token."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "full Inline prompt auto spec paths for mux ospec and mux roadmap",
        },
        cwd=workspace,
    )
    assert resolved_spec_path == ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md"


def test_pending_mux_ospec_lock_rejects_help_slash_command(tmp_path: Path) -> None:
    """A pending mux-ospec lock must ignore slash commands like /help when resolving spec paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "/help",
        },
        cwd=workspace,
    )
    assert resolved_spec_path is None

    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": pending_lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_pending_mux_ospec_lock_rejects_spec_slash_command(tmp_path: Path) -> None:
    """A pending mux-ospec lock must ignore slash commands like /spec CREATE when resolving spec paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "/spec CREATE",
        },
        cwd=workspace,
    )
    assert resolved_spec_path is None

    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": pending_lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_pending_mux_roadmap_lock_accepts_follow_up_inline_prompt(tmp_path: Path) -> None:
    """A pending mux-roadmap lock should also resolve from a later inline prompt."""
    workspace = create_branch_spec_workspace(tmp_path)
    pending_lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-roadmap", "source": "alias-command", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    resolved_spec_path = run_runtime(
        {
            "action": "resolve_pending_spec_path",
            "lock": pending_lock,
            "text": "Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    assert resolved_spec_path == ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-roadmap.md"



def test_prepare_spawn_creates_missing_bound_spec_and_binds_prompt(tmp_path: Path) -> None:
    """Bound mux spec paths should be created before spawn and injected into the child prompt when absent."""
    workspace = create_branch_spec_workspace(tmp_path)
    spec_path = ".specs/specs/2026/04/pi-adoption-it001/008-inline-prompt-auto-spec-paths-for-mux-ospec-and-mux-roadmap.md"
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {
                "mode": "mux-ospec",
                "source": "skill-command",
                "specPath": spec_path,
                "requiresSpecPath": False,
            },
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    prepared = run_runtime(
        {
            "action": "prepare_spawn",
            "lock": lock,
            "prompt": "Run the next stage.",
        },
        cwd=workspace,
    )
    assert prepared == {
        "prompt": f"Use this spec path for the run, and create it first if missing:\n{spec_path}\n\nRun the next stage.",
        "specPath": spec_path,
        "specCreated": True,
    }
    created_spec = workspace / spec_path
    assert created_spec.exists()
    created_text = created_spec.read_text()
    assert created_text.startswith("# Human Section\n")
    assert "auto-created by the pimux control-plane runtime" in created_text


def test_pre_spawn_lock_blocks_parent_repo_tools_and_non_spawn_pimux_actions() -> None:
    """Before the first child exists, the parent should be fail-closed to spawn-only orchestration."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "skill-command", "requiresSpecPath": False},
            "previousActiveTools": ["read", "bash", "pimux", "AskUserQuestion", "say"],
        }
    )

    blocked_bash = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "bash", "input": {"command": "rg -n pimux ."}},
        }
    )
    assert blocked_bash == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Only pimux, AskUserQuestion, and say are allowed in the parent while the wrapper lock is active.",
    }

    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "last"}},
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Before the first child exists, the only allowed pimux action is spawn.",
    }

    allowed_question = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "AskUserQuestion", "input": {"question": "Which spec path?"}},
        }
    )
    assert allowed_question == {"allow": True}


def test_mux_ospec_inline_prompt_allows_spawn_without_ask_user_question(tmp_path: Path) -> None:
    """Inline mux-ospec prompts should no longer fail closed on missing explicit paths."""
    workspace = create_branch_spec_workspace(tmp_path)
    trigger = run_runtime(
        {
            "action": "parse",
            "text": "/mux-ospec full Inline prompt auto spec paths for mux ospec and mux roadmap",
        },
        cwd=workspace,
    )
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": trigger,
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        },
        cwd=workspace,
    )
    assert decision == {"allow": True}


def test_mux_ospec_spawn_is_blocked_only_when_no_path_or_inline_prompt_exists() -> None:
    """Missing mux-ospec input should still fail closed before spawn."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-ospec", "source": "embedded-skill", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the next stage."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_mux_roadmap_inline_prompt_allows_spawn_without_ask_user_question(tmp_path: Path) -> None:
    """Inline mux-roadmap prompts should derive a branch-local spec path and allow spawn."""
    workspace = create_branch_spec_workspace(tmp_path)
    trigger = run_runtime(
        {
            "action": "parse",
            "text": "/mux-roadmap Inline prompt auto spec paths for mux roadmap",
        },
        cwd=workspace,
    )
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": trigger,
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        },
        cwd=workspace,
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the roadmap phase."}},
        },
        cwd=workspace,
    )
    assert decision == {"allow": True}


def test_mux_roadmap_spawn_is_blocked_only_when_no_path_or_inline_prompt_exists() -> None:
    """Missing mux-roadmap input should also fail closed before spawn."""
    lock = run_runtime(
        {
            "action": "build_lock",
            "trigger": {"mode": "mux-roadmap", "source": "alias-command", "requiresSpecPath": True},
            "previousActiveTools": ["pimux", "AskUserQuestion", "say"],
        }
    )
    decision = run_runtime(
        {
            "action": "evaluate",
            "lock": lock,
            "event": {"toolName": "pimux", "input": {"action": "spawn", "prompt": "Run the roadmap phase."}},
        }
    )
    assert decision == {
        "allow": False,
        "reason": "Explicit mux-roadmap parent is control-plane locked. Explicit mux-roadmap requires an explicit roadmap/spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.",
    }


def test_successful_spawn_transitions_lock_to_post_spawn_supervision() -> None:
    """A successful spawn should unlock post-spawn supervision without permitting repo work."""
    post_spawn = spawn_post_lock()
    assert post_spawn["phase"] == "post_spawn"
    assert post_spawn["lastSpawnedAgentId"] == "mux-ospec-stage-001"
    assert post_spawn["initialVerificationUsed"] is False
    assert post_spawn["recoveryMessageUsed"] is False
    assert post_spawn["settlementVerificationPending"] is False

    allowed_status = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
        }
    )
    assert allowed_status == {"allow": True}

    blocked_read = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "read", "input": {"path": "README.md"}},
        }
    )
    assert blocked_read == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Only pimux, AskUserQuestion, and say are allowed in the parent while the wrapper lock is active.",
    }


def test_post_spawn_allows_only_one_initial_verification_check() -> None:
    """The parent should get one immediate check, then must wait for child activity or watchdog."""
    post_spawn = spawn_post_lock()
    first_status = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
        }
    )
    assert first_status == {"allow": True}

    after_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    blocked_status = run_runtime(
        {
            "action": "evaluate",
            "lock": after_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child bridge activity is delivered automatically. After spawn, use at most one initial status/capture/tree/list check per activity window, then wait for new child activity or the 10m inactivity watchdog.",
    }



def test_capture_is_blocked_after_the_initial_verification_is_used() -> None:
    """A different check action should still be blocked after the one initial verification is spent."""
    post_spawn = spawn_post_lock()
    after_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    blocked_capture = run_runtime(
        {
            "action": "evaluate",
            "lock": after_status,
            "event": {"toolName": "pimux", "input": {"action": "capture", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_capture == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child bridge activity is delivered automatically. After spawn, use at most one initial status/capture/tree/list check per activity window, then wait for new child activity or the 10m inactivity watchdog.",
    }



def test_post_spawn_allows_only_one_recovery_message_per_activity_window() -> None:
    """Recovery nudges should be single-shot until the child reports again or the watchdog window opens."""
    post_spawn = spawn_post_lock()
    first_message = run_runtime(
        {
            "action": "evaluate",
            "lock": post_spawn,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Recover the missing path."},
            },
        }
    )
    assert first_message == {"allow": True}

    after_message = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "send_message"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    blocked_message = run_runtime(
        {
            "action": "evaluate",
            "lock": after_message,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Try again."},
            },
            "now": "2026-04-17T10:01:00Z",
        }
    )
    assert blocked_message == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. A recovery send_message already went out for the current activity window. Wait for new child activity or the 10m inactivity watchdog before nudging again.",
    }



def test_child_activity_rearms_one_check_and_one_recovery_message() -> None:
    """A real child report should reopen the supervision window once."""
    post_spawn = spawn_post_lock()
    after_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    exhausted = run_runtime(
        {
            "action": "update_tool_result",
            "lock": after_status,
            "event": {"toolName": "pimux", "details": {"action": "send_message"}, "isError": False},
            "now": "2026-04-17T10:00:45Z",
        }
    )
    rearmed = run_runtime(
        {
            "action": "child_activity",
            "lock": exhausted,
            "event": {
                "agentId": "mux-ospec-stage-001",
                "eventId": "evt-progress-1",
                "timestamp": "2026-04-17T10:02:00Z",
            },
        }
    )
    allowed_status = run_runtime(
        {
            "action": "evaluate",
            "lock": rearmed,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:02:05Z",
        }
    )
    assert allowed_status == {"allow": True}

    after_rearmed_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": rearmed,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:02:05Z",
        }
    )
    allowed_message = run_runtime(
        {
            "action": "evaluate",
            "lock": after_rearmed_status,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Continue."},
            },
            "now": "2026-04-17T10:02:10Z",
        }
    )
    assert allowed_message == {"allow": True}



def test_terminal_settlement_rearms_one_final_status_only() -> None:
    """Terminal settlement should allow one final status verification, not more capture or nudges."""
    post_spawn = spawn_post_lock()
    settled = run_runtime(
        {
            "action": "terminal_settlement",
            "lock": post_spawn,
            "event": {
                "agentId": "mux-ospec-stage-001",
                "eventId": "evt-closeout-1",
                "timestamp": "2026-04-17T10:03:00Z",
            },
        }
    )
    allowed_status = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
        }
    )
    assert allowed_status == {"allow": True}

    blocked_capture = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {"toolName": "pimux", "input": {"action": "capture", "target": "mux-ospec-stage-001"}},
        }
    )
    assert blocked_capture == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Terminal settlement is ready. Use one final pimux status check, then stop supervising this child.",
    }

    blocked_message = run_runtime(
        {
            "action": "evaluate",
            "lock": settled,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Any update?"},
            },
        }
    )
    assert blocked_message == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Terminal settlement is ready. Use one final pimux status check, then stop supervising this child.",
    }

    after_final_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": settled,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:03:05Z",
        }
    )
    blocked_second_status = run_runtime(
        {
            "action": "evaluate",
            "lock": after_final_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:03:10Z",
        }
    )
    assert blocked_second_status == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child bridge activity is delivered automatically. After spawn, use at most one initial status/capture/tree/list check per activity window, then wait for new child activity or the 10m inactivity watchdog.",
    }



def test_inactivity_watchdog_allows_one_follow_up_check_without_restarting_polling() -> None:
    """A real inactivity threshold may reopen one check, but not a new polling loop."""
    post_spawn = spawn_post_lock()
    after_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    blocked_early = run_runtime(
        {
            "action": "evaluate",
            "lock": after_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:05:00Z",
        }
    )
    assert blocked_early["allow"] is False

    allowed_watchdog = run_runtime(
        {
            "action": "evaluate",
            "lock": after_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert allowed_watchdog == {"allow": True}

    after_watchdog_status = run_runtime(
        {
            "action": "update_tool_result",
            "lock": after_status,
            "event": {"toolName": "pimux", "details": {"action": "status"}, "isError": False},
            "now": "2026-04-17T10:11:00Z",
        }
    )
    blocked_again = run_runtime(
        {
            "action": "evaluate",
            "lock": after_watchdog_status,
            "event": {"toolName": "pimux", "input": {"action": "status", "target": "mux-ospec-stage-001"}},
            "now": "2026-04-17T10:11:30Z",
        }
    )
    assert blocked_again == {
        "allow": False,
        "reason": "Explicit mux-ospec parent is control-plane locked. Notify-first pacing is active. Child bridge activity is delivered automatically. After spawn, use at most one initial status/capture/tree/list check per activity window, then wait for new child activity or the 10m inactivity watchdog.",
    }



def test_inactivity_watchdog_can_reopen_one_recovery_message() -> None:
    """The watchdog should also reopen one concise recovery hint when the child has been quiet long enough."""
    post_spawn = spawn_post_lock()
    after_message = run_runtime(
        {
            "action": "update_tool_result",
            "lock": post_spawn,
            "event": {"toolName": "pimux", "details": {"action": "send_message"}, "isError": False},
            "now": "2026-04-17T10:00:30Z",
        }
    )
    blocked_early = run_runtime(
        {
            "action": "evaluate",
            "lock": after_message,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Still there?"},
            },
            "now": "2026-04-17T10:05:00Z",
        }
    )
    assert blocked_early["allow"] is False

    allowed_watchdog = run_runtime(
        {
            "action": "evaluate",
            "lock": after_message,
            "event": {
                "toolName": "pimux",
                "input": {"action": "send_message", "target": "mux-ospec-stage-001", "message": "Still there?"},
            },
            "now": "2026-04-17T10:11:00Z",
        }
    )
    assert allowed_watchdog == {"allow": True}
