import { promises as fs, watch as watchFs } from "node:fs";
import type { FSWatcher } from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from "@mariozechner/pi-coding-agent";
import {
	appendBridgeEvent,
	buildBridgeSessionEntry,
	buildChildProtocol,
	createBridgeLaunch,
	readBridgeChildState,
	readBridgeEvents,
	readBridgeLaunch,
	readBridgeParentState,
	writeBridgeChildState,
	writeBridgeEventSignal,
	writeBridgeParentState,
	writeBridgeReport,
	type BridgeChildState,
	type BridgeEvent,
	type BridgeLaunchFile,
	type ReportParentKind,
	type SessionBridgeEntry,
} from "./bridge.ts";
import {
	bindBridgeAuthoritativeSession,
	evaluateBridgeAuthority,
	hasBoundBridgeAuthority,
	type BridgeAuthorityBinding,
	type BridgeRuntimeSessionIdentity,
} from "./authority.ts";
import {
	buildProtocolViolationDeliveryContent,
	buildChildMessageContent,
	buildParentDeliveryContent,
} from "./render.ts";
import {
	CONTROL_PLANE_LOCK_ENTRY_TYPE,
	NO_POLLING_SUPERVISION_ENTRY_TYPE,
	buildControlPlaneLock,
	buildControlPlaneSystemPrompt,
	buildNoPollingSupervisionForSpawn,
	buildUnlockedControlPlaneLock,
	evaluateControlPlaneToolCall,
	evaluateNoPollingSupervisionToolCall,
	normalizeControlPlaneLockState,
	normalizeNoPollingSupervisionState,
	parseExplicitControlPlaneTrigger,
	prepareControlPlaneSpawn,
	resolveControlPlaneSpecPath,
	resolvePendingControlPlaneSpecPath,
	updateControlPlaneLockForChildActivity,
	updateControlPlaneLockForTerminalSettlement,
	updateControlPlaneLockForToolResult,
	updateNoPollingSupervisionForChildActivity,
	updateNoPollingSupervisionForTerminalSettlement,
	updateNoPollingSupervisionForToolResult,
	type ControlPlaneLockState,
	type NoPollingSupervisionState,
} from "./control-plane.ts";
import {
	archivePrunedAgents,
	buildTreeLines,
	buildTreeNodes,
	dashboardLines,
	filterStatusesByScope,
	filterStatusesForList,
	findBlockingDirectChildrenForCloseout,
	flattenTreeNodes,
	formatAgentDetails,
	formatAgentSummary,
	formatPruneCandidate,
	parseAgeThresholdMs,
	readRegistry,
	readSessionRegistry,
	rememberSessionBridge,
	resolvePruneAgeReference,
	resolveStatuses,
	resolveTargetFromInput,
	shouldPruneStatus,
	suggestSupervisorTerminalReportKind,
	uniqueAgentIdentity,
	updateRegistry,
	type AgentScope,
	type ManagedAgentRecord,
	type PruneMode,
	type ResolvedStatus,
} from "./registry.ts";
import { PIMUX_PARAMS } from "./schema.ts";
import {
	DEFAULT_CAPTURE_LINES,
	DEFAULT_MODEL,
	DEFAULT_NOTIFICATION_MODE,
	EXTENSION_NAME,
	getAgentDir,
	getAgentLaunchPacketPath,
	getAgentLauncherPath,
	getAgentManifestPath,
	getAgentPromptPath,
	getBridgeSignalsDir,
	getCurrentEnv,
	getStateRoot,
	nowIso,
	normalizeNotificationMode,
	normalizeOptional,
	summarizePrompt,
} from "./paths.ts";
import {
	evaluateBridgeSettlement,
	isTerminalChildReportEvent,
	shouldDeliverBridgeEventToParent,
	shouldTriggerTurnForEvent,
	shouldTriggerTurnForSettledState,
} from "./settlement.ts";
import {
	buildSessionName,
	captureTmuxPane,
	closeItermTabs,
	createTmuxSession,
	extensionEntryPath,
	killTmuxSession,
	openItermTab,
	tmuxHasSession,
	writeLauncherScript,
} from "./tmux.ts";

interface SpawnRequest {
	agentId?: string;
	cwd?: string;
	model?: string;
	prompt: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId?: string;
	openIterm?: boolean;
	contextBrief?: string;
}

interface SendMessageRequest {
	target: string;
	message: string;
	senderAgentId?: string;
}

interface ReportParentRequest {
	kind: ReportParentKind;
	summary: string;
	reportMarkdown?: string;
	requiresResponse?: boolean;
}

interface ParsedArgs {
	flags: Map<string, string | boolean>;
	positionals: string[];
}

function buildUsage(): string {
	return [
		"Usage:",
		"  /pimux spawn [--open] [--cwd PATH] [--model PROVIDER/MODEL] [--agent-id ID] [--role ROLE] [--goal TEXT] [--parent ID] [--root ID] [--context TEXT] <prompt>",
		"  /pimux open [target|last]",
		"  /pimux list [--all] [--include-exited] [--root ID]",
		"  /pimux tree [--all] [--include-exited] [--root ID]",
		"  /pimux navigate [--all] [--include-exited] [--root ID]",
		"  /pimux status [target|last]",
		"  /pimux capture [target|last] [--lines N]",
		"  /pimux send [target|last] <message>",
		"  /pimux kill [target|last]",
		"  /pimux prune [--all] [--root ID] [--older-than 7d] [--dry-run]",
		"  /pimux unlock",
		"  /pimux smoke-nested [--prefix ID] [--output PATH]",
	].join("\n");
}

function formatCurrentModel(ctx: ExtensionContext): string | undefined {
	if (!ctx.model) return undefined;
	const provider = (ctx.model as { provider?: string }).provider;
	const id = (ctx.model as { id?: string }).id;
	if (!provider || !id) return undefined;
	return `${provider}/${id}`;
}

function getSessionKey(ctx: ExtensionContext): string {
	return ctx.sessionManager.getSessionFile() ?? `ephemeral:${ctx.cwd}`;
}

function getCurrentBridgeSessionIdentity(ctx: ExtensionContext): BridgeRuntimeSessionIdentity {
	return {
		sessionFile: ctx.sessionManager.getSessionFile() ?? undefined,
		sessionKey: getSessionKey(ctx),
		leafId: ctx.sessionManager.getLeafId() ?? undefined,
		processId: process.pid,
	};
}

function inferRoleFromPrompt(prompt: string): string | undefined {
	const text = prompt.toLowerCase();
	if (/\bchief of staff\b|\bchief-of-staff\b/.test(text)) return "chief-of-staff";
	if (/\bbrainstorm\b|\bteam\b|\borchestrator\b/.test(text)) return "orchestrator";
	if (/\bplanner\b|\bplan\b|\broadmap\b/.test(text)) return "planner";
	if (/\bscout\b|\bresearch\b|\binventory\b/.test(text)) return "scout";
	if (/\breview\b|\baudit\b/.test(text)) return "reviewer";
	if (/\bimplement\b|\bcode\b|\bfix\b|\bbuild\b/.test(text)) return "worker";
	return undefined;
}

function inferOpenItermFromPrompt(prompt: string): boolean {
	const text = prompt.toLowerCase();
	return /\bwatch live\b|\bopen (?:an )?iterm\b|\bshow me\b|\bvisible\b|\binspect live\b|\bopen a tab\b|\bso i can see\b/.test(text);
}

function buildSmokeNestedPrefix(): string {
	return `nested-smoke-${nowIso().replace(/[^0-9]/g, "").slice(0, 14)}`;
}

function buildSmokeNestedGuide(prefix: string): string {
	const happy = {
		l1a: `${prefix}-happy-l1a`,
		l1b: `${prefix}-happy-l1b`,
		l2a1: `${prefix}-happy-l2a1`,
		l2a2: `${prefix}-happy-l2a2`,
		l2b1: `${prefix}-happy-l2b1`,
		l2b2: `${prefix}-happy-l2b2`,
	};
	const blocker = {
		l1a: `${prefix}-blocker-l1a`,
		l1b: `${prefix}-blocker-l1b`,
		l2a1: `${prefix}-blocker-l2a1`,
		l2a2: `${prefix}-blocker-l2a2`,
		l2b1: `${prefix}-blocker-l2b1`,
		l2b2: `${prefix}-blocker-l2b2`,
	};
	const proto = {
		l1a: `${prefix}-proto-l1a`,
		l1b: `${prefix}-proto-l1b`,
		l2a1: `${prefix}-proto-l2a1`,
		l2a2: `${prefix}-proto-l2a2`,
		l2b1: `${prefix}-proto-l2b1`,
		l2b2: `${prefix}-proto-l2b2`,
	};
	const cascade = {
		supervisor: `${prefix}-cascade-supervisor`,
		parent: `${prefix}-cascade-parent`,
		descendant: `${prefix}-cascade-descendant`,
	};
	return [
		`# pimux smoke-nested guide: ${prefix}`,
		"",
		"This canned guide uses the simplified scaffold pattern validated during the nested messaging investigation.",
		"",
		"## Topology",
		"- l0: current session",
		"- l1: 2 scaffolds",
		"- l2: 2 leaves under each l1",
		"",
		"## Happy path IDs",
		`- ${happy.l1a}`,
		`- ${happy.l1b}`,
		`- ${happy.l2a1}`,
		`- ${happy.l2a2}`,
		`- ${happy.l2b1}`,
		`- ${happy.l2b2}`,
		"",
		"## Blocker path IDs",
		`- ${blocker.l1a}`,
		`- ${blocker.l1b}`,
		`- ${blocker.l2a1}`,
		`- ${blocker.l2a2}`,
		`- ${blocker.l2b1}`,
		`- ${blocker.l2b2}`,
		"",
		"## Protocol-violation path IDs",
		`- ${proto.l1a}`,
		`- ${proto.l1b}`,
		`- ${proto.l2a1}`,
		`- ${proto.l2a2}`,
		`- ${proto.l2b1}`,
		`- ${proto.l2b2}`,
		"",
		"## Cascade-kill path IDs",
		`- ${cascade.supervisor}`,
		`- ${cascade.parent}`,
		`- ${cascade.descendant}`,
		"",
		"## Recommended scaffold approach",
		"1. Spawn l1 scaffolds with stable IDs.",
		"2. Let each l1 scaffold spawn its two l2 leaves and report `spawned:<id>`.",
		"3. Use `send_message` from l0 to each l1 to test l0 -> l1 delivery.",
		"4. Use `send_message` with `senderAgentId=<l1>` to each l2 to simulate deterministic l1 -> l2 delivery without relying on l1 prompt improvisation.",
		"5. Verify leaf bridge events and settlement states through `status` plus recent bridge events.",
		"6. For blocker scenarios, let the wrapper report `blocker` and exit after all direct children reach terminal states.",
		"7. For protocol-violation scenarios, kill one l2 before any terminal report, then let the wrapper report `failure` and exit after capturing the leaf verdict.",
		"8. For cascade-kill validation, use a supervisor that kills a disposable parent+descendant pair, verifies the descendant shutdown, then exits cleanly itself.",
		"",
		"## Wrapper exit rules",
		"- use `closeout` only when every direct child is `settled_completion`",
		"- use `question` when a direct child settled `settled_waiting_on_parent`",
		"- use `blocker` when a direct child settled `settled_blocked`",
		"- use `failure` when a direct child settled `settled_failure` or `protocol_violation`",
		"- do not make the wrapper itself the killed parent in a cascade test; kill a disposable child-parent pair under the wrapper instead",
		"",
		"## Verification targets",
		"- exact payload fidelity in child delivery",
		"- settled_completion for happy leaves",
		"- settled_blocked for the intentional blocker leaf",
		"- protocol_violation for the killed leaf",
		"- clean wrapper exits without manual teardown where the wrapper is not itself the object under test",
		"- recent bridge events visible in `pimux status` output",
	].join("\n");
}

function tokenizeArgs(input: string): string[] {
	const tokens: string[] = [];
	let current = "";
	let quote: "single" | "double" | null = null;
	let escaping = false;

	for (const char of input) {
		if (escaping) {
			current += char;
			escaping = false;
			continue;
		}
		if (char === "\\" && quote !== "single") {
			escaping = true;
			continue;
		}
		if (quote === "single") {
			if (char === "'") quote = null;
			else current += char;
			continue;
		}
		if (quote === "double") {
			if (char === '"') quote = null;
			else current += char;
			continue;
		}
		if (char === "'") {
			quote = "single";
			continue;
		}
		if (char === '"') {
			quote = "double";
			continue;
		}
		if (/\s/.test(char)) {
			if (current.length > 0) {
				tokens.push(current);
				current = "";
			}
			continue;
		}
		current += char;
	}
	if (quote) throw new Error("Unterminated quoted string in command arguments");
	if (current.length > 0) tokens.push(current);
	return tokens;
}

function parseArgs(tokens: string[]): ParsedArgs {
	const flags = new Map<string, string | boolean>();
	const positionals: string[] = [];
	for (let index = 0; index < tokens.length; index += 1) {
		const token = tokens[index];
		if (!token.startsWith("--")) {
			positionals.push(token);
			continue;
		}
		const eqIndex = token.indexOf("=");
		if (eqIndex !== -1) {
			flags.set(token.slice(2, eqIndex), token.slice(eqIndex + 1));
			continue;
		}
		const key = token.slice(2);
		const next = tokens[index + 1];
		if (!next || next.startsWith("--")) {
			flags.set(key, true);
			continue;
		}
		flags.set(key, next);
		index += 1;
	}
	return { flags, positionals };
}

function hasFlag(parsed: ParsedArgs, ...names: string[]): boolean {
	return names.some((name) => Boolean(parsed.flags.get(name)));
}

function getStringFlag(parsed: ParsedArgs, name: string): string | undefined {
	const value = parsed.flags.get(name);
	if (typeof value !== "string") return undefined;
	const trimmed = value.trim();
	return trimmed ? trimmed : undefined;
}

function assertNoLegacyNotificationModeFlags(parsed: ParsedArgs): void {
	if (hasFlag(parsed, "notify", "follow-up", "followup", "silent")) {
		throw new Error("pimux always uses notify-and-follow-up; explicit notification flags are no longer supported.");
	}
}

function buildSpawnRequest(parsed: ParsedArgs, ctx: ExtensionContext): SpawnRequest {
	const prompt = parsed.positionals.join(" ").trim();
	if (!prompt) throw new Error("spawn requires a prompt");
	assertNoLegacyNotificationModeFlags(parsed);
	return {
		agentId: getStringFlag(parsed, "agent-id"),
		cwd: getStringFlag(parsed, "cwd") ?? ctx.cwd,
		model: getStringFlag(parsed, "model") ?? formatCurrentModel(ctx) ?? DEFAULT_MODEL,
		prompt,
		role: getStringFlag(parsed, "role") ?? inferRoleFromPrompt(prompt),
		goal: getStringFlag(parsed, "goal") ?? summarizePrompt(prompt),
		parentAgentId: getStringFlag(parsed, "parent"),
		rootAgentId: getStringFlag(parsed, "root"),
		openIterm: hasFlag(parsed, "open", "watch") ? true : inferOpenItermFromPrompt(prompt),
		contextBrief: getStringFlag(parsed, "context"),
	};
}

function inferScope(value: string | undefined, fallback: AgentScope = "session"): AgentScope {
	if (!value) return fallback;
	if (value === "session" || value === "root" || value === "all") return value;
	throw new Error(`Invalid pimux scope: ${value}`);
}

function buildAgentIdentitySeed(role: string | undefined, goal: string | undefined, prompt: string): string {
	const normalizedRole = normalizeOptional(role);
	const normalizedGoal = normalizeOptional(goal);
	if (normalizedRole && normalizedGoal) {
		return normalizedGoal.toLowerCase().startsWith(normalizedRole.toLowerCase())
			? normalizedGoal
			: `${normalizedRole} ${normalizedGoal}`;
	}
	return normalizedRole ?? normalizedGoal ?? prompt;
}

async function resolveChildExtensionPaths(extensionPath: string): Promise<string[]> {
	const authoritativeExtensionPath = path.resolve(extensionPath);
	const extensionPaths = [authoritativeExtensionPath];
	const strictRuntimeExtensionPath = path.resolve(path.dirname(path.dirname(authoritativeExtensionPath)), "strict-mux-runtime", "index.js");
	if (strictRuntimeExtensionPath !== authoritativeExtensionPath) {
		try {
			await fs.access(strictRuntimeExtensionPath);
			extensionPaths.push(strictRuntimeExtensionPath);
		} catch {
			// Ignore missing optional sibling runtime path.
		}
	}
	return extensionPaths;
}

function getBridgeAuthorityBinding(state: BridgeChildState): BridgeAuthorityBinding {
	return {
		authoritativeSessionKey: state.authoritativeSessionKey,
		authoritativeSessionFile: state.authoritativeSessionFile,
		authoritativeLeafId: state.authoritativeLeafId,
		authoritativeProcessId: state.authoritativeProcessId,
	};
}

function applyBridgeAuthorityBinding(state: BridgeChildState, binding: BridgeAuthorityBinding): boolean {
	let changed = false;
	if (!state.authoritativeSessionKey && binding.authoritativeSessionKey) {
		state.authoritativeSessionKey = binding.authoritativeSessionKey;
		changed = true;
	}
	if (!state.authoritativeSessionFile && binding.authoritativeSessionFile) {
		state.authoritativeSessionFile = binding.authoritativeSessionFile;
		changed = true;
	}
	if (!state.authoritativeLeafId && binding.authoritativeLeafId) {
		state.authoritativeLeafId = binding.authoritativeLeafId;
		changed = true;
	}
	if (state.authoritativeProcessId === undefined && binding.authoritativeProcessId !== undefined) {
		state.authoritativeProcessId = binding.authoritativeProcessId;
		changed = true;
	}
	return changed;
}

async function resolveBridgeAuthority(
	bridgeDir: string,
	ctx: ExtensionContext,
	options: { bindIfMissing?: boolean } = {},
): Promise<{ childState: BridgeChildState; currentSession: BridgeRuntimeSessionIdentity; isAuthoritative: boolean; reason?: string }> {
	const childState = await readBridgeChildState(bridgeDir);
	const currentSession = getCurrentBridgeSessionIdentity(ctx);
	const existingBinding = getBridgeAuthorityBinding(childState);
	if (!hasBoundBridgeAuthority(existingBinding)) {
		if (!options.bindIfMissing) {
			return {
				childState,
				currentSession,
				isAuthoritative: false,
				reason: "No authoritative pimux child session has been bound to this bridge yet.",
			};
		}
		applyBridgeAuthorityBinding(childState, bindBridgeAuthoritativeSession(currentSession));
		const boundAt = nowIso();
		childState.authoritativeBoundAt = boundAt;
		childState.lastAuthoritativeSeenAt = boundAt;
		await writeBridgeChildState(bridgeDir, childState);
		return { childState, currentSession, isAuthoritative: true };
	}

	const evaluation = evaluateBridgeAuthority(existingBinding, currentSession);
	if (evaluation.isAuthoritative) {
		const strengthenedBinding = bindBridgeAuthoritativeSession(currentSession);
		const changed = applyBridgeAuthorityBinding(childState, strengthenedBinding);
		const previousSeenAt = childState.lastAuthoritativeSeenAt;
		const seenAt = nowIso();
		childState.lastAuthoritativeSeenAt = seenAt;
		if (changed || previousSeenAt !== seenAt) {
			await writeBridgeChildState(bridgeDir, childState);
		}
	}

	return {
		childState,
		currentSession,
		isAuthoritative: evaluation.isAuthoritative,
		reason: evaluation.reason,
	};
}

async function persistAgentManifest(record: ManagedAgentRecord): Promise<void> {
	await fs.mkdir(path.dirname(record.manifestPath), { recursive: true });
	await fs.writeFile(record.manifestPath, `${JSON.stringify(record, null, 2)}\n`, "utf-8");
}

async function ensureDirectoryExists(targetCwd: string): Promise<void> {
	const resolved = path.resolve(targetCwd);
	const stat = await fs.stat(resolved).catch(() => undefined);
	if (!stat || !stat.isDirectory()) {
		throw new Error(`Directory not found: ${resolved}`);
	}
}

async function listManagedAgents(
	ctx: ExtensionContext,
	options: { scope?: AgentScope; rootAgentId?: string; includeExited?: boolean } = {},
): Promise<ResolvedStatus[]> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const statuses = await resolveStatuses(stateRoot, registry);
	const currentEnv = getCurrentEnv();
	const sessionKey = getSessionKey(ctx);
	const ownerSessionKey = currentEnv.rootOwnerSessionKey ?? sessionKey;
	const sessionRegistry = await readSessionRegistry(stateRoot, ownerSessionKey);
	const scope = options.scope ?? (options.rootAgentId ? "root" : "session");
	const filtered = filterStatusesForList(
		filterStatusesByScope(statuses, scope, {
			rootAgentId: options.rootAgentId ?? currentEnv.rootAgentId,
			ownerSessionKey,
			sessionRootAgentIds: currentEnv.rootAgentId
				? [...new Set([...sessionRegistry.rootAgentIds, currentEnv.rootAgentId])]
				: sessionRegistry.rootAgentIds,
		}),
		options.includeExited ?? false,
	);
	filtered.sort((left, right) => (right.record.updatedAt || right.record.createdAt).localeCompare(left.record.updatedAt || left.record.createdAt));
	return filtered;
}

async function treeManagedAgents(
	ctx: ExtensionContext,
	options: { scope?: AgentScope; rootAgentId?: string; includeExited?: boolean } = {},
	formatOptions: { colorize?: boolean } = {},
): Promise<{ lines: string[]; nodes: ReturnType<typeof buildTreeNodes> }> {
	const statuses = await listManagedAgents(ctx, options);
	const nodes = buildTreeNodes(statuses);
	return { lines: buildTreeLines(nodes, formatOptions), nodes };
}

async function statusManagedAgent(
	ctx: ExtensionContext,
	target: string | undefined,
	lines = 40,
): Promise<{ status: ResolvedStatus; capture?: string }> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const currentEnv = getCurrentEnv();
	const record = resolveTargetFromInput(registry, target, currentEnv.agentId);
	if (!record) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	const statuses = await resolveStatuses(stateRoot, registry);
	const status = statuses.find((entry) => entry.record.agentId === record.agentId);
	if (!status) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	let capture: string | undefined;
	if (status.hasSession) {
		capture = await captureTmuxPane(status.record.sessionName, lines).catch(() => undefined);
	}
	return { status, capture };
}

async function captureManagedAgent(
	ctx: ExtensionContext,
	target: string | undefined,
	lines = DEFAULT_CAPTURE_LINES,
): Promise<{ status: ResolvedStatus; capture: string }> {
	const result = await statusManagedAgent(ctx, target, lines);
	if (!result.capture) throw new Error(`No tmux pane capture available for ${target ?? "(current)"}`);
	return { status: result.status, capture: result.capture };
}

async function openManagedAgent(ctx: ExtensionContext, target: string | undefined): Promise<ManagedAgentRecord> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const currentEnv = getCurrentEnv();
	const record = resolveTargetFromInput(registry, target, currentEnv.agentId);
	if (!record) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	if (!(await tmuxHasSession(record.sessionName).catch(() => false))) {
		throw new Error(`tmux session is not running for ${record.agentId}`);
	}
	const visual = await openItermTab(record.cwd, record.sessionName);
	const openedAt = visual.openedAt;
	record.visualMode = "iterm-opened";
	record.managedVisuals = [...(record.managedVisuals ?? []), visual];
	record.openCount = record.managedVisuals.length;
	record.lastOpenedAt = openedAt;
	record.updatedAt = openedAt;
	await updateRegistry(stateRoot, (next) => {
		const found = next.agents.find((entry) => entry.agentId === record.agentId);
		if (found) Object.assign(found, record);
	});
	await persistAgentManifest(record);
	return record;
}

async function ensureExitedBridgeEvent(params: {
	bridgeDir?: string;
	launchId?: string;
	agentId: string;
	sessionName: string;
	exitSummary: string;
}): Promise<BridgeEvent[]> {
	if (!params.bridgeDir || !params.launchId) return [];

	let events = await readBridgeEvents(params.bridgeDir).catch(() => []);
	const hasExitedEvent = events.some((event) => event.direction === "system" && event.type === "exited");
	if (!hasExitedEvent) {
		const exitedEvent = await appendBridgeEvent(params.bridgeDir, {
			launchId: params.launchId,
			direction: "system",
			type: "exited",
			from: { agentId: params.agentId, sessionName: params.sessionName },
			summary: params.exitSummary,
		});
		await writeBridgeEventSignal(params.bridgeDir, exitedEvent, true);
		events = [...events, exitedEvent];
	}
	return events;
}

async function finalizeBridgeAfterForcedTermination(record: ManagedAgentRecord, exitSummary?: string): Promise<void> {
	const events = await ensureExitedBridgeEvent({
		bridgeDir: record.bridgeDir,
		launchId: record.launchId,
		agentId: record.agentId,
		sessionName: record.sessionName,
		exitSummary: exitSummary ?? `${record.agentId} terminated by parent`,
	});
	const settlement = evaluateBridgeSettlement(events);
	if (settlement.settledState === "running" || !record.bridgeDir) return;

	const parentState = await readBridgeParentState(record.bridgeDir).catch(() => ({ deliveredEventIds: [] }));
	parentState.terminalState = settlement.settledState;
	parentState.terminalEventId = settlement.terminalEvent?.eventId;
	parentState.terminalFinalizedAt = nowIso();
	parentState.protocolViolationReason = settlement.protocolViolationReason;
	await writeBridgeParentState(record.bridgeDir, parentState);
}

function collectDescendantStatuses(statuses: ResolvedStatus[], parentAgentId: string): ResolvedStatus[] {
	const byParent = new Map<string, ResolvedStatus[]>();
	for (const status of statuses) {
		const parentId = status.record.parentAgentId;
		if (!parentId) continue;
		const bucket = byParent.get(parentId) ?? [];
		bucket.push(status);
		byParent.set(parentId, bucket);
	}
	const descendants: ResolvedStatus[] = [];
	const visit = (agentId: string) => {
		for (const child of byParent.get(agentId) ?? []) {
			visit(child.record.agentId);
			descendants.push(child);
		}
	};
	visit(parentAgentId);
	return descendants;
}

async function requestManagedAgentShutdown(
	record: ManagedAgentRecord,
	requesterAgentId: string,
	sessionFile: string | undefined,
	summary?: string,
): Promise<void> {
	if (!record.bridgeDir || !record.launchId) return;
	const event = await appendBridgeEvent(record.bridgeDir, {
		launchId: record.launchId,
		direction: "parent_to_child",
		type: "shutdown_request",
		from: { agentId: requesterAgentId, sessionFile },
		to: { agentId: record.agentId, sessionName: record.sessionName },
		summary: summary ?? `Shutdown requested for ${record.agentId}`,
		message: summary ?? `shutdown:${record.agentId}`,
	});
	await writeBridgeEventSignal(record.bridgeDir, event, true);
}

async function terminateManagedAgentRecord(
	record: ManagedAgentRecord,
	stateRoot: string,
	options: { exitSummary?: string } = {},
): Promise<ManagedAgentRecord> {
	if ((record.managedVisuals ?? []).length > 0) {
		await closeItermTabs(record.managedVisuals ?? []);
	}
	if (await tmuxHasSession(record.sessionName).catch(() => false)) {
		await killTmuxSession(record.sessionName);
	}
	const terminatedAt = nowIso();
	record.status = "terminated";
	record.terminatedAt = terminatedAt;
	record.updatedAt = terminatedAt;
	record.visualMode = "headless";
	record.managedVisuals = [];
	record.openCount = 0;
	await updateRegistry(stateRoot, (next) => {
		const found = next.agents.find((entry) => entry.agentId === record.agentId);
		if (found) Object.assign(found, record);
	});
	await finalizeBridgeAfterForcedTermination(record, options.exitSummary);
	await persistAgentManifest(record);
	return record;
}

async function finalizeManagedAgentAfterTerminalReport(
	launch: Pick<BridgeLaunchFile, "agentId" | "sessionName" | "bridgeDir" | "launchId">,
	ctx: ExtensionContext,
): Promise<BridgeEvent[]> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const record = registry.agents.find((agent) => agent.agentId === launch.agentId || agent.sessionName === launch.sessionName);
	if (await tmuxHasSession(launch.sessionName).catch(() => false)) {
		await killTmuxSession(launch.sessionName);
	}
	if (record) {
		const exitedAt = nowIso();
		record.status = "exited";
		record.updatedAt = exitedAt;
		await updateRegistry(stateRoot, (next) => {
			const found = next.agents.find((entry) => entry.agentId === record.agentId);
			if (found) Object.assign(found, record);
		});
		await persistAgentManifest(record);
	}
	return await ensureExitedBridgeEvent({
		bridgeDir: launch.bridgeDir,
		launchId: launch.launchId,
		agentId: launch.agentId,
		sessionName: launch.sessionName,
		exitSummary: `${launch.agentId} exited after terminal report`,
	});
}

async function killManagedAgent(ctx: ExtensionContext, target: string | undefined): Promise<ManagedAgentRecord> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const currentEnv = getCurrentEnv();
	const record = resolveTargetFromInput(registry, target, currentEnv.agentId);
	if (!record) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	const statuses = await resolveStatuses(stateRoot, registry);
	const descendants = collectDescendantStatuses(statuses, record.agentId)
		.filter((status) => status.hasSession || status.effectiveStatus === "running" || (status.bridgeSettlementState ?? "running") === "running")
		.map((status) => status.record);
	const requesterAgentId = currentEnv.agentId ?? "human";
	for (const descendant of descendants) {
		await requestManagedAgentShutdown(
			descendant,
			requesterAgentId,
			ctx.sessionManager.getSessionFile() ?? undefined,
			`${descendant.agentId} terminated because ancestor ${record.agentId} was killed`,
		);
		await terminateManagedAgentRecord(descendant, stateRoot, {
			exitSummary: `${descendant.agentId} terminated because ancestor ${record.agentId} was killed`,
		});
	}
	return await terminateManagedAgentRecord(record, stateRoot);
}

async function sendManagedMessage(request: SendMessageRequest, ctx: ExtensionContext): Promise<ManagedAgentRecord> {
	const stateRoot = getStateRoot(ctx.cwd);
	const registry = await readRegistry(stateRoot);
	const currentEnv = getCurrentEnv();
	const record = resolveTargetFromInput(registry, request.target, currentEnv.agentId);
	if (!record) throw new Error(`Managed agent not found: ${request.target}`);
	if (!record.bridgeDir || !record.launchId) {
		throw new Error(`Managed agent ${record.agentId} does not have a bridge inbox.`);
	}
	const senderAgentId = normalizeOptional(request.senderAgentId) ?? currentEnv.agentId ?? "human";
	const isAgentRoutedMessage = Boolean(currentEnv.agentId || normalizeOptional(request.senderAgentId));
	const event = await appendBridgeEvent(record.bridgeDir, {
		launchId: record.launchId,
		direction: "parent_to_child",
		type: isAgentRoutedMessage ? "instruction" : "answer",
		from: { agentId: senderAgentId, sessionFile: ctx.sessionManager.getSessionFile() ?? undefined },
		to: { agentId: record.agentId, sessionName: record.sessionName },
		message: request.message,
		summary: summarizePrompt(request.message),
	});
	await writeBridgeEventSignal(record.bridgeDir, event, true);
	record.lastMessageAt = nowIso();
	record.updatedAt = record.lastMessageAt;
	await updateRegistry(stateRoot, (next) => {
		const found = next.agents.find((entry) => entry.agentId === record.agentId);
		if (found) Object.assign(found, record);
	});
	await persistAgentManifest(record);
	return record;
}

async function reportParent(
	request: ReportParentRequest,
	ctx: ExtensionContext,
): Promise<{ bridgeDir: string; event: BridgeEvent }> {
	const currentEnv = getCurrentEnv();
	if (!currentEnv.bridgeDir || !currentEnv.launchId || !currentEnv.agentId) {
		throw new Error("report_parent requires a pimux child launch bridge");
	}
	const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx, { bindIfMissing: true });
	if (!authority.isAuthoritative) {
		throw new Error(
			`report_parent is reserved for the authoritative pimux child session. Local helpers or nested subagents must report back only to their supervising pimux agent. ${authority.reason ?? ""}`.trim(),
		);
	}
	if (request.kind === "closeout") {
		const stateRoot = getStateRoot(ctx.cwd);
		const registry = await readRegistry(stateRoot);
		const statuses = await resolveStatuses(stateRoot, registry);
		const blocking = findBlockingDirectChildrenForCloseout(statuses, currentEnv.agentId);
		if (blocking.length > 0) {
			const details = blocking.map((status) => `${status.record.agentId} [status=${status.effectiveStatus}, settled=${status.bridgeSettlementState ?? "running"}]`).join(", ");
			const suggestedKind = suggestSupervisorTerminalReportKind(statuses, currentEnv.agentId);
			const guidance =
				suggestedKind && suggestedKind !== "closeout"
					? `Suggested terminal report: ${suggestedKind}. Use report_parent(${suggestedKind}) if these child outcomes are intentional.`
					: "Wait for unsettled children to reach terminal settlement before using report_parent(closeout).";
			throw new Error(
				`Cannot close out ${currentEnv.agentId}: direct pimux children must be settled_completion first. Blocking children: ${details}. ${guidance}`,
			);
		}
	}
	let reportPath: string | undefined;
	if (request.reportMarkdown?.trim()) {
		const report = await writeBridgeReport(currentEnv.bridgeDir, request.kind, request.reportMarkdown);
		reportPath = report.reportPath;
	}
	const launch = await readBridgeLaunch(currentEnv.bridgeDir);
	const defaultRequiresResponse = request.kind === "question" || request.kind === "blocker";
	const requiresResponse = request.kind === "closeout" ? false : request.requiresResponse ?? defaultRequiresResponse;
	const event = await appendBridgeEvent(currentEnv.bridgeDir, {
		launchId: currentEnv.launchId,
		direction: "child_to_parent",
		type: request.kind,
		from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
		summary: request.summary.trim(),
		requiresResponse,
		reportPath,
	});
	event.signalPath = await writeBridgeEventSignal(currentEnv.bridgeDir, event, request.kind !== "failure");
	return { bridgeDir: currentEnv.bridgeDir, event };
}

async function pruneManagedAgents(
	ctx: ExtensionContext,
	options: {
		scope?: AgentScope;
		rootAgentId?: string;
		includeExited?: boolean;
		olderThan?: string;
		dryRun?: boolean;
		mode?: PruneMode;
	} = {},
): Promise<{ candidates: ResolvedStatus[]; pruned: ResolvedStatus[]; scope: AgentScope; olderThan: string; dryRun: boolean; mode: PruneMode }> {
	const stateRoot = getStateRoot(ctx.cwd);
	const mode = options.mode ?? "manual";
	const scope = options.scope ?? (mode === "auto" ? "all" : "session");
	const olderThan = normalizeOptional(options.olderThan) ?? (mode === "auto" ? "1d" : "0s");
	const dryRun = options.dryRun ?? false;
	const thresholdMs = parseAgeThresholdMs(olderThan);
	const now = Date.now();
	const statuses = await listManagedAgents(ctx, { scope, rootAgentId: options.rootAgentId, includeExited: true });
	const candidates = statuses.filter((status) => {
		if (!shouldPruneStatus(status, mode)) return false;
		const ageReference = resolvePruneAgeReference(status);
		if (ageReference === undefined) return false;
		return now - ageReference >= thresholdMs;
	});
	if (dryRun || candidates.length === 0) {
		return { candidates, pruned: [], scope, olderThan, dryRun, mode };
	}
	await archivePrunedAgents(stateRoot, candidates, scope, mode, olderThan);
	const pruneIds = new Set(candidates.map((status) => status.record.agentId));
	await updateRegistry(stateRoot, (next) => {
		next.agents = next.agents.filter((agent) => !pruneIds.has(agent.agentId));
	});
	return { candidates, pruned: candidates, scope, olderThan, dryRun, mode };
}

async function chooseAgent(
	ctx: ExtensionCommandContext,
	title: string,
	options: { scope?: AgentScope; rootAgentId?: string; includeExited?: boolean; requireSession?: boolean; emptyMessage?: string } = {},
): Promise<ManagedAgentRecord | undefined> {
	const statuses = await listManagedAgents(ctx, {
		scope: options.scope ?? "session",
		rootAgentId: options.rootAgentId,
		includeExited: options.includeExited ?? true,
	});
	const filtered = options.requireSession ? statuses.filter((status) => status.hasSession) : statuses;
	if (filtered.length === 0) {
		ctx.ui.notify(options.emptyMessage ?? "No pimux agents available in the selected hierarchy.", "warning");
		return undefined;
	}
	const items = filtered.map((status) => ({ value: status.record.agentId, label: formatAgentSummary(status) }));
	const choice = await ctx.ui.select(title, items.map((item) => item.label));
	if (!choice) return undefined;
	const selected = items.find((item) => item.label === choice);
	if (!selected) return undefined;
	const registry = await readRegistry(getStateRoot(ctx.cwd));
	return registry.agents.find((agent) => agent.agentId === selected.value) ?? undefined;
}

async function chooseTreeNode(
	ctx: ExtensionCommandContext,
	title: string,
	options: { scope?: AgentScope; rootAgentId?: string; includeExited?: boolean; emptyMessage?: string } = {},
): Promise<ManagedAgentRecord | undefined> {
	const tree = await treeManagedAgents(ctx, {
		scope: options.scope ?? "session",
		rootAgentId: options.rootAgentId,
		includeExited: options.includeExited ?? false,
	});
	const flattened = flattenTreeNodes(tree.nodes);
	if (flattened.length === 0) {
		ctx.ui.notify(options.emptyMessage ?? "No pimux agents available in the selected hierarchy.", "warning");
		return undefined;
	}
	const choice = await ctx.ui.select(title, flattened.map((entry) => entry.label));
	if (!choice) return undefined;
	const selected = flattened.find((entry) => entry.label === choice);
	if (!selected) return undefined;
	const registry = await readRegistry(getStateRoot(ctx.cwd));
	return registry.agents.find((agent) => agent.agentId === selected.node.agentId) ?? undefined;
}

async function presentText(ctx: ExtensionCommandContext, title: string, lines: string[]): Promise<void> {
	if (!ctx.hasUI) {
		console.log(lines.join("\n"));
		return;
	}
	await ctx.ui.select(title, lines.length > 0 ? lines : ["(empty)"]);
}

function formatPruneResultLines(result: {
	candidates: ResolvedStatus[];
	pruned: ResolvedStatus[];
	scope: AgentScope;
	olderThan: string;
	dryRun: boolean;
	mode: PruneMode;
}): string[] {
	const subject = result.dryRun ? result.candidates : result.pruned;
	if (subject.length === 0) {
		return [`No prune candidates matched scope=${result.scope} olderThan=${result.olderThan} mode=${result.mode}.`];
	}
	return [
		result.dryRun
			? `Prune dry-run matched ${subject.length} agent(s) for scope=${result.scope} olderThan=${result.olderThan} mode=${result.mode}.`
			: `Pruned ${subject.length} agent(s) for scope=${result.scope} olderThan=${result.olderThan} mode=${result.mode}.`,
		"",
		...subject.map(formatPruneCandidate),
	];
}

async function runPruneCommand(
	ctx: ExtensionCommandContext,
	options: { scope?: AgentScope; rootAgentId?: string; olderThan?: string; dryRun?: boolean } = {},
): Promise<void> {
	const dryRun = options.dryRun ?? false;
	const preview = await pruneManagedAgents(ctx, { ...options, dryRun: true, mode: "manual" });
	if (dryRun || preview.candidates.length === 0) {
		await presentText(ctx, "pimux prune", formatPruneResultLines(preview));
		return;
	}
	if (ctx.hasUI) {
		const previewLines = formatPruneResultLines(preview).slice(0, 16).join("\n");
		const confirmed = await ctx.ui.confirm("Prune pimux registry entries?", previewLines);
		if (!confirmed) {
			ctx.ui.notify("Prune cancelled.", "info");
			return;
		}
	}
	const result = await pruneManagedAgents(ctx, { ...options, dryRun: false, mode: "manual" });
	await presentText(ctx, "pimux prune", formatPruneResultLines(result));
}

async function navigateManagedAgents(
	ctx: ExtensionCommandContext,
	options: { scope?: AgentScope; rootAgentId?: string; includeExited?: boolean } = {},
): Promise<void> {
	if (!ctx.hasUI) throw new Error("navigate requires interactive mode");
	while (true) {
		const record = await chooseTreeNode(ctx, "Navigate pimux hierarchy", options);
		if (!record) return;
		let stayOnNode = true;
		while (stayOnNode) {
			const action = await ctx.ui.select(`pimux: ${record.agentId}`, [
				{ value: "open", label: "Open in iTerm" },
				{ value: "status", label: "Show status" },
				{ value: "capture", label: "Capture pane" },
				{ value: "send", label: "Send message" },
				{ value: "kill", label: "Kill agent" },
				{ value: "back", label: "Back to tree" },
				{ value: "done", label: "Done" },
			]);
			if (!action || action === "done") return;
			switch (action) {
				case "open": {
					const opened = await openManagedAgent(ctx, record.agentId);
					ctx.ui.notify(`Opened ${opened.agentId}.`, "info");
					break;
				}
				case "status": {
					const result = await statusManagedAgent(ctx, record.agentId, 40);
					const lines = [...formatAgentDetails(result.status)];
					if (result.capture) lines.push("", "capture:", ...result.capture.trimEnd().split(/\r?\n/).slice(-20));
					await presentText(ctx, `pimux status: ${record.agentId}`, lines);
					break;
				}
				case "capture": {
					const result = await captureManagedAgent(ctx, record.agentId, DEFAULT_CAPTURE_LINES);
					await presentText(ctx, `pimux capture: ${record.agentId}`, result.capture.trimEnd().split(/\r?\n/));
					break;
				}
				case "send": {
					const message = await ctx.ui.input(`Send message to ${record.agentId}`, "Enter message...");
					if (!message?.trim()) break;
					await sendManagedMessage({ target: record.agentId, message }, ctx);
					ctx.ui.notify(`Sent message to ${record.agentId}.`, "info");
					break;
				}
				case "kill": {
					const confirmed = await ctx.ui.confirm(`Kill ${record.agentId}?`, "This will terminate the managed tmux session.");
					if (!confirmed) break;
					await killManagedAgent(ctx, record.agentId);
					await updateDashboard(ctx);
					ctx.ui.notify(`Killed ${record.agentId}.`, "info");
					stayOnNode = false;
					break;
				}
				case "back": {
					stayOnNode = false;
					break;
				}
			}
		}
	}
}

function buildToolResult(text: string, details: Record<string, unknown>) {
	return {
		content: [{ type: "text" as const, text }],
		details,
	};
}

const CONTROL_PLANE_ACTIVE_TOOLS = ["pimux", "AskUserQuestion", "say"];
const NO_POLLING_SPAWN_ECHO = "NO-POLL: do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity.";

function filterAvailableTools(pi: ExtensionAPI, requestedTools: string[]): string[] {
	const available = new Set(pi.getAllTools().map((tool) => tool.name));
	return requestedTools.filter((name, index) => requestedTools.indexOf(name) === index && available.has(name));
}

function applyControlPlaneToolSurface(pi: ExtensionAPI): void {
	pi.setActiveTools(filterAvailableTools(pi, CONTROL_PLANE_ACTIVE_TOOLS));
}

function restoreToolSurface(pi: ExtensionAPI, requestedTools: string[] | undefined): string[] {
	if (!requestedTools || requestedTools.length === 0) return [];
	const restored = filterAvailableTools(pi, requestedTools);
	if (restored.length > 0) {
		pi.setActiveTools(restored);
	}
	return restored;
}

function getLatestNoPollingSupervisionState(ctx: ExtensionContext): NoPollingSupervisionState | undefined {
	let latest: NoPollingSupervisionState | undefined;
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "custom" || entry.customType !== NO_POLLING_SUPERVISION_ENTRY_TYPE) continue;
		const state = normalizeNoPollingSupervisionState(entry.data);
		if (state) {
			latest = state;
		}
	}
	return latest;
}

function getLatestControlPlaneLockState(ctx: ExtensionContext): ControlPlaneLockState | undefined {
	let latest: ControlPlaneLockState | undefined;
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "custom" || entry.customType !== CONTROL_PLANE_LOCK_ENTRY_TYPE) continue;
		const state = normalizeControlPlaneLockState(entry.data);
		if (state) {
			latest = state;
		}
	}
	return latest;
}

function getParentControlPlaneLock(ctx: ExtensionContext, current: ControlPlaneLockState | undefined): ControlPlaneLockState | undefined {
	if (getCurrentEnv().agentId) return undefined;
	return current ?? getLatestControlPlaneLockState(ctx);
}

function getControlPlaneUnlockMessage(restoredTools: string[]): string {
	if (restoredTools.length > 0) {
		return `Released pimux control-plane lock. Restored tools: ${restoredTools.join(", ")}`;
	}
	return "Released pimux control-plane lock.";
}

function getControlPlaneActiveMessage(lock: ControlPlaneLockState): string {
	const status = (lock.mode === "mux-ospec" || lock.mode === "mux-roadmap") && lock.requiresSpecPath ? " awaiting path or inline prompt" : "";
	return `pimux control-plane lock active for ${lock.mode ?? "mux-family"}${status}.`;
}

function getSessionBridgeEntries(ctx: ExtensionContext): SessionBridgeEntry[] {
	const deduped = new Map<string, SessionBridgeEntry>();
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "custom" || entry.customType !== "pimux-bridge") continue;
		const data = entry.data as Partial<SessionBridgeEntry> | undefined;
		if (!data?.launchId || !data.bridgeDir || !data.agentId || !data.sessionName || !data.rootAgentId || !data.createdAt) continue;
		deduped.set(data.bridgeDir, {
			launchId: data.launchId,
			bridgeDir: data.bridgeDir,
			agentId: data.agentId,
			sessionName: data.sessionName,
			rootAgentId: data.rootAgentId,
			createdAt: data.createdAt,
			notificationMode: normalizeNotificationMode(data.notificationMode) ?? DEFAULT_NOTIFICATION_MODE,
		});
	}
	return [...deduped.values()];
}

export default function pimuxExtension(pi: ExtensionAPI) {
	const parentBridgeWatchers = new Map<string, FSWatcher>();
	let childBridgeWatcher: FSWatcher | undefined;
	const processingParentBridges = new Set<string>();
	let processingChildBridge = false;
	const queuedChildInboxEventIds = new Set<string>();
	let controlPlaneLock: ControlPlaneLockState | undefined;
	let noPollingSupervision: NoPollingSupervisionState | undefined;

	const persistNoPollingSupervision = (nextState: NoPollingSupervisionState): void => {
		noPollingSupervision = nextState;
		pi.appendEntry(NO_POLLING_SUPERVISION_ENTRY_TYPE, nextState);
	};

	const persistControlPlaneLock = (nextLock: ControlPlaneLockState): void => {
		controlPlaneLock = nextLock;
		pi.appendEntry(CONTROL_PLANE_LOCK_ENTRY_TYPE, nextLock);
	};

	const activateControlPlaneLock = (ctx: ExtensionContext, nextLock: ControlPlaneLockState): void => {
		persistControlPlaneLock(nextLock);
		applyControlPlaneToolSurface(pi);
		if (ctx.hasUI) {
			ctx.ui.notify(getControlPlaneActiveMessage(nextLock), "info");
		}
	};

	const releaseControlPlaneLock = (ctx: ExtensionContext): string => {
		const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
		if (!currentLock?.active) {
			return "pimux control-plane lock is already off.";
		}
		const previousTools = currentLock.previousActiveTools;
		const restoredTools = restoreToolSurface(pi, previousTools);
		const unlocked = buildUnlockedControlPlaneLock(previousTools);
		persistControlPlaneLock(unlocked);
		return getControlPlaneUnlockMessage(restoredTools);
	};

	const syncControlPlaneLock = (ctx: ExtensionContext): void => {
		noPollingSupervision = getLatestNoPollingSupervisionState(ctx) ?? noPollingSupervision;
		if (getCurrentEnv().agentId) {
			controlPlaneLock = undefined;
			return;
		}
		const restored = getLatestControlPlaneLockState(ctx);
		if (!restored) return;
		controlPlaneLock = restored;
		if (restored.active) {
			applyControlPlaneToolSurface(pi);
			return;
		}
		restoreToolSurface(pi, restored.previousActiveTools);
	};

	const updateDashboard = async (ctx: ExtensionContext) => {
		if (!ctx.hasUI) return;
		const statuses = await listManagedAgents(ctx, { scope: "session", includeExited: false }).catch(() => []);
		ctx.ui.setWidget(EXTENSION_NAME, dashboardLines(statuses));
	};

	const processBridgeDeliveries = async (bridgeDir: string, sessionKey: string, ctx: ExtensionContext) => {
		if (processingParentBridges.has(bridgeDir)) return;
		processingParentBridges.add(bridgeDir);
		try {
			const launch = await readBridgeLaunch(bridgeDir);
			if (launch.parentSessionKey !== sessionKey) return;
			let parentState = await readBridgeParentState(bridgeDir);
			const delivered = new Set(parentState.deliveredEventIds);
			let changed = false;
			let events = await readBridgeEvents(bridgeDir);
			let terminalReportForAutoExit: BridgeEvent | undefined;
			const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
			const currentSupervision = noPollingSupervision;
			let nextLock = currentLock;
			let nextSupervision = currentSupervision;
			for (const event of events) {
				if (delivered.has(event.eventId)) continue;
				if (isTerminalChildReportEvent(event)) {
					terminalReportForAutoExit = event;
				}
				if (event.direction === "child_to_parent" && !isTerminalChildReportEvent(event)) {
					nextLock = updateControlPlaneLockForChildActivity(nextLock, {
						agentId: launch.agentId,
						eventId: event.eventId,
						timestamp: event.timestamp,
					});
					nextSupervision = updateNoPollingSupervisionForChildActivity(nextSupervision, {
						agentId: launch.agentId,
						eventId: event.eventId,
						timestamp: event.timestamp,
					});
				}
				if (shouldDeliverBridgeEventToParent(event)) {
					const content = await buildParentDeliveryContent(event, launch);
					pi.sendMessage(
						{ customType: "pimux-report", content, display: true, details: { launch, event } },
						shouldTriggerTurnForEvent(event, launch)
							? { triggerTurn: true, deliverAs: "followUp" }
							: { triggerTurn: false },
					);
				}
				delivered.add(event.eventId);
				changed = true;
			}
			if (terminalReportForAutoExit && !events.some((event) => event.direction === "system" && event.type === "exited")) {
				events = await finalizeManagedAgentAfterTerminalReport(launch, ctx);
				parentState = await readBridgeParentState(bridgeDir);
			}
			const settlement = evaluateBridgeSettlement(events);
			const alreadyFinalized =
				Boolean(parentState.terminalFinalizedAt) &&
				parentState.terminalState === settlement.settledState &&
				parentState.terminalEventId === settlement.terminalEvent?.eventId &&
				parentState.protocolViolationReason === settlement.protocolViolationReason;
			if (settlement.settledState !== "running" && !alreadyFinalized) {
				const finalizedAt = nowIso();
				let content: string;
				if (settlement.terminalEvent) {
					content = await buildParentDeliveryContent(settlement.terminalEvent, launch, {
						terminalEventId: settlement.terminalEvent.eventId,
						finalizedAt,
						settledState: settlement.settledState,
						settlementReason: settlement.protocolViolationReason,
					});
				} else {
					content = buildProtocolViolationDeliveryContent(
						launch,
						finalizedAt,
						settlement.protocolViolationReason ?? "Child exited without a valid terminal declaration.",
					);
				}
				pi.sendMessage(
					{ customType: "pimux-report", content, display: true, details: { launch, settlement, finalizedAt } },
					shouldTriggerTurnForSettledState(settlement.settledState, launch)
						? { triggerTurn: true, deliverAs: "followUp" }
						: { triggerTurn: false },
				);
				parentState.terminalState = settlement.settledState;
				parentState.terminalEventId = settlement.terminalEvent?.eventId;
				parentState.terminalFinalizedAt = finalizedAt;
				parentState.protocolViolationReason = settlement.protocolViolationReason;
				nextLock = updateControlPlaneLockForTerminalSettlement(nextLock, {
					agentId: launch.agentId,
					eventId: settlement.terminalEvent?.eventId,
					timestamp: finalizedAt,
				});
				nextSupervision = updateNoPollingSupervisionForTerminalSettlement(nextSupervision, {
					agentId: launch.agentId,
					eventId: settlement.terminalEvent?.eventId,
					timestamp: finalizedAt,
				});
				changed = true;
			}
			if (nextLock && nextLock !== currentLock) {
				persistControlPlaneLock(nextLock);
				applyControlPlaneToolSurface(pi);
			}
			if (nextSupervision && nextSupervision !== currentSupervision) {
				persistNoPollingSupervision(nextSupervision);
			}
			if (changed) {
				parentState.deliveredEventIds = Array.from(delivered).slice(-500);
				await writeBridgeParentState(bridgeDir, parentState);
			}
			await updateDashboard(ctx);
		} finally {
			processingParentBridges.delete(bridgeDir);
		}
	};

	const subscribeParentBridge = async (bridgeDir: string, ctx: ExtensionContext) => {
		if (parentBridgeWatchers.has(bridgeDir)) return;
		await fs.mkdir(getBridgeSignalsDir(bridgeDir), { recursive: true });
		const watcher = watchFs(getBridgeSignalsDir(bridgeDir), { persistent: false }, () => {
			void processBridgeDeliveries(bridgeDir, getSessionKey(ctx), ctx);
		});
		parentBridgeWatchers.set(bridgeDir, watcher);
	};

	const reconcileParentBridgeWatchers = async (ctx: ExtensionContext) => {
		const desired = new Set<string>();
		for (const entry of getSessionBridgeEntries(ctx)) {
			desired.add(entry.bridgeDir);
			await subscribeParentBridge(entry.bridgeDir, ctx);
			await processBridgeDeliveries(entry.bridgeDir, getSessionKey(ctx), ctx);
		}
		for (const [bridgeDir, watcher] of parentBridgeWatchers.entries()) {
			if (desired.has(bridgeDir)) continue;
			watcher.close();
			parentBridgeWatchers.delete(bridgeDir);
		}
	};

	const processChildInbox = async (ctx: ExtensionContext) => {
		if (processingChildBridge) return;
		processingChildBridge = true;
		try {
			const currentEnv = getCurrentEnv();
			if (!currentEnv.bridgeDir || !currentEnv.agentId) return;
			const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx);
			if (!authority.isAuthoritative) return;
			const childState = await readBridgeChildState(currentEnv.bridgeDir);
			const delivered = new Set(childState.deliveredParentEventIds ?? []);
			let changed = false;
			const events = (await readBridgeEvents(currentEnv.bridgeDir))
				.filter((event) => event.direction === "parent_to_child")
				.sort((left, right) => left.timestamp.localeCompare(right.timestamp) || left.eventId.localeCompare(right.eventId));
			for (const event of events) {
				if (delivered.has(event.eventId) || queuedChildInboxEventIds.has(event.eventId)) continue;
				queuedChildInboxEventIds.add(event.eventId);
				if (event.type === "shutdown_request") {
					delivered.add(event.eventId);
					changed = true;
					ctx.shutdown();
					continue;
				}
				const message = buildChildMessageContent(event).trim();
				if (message) {
					if (ctx.isIdle()) {
						pi.sendUserMessage(message);
					} else {
						pi.sendUserMessage(message, { deliverAs: "steer" });
					}
				}
				delivered.add(event.eventId);
				changed = true;
			}
			if (changed) {
				childState.deliveredParentEventIds = Array.from(delivered).slice(-500);
				await writeBridgeChildState(currentEnv.bridgeDir, childState);
			}
		} finally {
			processingChildBridge = false;
		}
	};

	const reconcileChildWatcher = async (ctx: ExtensionContext) => {
		const currentEnv = getCurrentEnv();
		if (!currentEnv.bridgeDir || !currentEnv.agentId) {
			childBridgeWatcher?.close();
			childBridgeWatcher = undefined;
			return;
		}
		const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx, { bindIfMissing: true });
		if (!authority.isAuthoritative) {
			childBridgeWatcher?.close();
			childBridgeWatcher = undefined;
			return;
		}
		if (!childBridgeWatcher) {
			await fs.mkdir(getBridgeSignalsDir(currentEnv.bridgeDir), { recursive: true });
			childBridgeWatcher = watchFs(getBridgeSignalsDir(currentEnv.bridgeDir), { persistent: false }, () => {
				void processChildInbox(ctx);
			});
		}
		await processChildInbox(ctx);
	};

	const rememberBridge = async (launch: BridgeLaunchFile, ctx: ExtensionContext) => {
		const entry = buildBridgeSessionEntry(launch);
		pi.appendEntry("pimux-bridge", entry);
		await rememberSessionBridge(getStateRoot(ctx.cwd), getSessionKey(ctx), { bridgeDir: entry.bridgeDir, rootAgentId: entry.rootAgentId });
		await reconcileParentBridgeWatchers(ctx);
		await updateDashboard(ctx);
	};

	const spawnManagedAgent = async (request: SpawnRequest, ctx: ExtensionContext): Promise<ManagedAgentRecord> => {
		const cwd = path.resolve(request.cwd ?? ctx.cwd);
		await ensureDirectoryExists(cwd);
		const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
		const preparedSpawn = await prepareControlPlaneSpawn(currentLock, request.prompt, cwd);
		const prompt = preparedSpawn.prompt;
		if (!prompt) throw new Error("A non-empty prompt is required to spawn a pimux agent");
		const stateRoot = getStateRoot(ctx.cwd);
		const registry = await readRegistry(stateRoot);
		const currentEnv = getCurrentEnv();
		const currentSessionKey = getSessionKey(ctx);
		const role = normalizeOptional(request.role) ?? inferRoleFromPrompt(prompt);
		const goal = normalizeOptional(request.goal) ?? summarizePrompt(prompt);
		const openIterm = request.openIterm ?? inferOpenItermFromPrompt(prompt);
		const notificationMode = DEFAULT_NOTIFICATION_MODE;
		const contextBrief = normalizeOptional(request.contextBrief);
		const parentAgentId = normalizeOptional(request.parentAgentId) ?? currentEnv.agentId;
		let rootAgentId = normalizeOptional(request.rootAgentId);
		let rootOwnerSessionKey = currentEnv.rootOwnerSessionKey ?? currentSessionKey;
		if (!rootAgentId && parentAgentId) {
			const parent = registry.agents.find((agent) => agent.agentId === parentAgentId);
			rootAgentId = parent?.rootAgentId ?? parentAgentId;
			rootOwnerSessionKey = parent?.rootOwnerSessionKey ?? rootOwnerSessionKey;
		}
		const { agentId, sessionName } = await uniqueAgentIdentity(
			registry,
			request.agentId,
			buildAgentIdentitySeed(role, goal, prompt),
			tmuxHasSession,
			buildSessionName,
		);
		rootAgentId ??= currentEnv.rootAgentId ?? currentEnv.agentId ?? agentId;
		const extensionPath = currentEnv.extensionPath ?? extensionEntryPath();
		const extensionPaths = await resolveChildExtensionPaths(extensionPath);
		const bridgeBaseDir = path.join(stateRoot, "bridges");
		await fs.mkdir(bridgeBaseDir, { recursive: true });
		const bridgeDir = await fs.mkdtemp(path.join(bridgeBaseDir, "bridge-"));
		const launch = await createBridgeLaunch({
			bridgeDir,
			agentId,
			sessionName,
			cwd,
			model: normalizeOptional(request.model) ?? formatCurrentModel(ctx) ?? DEFAULT_MODEL,
			prompt,
			role,
			goal,
			parentAgentId,
			rootAgentId,
			rootOwnerSessionKey,
			parentSessionKey: currentSessionKey,
			notificationMode,
			contextBrief,
			stateRoot,
			extensionPath,
		});
		const agentDir = getAgentDir(stateRoot, agentId);
		const promptPath = getAgentPromptPath(stateRoot, agentId);
		const launcherPath = getAgentLauncherPath(stateRoot, agentId);
		const manifestPath = getAgentManifestPath(stateRoot, agentId);
		const launchPacketPath = getAgentLaunchPacketPath(stateRoot, agentId);
		await fs.mkdir(agentDir, { recursive: true });
		await fs.writeFile(promptPath, `${prompt}\n`, "utf-8");
		await fs.writeFile(path.join(bridgeDir, "child", "protocol.md"), `${buildChildProtocol(launch)}\n`, "utf-8");
		await writeLauncherScript({
			launcherPath,
			promptPath,
			cwd,
			model: launch.model,
			agentId,
			parentAgentId,
			rootAgentId,
			role,
			goal,
			bridgeDir,
			launchId: launch.launchId,
			parentSessionKey: currentSessionKey,
			notificationMode,
			contextBrief,
			stateRoot,
			rootOwnerSessionKey,
			extensionPath,
			extensionPaths,
		});
		await createTmuxSession(sessionName, cwd, launcherPath);
		const createdAt = nowIso();
		const record: ManagedAgentRecord = {
			agentId,
			sessionName,
			cwd,
			model: launch.model,
			promptPreview: summarizePrompt(prompt),
			role,
			goal,
			parentAgentId,
			rootAgentId,
			rootOwnerSessionKey,
			status: "running",
			visualMode: "headless",
			createdAt,
			updatedAt: createdAt,
			openCount: 0,
			runDir: agentDir,
			launcherPath,
			promptPath,
			manifestPath,
			launchPacketPath,
			launchId: launch.launchId,
			bridgeDir,
			parentSessionKey: currentSessionKey,
			notificationMode,
			contextBrief,
		};
		await updateRegistry(stateRoot, (next) => {
			next.agents.push(record);
		});
		await persistAgentManifest(record);
		if (openIterm) {
			const visual = await openItermTab(cwd, sessionName);
			record.visualMode = "iterm-opened";
			record.managedVisuals = [visual];
			record.openCount = record.managedVisuals.length;
			record.lastOpenedAt = visual.openedAt;
			record.updatedAt = visual.openedAt;
			await updateRegistry(stateRoot, (next) => {
				const found = next.agents.find((entry) => entry.agentId === record.agentId);
				if (found) Object.assign(found, record);
			});
			await persistAgentManifest(record);
		}
		await rememberBridge(launch, ctx);
		persistNoPollingSupervision(buildNoPollingSupervisionForSpawn(record.agentId));
		return record;
	};

	const handleCommand = async (rawArgs: string, ctx: ExtensionCommandContext) => {
		const trimmed = rawArgs.trim();
		if (!trimmed) {
			if (!ctx.hasUI) {
				console.log(buildUsage());
				return;
			}
			const selected = await ctx.ui.select("pimux", ["spawn", "open", "list", "tree", "navigate", "status", "capture", "send", "kill", "prune", "unlock", "smoke-nested"]);
			if (!selected) return;
			await handleCommand(selected, ctx);
			return;
		}

		const tokens = tokenizeArgs(trimmed);
		const subcommand = tokens[0];
		const parsed = parseArgs(tokens.slice(1));

		switch (subcommand) {
			case "spawn": {
				const record = await spawnManagedAgent(buildSpawnRequest(parsed, ctx), ctx);
				const opened = record.visualMode === "iterm-opened";
				const summary = `Spawned ${record.agentId} (${record.role ?? "worker"}, ${opened ? "opened in iTerm" : "headless"}). ${NO_POLLING_SPAWN_ECHO}`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "open": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Open pimux agent in iTerm", {
						requireSession: true,
						includeExited: false,
						emptyMessage: "No live pimux agents are available to open.",
					});
					target = selected?.agentId;
					if (!target) return;
				}
				const record = await openManagedAgent(ctx, target);
				const summary = `Opened ${record.agentId} (${record.sessionName}) in the current iTerm window.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "list": {
				const scope = hasFlag(parsed, "all") ? "all" : getStringFlag(parsed, "root") ? "root" : "session";
				const statuses = await listManagedAgents(ctx, {
					scope,
					rootAgentId: getStringFlag(parsed, "root"),
					includeExited: hasFlag(parsed, "include-exited"),
				});
				const lines = statuses.length > 0 ? statuses.map((status) => formatAgentSummary(status, { colorize: !ctx.hasUI })) : ["No pimux agents recorded."];
				await presentText(ctx, `pimux list (${scope})`, lines);
				return;
			}
			case "tree": {
				const scope = hasFlag(parsed, "all") ? "all" : getStringFlag(parsed, "root") ? "root" : "session";
				const tree = await treeManagedAgents(
					ctx,
					{
						scope,
						rootAgentId: getStringFlag(parsed, "root"),
						includeExited: hasFlag(parsed, "include-exited"),
					},
					{ colorize: !ctx.hasUI },
				);
				await presentText(ctx, `pimux tree (${scope})`, tree.lines);
				return;
			}
			case "navigate": {
				await navigateManagedAgents(ctx, {
					scope: hasFlag(parsed, "all") ? "all" : getStringFlag(parsed, "root") ? "root" : "session",
					rootAgentId: getStringFlag(parsed, "root"),
					includeExited: hasFlag(parsed, "include-exited"),
				});
				return;
			}
			case "status": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "pimux status", {
						includeExited: true,
						emptyMessage: "No pimux agents are available to inspect.",
					});
					target = selected?.agentId;
					if (!target) return;
				}
				const result = await statusManagedAgent(ctx, target, 40);
				const lines = [...formatAgentDetails(result.status)];
				if (result.capture) lines.push("", "capture:", ...result.capture.trimEnd().split(/\r?\n/).slice(-20));
				await presentText(ctx, `pimux status: ${result.status.record.agentId}`, lines);
				return;
			}
			case "capture": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "pimux capture", {
						requireSession: true,
						includeExited: false,
						emptyMessage: "No live pimux agents are available to capture.",
					});
					target = selected?.agentId;
					if (!target) return;
				}
				const lines = Number(getStringFlag(parsed, "lines") ?? DEFAULT_CAPTURE_LINES);
				const result = await captureManagedAgent(ctx, target, lines);
				await presentText(ctx, `pimux capture: ${result.status.record.agentId}`, result.capture.trimEnd().split(/\r?\n/));
				return;
			}
			case "send": {
				let [target, ...messageParts] = parsed.positionals;
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Send message to pimux agent", {
						requireSession: true,
						includeExited: false,
						emptyMessage: "No live pimux agents are available to message.",
					});
					target = selected?.agentId;
					if (!target) return;
				}
				if (!target) throw new Error("send requires target");
				let message = messageParts.join(" ").trim();
				if (!message && ctx.hasUI) {
					message = (await ctx.ui.input(`Send message to ${target}`, "Enter message..."))?.trim() ?? "";
					if (!message) return;
				}
				if (!message) throw new Error("send requires a message");
				const record = await sendManagedMessage({ target, message }, ctx);
				const summary = `Sent message to ${record.agentId}.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "kill": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Kill pimux agent", {
						requireSession: true,
						includeExited: false,
						emptyMessage: "No live pimux agents are available to kill.",
					});
					target = selected?.agentId;
					if (!target) return;
				}
				const record = await killManagedAgent(ctx, target);
				await updateDashboard(ctx);
				const summary = `Killed ${record.agentId}.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "prune": {
				await runPruneCommand(ctx, {
					scope: hasFlag(parsed, "all") ? "all" : getStringFlag(parsed, "root") ? "root" : "session",
					rootAgentId: getStringFlag(parsed, "root"),
					olderThan: getStringFlag(parsed, "older-than"),
					dryRun: hasFlag(parsed, "dry-run"),
				});
				return;
			}
			case "unlock": {
				const summary = releaseControlPlaneLock(ctx);
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "smoke-nested": {
				const prefix = getStringFlag(parsed, "prefix") ?? buildSmokeNestedPrefix();
				const outputPath = path.resolve(getStringFlag(parsed, "output") ?? path.join(ctx.cwd, "tmp", "pimux", `${prefix}.md`));
				const guide = buildSmokeNestedGuide(prefix);
				await fs.mkdir(path.dirname(outputPath), { recursive: true });
				await fs.writeFile(outputPath, `${guide}\n`, "utf-8");
				const summary = `Wrote pimux smoke-nested guide to ${outputPath}`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			default:
				throw new Error(`Unknown pimux subcommand: ${subcommand}\n\n${buildUsage()}`);
		}
	};

	pi.on("input", async (event, ctx) => {
		if (getCurrentEnv().agentId) {
			return { action: "continue" as const };
		}

		const explicitTrigger = parseExplicitControlPlaneTrigger(event.text, ctx.cwd);
		if (explicitTrigger) {
			const previousActiveTools = controlPlaneLock?.previousActiveTools?.length ? controlPlaneLock.previousActiveTools : pi.getActiveTools();
			activateControlPlaneLock(ctx, buildControlPlaneLock(explicitTrigger, previousActiveTools));
			return { action: "continue" as const };
		}

		const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
		if (
			currentLock?.active
			&& (currentLock.mode === "mux-ospec" || currentLock.mode === "mux-roadmap")
			&& currentLock.requiresSpecPath
		) {
			const specPath = resolvePendingControlPlaneSpecPath(currentLock, event.text, ctx.cwd);
			if (specPath) {
				persistControlPlaneLock(resolveControlPlaneSpecPath(currentLock, specPath));
				applyControlPlaneToolSurface(pi);
			}
		}

		return { action: "continue" as const };
	});

	pi.on("tool_call", async (event, ctx) => {
		const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
		const decision = evaluateControlPlaneToolCall(currentLock, {
			toolName: event.toolName,
			input: event.input as Record<string, unknown> | undefined,
		});
		if (!decision.allow) {
			return {
				block: true,
				reason: decision.reason,
			};
		}
		const supervisionDecision = evaluateNoPollingSupervisionToolCall(noPollingSupervision, {
			toolName: event.toolName,
			input: event.input as Record<string, unknown> | undefined,
		});
		if (!supervisionDecision.allow) {
			return {
				block: true,
				reason: supervisionDecision.reason,
			};
		}
		return undefined;
	});

	pi.on("tool_result", async (event, ctx) => {
		const currentLock = getParentControlPlaneLock(ctx, controlPlaneLock);
		const updatedLock = updateControlPlaneLockForToolResult(currentLock, {
			toolName: event.toolName,
			details: event.details as Record<string, unknown> | undefined,
			isError: event.isError,
		});
		if (updatedLock && updatedLock !== currentLock) {
			persistControlPlaneLock(updatedLock);
			applyControlPlaneToolSurface(pi);
		}
		const updatedSupervision = updateNoPollingSupervisionForToolResult(noPollingSupervision, {
			toolName: event.toolName,
			details: event.details as Record<string, unknown> | undefined,
			isError: event.isError,
		});
		if (updatedSupervision && updatedSupervision !== noPollingSupervision) {
			persistNoPollingSupervision(updatedSupervision);
		}
		return undefined;
	});

	pi.on("session_start", async (_event, ctx) => {
		const stateRoot = getStateRoot(ctx.cwd);
		await fs.mkdir(stateRoot, { recursive: true });
		const currentEnv = getCurrentEnv();
		if (!currentEnv.agentId) {
			await pruneManagedAgents(ctx, { scope: "all", olderThan: "1d", dryRun: false, mode: "auto" });
		}
		let shouldShutdownTerminatedAgent = false;
		if (currentEnv.agentId) {
			ctx.ui.setStatus(EXTENSION_NAME, `pimux:${currentEnv.agentId}`);
			await updateRegistry(stateRoot, (registry) => {
				const existing = registry.agents.find((agent) => agent.agentId === currentEnv.agentId);
				if (existing) {
					if (existing.status === "terminated") {
						shouldShutdownTerminatedAgent = true;
						return;
					}
					existing.status = "running";
					existing.lastSeenAt = nowIso();
					existing.updatedAt = existing.lastSeenAt;
					existing.role ??= currentEnv.role;
					existing.goal ??= currentEnv.goal;
					existing.parentAgentId ??= currentEnv.parentAgentId;
					existing.rootAgentId = existing.rootAgentId || currentEnv.rootAgentId || existing.agentId;
				}
			});
		}
		if (currentEnv.bridgeDir && currentEnv.launchId && currentEnv.agentId && !shouldShutdownTerminatedAgent) {
			const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx, { bindIfMissing: true });
			if (authority.isAuthoritative) {
				const launch = await readBridgeLaunch(currentEnv.bridgeDir);
				const launchedEvent = await appendBridgeEvent(currentEnv.bridgeDir, {
					launchId: currentEnv.launchId,
					direction: "system",
					type: "launched",
					from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
					summary: `${currentEnv.agentId} launched. ${NO_POLLING_SPAWN_ECHO}`,
				});
				await writeBridgeEventSignal(currentEnv.bridgeDir, launchedEvent, true);
			}
		}
		syncControlPlaneLock(ctx);
		await reconcileParentBridgeWatchers(ctx);
		await reconcileChildWatcher(ctx);
		await updateDashboard(ctx);
		if (shouldShutdownTerminatedAgent) {
			ctx.shutdown();
		}
	});

	pi.on("session_tree", async (_event, ctx) => {
		syncControlPlaneLock(ctx);
		await reconcileParentBridgeWatchers(ctx);
		await reconcileChildWatcher(ctx);
		await updateDashboard(ctx);
	});

	pi.on("before_agent_start", async (event, ctx) => {
		const currentEnv = getCurrentEnv();
		let systemPrompt = event.systemPrompt;

		if (!currentEnv.agentId) {
			const controlPlanePrompt = buildControlPlaneSystemPrompt(getParentControlPlaneLock(ctx, controlPlaneLock));
			if (controlPlanePrompt) {
				systemPrompt = `${systemPrompt}\n\n${controlPlanePrompt}`;
			}
		}

		if (!currentEnv.bridgeDir) {
			if (systemPrompt === event.systemPrompt) return;
			return { systemPrompt };
		}
		const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx);
		if (!authority.isAuthoritative) {
			if (systemPrompt === event.systemPrompt) return;
			return { systemPrompt };
		}
		const protocolPath = path.join(currentEnv.bridgeDir, "child", "protocol.md");
		const protocol = await fs.readFile(protocolPath, "utf-8").catch(() => undefined);
		if (!protocol?.trim()) {
			if (systemPrompt === event.systemPrompt) return;
			return { systemPrompt };
		}
		return { systemPrompt: `${systemPrompt}\n\n${protocol.trim()}` };
	});

	pi.on("session_shutdown", async (_event, ctx) => {
		const currentEnv = getCurrentEnv();
		const stateRoot = getStateRoot(ctx.cwd);
		if (currentEnv.agentId) {
			await updateRegistry(stateRoot, (registry) => {
				const existing = registry.agents.find((agent) => agent.agentId === currentEnv.agentId);
				if (existing && existing.status !== "terminated") {
					existing.status = "exited";
					existing.updatedAt = nowIso();
				}
			});
		}
		if (currentEnv.bridgeDir && currentEnv.launchId && currentEnv.agentId) {
			const authority = await resolveBridgeAuthority(currentEnv.bridgeDir, ctx);
			if (authority.isAuthoritative) {
				const launch = await readBridgeLaunch(currentEnv.bridgeDir);
				const exitedEvent = await appendBridgeEvent(currentEnv.bridgeDir, {
					launchId: currentEnv.launchId,
					direction: "system",
					type: "exited",
					from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
					summary: `${currentEnv.agentId} exited`,
				});
				await writeBridgeEventSignal(currentEnv.bridgeDir, exitedEvent, true);
			}
		}
		for (const watcher of parentBridgeWatchers.values()) watcher.close();
		parentBridgeWatchers.clear();
		childBridgeWatcher?.close();
		childBridgeWatcher = undefined;
	});

	pi.registerCommand("pimux", {
		description: "Spawn and manage minimal tmux-backed Pi agents",
		handler: async (args, ctx) => {
			try {
				await handleCommand(args, ctx);
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				if (ctx.hasUI) ctx.ui.notify(message, "error");
				else console.error(message);
			}
		},
	});

	pi.registerTool({
		name: "pimux",
		label: "Pimux",
		description: "Launch and manage minimal tmux-backed Pi agents with explicit parent-child messaging, session-scoped supervision, and nested hierarchy support.",
		promptSnippet: "Launch and manage tmux-backed Pi agents with explicit messaging/inboxing, notify-first/no-poll supervision, and one-hop parent reporting.",
		promptGuidelines: [
			"FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.",
			"Use this tool when the user wants long-lived tmux-backed Pi agents managed from the current session.",
			"Default to headless agents unless the user explicitly wants to watch live.",
			"Use send_message for parent-to-child messaging and report_parent for child-to-parent reporting.",
			"Treat status/capture/tree/list/open as recovery-only after spawn; do not inspect routine progress.",
			"Use report_parent only from the authoritative direct pimux child session. Local helpers are local-only and must not call pimux or report_parent.",
			"Success settles only after closeout plus child exit. Progress is non-terminal; question is terminal waiting-on-parent settlement.",
			"For same-session child questions that must continue, use report_parent(progress, requiresResponse=true), not question.",
			"Use session-scoped list/tree/status by default. Broaden scope only when explicitly needed.",
			"Use prune to clean historical terminated or missing registry noise; auto-prune already removes terminated/missing pimux entries aged at least 1d.",
		],
		parameters: PIMUX_PARAMS,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			try {
				switch (params.action) {
					case "spawn": {
						if (!params.prompt?.trim()) throw new Error("spawn requires prompt");
						const record = await spawnManagedAgent(
							{
								agentId: params.agentId,
								cwd: params.cwd ?? ctx.cwd,
								model: params.model,
								prompt: params.prompt,
								role: params.role,
								goal: params.goal,
								parentAgentId: params.parentAgentId,
								rootAgentId: params.rootAgentId,
								openIterm: params.openIterm,
								contextBrief: params.contextBrief,
							},
							ctx,
						);
						return buildToolResult(`Spawned ${record.agentId} (${record.visualMode === "iterm-opened" ? "opened in iTerm" : "headless"}). ${NO_POLLING_SPAWN_ECHO}`, { action: params.action, agent: record });
					}
					case "open": {
						const record = await openManagedAgent(ctx, params.target);
						return buildToolResult(`Opened ${record.agentId} in the current iTerm window.`, { action: params.action, agent: record });
					}
					case "list": {
						const scope = inferScope(params.scope, params.rootAgentId ? "root" : "session");
						const statuses = await listManagedAgents(ctx, { scope, rootAgentId: params.rootAgentId, includeExited: params.includeExited ?? false });
						return buildToolResult(statuses.map(formatAgentSummary).join("\n") || "No pimux agents recorded.", {
							action: params.action,
							scope,
							agents: statuses.map((status) => ({
								...status.record,
								effectiveStatus: status.effectiveStatus,
								bridgeSettlementState: status.bridgeSettlementState,
								bridgeSettlementFinalizedAt: status.bridgeSettlementFinalizedAt,
								bridgeProtocolViolationReason: status.bridgeProtocolViolationReason,
							})),
						});
					}
					case "tree": {
						const scope = inferScope(params.scope, params.rootAgentId ? "root" : "session");
						const tree = await treeManagedAgents(ctx, { scope, rootAgentId: params.rootAgentId, includeExited: params.includeExited ?? false });
						return buildToolResult(tree.lines.join("\n"), { action: params.action, scope, tree: tree.lines, nodes: tree.nodes });
					}
					case "status": {
						const result = await statusManagedAgent(ctx, params.target, params.lines ?? 40);
						const lines = [...formatAgentDetails(result.status)];
						if (result.capture) lines.push("", "capture:", ...result.capture.trimEnd().split(/\r?\n/).slice(-20));
						return buildToolResult(lines.join("\n"), { action: params.action, status: result.status, capture: result.capture });
					}
					case "capture": {
						const result = await captureManagedAgent(ctx, params.target, params.lines ?? DEFAULT_CAPTURE_LINES);
						return buildToolResult(result.capture, { action: params.action, status: result.status, lines: params.lines ?? DEFAULT_CAPTURE_LINES });
					}
					case "send_message": {
						if (!params.target?.trim()) throw new Error("send_message requires target");
						if (!params.message?.trim()) throw new Error("send_message requires message");
						const record = await sendManagedMessage({ target: params.target, message: params.message, senderAgentId: params.senderAgentId }, ctx);
						return buildToolResult(`Sent message to ${record.agentId}.`, { action: params.action, agent: record });
					}
					case "kill": {
						const record = await killManagedAgent(ctx, params.target);
						await updateDashboard(ctx);
						return buildToolResult(`Killed ${record.agentId}.`, { action: params.action, agent: record });
					}
					case "prune": {
						const scope = inferScope(params.scope, params.rootAgentId ? "root" : "session");
						const result = await pruneManagedAgents(ctx, {
							scope,
							rootAgentId: params.rootAgentId,
							olderThan: params.olderThan,
							dryRun: params.dryRun ?? false,
							mode: "manual",
						});
						return buildToolResult(formatPruneResultLines(result).join("\n"), {
							action: params.action,
							scope: result.scope,
							olderThan: result.olderThan,
							dryRun: result.dryRun,
							mode: result.mode,
							candidateAgentIds: result.candidates.map((status) => status.record.agentId),
							prunedAgentIds: result.pruned.map((status) => status.record.agentId),
						});
					}
					case "report_parent": {
						if (!params.reportKind) throw new Error("report_parent requires reportKind");
						if (!params.summary?.trim()) throw new Error("report_parent requires summary");
						const result = await reportParent(
							{
								kind: params.reportKind,
								summary: params.summary,
								reportMarkdown: params.reportMarkdown,
								requiresResponse: params.requiresResponse,
							},
							ctx,
						);
						return buildToolResult(`Reported ${params.reportKind} to parent.`, { action: params.action, event: result.event, bridgeDir: result.bridgeDir });
					}
					default:
						throw new Error(`Unsupported pimux action: ${(params as { action: string }).action}`);
				}
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				return buildToolResult(`Error: ${message}`, { action: params.action, error: message });
			}
		},
	});
}
