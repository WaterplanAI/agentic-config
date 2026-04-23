import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import * as path from "node:path";
import type { BridgeAuthorityBinding } from "./authority.ts";
import { withQueuedFileOperation } from "./file-queue.ts";
import {
	DEFAULT_MODEL,
	DEFAULT_NOTIFICATION_MODE,
	DEFAULT_REPORT_BYTES,
	PROTOCOL_VERSION,
	getBridgeChildStatePath,
	getBridgeEventsPath,
	getBridgeLaunchPath,
	getBridgeParentStatePath,
	getBridgeReportsDir,
	getBridgeSignalsDir,
	makeSignalName,
	normalizeNotificationMode,
	nowIso,
	slugify,
	summarizePrompt,
	truncate,
	type NotificationMode,
} from "./paths.ts";
import type { BridgeEventDirection, BridgeEventType, SettledTerminalState } from "./settlement.ts";

export type ReportParentKind = "question" | "blocker" | "progress" | "failure" | "closeout";

export interface BridgeLaunchFile {
	protocolVersion: number;
	launchId: string;
	bridgeDir: string;
	createdAt: string;
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
	parentSessionKey: string;
	notificationMode: NotificationMode;
	contextBrief?: string;
	stateRoot: string;
	extensionPath: string;
}

export interface BridgeEvent {
	eventId: string;
	timestamp: string;
	launchId: string;
	direction: BridgeEventDirection;
	type: BridgeEventType;
	from?: {
		agentId?: string;
		sessionName?: string;
		sessionFile?: string;
	};
	to?: {
		agentId?: string;
		sessionName?: string;
	};
	summary?: string;
	message?: string;
	requiresResponse?: boolean;
	reportPath?: string;
	signalPath?: string;
}

export interface BridgeParentState {
	deliveredEventIds: string[];
	terminalEventId?: string;
	terminalFinalizedAt?: string;
	terminalState?: SettledTerminalState;
	protocolViolationReason?: string;
	updatedAt?: string;
}

export interface BridgeChildState extends BridgeAuthorityBinding {
	reportCount: number;
	deliveredParentEventIds: string[];
	authoritativeBoundAt?: string;
	lastAuthoritativeSeenAt?: string;
	updatedAt?: string;
}

export interface SessionBridgeEntry {
	launchId: string;
	bridgeDir: string;
	agentId: string;
	sessionName: string;
	rootAgentId: string;
	createdAt: string;
	notificationMode: NotificationMode;
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

async function writeTextFileAtomic(filePath: string, content: string): Promise<void> {
	await fs.mkdir(path.dirname(filePath), { recursive: true });
	const tempPath = `${filePath}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
	await fs.writeFile(tempPath, content, "utf-8");
	await fs.rename(tempPath, filePath);
}

async function appendJsonLine(filePath: string, value: unknown): Promise<void> {
	await fs.mkdir(path.dirname(filePath), { recursive: true });
	await fs.appendFile(filePath, `${JSON.stringify(value)}\n`, "utf-8");
}

function uniqueStrings(values: Array<string | undefined>): string[] {
	const seen = new Set<string>();
	const result: string[] = [];
	for (const value of values) {
		if (!value || seen.has(value)) continue;
		seen.add(value);
		result.push(value);
	}
	return result;
}

function preferLatestIso(left: string | undefined, right: string | undefined): string | undefined {
	if (!left) return right;
	if (!right) return left;
	return left >= right ? left : right;
}

function mergeBridgeParentState(current: BridgeParentState, next: BridgeParentState): BridgeParentState {
	return {
		...current,
		...next,
		deliveredEventIds: uniqueStrings([...(current.deliveredEventIds ?? []), ...(next.deliveredEventIds ?? [])]),
		terminalEventId: next.terminalEventId ?? current.terminalEventId,
		terminalFinalizedAt: preferLatestIso(current.terminalFinalizedAt, next.terminalFinalizedAt),
		terminalState: next.terminalState ?? current.terminalState,
		protocolViolationReason: next.protocolViolationReason ?? current.protocolViolationReason,
	};
}

function mergeBridgeChildState(current: BridgeChildState, next: BridgeChildState): BridgeChildState {
	return {
		...current,
		...next,
		reportCount: Math.max(current.reportCount ?? 0, next.reportCount ?? 0),
		deliveredParentEventIds: uniqueStrings([...(current.deliveredParentEventIds ?? []), ...(next.deliveredParentEventIds ?? [])]),
		authoritativeSessionKey: next.authoritativeSessionKey ?? current.authoritativeSessionKey,
		authoritativeSessionFile: next.authoritativeSessionFile ?? current.authoritativeSessionFile,
		authoritativeLeafId: next.authoritativeLeafId ?? current.authoritativeLeafId,
		authoritativeProcessId: next.authoritativeProcessId ?? current.authoritativeProcessId,
		authoritativeBoundAt: preferLatestIso(current.authoritativeBoundAt, next.authoritativeBoundAt),
		lastAuthoritativeSeenAt: preferLatestIso(current.lastAuthoritativeSeenAt, next.lastAuthoritativeSeenAt),
	};
}

export async function ensureBridgeDir(bridgeDir: string): Promise<void> {
	await fs.mkdir(path.join(bridgeDir, "parent"), { recursive: true });
	await fs.mkdir(path.join(bridgeDir, "child"), { recursive: true });
	await fs.mkdir(getBridgeSignalsDir(bridgeDir), { recursive: true });
	await fs.mkdir(getBridgeReportsDir(bridgeDir), { recursive: true });
}

export async function readBridgeLaunch(bridgeDir: string): Promise<BridgeLaunchFile> {
	const launch = await readJsonFile<BridgeLaunchFile>(getBridgeLaunchPath(bridgeDir), {
		protocolVersion: PROTOCOL_VERSION,
		launchId: "",
		bridgeDir,
		createdAt: nowIso(),
		agentId: "unknown",
		sessionName: "unknown",
		cwd: ".",
		model: DEFAULT_MODEL,
		promptPreview: "",
		rootAgentId: "unknown",
		rootOwnerSessionKey: "unknown",
		parentSessionKey: "unknown",
		notificationMode: DEFAULT_NOTIFICATION_MODE,
		stateRoot: path.resolve(bridgeDir, "..", ".."),
		extensionPath: "",
	});
	return {
		...launch,
		notificationMode: normalizeNotificationMode(launch.notificationMode) ?? DEFAULT_NOTIFICATION_MODE,
	};
}

export async function writeBridgeLaunch(bridgeDir: string, launch: BridgeLaunchFile): Promise<void> {
	await ensureBridgeDir(bridgeDir);
	await writeJsonFileAtomic(getBridgeLaunchPath(bridgeDir), launch);
}

export async function readBridgeParentState(bridgeDir: string): Promise<BridgeParentState> {
	return await readJsonFile<BridgeParentState>(getBridgeParentStatePath(bridgeDir), { deliveredEventIds: [] });
}

export async function writeBridgeParentState(bridgeDir: string, state: BridgeParentState): Promise<void> {
	const parentStatePath = getBridgeParentStatePath(bridgeDir);
	await withQueuedFileOperation(parentStatePath, async () => {
		const current = await readJsonFile<BridgeParentState>(parentStatePath, { deliveredEventIds: [] });
		const merged = mergeBridgeParentState(current, state);
		merged.updatedAt = nowIso();
		await writeJsonFileAtomic(parentStatePath, merged);
	});
}

export async function readBridgeChildState(bridgeDir: string): Promise<BridgeChildState> {
	return await readJsonFile<BridgeChildState>(getBridgeChildStatePath(bridgeDir), {
		reportCount: 0,
		deliveredParentEventIds: [],
	});
}

export async function writeBridgeChildState(bridgeDir: string, state: BridgeChildState): Promise<void> {
	const childStatePath = getBridgeChildStatePath(bridgeDir);
	await withQueuedFileOperation(childStatePath, async () => {
		const current = await readJsonFile<BridgeChildState>(childStatePath, {
			reportCount: 0,
			deliveredParentEventIds: [],
		});
		const merged = mergeBridgeChildState(current, state);
		merged.updatedAt = nowIso();
		await writeJsonFileAtomic(childStatePath, merged);
	});
}

export async function readBridgeEvents(bridgeDir: string): Promise<BridgeEvent[]> {
	try {
		const content = await fs.readFile(getBridgeEventsPath(bridgeDir), "utf-8");
		return content
			.split(/\r?\n/)
			.map((line) => line.trim())
			.filter(Boolean)
			.map((line) => JSON.parse(line) as BridgeEvent);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
		throw error;
	}
}

export async function appendBridgeEvent(
	bridgeDir: string,
	event: Omit<BridgeEvent, "eventId" | "timestamp">,
): Promise<BridgeEvent> {
	const fullEvent: BridgeEvent = {
		eventId: randomUUID(),
		timestamp: nowIso(),
		...event,
	};
	const eventsPath = getBridgeEventsPath(bridgeDir);
	await withQueuedFileOperation(eventsPath, async () => {
		await appendJsonLine(eventsPath, fullEvent);
	});
	return fullEvent;
}

export async function writeSignalFile(
	filePath: string,
	fields: Record<string, unknown>,
	success = true,
): Promise<string> {
	const resolved = filePath.endsWith(".done") || filePath.endsWith(".fail") ? filePath : `${filePath}.${success ? "done" : "fail"}`;
	const lines = Object.entries(fields).map(([key, value]) => `${key}: ${String(value ?? "")}`);
	await writeTextFileAtomic(resolved, `${lines.join("\n")}\n`);
	return resolved;
}

export async function writeBridgeEventSignal(bridgeDir: string, event: BridgeEvent, success = true): Promise<string> {
	const safeType = slugify(event.type) || "event";
	const signalBase = path.join(getBridgeSignalsDir(bridgeDir), `${safeType}-${event.eventId}`);
	return await writeSignalFile(
		signalBase,
		{
			event_id: event.eventId,
			launch_id: event.launchId,
			type: event.type,
			status: success ? "success" : "fail",
			created_at: event.timestamp,
			report_path: event.reportPath ?? "",
			summary: event.summary ?? "",
		},
		success,
	);
}

export async function nextBridgeReportNumber(bridgeDir: string): Promise<number> {
	const childStatePath = getBridgeChildStatePath(bridgeDir);
	return await withQueuedFileOperation(childStatePath, async () => {
		const state = await readJsonFile<BridgeChildState>(childStatePath, {
			reportCount: 0,
			deliveredParentEventIds: [],
		});
		state.reportCount = (state.reportCount ?? 0) + 1;
		state.updatedAt = nowIso();
		await writeJsonFileAtomic(childStatePath, state);
		return state.reportCount;
	});
}

export async function writeBridgeReport(
	bridgeDir: string,
	kind: ReportParentKind,
	markdown: string,
): Promise<{ reportPath: string; reportNumber: number }> {
	const reportNumber = await nextBridgeReportNumber(bridgeDir);
	const reportPath = path.join(getBridgeReportsDir(bridgeDir), `${String(reportNumber).padStart(3, "0")}-${kind}.md`);
	await writeTextFileAtomic(reportPath, markdown.trimEnd() + "\n");
	return { reportPath, reportNumber };
}

function extractHeaders(content: string): string[] {
	return content
		.split(/\r?\n/)
		.filter((line) => /^#{1,6}\s+/.test(line))
		.slice(0, 32)
		.map((line) => `- ${line.trim()}`);
}

function extractExecutiveSummary(content: string, maxBytes = DEFAULT_REPORT_BYTES): string {
	const lines = content.split(/\r?\n/);
	let start = -1;
	let end = lines.length;
	for (let index = 0; index < lines.length; index += 1) {
		if (/^##\s+Executive Summary/i.test(lines[index])) {
			start = index + 1;
			continue;
		}
		if (start >= 0 && (/^##\s+/.test(lines[index]) || lines[index].trim() === "---")) {
			end = index;
			break;
		}
	}
	if (start === -1) return "No Executive Summary section found";
	const section = lines.slice(start, end).join("\n").trim();
	const buffer = Buffer.from(section, "utf-8");
	return buffer.byteLength > maxBytes ? buffer.subarray(0, maxBytes).toString("utf-8") : section;
}

export async function readBoundedReportSummary(reportPath: string, maxBytes = DEFAULT_REPORT_BYTES): Promise<string> {
	const absolutePath = path.resolve(reportPath);
	const content = await fs.readFile(absolutePath, "utf-8");
	const stat = await fs.stat(absolutePath);
	const words = content.split(/\s+/).filter(Boolean).length;
	const headers = extractHeaders(content);
	const executiveSummary = extractExecutiveSummary(content, maxBytes);
	return [
		"## File Metadata",
		`- Path: ${absolutePath}`,
		`- Size: ${stat.size} bytes`,
		`- Words: ${words}`,
		`- Modified: ${new Date(stat.mtimeMs).toISOString()}`,
		"",
		"## Table of Contents",
		...(headers.length > 0 ? headers : ["No markdown headers found"]),
		"",
		"## Executive Summary",
		executiveSummary,
	].join("\n");
}

export function buildChildProtocol(launch: BridgeLaunchFile): string {
	const lines = [
		"You are a pimux child session linked to a parent session through a private bridge.",
		"",
		"Core rules:",
		"- Work on the assigned mission normally.",
		"- Parent -> child messaging uses pimux send_message and arrives through the bridge inbox.",
		"- Child -> parent reporting uses pimux report_parent only from this authoritative direct child session.",
		"- If you launch local helpers or subagents, they are local-only and must not call pimux or report_parent.",
		"- If you act as an orchestrator, you own the control-plane for your subtree.",
		"- Do not send repeated impatient nudges.",
		"- Do not retry a spawn if the requested child already exists.",
		"- Do not treat helper output, capture noise, or partial artifacts as completion.",
		"- If you spawn pimux children, verify them via pimux status before you consolidate upward.",
		"",
		"Terminal rules:",
		"- Emit progress only for bounded non-terminal updates.",
		"- For same-session parent input that you need before continuing, emit progress with requiresResponse=true.",
		"- Emit question only for terminal waiting-on-parent settlement; do not use question when you intend to keep working in this session.",
		"- Emit blocker when the run is terminally blocked and should settle blocked.",
		"- Emit failure for explicit non-success terminal handoff.",
		"- Emit closeout exactly once when the entire assigned mission is complete.",
		"- Success settles only after closeout plus managed-session exit.",
		"- After any terminal report (closeout, failure, blocker, or question), do not keep working or continue the conversation; the pimux runtime will finalize the managed session.",
		"- Exiting without a valid terminal declaration settles as protocol_violation.",
		"- If you are an orchestrator, do not emit closeout while any direct pimux child is still running or unsettled.",
		"",
		"Messaging contract:",
		"- Keep reports bounded and decision-oriented.",
		"- Include status, delivered work, blockers, and next recommendation in summaries.",
		"- Use requiresResponse=true on progress when the parent must answer before you can continue.",
		launch.goal ? `Launch goal: ${launch.goal}` : `Launch goal: ${launch.promptPreview}`,
		launch.role ? `Launch role: ${launch.role}` : undefined,
		launch.contextBrief ? `Context brief: ${truncate(launch.contextBrief, 500)}` : undefined,
	].filter((line): line is string => Boolean(line));
	return lines.join("\n");
}

export async function writeLaunchPacket(
	stateRoot: string,
	agentId: string,
	launch: BridgeLaunchFile,
	prompt: string,
): Promise<void> {
	const packetPath = path.join(stateRoot, "agents", slugify(agentId) || agentId, "launch.md");
	const content = [
		`# pimux launch packet: ${agentId}`,
		"",
		"## Mission",
		launch.goal ?? launch.promptPreview,
		"",
		"## Prompt",
		prompt.trim(),
		"",
		"## Context",
		`- Agent ID: ${launch.agentId}`,
		`- Session Name: ${launch.sessionName}`,
		`- Root Agent ID: ${launch.rootAgentId}`,
		launch.parentAgentId ? `- Parent Agent ID: ${launch.parentAgentId}` : undefined,
		`- Notification Mode: ${launch.notificationMode}`,
		launch.contextBrief ? `- Context Brief: ${launch.contextBrief}` : undefined,
	].filter((line): line is string => Boolean(line)).join("\n");
	await writeTextFileAtomic(packetPath, `${content}\n`);
}

export function buildBridgeSessionEntry(launch: BridgeLaunchFile): SessionBridgeEntry {
	return {
		launchId: launch.launchId,
		bridgeDir: launch.bridgeDir,
		agentId: launch.agentId,
		sessionName: launch.sessionName,
		rootAgentId: launch.rootAgentId,
		createdAt: launch.createdAt,
		notificationMode: normalizeNotificationMode(launch.notificationMode) ?? DEFAULT_NOTIFICATION_MODE,
	};
}

export async function createBridgeLaunch(params: {
	bridgeDir: string;
	agentId: string;
	sessionName: string;
	cwd: string;
	model: string;
	prompt: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId: string;
	rootOwnerSessionKey: string;
	parentSessionKey: string;
	notificationMode: NotificationMode;
	contextBrief?: string;
	stateRoot: string;
	extensionPath: string;
}): Promise<BridgeLaunchFile> {
	const launch: BridgeLaunchFile = {
		protocolVersion: PROTOCOL_VERSION,
		launchId: randomUUID(),
		bridgeDir: params.bridgeDir,
		createdAt: nowIso(),
		agentId: params.agentId,
		sessionName: params.sessionName,
		cwd: params.cwd,
		model: params.model,
		promptPreview: summarizePrompt(params.prompt),
		role: params.role,
		goal: params.goal,
		parentAgentId: params.parentAgentId,
		rootAgentId: params.rootAgentId,
		rootOwnerSessionKey: params.rootOwnerSessionKey,
		parentSessionKey: params.parentSessionKey,
		notificationMode: normalizeNotificationMode(params.notificationMode) ?? DEFAULT_NOTIFICATION_MODE,
		contextBrief: params.contextBrief,
		stateRoot: params.stateRoot,
		extensionPath: params.extensionPath,
	};
	await ensureBridgeDir(params.bridgeDir);
	await writeBridgeLaunch(params.bridgeDir, launch);
	await writeBridgeParentState(params.bridgeDir, { deliveredEventIds: [] });
	await writeBridgeChildState(params.bridgeDir, { reportCount: 0, deliveredParentEventIds: [] });
	await writeTextFileAtomic(path.join(params.bridgeDir, "child", "protocol.md"), `${buildChildProtocol(launch)}\n`);
	await writeTextFileAtomic(path.join(params.bridgeDir, "child", "prompt.txt"), `${params.prompt.trim()}\n`);
	await writeLaunchPacket(params.stateRoot, params.agentId, launch, params.prompt);
	return launch;
}
