#!/usr/bin/env python3
"""Surface checks for pimux runtime consistency fixes."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIMUX_PACKAGE_DIR = PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux"
PIMUX_INDEX = PIMUX_PACKAGE_DIR / "index.ts"
PIMUX_BRIDGE = PIMUX_PACKAGE_DIR / "bridge.ts"
PIMUX_RENDER = PIMUX_PACKAGE_DIR / "render.ts"
PIMUX_REGISTRY = PIMUX_PACKAGE_DIR / "registry.ts"
PIMUX_TMUX = PIMUX_PACKAGE_DIR / "tmux.ts"
PIMUX_SHIM = PROJECT_ROOT / ".pi" / "extensions" / "pimux" / "index.ts"


def test_parent_runtime_auto_finalizes_terminal_child_reports() -> None:
    """The parent runtime should auto-finalize a child after a terminal bridge report."""
    text = PIMUX_INDEX.read_text()
    assert "async function finalizeManagedAgentAfterTerminalReport(" in text
    assert "if (terminalReportForAutoExit && !events.some((event) => event.direction === \"system\" && event.type === \"exited\")) {" in text
    assert "events = await finalizeManagedAgentAfterTerminalReport(launch, ctx);" in text


def test_ui_selectors_render_string_labels_instead_of_objects() -> None:
    """The open/tree pickers should pass display strings to ctx.ui.select."""
    text = PIMUX_INDEX.read_text()
    assert "const choice = await ctx.ui.select(title, items.map((item) => item.label));" in text
    assert "const selected = items.find((item) => item.label === choice);" in text
    assert "const choice = await ctx.ui.select(title, flattened.map((entry) => entry.label));" in text
    assert "const selected = flattened.find((entry) => entry.label === choice);" in text



def test_spawn_identity_seed_uses_role_and_goal_for_clearer_generated_agent_ids() -> None:
    """Generated agent IDs should draw from both role and goal when available."""
    text = PIMUX_INDEX.read_text()
    assert "function buildAgentIdentitySeed(" in text
    assert "buildAgentIdentitySeed(role, goal, prompt)" in text


def test_interactive_agent_actions_prefer_live_targets_and_support_send_selection() -> None:
    """Interactive open/capture/send/kill flows should steer users toward live agents."""
    text = PIMUX_INDEX.read_text()
    assert 'const selected = await chooseAgent(ctx, "Open pimux agent in iTerm", {' in text
    assert 'const selected = await chooseAgent(ctx, "pimux capture", {' in text
    assert 'const selected = await chooseAgent(ctx, "Send message to pimux agent", {' in text
    assert 'const selected = await chooseAgent(ctx, "Kill pimux agent", {' in text
    assert 'requireSession: true' in text
    assert 'message = (await ctx.ui.input(`Send message to ${target}`, "Enter message..."))?.trim() ?? "";' in text



def test_parent_runtime_surfaces_parent_to_child_bridge_messages() -> None:
    """The parent delivery loop should no longer drop outbound bridge messages on the floor."""
    text = PIMUX_INDEX.read_text()
    assert 'if (event.direction !== "child_to_parent") {' not in text
    assert "if (shouldDeliverBridgeEventToParent(event)) {" in text



def test_child_inbox_uses_exact_message_content_and_steering_delivery() -> None:
    """Child delivery should preserve raw payloads and steer queued messages deterministically."""
    index_text = PIMUX_INDEX.read_text()
    render_text = PIMUX_RENDER.read_text()
    assert "const queuedChildInboxEventIds = new Set<string>();" in index_text
    assert 'pi.sendUserMessage(message, { deliverAs: "steer" });' in index_text
    assert 'return event.message?.trim() || event.summary?.trim() || "";' in render_text



def test_kill_runtime_cascades_to_live_descendants_before_parent_termination() -> None:
    """Killing a parent should recursively terminate live descendants first."""
    text = PIMUX_INDEX.read_text()
    assert "function collectDescendantStatuses(" in text
    assert "async function requestManagedAgentShutdown(" in text
    assert "async function terminateManagedAgentRecord(" in text
    assert "terminated because ancestor" in text
    assert 'event.type === "shutdown_request"' in text
    assert "shouldShutdownTerminatedAgent" in text



def test_command_surface_includes_canned_smoke_nested_mode() -> None:
    """The command surface should expose the canned nested smoke guide mode."""
    text = PIMUX_INDEX.read_text()
    assert '"  /pimux unlock"' in text
    assert 'case "unlock": {' in text
    assert '"  /pimux smoke-nested [--prefix ID] [--output PATH]"' in text
    assert 'case "smoke-nested": {' in text
    assert '"## Wrapper exit rules"' in text
    assert '"- use `failure` when a direct child settled `settled_failure` or `protocol_violation`"' in text
    assert '"- do not make the wrapper itself the killed parent in a cascade test; kill a disposable child-parent pair under the wrapper instead"' in text



def test_parent_control_plane_lock_is_extension_enforced() -> None:
    """The authoritative pimux extension should enforce mux-family parent locking at runtime."""
    text = PIMUX_INDEX.read_text()
    bridge_text = PIMUX_BRIDGE.read_text()
    helper_text = (PROJECT_ROOT / "packages" / "pi-ac-workflow" / "extensions" / "pimux" / "control-plane.ts").read_text()
    assert 'pi.on("input", async (event, ctx) => {' in text
    assert 'pi.on("tool_call", async (event, ctx) => {' in text
    assert 'pi.on("tool_result", async (event, ctx) => {' in text
    assert 'CONTROL_PLANE_LOCK_ENTRY_TYPE' in text
    assert 'applyControlPlaneToolSurface(pi);' in text
    assert 'parseExplicitControlPlaneTrigger' in text
    assert 'resolvePendingControlPlaneSpecPath' in text
    assert 'prepareControlPlaneSpawn' in text
    assert 'const preparedSpawn = await prepareControlPlaneSpawn(currentLock, request.prompt, cwd);' in text
    assert 'const specPath = resolvePendingControlPlaneSpecPath(currentLock, event.text, ctx.cwd);' in text
    assert 'evaluateControlPlaneToolCall' in text
    assert 'updateControlPlaneLockForChildActivity' in text
    assert 'updateControlPlaneLockForTerminalSettlement' in text
    assert 'updateControlPlaneLockForToolResult' in text
    assert 'POST_SPAWN_ALLOWED_ACTIONS' in helper_text
    assert 'CONTROL_PLANE_INACTIVITY_WATCHDOG_MS' in helper_text
    assert 'Do not poll pimux; wait for delivered child activity.' in helper_text
    assert 'status/capture/tree/list/open are recovery-only' in helper_text
    assert 'Wait for a delivered child report before sending messages' in helper_text
    assert 'A recovery send_message already went out for the current activity window.' in helper_text
    assert 'Terminal settlement is ready. Use one final pimux status check, then stop supervising this child.' in helper_text
    assert 'PIMUX HAPPY-PATH DISCIPLINE: this run is notify-first, not poll-first.' in helper_text
    assert 'Allowed happy-path sequence: spawn -> wait for child report -> send_message once if needed -> wait for closeout -> final status verification.' in helper_text
    assert 'after terminal settlement, use one final pimux status check before advancing.' in helper_text
    assert 'Progress is non-terminal; question is terminal waiting-on-parent settlement.' in text
    assert 'For same-session child questions that must continue, use report_parent(progress, requiresResponse=true), not question.' in text
    assert 'For same-session parent input that you need before continuing, emit progress with requiresResponse=true.' in bridge_text
    assert 'Use this spec path for the run, and create it first if missing:' in helper_text
    assert 'create the bound spec file before spawn if it does not exist yet.' in helper_text
    assert 'Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn.' in helper_text
    assert 'Explicit mux-roadmap requires an explicit roadmap/spec path or inline prompt before pimux spawn.' in helper_text


def test_closeout_guard_suggests_non_success_terminal_reports_for_wrappers() -> None:
    """Supervisors should get actionable guidance when closeout is blocked by non-success child outcomes."""
    index_text = PIMUX_INDEX.read_text()
    registry_text = PIMUX_REGISTRY.read_text()
    assert "suggestSupervisorTerminalReportKind" in registry_text
    assert 'Suggested terminal report: ${suggestedKind}.' in index_text
    assert 'Use report_parent(${suggestedKind}) if these child outcomes are intentional.' in index_text
    assert 'Wait for unsettled children to reach terminal settlement before using report_parent(closeout).' in index_text



def test_launcher_reports_startup_failures_and_exits_instead_of_dropping_to_a_shell() -> None:
    """Managed launchers should synthesize bridge evidence for startup failures and then exit."""
    tmux_text = PIMUX_TMUX.read_text()
    assert 'new URL("./launcher-exit-cli.ts", import.meta.url)' in tmux_text
    assert '"--no-extensions"' in tmux_text
    assert '...params.extensionPaths.flatMap((extensionPath) => ["-e", extensionPath])' in tmux_text
    assert 'PI_EXIT_CMD=(' in tmux_text
    assert 'tee "$PI_LOG"' in tmux_text
    assert 'status=\\${PIPESTATUS[0]}' in tmux_text
    assert '"\\${PI_EXIT_CMD[@]}" --bridge-dir' in tmux_text
    assert 'exit "$status"' in tmux_text
    assert 'exec "${SHELL:-/bin/bash}"' not in tmux_text



def test_spawn_resolves_strict_runtime_as_an_explicit_child_extension() -> None:
    """Child launches should carry the authoritative pimux extension plus its strict sibling explicitly."""
    text = PIMUX_INDEX.read_text()
    assert "async function resolveChildExtensionPaths(" in text
    assert 'path.resolve(path.dirname(path.dirname(authoritativeExtensionPath)), "strict-mux-runtime", "index.js")' in text
    assert 'const extensionPaths = await resolveChildExtensionPaths(extensionPath);' in text
    assert 'extensionPaths,' in text



def test_project_local_pimux_extension_is_now_a_tool_free_compatibility_shim() -> None:
    """The project-local pimux entrypoint should no longer register a competing runtime tool."""
    text = PIMUX_SHIM.read_text()
    assert "Project-local pimux compatibility shim." in text
    assert "packages/pi-ac-workflow/extensions/pimux/" in text
    assert "archived at:" in text
    assert "Intentionally empty." in text
