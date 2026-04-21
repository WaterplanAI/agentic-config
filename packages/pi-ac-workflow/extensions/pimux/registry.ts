import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import * as path from "node:path";
import type { BridgeEvent, BridgeParentState, SessionBridgeEntry } from "./bridge.ts";
import { readBridgeEvents, readBridgeParentState } from "./bridge.ts";
import { withQueuedFileOperation } from "./file-queue.ts";
import {
	DEFAULT_NOTIFICATION_MODE,
	getAgentManifestPath,
	getRegistryArchivePath,
	getRegistryPath,
	getSessionRegistryPath,
	normalizeNotificationMode,
	nowIso,
	sessionKeyToId,
	slugify,
	truncate,
	type NotificationMode,
} from "./paths.ts";
import { evaluateBridgeSettlement, isSettledTerminalState, type BridgeSettlementState } from "./settlement.ts";
import type { ManagedVisualRef } from "./tmux.ts";
import { tmuxHasSession } from "./tmux.ts";

export type AgentStatus = "running" | "exited" | "terminated" | "missing";
export type VisualMode = "headless" | "iterm-opened";
export type AgentScope = "session" | "root" | "all";

export interface ManagedAgentRecord {
	agentId: string;
	sessionName: string;
	cwd: string;
	model: string;
	promptPreview: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId: string;
	rootOwnerSessionKey: string;
	status: AgentStatus;
	visualMode: VisualMode;
	createdAt: string;
	updatedAt: string;
	lastOpenedAt?: string;
	lastMessageAt?: string;
	lastSeenAt?: string;
	terminatedAt?: string;
	openCount: number;
	managedVisuals?: ManagedVisualRef[];
	runDir: string;
	launcherPath: string;
	promptPath: string;
	manifestPath: string;
	launchPacketPath: string;
	launchId?: string;
	bridgeDir?: string;
	parentSessionKey?: string;
	notificationMode?: NotificationMode;
	contextBrief?: string;
}

export interface RegistryFile {
	version: number;
	updatedAt: string;
	agents: ManagedAgentRecord[];
}

export interface SessionRegistryFile {
	sessionKey: string;
	sessionId: string;
	updatedAt: string;
	rootAgentIds: string[];
	bridgeDirs: string[];
}

export interface ResolvedStatus {
	record: ManagedAgentRecord;
	hasSession: boolean;
	effectiveStatus: AgentStatus;
	bridgeSettlementState?: BridgeSettlementState;
	bridgeSettlementFinalizedAt?: string;
	bridgeProtocolViolationReason?: string;
	recentBridgeEvents?: string[];
}

export interface AgentTreeNode {
	agentId: string;
	sessionName: string;
	parentAgentId?: string;
	rootAgentId: string;
	depth: number;
	effectiveStatus: AgentStatus;
	bridgeSettlementState: BridgeSettlementState;
	visualMode: VisualMode;
	openCount: number;
	role?: string;
	goal?: string;
	displayLabel: string;
	children: AgentTreeNode[];
}

export interface FlattenedTreeNode {
	node: AgentTreeNode;
	label: string;
}

export type PruneMode = "manual" | "auto";

type FormatTone = "bold" | "cyan" | "green" | "yellow" | "red" | "magenta" | "blue";

function shouldUseAnsiStyling(colorize: boolean | undefined): boolean {
	if (!colorize) return false;
	if (process.env.NO_COLOR) return false;
	const preferred = process.env.PI_PIMUX_STYLE?.trim().toLowerCase();
	if (preferred === "plain") return false;
	if (preferred === "ansi") return true;
	return Boolean(process.stdout?.isTTY && process.env.TERM && process.env.TERM !== "dumb");
}

function toneText(text: string, colorize: boolean | undefined, ...tones: FormatTone[]): string {
	if (!shouldUseAnsiStyling(colorize) || tones.length === 0) return text;
	const codes = tones.map((tone) => {
		switch (tone) {
			case "bold":
				return "1";
			case "cyan":
				return "36";
			case "green":
				return "32";
			case "yellow":
				return "33";
			case "red":
				return "31";
			case "magenta":
				return "35";
			case "blue":
				return "34";
		}
	});
	return `\u001b[${codes.join(";")}m${text}\u001b[0m`;
}

function badge(label: string, colorize: boolean | undefined, ...tones: FormatTone[]): string {
	return toneText(`[${label}]`, colorize, ...tones);
}

function buildAgentLabel(
	record: Pick<ManagedAgentRecord, "agentId" | "role" | "goal" | "promptPreview">,
	maxLength = 56,
): string {
	const role = record.role?.trim();
	const goal = record.goal?.trim() ?? record.promptPreview?.trim();
	if (role && goal) {
		if (goal.toLowerCase() === role.toLowerCase()) return role;
		return `${role} · ${truncate(goal, maxLength)}`;
	}
	if (role) return role;
	if (goal) return truncate(goal, maxLength);
	return record.agentId;
}

function formatEffectiveStatusBadge(status: AgentStatus, colorize: boolean | undefined): string {
	switch (status) {
		case "running":
			return badge("LIVE", colorize, "green");
		case "exited":
			return badge("EXIT", colorize, "blue");
		case "terminated":
			return badge("TERM", colorize, "red");
		case "missing":
			return badge("MISS", colorize, "yellow");
	}
}

function formatSettlementBadge(state: BridgeSettlementState | undefined, colorize: boolean | undefined): string | undefined {
	switch (state) {
		case "settled_completion":
			return badge("DONE", colorize, "green");
		case "settled_failure":
			return badge("FAIL", colorize, "red");
		case "settled_blocked":
			return badge("BLOCK", colorize, "yellow");
		case "settled_waiting_on_parent":
			return badge("WAIT", colorize, "magenta");
		case "protocol_violation":
			return badge("BROKEN", colorize, "red");
		default:
			return undefined;
	}
}

function buildTreePrefix(ancestorLastStates: boolean[]): string {
	if (ancestorLastStates.length === 0) return "";
	const branchPrefix = ancestorLastStates.slice(0, -1).map((isLast) => (isLast ? "   " : "│  ")).join("");
	const isLast = ancestorLastStates[ancestorLastStates.length - 1];
	return `${branchPrefix}${isLast ? "└─ " : "├─ "}`;
}

function formatRecentBridgeEvent(event: BridgeEvent): string {
	const route = event.direction === "parent_to_child"
		? `${event.from?.agentId ?? "parent"} -> ${event.to?.agentId ?? "child"}`
		: event.direction === "child_to_parent"
			? `${event.from?.agentId ?? "child"} -> ${event.to?.agentId ?? "parent"}`
			: event.from?.agentId ?? "system";
	const summary = truncate(event.summary ?? event.message ?? event.type, 120);
	return `${event.timestamp} | ${event.type} | ${route} | ${summary}`;
}

function formatRecentBridgeEvents(events: BridgeEvent[], limit = 5): string[] {
	return events.slice(-limit).map(formatRecentBridgeEvent);
}

async function readJsonFile<T>(filePath: string, fallback: T): Promise<T> {
	try {
		const content = await fs.readFile(filePath, "utf-8");
		return JSON.parse(content) as T;
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return fallback;
		throw error;
	}
}

async function writeJsonFileAtomic(filePath: string, data: unknown): Promise<void> {
	await fs.mkdir(path.dirname(filePath), { recursive: true });
	const tempPath = `${filePath}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
	await fs.writeFile(tempPath, `${JSON.stringify(data, null, 2)}\n`, "utf-8");
	await fs.rename(tempPath, filePath);
}

async function appendJsonLine(filePath: string, value: unknown): Promise<void> {
	await fs.mkdir(path.dirname(filePath), { recursive: true });
	await fs.appendFile(filePath, `${JSON.stringify(value)}\n`, "utf-8");
}

export function isManagedAgentRecord(value: unknown): value is ManagedAgentRecord {
	if (!value || typeof value !== "object") return false;
	const record = value as Partial<ManagedAgentRecord>;
	return (
		typeof record.agentId === "string" &&
		typeof record.sessionName === "string" &&
		typeof record.cwd === "string" &&
		typeof record.model === "string" &&
		typeof record.promptPreview === "string" &&
		typeof record.rootAgentId === "string" &&
		typeof record.rootOwnerSessionKey === "string" &&
		typeof record.status === "string" &&
		typeof record.visualMode === "string" &&
		typeof record.createdAt === "string" &&
		typeof record.updatedAt === "string" &&
		typeof record.openCount === "number" &&
		typeof record.runDir === "string" &&
		typeof record.launcherPath === "string" &&
		typeof record.promptPath === "string" &&
		typeof record.manifestPath === "string" &&
		typeof record.launchPacketPath === "string"
	);
}

export async function readRegistry(stateRoot: string): Promise<RegistryFile> {
	const parsed = await readJsonFile<Partial<RegistryFile>>(getRegistryPath(stateRoot), {
		version: 1,
		updatedAt: nowIso(),
		agents: [],
	});
	const agents = Array.isArray(parsed.agents)
		? parsed.agents.filter(isManagedAgentRecord).map((agent) => ({
			...agent,
			notificationMode: agent.notificationMode ? normalizeNotificationMode(agent.notificationMode) ?? DEFAULT_NOTIFICATION_MODE : undefined,
		}))
		: [];
	return {
		version: 1,
		updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : nowIso(),
		agents,
	};
}

export async function writeRegistry(stateRoot: string, registry: RegistryFile): Promise<void> {
	registry.updatedAt = nowIso();
	await writeJsonFileAtomic(getRegistryPath(stateRoot), registry);
}

export async function updateRegistry(
	stateRoot: string,
	mutator: (registry: RegistryFile) => void,
): Promise<RegistryFile> {
	const registryPath = getRegistryPath(stateRoot);
	return await withQueuedFileOperation(registryPath, async () => {
		const registry = await readRegistry(stateRoot);
		mutator(registry);
		await writeRegistry(stateRoot, registry);
		return registry;
	});
}

export async function readSessionRegistry(stateRoot: string, sessionKey: string): Promise<SessionRegistryFile> {
	return await readJsonFile<SessionRegistryFile>(getSessionRegistryPath(stateRoot, sessionKey), {
		sessionKey,
		sessionId: sessionKeyToId(sessionKey),
		updatedAt: nowIso(),
		rootAgentIds: [],
		bridgeDirs: [],
	});
}

export async function rememberSessionBridge(
	stateRoot: string,
	sessionKey: string,
	entry: Pick<SessionBridgeEntry, "bridgeDir" | "rootAgentId">,
): Promise<void> {
	const sessionRegistryPath = getSessionRegistryPath(stateRoot, sessionKey);
	await withQueuedFileOperation(sessionRegistryPath, async () => {
		const sessionRegistry = await readSessionRegistry(stateRoot, sessionKey);
		if (!sessionRegistry.bridgeDirs.includes(entry.bridgeDir)) {
			sessionRegistry.bridgeDirs.push(entry.bridgeDir);
		}
		if (!sessionRegistry.rootAgentIds.includes(entry.rootAgentId)) {
			sessionRegistry.rootAgentIds.push(entry.rootAgentId);
		}
		sessionRegistry.updatedAt = nowIso();
		await writeJsonFileAtomic(sessionRegistryPath, sessionRegistry);
	});
}

export async function resolveStatuses(stateRoot: string, registry: RegistryFile): Promise<ResolvedStatus[]> {
	const results: ResolvedStatus[] = [];
	for (const record of registry.agents) {
		const hasSession = await tmuxHasSession(record.sessionName).catch(() => false);
		let effectiveStatus: AgentStatus = record.status;
		if (record.status === "terminated") effectiveStatus = "terminated";
		else if (!hasSession) effectiveStatus = "missing";

		let bridgeSettlementState: BridgeSettlementState | undefined;
		let bridgeSettlementFinalizedAt: string | undefined;
		let bridgeProtocolViolationReason: string | undefined;
		let recentBridgeEvents: string[] | undefined;
		if (record.bridgeDir) {
			const [parentState, events] = await Promise.all([
				readBridgeParentState(record.bridgeDir).catch(() => undefined),
				readBridgeEvents(record.bridgeDir).catch(() => []),
			]);
			const settled = evaluateBridgeSettlement(events);
			if (settled.settledState !== "running") {
				bridgeSettlementState = settled.settledState;
				bridgeProtocolViolationReason = settled.protocolViolationReason;
			}
			const bridgeParentState = parentState as BridgeParentState | undefined;
			bridgeSettlementState ??= bridgeParentState?.terminalState;
			bridgeSettlementFinalizedAt = bridgeParentState?.terminalFinalizedAt;
			bridgeProtocolViolationReason ??= bridgeParentState?.protocolViolationReason;
			recentBridgeEvents = formatRecentBridgeEvents(events);
		}

		results.push({
			record,
			hasSession,
			effectiveStatus,
			bridgeSettlementState,
			bridgeSettlementFinalizedAt,
			bridgeProtocolViolationReason,
			recentBridgeEvents,
		});
	}
	return results;
}

export function formatAgentSummary(status: ResolvedStatus, options: { colorize?: boolean } = {}): string {
	const colorize = options.colorize ?? false;
	const label = buildAgentLabel(status.record, 52);
	const parts = [
		toneText(status.record.agentId, colorize, "bold"),
		label !== status.record.agentId ? toneText(label, colorize, "cyan") : undefined,
		formatEffectiveStatusBadge(status.effectiveStatus, colorize),
		formatSettlementBadge(status.bridgeSettlementState, colorize),
		status.record.visualMode === "iterm-opened" ? badge("OPEN", colorize, "blue") : undefined,
		`session=${status.record.sessionName}`,
	];
	return parts.filter(Boolean).join(" | ");
}

export function formatAgentDetails(status: ResolvedStatus): string[] {
	const statusBadge = formatEffectiveStatusBadge(status.effectiveStatus, false);
	const settlementBadge = formatSettlementBadge(status.bridgeSettlementState, false);
	const recentBridgeEvents = status.recentBridgeEvents ?? [];
	return [
		`label: ${buildAgentLabel(status.record)}`,
		`agentId: ${status.record.agentId}`,
		`sessionName: ${status.record.sessionName}`,
		`status: ${status.effectiveStatus} | ${statusBadge}`,
		`bridgeSettlementState: ${status.bridgeSettlementState ?? "running"}${settlementBadge ? ` | ${settlementBadge}` : ""}`,
		status.bridgeSettlementFinalizedAt ? `bridgeSettlementFinalizedAt: ${status.bridgeSettlementFinalizedAt}` : undefined,
		status.bridgeProtocolViolationReason ? `bridgeProtocolViolationReason: ${status.bridgeProtocolViolationReason}` : undefined,
		recentBridgeEvents.length > 0 ? "recentBridgeEvents:" : undefined,
		...recentBridgeEvents.map((event) => `  - ${event}`),
		status.record.role ? `role: ${status.record.role}` : undefined,
		status.record.goal ? `goal: ${status.record.goal}` : undefined,
		status.record.parentAgentId ? `parent: ${status.record.parentAgentId}` : undefined,
		`root: ${status.record.rootAgentId}`,
		`rootOwnerSessionKey: ${status.record.rootOwnerSessionKey}`,
		status.record.bridgeDir ? `bridgeDir: ${status.record.bridgeDir}` : undefined,
		status.record.notificationMode ? `notificationMode: ${status.record.notificationMode}` : undefined,
		`visualMode: ${status.record.visualMode}`,
		`openCount: ${status.record.openCount}`,
		`cwd: ${status.record.cwd}`,
		`model: ${status.record.model}`,
		status.record.lastOpenedAt ? `lastOpenedAt: ${status.record.lastOpenedAt}` : undefined,
		status.record.lastMessageAt ? `lastMessageAt: ${status.record.lastMessageAt}` : undefined,
		status.record.lastSeenAt ? `lastSeenAt: ${status.record.lastSeenAt}` : undefined,
		`createdAt: ${status.record.createdAt}`,
	].filter((line): line is string => Boolean(line));
}

export function filterStatusesByScope(
	statuses: ResolvedStatus[],
	scope: AgentScope,
	options: { rootAgentId?: string; ownerSessionKey?: string; sessionRootAgentIds?: string[] } = {},
): ResolvedStatus[] {
	if (scope === "all") return statuses;
	if (scope === "root") {
		if (!options.rootAgentId) return [];
		return statuses.filter((status) => status.record.rootAgentId === options.rootAgentId);
	}
	const allowedRoots = new Set(options.sessionRootAgentIds ?? []);
	const ownerSessionKey = options.ownerSessionKey;
	return statuses.filter((status) => {
		if (allowedRoots.has(status.record.rootAgentId)) return true;
		return ownerSessionKey ? status.record.rootOwnerSessionKey === ownerSessionKey : false;
	});
}

export function filterStatusesForList(statuses: ResolvedStatus[], includeExited = false): ResolvedStatus[] {
	if (includeExited) return statuses;
	return statuses.filter((status) => status.hasSession || status.effectiveStatus === "running");
}

export function buildTreeNodes(statuses: ResolvedStatus[]): AgentTreeNode[] {
	const byId = new Map(statuses.map((status) => [status.record.agentId, status]));
	const children = new Map<string, ResolvedStatus[]>();
	for (const status of statuses) {
		const parentAgentId = status.record.parentAgentId;
		if (!parentAgentId) continue;
		const bucket = children.get(parentAgentId) ?? [];
		bucket.push(status);
		children.set(parentAgentId, bucket);
	}
	const roots = statuses.filter((status) => !status.record.parentAgentId || !byId.has(status.record.parentAgentId));
	roots.sort((left, right) => left.record.createdAt.localeCompare(right.record.createdAt));

	const visit = (status: ResolvedStatus, depth: number): AgentTreeNode => {
		const childStatuses = children.get(status.record.agentId) ?? [];
		childStatuses.sort((left, right) => left.record.createdAt.localeCompare(right.record.createdAt));
		return {
			agentId: status.record.agentId,
			sessionName: status.record.sessionName,
			parentAgentId: status.record.parentAgentId,
			rootAgentId: status.record.rootAgentId,
			depth,
			effectiveStatus: status.effectiveStatus,
			bridgeSettlementState: status.bridgeSettlementState ?? "running",
			visualMode: status.record.visualMode,
			openCount: status.record.openCount,
			role: status.record.role,
			goal: status.record.goal,
			displayLabel: buildAgentLabel(status.record, 46),
			children: childStatuses.map((child) => visit(child, depth + 1)),
		};
	};

	return roots.map((root) => visit(root, 0));
}

export function formatTreeNodeLabel(node: AgentTreeNode, options: { colorize?: boolean } = {}): string {
	const colorize = options.colorize ?? false;
	const parts = [
		toneText(node.agentId, colorize, "bold"),
		node.displayLabel !== node.agentId ? toneText(node.displayLabel, colorize, "cyan") : undefined,
		formatEffectiveStatusBadge(node.effectiveStatus, colorize),
		formatSettlementBadge(node.bridgeSettlementState, colorize),
		node.depth === 0 ? badge("ROOT", colorize, "magenta") : undefined,
		node.visualMode === "iterm-opened" ? badge("OPEN", colorize, "blue") : undefined,
	];
	return parts.filter(Boolean).join(" | ");
}

export function flattenTreeNodes(nodes: AgentTreeNode[], options: { colorize?: boolean } = {}): FlattenedTreeNode[] {
	const flattened: FlattenedTreeNode[] = [];
	const visit = (node: AgentTreeNode, ancestorLastStates: boolean[]) => {
		flattened.push({
			node,
			label: `${buildTreePrefix(ancestorLastStates)}${formatTreeNodeLabel(node, options)}`,
		});
		node.children.forEach((child, index) => {
			visit(child, [...ancestorLastStates, index === node.children.length - 1]);
		});
	};
	nodes.forEach((node) => visit(node, []));
	return flattened;
}

export function buildTreeLines(nodes: AgentTreeNode[], options: { colorize?: boolean } = {}): string[] {
	const lines = flattenTreeNodes(nodes, options).map((entry) => entry.label);
	if (lines.length === 0) lines.push("No pimux agents available in the current session hierarchy.");
	return lines;
}

export function resolveTargetFromInput(
	registry: RegistryFile,
	input: string | undefined,
	currentAgentId?: string,
): ManagedAgentRecord | undefined {
	const trimmed = input?.trim();
	if (trimmed === "last" || !trimmed) {
		if (!trimmed && currentAgentId) {
			const current = registry.agents.find((agent) => agent.agentId === currentAgentId);
			if (current) return current;
		}
		return [...registry.agents].sort((left, right) => (right.updatedAt || right.createdAt).localeCompare(left.updatedAt || left.createdAt))[0];
	}
	return registry.agents.find((agent) => agent.agentId === trimmed || agent.sessionName === trimmed || agent.launchId === trimmed);
}

export function buildAgentId(seed?: string, fallback?: string, attempt = 0): string {
	const primary = (slugify(seed || "") || slugify(fallback || "") || "agent").slice(0, 28) || "agent";
	const now = new Date();
	const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
	const suffix = attempt > 0 ? `-${attempt}` : "";
	return `${primary}-${timestamp}${suffix}`;
}

export async function uniqueAgentIdentity(
	registry: RegistryFile,
	preferredAgentId: string | undefined,
	preferredSeed: string | undefined,
	hasSession: (sessionName: string) => Promise<boolean>,
	buildSessionName: (agentId: string) => string,
): Promise<{ agentId: string; sessionName: string }> {
	const explicit = preferredAgentId?.trim();
	if (explicit) {
		const normalized = slugify(explicit);
		if (!normalized) throw new Error("Invalid agentId. Use letters, numbers, and hyphens.");
		if (registry.agents.some((agent) => agent.agentId === normalized)) {
			throw new Error(`Agent ID already exists: ${normalized}`);
		}
		const sessionName = buildSessionName(normalized);
		if (await hasSession(sessionName)) {
			throw new Error(`tmux session already exists for ${normalized}: ${sessionName}`);
		}
		return { agentId: normalized, sessionName };
	}

	let attempt = 0;
	while (attempt < 50) {
		const agentId = buildAgentId(preferredSeed, preferredSeed, attempt);
		const sessionName = buildSessionName(agentId);
		const registryConflict = registry.agents.some((agent) => agent.agentId === agentId || agent.sessionName === sessionName);
		const tmuxConflict = await hasSession(sessionName).catch(() => false);
		if (!registryConflict && !tmuxConflict) return { agentId, sessionName };
		attempt += 1;
	}
	throw new Error("Failed to allocate a unique agent ID and tmux session name");
}

export function findBlockingDirectChildrenForCloseout(
	statuses: ResolvedStatus[],
	agentId: string,
): ResolvedStatus[] {
	const directChildren = statuses.filter((status) => status.record.parentAgentId === agentId);
	return directChildren.filter((status) => status.bridgeSettlementState !== "settled_completion");
}

export function suggestSupervisorTerminalReportKind(
	statuses: ResolvedStatus[],
	agentId: string,
): "question" | "blocker" | "failure" | "closeout" | undefined {
	const directChildren = statuses.filter((status) => status.record.parentAgentId === agentId);
	if (directChildren.length === 0) return "closeout";
	if (directChildren.some((status) => !isSettledTerminalState(status.bridgeSettlementState))) return undefined;
	if (directChildren.some((status) => status.bridgeSettlementState === "settled_waiting_on_parent")) return "question";
	if (
		directChildren.some(
			(status) => status.bridgeSettlementState === "settled_failure" || status.bridgeSettlementState === "protocol_violation",
		)
	)
		return "failure";
	if (directChildren.some((status) => status.bridgeSettlementState === "settled_blocked")) return "blocker";
	return "closeout";
}

export function findUnsettledDirectChildren(statuses: ResolvedStatus[], agentId: string): ResolvedStatus[] {
	const directChildren = statuses.filter((status) => status.record.parentAgentId === agentId);
	return directChildren.filter((status) => !isSettledTerminalState(status.bridgeSettlementState));
}

export function dashboardLines(statuses: ResolvedStatus[]): string[] {
	const nodes = buildTreeNodes(statuses);
	const liveCount = statuses.filter((status) => status.effectiveStatus === "running").length;
	const openCount = statuses.filter((status) => status.record.visualMode === "iterm-opened").length;
	const settledCount = statuses.filter((status) => status.bridgeSettlementState && status.bridgeSettlementState !== "running").length;
	const header = [
		"pimux",
		`${statuses.length} agents`,
		`live=${liveCount}`,
		openCount > 0 ? `open=${openCount}` : undefined,
		settledCount > 0 ? `settled=${settledCount}` : undefined,
	].filter((part): part is string => Boolean(part)).join(" | ");
	const lines = buildTreeLines(nodes);
	return [header, ...lines].slice(0, 10);
}

export function resolvePruneAgeReference(status: ResolvedStatus): number | undefined {
	const timestamp = status.record.terminatedAt ?? status.record.lastSeenAt ?? status.record.updatedAt ?? status.record.createdAt;
	const parsed = Date.parse(timestamp);
	return Number.isFinite(parsed) ? parsed : undefined;
}

export function parseAgeThresholdMs(value: string | undefined, fallback = "0s"): number {
	const normalized = value?.trim() || fallback;
	const match = normalized.match(/^(\d+)([smhdw])$/);
	if (!match) throw new Error(`Invalid olderThan threshold: ${normalized}. Use values like 0s, 30m, 12h, or 7d.`);
	const amount = Number(match[1]);
	const unit = match[2];
	const multiplier = unit === "s" ? 1000 : unit === "m" ? 60_000 : unit === "h" ? 3_600_000 : unit === "d" ? 86_400_000 : 604_800_000;
	return amount * multiplier;
}

export function shouldPruneStatus(status: ResolvedStatus, mode: PruneMode): boolean {
	if (status.effectiveStatus === "running") return false;
	if (mode === "auto") {
		return status.record.status === "terminated" || status.effectiveStatus === "missing";
	}
	return status.record.status === "terminated" || status.record.status === "exited" || status.effectiveStatus === "missing";
}

export function formatPruneCandidate(status: ResolvedStatus): string {
	const ageReference = resolvePruneAgeReference(status);
	const ageText = ageReference ? new Date(ageReference).toISOString() : "unknown-age";
	return `${status.record.agentId} | recorded=${status.record.status} | effective=${status.effectiveStatus} | ageReference=${ageText}`;
}

export async function archivePrunedAgents(
	stateRoot: string,
	statuses: ResolvedStatus[],
	scope: AgentScope,
	trigger: PruneMode,
	olderThan: string,
): Promise<void> {
	const archivedAt = nowIso();
	for (const status of statuses) {
		await appendJsonLine(getRegistryArchivePath(stateRoot), {
			archivedAt,
			reason: "prune",
			trigger,
			scope,
			olderThan,
			agent: status.record,
			effectiveStatus: status.effectiveStatus,
			bridgeSettlementState: status.bridgeSettlementState,
			bridgeSettlementFinalizedAt: status.bridgeSettlementFinalizedAt,
			bridgeProtocolViolationReason: status.bridgeProtocolViolationReason,
		});
	}
}

export async function writeAgentManifest(record: ManagedAgentRecord): Promise<void> {
	const manifestPath = getAgentManifestPath(path.resolve(record.runDir, "..", ".."), record.agentId);
	await withQueuedFileOperation(manifestPath, async () => {
		await writeJsonFileAtomic(manifestPath, record);
	});
}
