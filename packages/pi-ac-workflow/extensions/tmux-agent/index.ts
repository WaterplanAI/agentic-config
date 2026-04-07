import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { promises as fs, watch as watchFs } from "node:fs";
import type { FSWatcher } from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { StringEnum } from "@mariozechner/pi-ai";
import { getAgentDir, type ExtensionAPI, type ExtensionCommandContext, type ExtensionContext } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

const EXTENSION_NAME = "tmux-agent";
const DEFAULT_MODEL = "openai-codex/gpt-5.3-codex";
const DEFAULT_CAPTURE_LINES = 80;
const DEFAULT_REPORT_BYTES = 2048;
const TERMINAL_COMPLETION_SETTLE_MS = 30_000;
const SESSION_WINDOW = "agent";
const REGISTRY_VERSION = 2;
const BRIDGE_VERSION = 1;
const ROOT_VERSION = 1;

const ENV_AGENT_ID = "PI_TMUX_AGENT_ID";
const ENV_PARENT_AGENT_ID = "PI_TMUX_AGENT_PARENT_ID";
const ENV_ROOT_AGENT_ID = "PI_TMUX_AGENT_ROOT_ID";
const ENV_ROLE = "PI_TMUX_AGENT_ROLE";
const ENV_GOAL = "PI_TMUX_AGENT_GOAL";
const ENV_BRIDGE_DIR = "PI_TMUX_BRIDGE_DIR";
const ENV_LAUNCH_ID = "PI_TMUX_LAUNCH_ID";
const ENV_PARENT_SESSION_FILE = "PI_TMUX_PARENT_SESSION_FILE";
const ENV_PARENT_SESSION_KEY = "PI_TMUX_PARENT_SESSION_KEY";
const ENV_PARENT_LEAF_ID = "PI_TMUX_PARENT_LEAF_ID";
const ENV_NOTIFICATION_MODE = "PI_TMUX_NOTIFICATION_MODE";
const ENV_CONTEXT_BRIEF = "PI_TMUX_CONTEXT_BRIEF";
const ENV_ROOT_DIR = "PI_TMUX_ROOT_DIR";

const stateDir = path.join(getAgentDir(), "state", EXTENSION_NAME);
const runsDir = path.join(stateDir, "runs");
const logsDir = path.join(stateDir, "logs");
const registryPath = path.join(stateDir, "registry.json");
const messageAuditPath = path.join(stateDir, "messages.jsonl");

type AgentStatus = "running" | "exited" | "missing" | "terminated";
type VisualMode = "headless" | "iterm-opened";
type NotificationMode = "notify" | "notify-and-follow-up" | "silent";
type PeerMode = "alone" | "all" | "subset" | "direct";
type DebateMirrorMode = "none" | "summary-only" | "full-events";
type DebateStatus = "open" | "closed";
type BridgeEventDirection = "system" | "parent_to_child" | "child_to_parent";
type BridgeEventType =
	| "launched"
	| "instruction"
	| "answer"
	| "clarification"
	| "completion"
	| "question"
	| "blocker"
	| "progress"
	| "failure"
	| "exited"
	| "shutdown_request"
	| "closeout";
type ReportParentKind = "question" | "blocker" | "progress" | "failure";
type DebateEventType = "debate_message" | "debate_summary" | "debate_closed";

interface ManagedVisualRef {
	kind: "iterm-session";
	sessionUniqueId: string;
	openedAt: string;
}

interface ManagedAgentRecord {
	agentId: string;
	sessionName: string;
	cwd: string;
	model: string;
	promptPreview: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId: string;
	createdByAgentId?: string;
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
	lastClosedAt?: string;
	runDir: string;
	launcherPath: string;
	promptPath: string;
	launchId?: string;
	bridgeDir?: string;
	parentSessionFile?: string;
	parentSessionKey?: string;
	parentLeafId?: string;
	notificationMode?: NotificationMode;
	contextBrief?: string;
	rootDir?: string;
	peerMode?: PeerMode;
	peerParticipants?: string[];
}

interface RegistryFile {
	version: number;
	updatedAt: string;
	agents: ManagedAgentRecord[];
}

interface CurrentAgentEnv {
	agentId?: string;
	parentAgentId?: string;
	rootAgentId?: string;
	role?: string;
	goal?: string;
	bridgeDir?: string;
	launchId?: string;
	parentSessionFile?: string;
	parentSessionKey?: string;
	parentLeafId?: string;
	notificationMode?: NotificationMode;
	contextBrief?: string;
	rootDir?: string;
}

interface SpawnRequest {
	agentId?: string;
	cwd?: string;
	model?: string;
	prompt: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId?: string;
	rootDir?: string;
	openIterm?: boolean;
	notificationMode?: NotificationMode;
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

interface ResolvedStatus {
	record: ManagedAgentRecord;
	hasSession: boolean;
	effectiveStatus: AgentStatus;
}

interface RunCommandOptions {
	cwd?: string;
	input?: string;
	signal?: AbortSignal;
}

interface RunCommandResult {
	code: number;
	stdout: string;
	stderr: string;
}

interface ParsedArgs {
	flags: Map<string, string | boolean>;
	positionals: string[];
}

interface BridgeLaunchFile {
	bridgeVersion: number;
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
	parentRootAgentId?: string;
	parentSessionFile?: string;
	parentSessionKey: string;
	parentLeafId?: string;
	notificationMode: NotificationMode;
	contextBrief?: string;
}

interface BridgeParentState {
	deliveredEventIds: string[];
	terminalEventId?: string;
	terminalFinalizedAt?: string;
	pendingTerminalEventId?: string;
	pendingTerminalObservedAt?: string;
	updatedAt?: string;
}

interface BridgeChildState {
	reportCount: number;
	updatedAt?: string;
}

interface BridgeEvent {
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

interface SessionBridgeEntry {
	launchId: string;
	bridgeDir: string;
	agentId: string;
	sessionName: string;
	createdAt: string;
	notificationMode: NotificationMode;
}

interface RootCoordinationFile {
	rootVersion: number;
	rootAgentId: string;
	rootDir: string;
	createdAt: string;
	updatedAt: string;
}

interface RootAgentState {
	agentId: string;
	sessionName: string;
	rootAgentId: string;
	rootDir: string;
	role?: string;
	goal?: string;
	status: AgentStatus;
	peerMode: PeerMode;
	peerParticipants: string[];
	createdAt: string;
	updatedAt: string;
}

interface DebateFile {
	debateId: string;
	rootAgentId: string;
	rootDir: string;
	createdBy: string;
	createdAt: string;
	updatedAt: string;
	mode: PeerMode;
	participants: string[];
	participantSessionNames: string[];
	mirrorToParent: DebateMirrorMode;
	status: DebateStatus;
	topic?: string;
	lastSeq: number;
}

interface DebateEvent {
	eventId: string;
	seq: number;
	timestamp: string;
	direction: "peer_to_peer";
	type: DebateEventType;
	debateId: string;
	from: {
		agentId: string;
	};
	scope: PeerMode;
	targets: string[];
	summary: string;
	message?: string;
	requiresResponse?: boolean;
	reportPath?: string;
}

interface DebateDeliveryState {
	debateId: string;
	agentId: string;
	lastDeliveredSeq: number;
	lastSeenAt?: string;
}

interface DebateStartRequest {
	debateId?: string;
	rootAgentId?: string;
	mode?: PeerMode;
	participants?: string[];
	topic?: string;
	mirrorToParent?: DebateMirrorMode;
	createdBy?: string;
}

interface DebateSendRequest {
	debateId: string;
	message: string;
	summary?: string;
	participants?: string[];
	rootAgentId?: string;
	senderAgentId?: string;
	requiresResponse?: boolean;
	reportMarkdown?: string;
}

interface DebateCloseRequest {
	debateId: string;
	rootAgentId?: string;
	closedBy?: string;
	summary?: string;
	reportMarkdown?: string;
}

interface PeerModeSetRequest {
	target: string;
	mode: PeerMode;
	participants?: string[];
}

interface PeerListEntry {
	agentId: string;
	sessionName: string;
	rootAgentId: string;
	rootDir: string;
	status: AgentStatus;
	peerMode: PeerMode;
	peerParticipants: string[];
}

const TMUX_AGENT_PARAMS = Type.Object({
	action: StringEnum([
		"spawn",
		"open_visual",
		"close_visual",
		"list",
		"status",
		"send_message",
		"capture",
		"kill",
		"tree",
		"report_parent",
		"debate_start",
		"debate_send",
		"debate_close",
		"peer_mode_set",
		"peer_list",
	] as const),
	target: Type.Optional(Type.String({ description: "Target agent ID, session name, or 'last'" })),
	agentId: Type.Optional(Type.String({ description: "Preferred agent ID when spawning" })),
	cwd: Type.Optional(Type.String({ description: "Working directory for a spawned agent" })),
	model: Type.Optional(Type.String({ description: "Model for a spawned agent, e.g. openai-codex/gpt-5.3-codex" })),
	prompt: Type.Optional(Type.String({ description: "Initial prompt for a spawned agent" })),
	role: Type.Optional(Type.String({ description: "Organizational role, e.g. chief-of-staff or head-of-engineering" })),
	goal: Type.Optional(Type.String({ description: "Short goal or mission for the agent" })),
	parentAgentId: Type.Optional(Type.String({ description: "Parent agent ID for hierarchy tracking" })),
	rootAgentId: Type.Optional(Type.String({ description: "Root agent ID for hierarchy tracking" })),
	debateId: Type.Optional(Type.String({ description: "Debate channel ID" })),
	peerMode: Type.Optional(StringEnum(["alone", "all", "subset", "direct"] as const)),
	participants: Type.Optional(Type.Array(Type.String({ description: "Participant agent ID or session name" }))),
	topic: Type.Optional(Type.String({ description: "Debate topic or short title" })),
	mirrorToParent: Type.Optional(StringEnum(["none", "summary-only", "full-events"] as const)),
	openIterm: Type.Optional(Type.Boolean({ description: "Open a new iTerm tab attached to the tmux session" })),
	notificationMode: Type.Optional(StringEnum(["notify", "notify-and-follow-up", "silent"] as const)),
	contextBrief: Type.Optional(Type.String({ description: "Optional compact context packet to preserve the launching session's intent" })),
	lines: Type.Optional(Type.Number({ description: "Number of pane lines to capture" })),
	message: Type.Optional(Type.String({ description: "Message to send to another managed agent" })),
	senderAgentId: Type.Optional(Type.String({ description: "Override sender agent ID when sending a message" })),
	includeExited: Type.Optional(Type.Boolean({ description: "Include exited or terminated agents when listing" })),
	reportKind: Type.Optional(StringEnum(["question", "blocker", "progress", "failure"] as const)),
	summary: Type.Optional(Type.String({ description: "Short structured summary for report_parent" })),
	reportMarkdown: Type.Optional(Type.String({ description: "Optional markdown artifact body for report_parent" })),
	requiresResponse: Type.Optional(Type.Boolean({ description: "Whether the parent should respond to the report_parent event" })),
});

function nowIso(): string {
	return new Date().toISOString();
}

function truncate(text: string, maxLength: number): string {
	const normalized = text.replace(/\s+/g, " ").trim();
	if (normalized.length <= maxLength) return normalized;
	return `${normalized.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function firstNonEmptyLine(text: string): string {
	for (const line of text.split(/\r?\n/)) {
		const trimmed = line.trim();
		if (trimmed) return trimmed;
	}
	return "";
}

function summarizePrompt(prompt: string): string {
	const firstLine = firstNonEmptyLine(prompt);
	return truncate(firstLine || prompt, 120);
}

function slugify(value: string): string {
	return value
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
		.replace(/-{2,}/g, "-")
		.slice(0, 32);
}

function shellQuote(value: string): string {
	return `'${value.replace(/'/g, `'"'"'`)}'`;
}

function normalizeOptional(value: string | undefined): string | undefined {
	const trimmed = value?.trim();
	return trimmed ? trimmed : undefined;
}

function requiredFlagValue(name: string, value: string | boolean | undefined): string {
	if (typeof value === "string" && value.trim()) return value.trim();
	throw new Error(`Missing value for ${name}`);
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

function getCurrentAgentEnv(): CurrentAgentEnv {
	return {
		agentId: normalizeOptional(process.env[ENV_AGENT_ID]),
		parentAgentId: normalizeOptional(process.env[ENV_PARENT_AGENT_ID]),
		rootAgentId: normalizeOptional(process.env[ENV_ROOT_AGENT_ID]),
		role: normalizeOptional(process.env[ENV_ROLE]),
		goal: normalizeOptional(process.env[ENV_GOAL]),
		bridgeDir: normalizeOptional(process.env[ENV_BRIDGE_DIR]),
		launchId: normalizeOptional(process.env[ENV_LAUNCH_ID]),
		parentSessionFile: normalizeOptional(process.env[ENV_PARENT_SESSION_FILE]),
		parentSessionKey: normalizeOptional(process.env[ENV_PARENT_SESSION_KEY]),
		parentLeafId: normalizeOptional(process.env[ENV_PARENT_LEAF_ID]),
		notificationMode: normalizeOptional(process.env[ENV_NOTIFICATION_MODE]) as NotificationMode | undefined,
		contextBrief: normalizeOptional(process.env[ENV_CONTEXT_BRIEF]),
		rootDir: normalizeOptional(process.env[ENV_ROOT_DIR]),
	};
}

function buildUsage(): string {
	return [
		"Usage:",
		"  /tmux-agent spawn <prompt>",
		"  /tmux-agent spawn [--watch|--open-iterm] [--cwd PATH] [--model PROVIDER/MODEL] <prompt>",
		"  /tmux-agent spawn [--notify|--follow-up|--silent] [--context TEXT] <prompt>",
		"  /tmux-agent spawn --advanced [--agent-id ID] [--role ROLE] [--goal TEXT] [--parent ID] [--root ID] <prompt>",
		"  /tmux-agent open [target|last]",
		"  /tmux-agent close [target|last]",
		"  /tmux-agent list",
		"  /tmux-agent status [target|last]",
		"  /tmux-agent capture [target|last] [--lines N]",
		"  /tmux-agent send [target|last] <message>",
		"  /tmux-agent kill [target|last]",
		"  /tmux-agent tree",
		"  /tmux-agent debate start [--id ID] [--all|--subset|--direct|--alone] [--participants a,b] [topic]",
		"  /tmux-agent debate send <debate-id> <message>",
		"  /tmux-agent debate close <debate-id> [summary]",
		"  /tmux-agent peer-mode <target> <alone|all|subset|direct> [--participants a,b]",
		"  /tmux-agent peer-list [target]",
		"",
		"Defaults:",
		"  spawn auto-uses the current cwd and current model, infers role/goal from the prompt,",
		"  creates a private launch bridge for bounded parent-child reporting, and notifies the launching session when the child completes.",
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

	if (escaping) current += "\\";
	if (quote) throw new Error("Unterminated quoted string in command arguments");
	if (current.length > 0) tokens.push(current);
	return tokens;
}

function parseArgs(tokens: string[]): ParsedArgs {
	const flags = new Map<string, string | boolean>();
	const positionals: string[] = [];

	for (let i = 0; i < tokens.length; i++) {
		const token = tokens[i];
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
		const next = tokens[i + 1];
		if (!next || next.startsWith("--")) {
			flags.set(key, true);
			continue;
		}

		flags.set(key, next);
		i += 1;
	}

	return { flags, positionals };
}

function getStringFlag(parsed: ParsedArgs, name: string): string | undefined {
	const value = parsed.flags.get(name);
	if (typeof value !== "string") return undefined;
	const trimmed = value.trim();
	return trimmed ? trimmed : undefined;
}

function hasFlag(parsed: ParsedArgs, ...names: string[]): boolean {
	return names.some((name) => Boolean(parsed.flags.get(name)));
}

function uniqueStrings(values: string[]): string[] {
	return [...new Set(values.filter(Boolean))];
}

function parseParticipantValues(values: string[] | undefined): string[] {
	if (!values) return [];
	return uniqueStrings(values.map((value) => value.trim()).filter(Boolean));
}

function parseParticipantFlag(value: string | undefined): string[] {
	if (!value) return [];
	return parseParticipantValues(value.split(",").map((item) => item.trim()));
}

function inferPeerMode(parsed: ParsedArgs, fallback: PeerMode = "all"): PeerMode {
	if (hasFlag(parsed, "alone")) return "alone";
	if (hasFlag(parsed, "all")) return "all";
	if (hasFlag(parsed, "subset")) return "subset";
	if (hasFlag(parsed, "direct")) return "direct";
	return fallback;
}

function normalizeDebateId(value: string | undefined, fallback?: string): string {
	const normalized = slugify(value ?? "") || slugify(fallback ?? "");
	if (!normalized) throw new Error("A debate ID is required");
	return normalized;
}

function inferMirrorMode(value: string | undefined): DebateMirrorMode | undefined {
	if (!value) return undefined;
	if (value === "none" || value === "summary-only" || value === "full-events") return value;
	throw new Error(`Invalid mirrorToParent: ${value}`);
}

function inferPeerModeValue(value: string | undefined): PeerMode | undefined {
	if (!value) return undefined;
	if (value === "alone" || value === "all" || value === "subset" || value === "direct") return value;
	throw new Error(`Invalid peer mode: ${value}`);
}

function inferDebateTopic(positionals: string[]): string | undefined {
	const topic = positionals.join(" ").trim();
	return topic || undefined;
}

function inferDebateSummary(message: string, explicitSummary?: string): string {
	return truncate(explicitSummary?.trim() || message.trim(), 500);
}

function inferTargetList(parsed: ParsedArgs): string[] {
	return parseParticipantFlag(getStringFlag(parsed, "participants"));
}

function inferRequiresResponse(parsed: ParsedArgs, fallback = false): boolean {
	if (hasFlag(parsed, "requires-response", "require-response", "ask-response")) return true;
	if (hasFlag(parsed, "no-response", "no-follow-up")) return false;
	return fallback;
}

function inferRoleFromPrompt(prompt: string): string | undefined {
	const text = prompt.toLowerCase();
	const headOfMatch = text.match(/\bhead of ([a-z0-9][a-z0-9/& -]{1,30})\b/);
	if (headOfMatch) return `head-of-${slugify(headOfMatch[1])}`;
	if (/\bchief of staff\b|\bchief-of-staff\b/.test(text)) return "chief-of-staff";
	if (/\bhead\b.*\bengineering\b|\bengineering head\b|\bhead-eng\b/.test(text)) return "head-of-engineering";
	if (/\bhead\b.*\bresearch\b|\bresearch head\b/.test(text)) return "head-of-research";
	if (/\bhead\b.*\boperations\b|\boperations head\b|\bhead-ops\b/.test(text)) return "head-of-operations";
	if (/\breview(?:er)?\b|\baudit\b/.test(text)) return "reviewer";
	if (/\bresearch(?:er)?\b|\binvestigat(?:e|ion)\b/.test(text)) return "researcher";
	if (/\bplan(?:ner|ning)?\b|\bdesign\b|\bscope\b|\broadmap\b/.test(text)) return "planner";
	if (/\btest(?:er|ing)?\b|\bqa\b|\bvalidate\b/.test(text)) return "tester";
	if (/\bdoer\b|\bworker\b/.test(text)) return "doer";
	if (/\bimplement\b|\bcode\b|\bfix\b|\brefactor\b|\bbuild\b/.test(text)) return "engineer";
	return undefined;
}

function inferOpenItermFromPrompt(prompt: string): boolean {
	const text = prompt.toLowerCase();
	return /\bwatch live\b|\bopen (?:an )?iterm\b|\bshow me\b|\bvisible\b|\binspect live\b|\bopen a tab\b|\bfocus that session\b|\bso i can see\b/.test(text);
}

function inferNotificationMode(parsed: ParsedArgs, currentEnv: CurrentAgentEnv): NotificationMode {
	if (hasFlag(parsed, "silent")) return "silent";
	if (hasFlag(parsed, "follow-up", "followup", "auto-follow-up")) return "notify-and-follow-up";
	if (hasFlag(parsed, "notify")) return "notify";
	return currentEnv.agentId ? "notify-and-follow-up" : "notify";
}

function buildSpawnRequest(parsed: ParsedArgs, prompt: string, ctx: ExtensionContext): SpawnRequest {
	const trimmedPrompt = prompt.trim();
	if (!trimmedPrompt) throw new Error("spawn requires a prompt");
	const currentEnv = getCurrentAgentEnv();
	return {
		agentId: getStringFlag(parsed, "agent-id"),
		cwd: getStringFlag(parsed, "cwd") ?? ctx.cwd,
		model: getStringFlag(parsed, "model") ?? formatCurrentModel(ctx) ?? DEFAULT_MODEL,
		prompt: trimmedPrompt,
		role: getStringFlag(parsed, "role") ?? inferRoleFromPrompt(trimmedPrompt),
		goal: getStringFlag(parsed, "goal") ?? summarizePrompt(trimmedPrompt),
		parentAgentId: getStringFlag(parsed, "parent"),
		rootAgentId: getStringFlag(parsed, "root"),
		openIterm: hasFlag(parsed, "headless") ? false : hasFlag(parsed, "open-iterm", "open", "watch", "live") ? true : inferOpenItermFromPrompt(trimmedPrompt),
		notificationMode: inferNotificationMode(parsed, currentEnv),
		contextBrief: getStringFlag(parsed, "context") ?? getStringFlag(parsed, "context-brief"),
	};
}

async function runCommand(command: string, args: string[], options: RunCommandOptions = {}): Promise<RunCommandResult> {
	return await new Promise<RunCommandResult>((resolve, reject) => {
		const proc = spawn(command, args, {
			cwd: options.cwd,
			stdio: ["pipe", "pipe", "pipe"],
			env: process.env,
		});

		let stdout = "";
		let stderr = "";
		let settled = false;

		const finishReject = (error: Error) => {
			if (settled) return;
			settled = true;
			reject(error);
		};

		const finishResolve = (code: number) => {
			if (settled) return;
			settled = true;
			resolve({ code, stdout, stderr });
		};

		proc.stdout.on("data", (chunk) => {
			stdout += chunk.toString();
		});
		proc.stderr.on("data", (chunk) => {
			stderr += chunk.toString();
		});
		proc.on("error", finishReject);
		proc.on("close", (code) => finishResolve(code ?? 1));

		if (options.signal) {
			const onAbort = () => {
				proc.kill("SIGTERM");
			};
			if (options.signal.aborted) onAbort();
			else options.signal.addEventListener("abort", onAbort, { once: true });
		}

		if (options.input !== undefined) proc.stdin.end(options.input);
		else proc.stdin.end();
	});
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

async function readJsonOptional<T>(filePath: string): Promise<T | undefined> {
	try {
		const content = await fs.readFile(filePath, "utf-8");
		return JSON.parse(content) as T;
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
		throw error;
	}
}

async function pathExists(filePath: string): Promise<boolean> {
	return Boolean(await fs.stat(filePath).catch(() => undefined));
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

function makeSignalName(baseName: string, success: boolean): string {
	return `${baseName}.${success ? "done" : "fail"}`;
}

async function writeSignalFile(filePath: string, fields: Record<string, unknown>, success = true): Promise<string> {
	const resolved = filePath.endsWith(".done") || filePath.endsWith(".fail") ? filePath : `${filePath}.${success ? "done" : "fail"}`;
	const lines = Object.entries(fields).map(([key, value]) => `${key}: ${String(value ?? "")}`);
	await writeTextFileAtomic(resolved, `${lines.join("\n")}\n`);
	return resolved;
}

async function ensureStateDirs(): Promise<void> {
	await fs.mkdir(runsDir, { recursive: true });
	await fs.mkdir(logsDir, { recursive: true });
}

async function readRegistry(): Promise<RegistryFile> {
	await ensureStateDirs();
	try {
		const content = await fs.readFile(registryPath, "utf-8");
		const parsed = JSON.parse(content) as Partial<RegistryFile>;
		const agents = Array.isArray(parsed.agents) ? parsed.agents : [];
		return {
			version: REGISTRY_VERSION,
			updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : nowIso(),
			agents: agents.filter(isManagedAgentRecord),
		};
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") {
			return { version: REGISTRY_VERSION, updatedAt: nowIso(), agents: [] };
		}
		throw error;
	}
}

function isManagedAgentRecord(value: unknown): value is ManagedAgentRecord {
	if (!value || typeof value !== "object") return false;
	const record = value as Partial<ManagedAgentRecord>;
	return (
		typeof record.agentId === "string" &&
		typeof record.sessionName === "string" &&
		typeof record.cwd === "string" &&
		typeof record.model === "string" &&
		typeof record.promptPreview === "string" &&
		typeof record.rootAgentId === "string" &&
		typeof record.status === "string" &&
		typeof record.visualMode === "string" &&
		typeof record.createdAt === "string" &&
		typeof record.updatedAt === "string" &&
		typeof record.openCount === "number" &&
		typeof record.runDir === "string" &&
		typeof record.launcherPath === "string" &&
		typeof record.promptPath === "string"
	);
}

async function writeRegistry(registry: RegistryFile): Promise<void> {
	await ensureStateDirs();
	registry.updatedAt = nowIso();
	await writeJsonFileAtomic(registryPath, registry);
}

async function updateRegistry(mutator: (registry: RegistryFile) => void): Promise<RegistryFile> {
	const registry = await readRegistry();
	mutator(registry);
	await writeRegistry(registry);
	return registry;
}

async function appendAuditLog(entry: Record<string, unknown>): Promise<void> {
	await ensureStateDirs();
	await fs.appendFile(messageAuditPath, `${JSON.stringify(entry)}\n`, "utf-8");
}

async function tmuxHasSession(sessionName: string): Promise<boolean> {
	const result = await runCommand("tmux", ["has-session", "-t", sessionName]);
	if (result.code === 0) return true;
	if (result.code === 1) return false;
	throw new Error(result.stderr.trim() || result.stdout.trim() || `tmux has-session failed for ${sessionName}`);
}

async function createTmuxSession(sessionName: string, cwd: string, launcherPath: string): Promise<void> {
	const result = await runCommand("tmux", ["new-session", "-d", "-s", sessionName, "-n", SESSION_WINDOW, "-c", cwd, launcherPath]);
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to create tmux session ${sessionName}`);
	}
}

async function captureTmuxPane(sessionName: string, lines = DEFAULT_CAPTURE_LINES): Promise<string> {
	const target = `${sessionName}:${SESSION_WINDOW}`;
	const result = await runCommand("tmux", ["capture-pane", "-p", "-t", target, "-S", `-${Math.max(1, lines)}`]);
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to capture tmux pane for ${sessionName}`);
	}
	return result.stdout;
}

async function killTmuxSession(sessionName: string): Promise<void> {
	const result = await runCommand("tmux", ["kill-session", "-t", sessionName]);
	if (result.code !== 0 && !(result.stderr.includes("can't find session") || result.stdout.includes("can't find session"))) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to kill tmux session ${sessionName}`);
	}
}

async function sendTmuxKeys(sessionName: string, message: string, pressEnter = true): Promise<void> {
	const target = `${sessionName}:${SESSION_WINDOW}`;
	const result = await runCommand("tmux", ["send-keys", "-t", target, "-l", message]);
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to send keys to ${sessionName}`);
	}
	if (pressEnter) {
		const enterResult = await runCommand("tmux", ["send-keys", "-t", target, "Enter"]);
		if (enterResult.code !== 0) {
			throw new Error(enterResult.stderr.trim() || enterResult.stdout.trim() || `Failed to send Enter to ${sessionName}`);
		}
	}
}

function parseManagedVisualRef(output: string): ManagedVisualRef {
	const sessionUniqueId = output.trim();
	if (!sessionUniqueId) throw new Error("Failed to capture iTerm session unique id");
	return {
		kind: "iterm-session",
		sessionUniqueId,
		openedAt: nowIso(),
	};
}

async function openItermTab(cwd: string, sessionName: string): Promise<ManagedVisualRef> {
	if (process.platform !== "darwin") {
		throw new Error("iTerm integration is only supported on macOS");
	}
	const attachCommand = `cd ${shellQuote(cwd)} && tmux attach -t ${shellQuote(sessionName)}`;
	const script = [
		"on run argv",
		"  set cmd to item 1 of argv",
		'  tell application "iTerm"',
		"    if (count of windows) = 0 then",
		"      create window with default profile",
		"    end if",
		"    tell current window",
		"      set previousTab to current tab",
		"      create tab with default profile",
		"      set newSession to current session of current tab",
		"      tell newSession",
		"        write text cmd",
		"      end tell",
		"      set newSessionId to unique id of newSession",
		"      select previousTab",
		"      return newSessionId",
		"    end tell",
		"  end tell",
		"end run",
	].join("\n");
	const result = await runCommand("osascript", ["-", attachCommand], { input: script });
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || "Failed to open iTerm tab");
	}
	return parseManagedVisualRef(result.stdout);
}

async function closeManagedVisualRef(visual: ManagedVisualRef): Promise<boolean> {
	if (process.platform !== "darwin") {
		throw new Error("iTerm integration is only supported on macOS");
	}
	const script = [
		"on run argv",
		"  set targetSessionId to item 1 of argv",
		'  tell application "iTerm"',
		"    repeat with w in windows",
		"      repeat with t in tabs of w",
		"        repeat with s in sessions of t",
		"          if unique id of s is targetSessionId then",
		"            tell s to close",
		"            return \"closed\"",
		"          end if",
		"        end repeat",
		"      end repeat",
		"    end repeat",
		"    return \"missing\"",
		"  end tell",
		"end run",
	].join("\n");
	const result = await runCommand("osascript", ["-", visual.sessionUniqueId], { input: script });
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || "Failed to close iTerm tab");
	}
	return result.stdout.trim() === "closed";
}

async function closeManagedVisualRefs(visuals: ManagedVisualRef[]): Promise<{ closedCount: number; missingCount: number }> {
	let closedCount = 0;
	let missingCount = 0;
	for (const visual of visuals) {
		const closed = await closeManagedVisualRef(visual);
		if (closed) closedCount += 1;
		else missingCount += 1;
	}
	return { closedCount, missingCount };
}

function getPiInvocation(args: string[]): { command: string; args: string[] } {
	const currentScript = process.argv[1];
	if (currentScript) {
		return { command: process.execPath, args: [currentScript, ...args] };
	}
	return { command: "pi", args };
}

function getBridgeLaunchPath(bridgeDir: string): string {
	return path.join(bridgeDir, "launch.json");
}

function getBridgeEventsPath(bridgeDir: string): string {
	return path.join(bridgeDir, "events.jsonl");
}

function getBridgeParentStatePath(bridgeDir: string): string {
	return path.join(bridgeDir, "parent", "state.json");
}

function getBridgeChildStatePath(bridgeDir: string): string {
	return path.join(bridgeDir, "child", "state.json");
}

function getBridgeSignalsDir(bridgeDir: string): string {
	return path.join(bridgeDir, ".signals");
}

async function readBridgeLaunch(bridgeDir: string): Promise<BridgeLaunchFile> {
	return await readJsonFile<BridgeLaunchFile>(getBridgeLaunchPath(bridgeDir), {
		bridgeVersion: BRIDGE_VERSION,
		launchId: "",
		bridgeDir,
		createdAt: nowIso(),
		agentId: "unknown",
		sessionName: "unknown",
		cwd: ".",
		model: DEFAULT_MODEL,
		promptPreview: "",
		parentSessionKey: "",
		notificationMode: "notify",
	});
}

async function readBridgeParentState(bridgeDir: string): Promise<BridgeParentState> {
	return await readJsonFile<BridgeParentState>(getBridgeParentStatePath(bridgeDir), { deliveredEventIds: [] });
}

async function writeBridgeParentState(bridgeDir: string, state: BridgeParentState): Promise<void> {
	state.updatedAt = nowIso();
	await writeJsonFileAtomic(getBridgeParentStatePath(bridgeDir), state);
}

async function readBridgeChildState(bridgeDir: string): Promise<BridgeChildState> {
	return await readJsonFile<BridgeChildState>(getBridgeChildStatePath(bridgeDir), { reportCount: 0 });
}

async function writeBridgeChildState(bridgeDir: string, state: BridgeChildState): Promise<void> {
	state.updatedAt = nowIso();
	await writeJsonFileAtomic(getBridgeChildStatePath(bridgeDir), state);
}

async function nextBridgeReportNumber(bridgeDir: string): Promise<number> {
	const state = await readBridgeChildState(bridgeDir);
	state.reportCount += 1;
	await writeBridgeChildState(bridgeDir, state);
	return state.reportCount;
}

function buildChildProtocol(launch: BridgeLaunchFile): string {
	const lines = [
		"You are a tmux-agent child session linked to a parent session via a private launch bridge.",
		"",
		"Your job:",
		"- Work normally on the assigned task.",
		"- Keep your final answer concise and decision-oriented.",
		"- Assume the extension will package your final answer into a bounded markdown report for the parent.",
		"",
		"When you finish a turn, prefer this response shape:",
		"## Summary",
		"**Purpose**: one sentence",
		"**Outcome**: one sentence",
		"**Key Findings**:",
		"- point 1",
		"- point 2",
		"- point 3",
		"### Next Steps",
		"- next step 1",
		"- next step 2",
		"",
		"If you need the parent to decide something BEFORE completion, call the tmux_agent tool with:",
		"- action: report_parent",
		"- reportKind: question | blocker | progress | failure",
		"- summary: short bounded summary",
		"- requiresResponse: true when the parent must answer",
		"",
		"If you are explicitly asked to participate in a peer debate, use tmux_agent with:",
		"- action: debate_send",
		"- debateId: the provided debate channel",
		"- message: short contribution",
		"- summary: optional bounded summary",
		"",
		"Do not dump raw transcripts back to the parent.",
		`Launch goal: ${launch.goal ?? launch.promptPreview}`,
		`Launch role: ${launch.role ?? "worker"}`,
	].filter(Boolean);
	return lines.join("\n");
}

async function createLaunchBridge(params: {
	agentId: string;
	sessionName: string;
	cwd: string;
	model: string;
	prompt: string;
	promptPreview: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	parentRootAgentId?: string;
	notificationMode: NotificationMode;
	contextBrief?: string;
	ctx: ExtensionContext;
}): Promise<BridgeLaunchFile> {
	const bridgeDir = await fs.mkdtemp(path.join(os.tmpdir(), "pi-tmux-agent-"));
	await fs.mkdir(path.join(bridgeDir, "parent"), { recursive: true });
	await fs.mkdir(path.join(bridgeDir, "child"), { recursive: true });
	await fs.mkdir(path.join(bridgeDir, ".signals"), { recursive: true });

	const launch: BridgeLaunchFile = {
		bridgeVersion: BRIDGE_VERSION,
		launchId: randomUUID(),
		bridgeDir,
		createdAt: nowIso(),
		agentId: params.agentId,
		sessionName: params.sessionName,
		cwd: params.cwd,
		model: params.model,
		promptPreview: params.promptPreview,
		role: params.role,
		goal: params.goal,
		parentAgentId: params.parentAgentId,
		parentRootAgentId: params.parentRootAgentId,
		parentSessionFile: params.ctx.sessionManager.getSessionFile() ?? undefined,
		parentSessionKey: getSessionKey(params.ctx),
		parentLeafId: params.ctx.sessionManager.getLeafId() ?? undefined,
		notificationMode: params.notificationMode,
		contextBrief: params.contextBrief,
	};

	await writeJsonFileAtomic(getBridgeLaunchPath(bridgeDir), launch);
	await writeJsonFileAtomic(path.join(bridgeDir, "parent", "context.json"), {
		launchPrompt: params.prompt,
		goal: params.goal,
		role: params.role,
		cwd: params.cwd,
		model: params.model,
		parentSessionFile: launch.parentSessionFile,
		parentSessionKey: launch.parentSessionKey,
		parentLeafId: launch.parentLeafId,
		parentAgentId: params.parentAgentId,
		parentRootAgentId: params.parentRootAgentId,
		contextBrief: params.contextBrief,
	});
	await writeJsonFileAtomic(getBridgeParentStatePath(bridgeDir), { deliveredEventIds: [] } satisfies BridgeParentState);
	await writeJsonFileAtomic(getBridgeChildStatePath(bridgeDir), { reportCount: 0 } satisfies BridgeChildState);
	await fs.writeFile(path.join(bridgeDir, "child", "prompt.txt"), `${params.prompt}\n`, "utf-8");
	await fs.writeFile(path.join(bridgeDir, "child", "protocol.md"), `${buildChildProtocol(launch)}\n`, "utf-8");
	await fs.writeFile(path.join(bridgeDir, ".trace"), `${randomUUID()}\n`, "utf-8");
	return launch;
}

async function appendBridgeEvent(bridgeDir: string, event: Omit<BridgeEvent, "eventId" | "timestamp">): Promise<BridgeEvent> {
	const fullEvent: BridgeEvent = {
		eventId: randomUUID(),
		timestamp: nowIso(),
		...event,
	};
	await appendJsonLine(getBridgeEventsPath(bridgeDir), fullEvent);
	return fullEvent;
}

async function writeBridgeEventSignal(bridgeDir: string, event: BridgeEvent, success = true): Promise<string> {
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

function buildBridgeSessionEntry(record: ManagedAgentRecord): SessionBridgeEntry | undefined {
	if (!record.launchId || !record.bridgeDir || !record.notificationMode) return undefined;
	return {
		launchId: record.launchId,
		bridgeDir: record.bridgeDir,
		agentId: record.agentId,
		sessionName: record.sessionName,
		createdAt: record.createdAt,
		notificationMode: record.notificationMode,
	};
}

function getRootFilePath(rootDir: string): string {
	return path.join(rootDir, "root.json");
}

function getRootSignalsDir(rootDir: string): string {
	return path.join(rootDir, ".signals");
}

function getRootAgentsDir(rootDir: string): string {
	return path.join(rootDir, "agents");
}

function getRootAgentStatePath(rootDir: string, agentId: string): string {
	return path.join(getRootAgentsDir(rootDir), `${slugify(agentId) || agentId}.json`);
}

function getRootDebatesDir(rootDir: string): string {
	return path.join(rootDir, "debates");
}

function getDebateDir(rootDir: string, debateId: string): string {
	return path.join(getRootDebatesDir(rootDir), normalizeDebateId(debateId));
}

function getDebateFilePath(rootDir: string, debateId: string): string {
	return path.join(getDebateDir(rootDir, debateId), "debate.json");
}

function getDebateEventsPath(rootDir: string, debateId: string): string {
	return path.join(getDebateDir(rootDir, debateId), "events.jsonl");
}

function getDebateSignalsDir(rootDir: string, debateId: string): string {
	return path.join(getDebateDir(rootDir, debateId), ".signals");
}

function getDebateReportsDir(rootDir: string, debateId: string): string {
	return path.join(getDebateDir(rootDir, debateId), "reports");
}

function getDebateDeliveriesDir(rootDir: string, debateId: string): string {
	return path.join(getDebateDir(rootDir, debateId), "deliveries");
}

function getDebateDeliveryStatePath(rootDir: string, debateId: string, agentId: string): string {
	return path.join(getDebateDeliveriesDir(rootDir, debateId), `${slugify(agentId) || agentId}.json`);
}

async function readRootCoordination(rootDir: string, rootAgentId?: string): Promise<RootCoordinationFile> {
	return await readJsonFile<RootCoordinationFile>(getRootFilePath(rootDir), {
		rootVersion: ROOT_VERSION,
		rootAgentId: rootAgentId ?? "unknown-root",
		rootDir,
		createdAt: nowIso(),
		updatedAt: nowIso(),
	});
}

async function ensureRootCoordination(rootAgentId: string, registry: RegistryFile, preferredRootDir?: string): Promise<string> {
	let rootDir = normalizeOptional(preferredRootDir) ?? registry.agents.find((agent) => agent.rootAgentId === rootAgentId && agent.rootDir)?.rootDir;
	if (rootDir && !(await pathExists(rootDir))) rootDir = undefined;
	if (!rootDir) {
		rootDir = await fs.mkdtemp(path.join(os.tmpdir(), `pi-tmux-root-${slugify(rootAgentId).slice(0, 12) || "root"}-`));
	}
	await fs.mkdir(getRootSignalsDir(rootDir), { recursive: true });
	await fs.mkdir(getRootAgentsDir(rootDir), { recursive: true });
	await fs.mkdir(getRootDebatesDir(rootDir), { recursive: true });
	const root = await readRootCoordination(rootDir, rootAgentId);
	root.rootVersion = ROOT_VERSION;
	root.rootAgentId = rootAgentId;
	root.rootDir = rootDir;
	root.updatedAt = nowIso();
	await writeJsonFileAtomic(getRootFilePath(rootDir), root);
	return rootDir;
}

async function readRootAgentState(rootDir: string, agentId: string): Promise<RootAgentState | undefined> {
	return await readJsonOptional<RootAgentState>(getRootAgentStatePath(rootDir, agentId));
}

async function writeRootAgentState(rootDir: string, state: RootAgentState): Promise<void> {
	state.updatedAt = nowIso();
	await writeJsonFileAtomic(getRootAgentStatePath(rootDir, state.agentId), state);
}

async function syncRootAgentState(record: ManagedAgentRecord): Promise<RootAgentState | undefined> {
	if (!record.rootDir) return undefined;
	const existing = await readRootAgentState(record.rootDir, record.agentId);
	const state: RootAgentState = {
		agentId: record.agentId,
		sessionName: record.sessionName,
		rootAgentId: record.rootAgentId,
		rootDir: record.rootDir,
		role: record.role,
		goal: record.goal,
		status: record.status,
		peerMode: existing?.peerMode ?? record.peerMode ?? "alone",
		peerParticipants: existing?.peerParticipants ?? record.peerParticipants ?? [],
		createdAt: existing?.createdAt ?? record.createdAt,
		updatedAt: nowIso(),
	};
	await writeRootAgentState(record.rootDir, state);
	return state;
}

async function updateRootAgentLifecycleState(rootDir: string | undefined, agentId: string, patch: Partial<RootAgentState>): Promise<RootAgentState | undefined> {
	if (!rootDir) return undefined;
	const existing = await readRootAgentState(rootDir, agentId);
	if (!existing) return undefined;
	const next: RootAgentState = {
		...existing,
		...patch,
		peerParticipants: patch.peerParticipants ?? existing.peerParticipants,
		peerMode: patch.peerMode ?? existing.peerMode,
		updatedAt: nowIso(),
	};
	await writeRootAgentState(rootDir, next);
	return next;
}

function resolveCanonicalAgents(registry: RegistryFile, inputs: string[]): ManagedAgentRecord[] {
	const results: ManagedAgentRecord[] = [];
	const seen = new Set<string>();
	for (const input of inputs) {
		const trimmed = input.trim();
		if (!trimmed) continue;
		const resolved = registry.agents.find((agent) => agent.agentId === trimmed || agent.sessionName === trimmed);
		if (!resolved) throw new Error(`Managed agent not found: ${trimmed}`);
		if (seen.has(resolved.agentId)) continue;
		seen.add(resolved.agentId);
		results.push(resolved);
	}
	return results;
}

function ensureSameRoot(records: ManagedAgentRecord[]): string {
	const roots = uniqueStrings(records.map((record) => record.rootAgentId));
	if (roots.length !== 1) throw new Error("Peer debate participants must belong to the same root hierarchy");
	return roots[0];
}

async function readDebate(rootDir: string, debateId: string): Promise<DebateFile | undefined> {
	return await readJsonOptional<DebateFile>(getDebateFilePath(rootDir, debateId));
}

async function writeDebate(rootDir: string, debate: DebateFile): Promise<void> {
	debate.updatedAt = nowIso();
	await fs.mkdir(getDebateSignalsDir(rootDir, debate.debateId), { recursive: true });
	await fs.mkdir(getDebateReportsDir(rootDir, debate.debateId), { recursive: true });
	await fs.mkdir(getDebateDeliveriesDir(rootDir, debate.debateId), { recursive: true });
	await writeJsonFileAtomic(getDebateFilePath(rootDir, debate.debateId), debate);
}

async function listDebates(rootDir: string): Promise<DebateFile[]> {
	const dir = getRootDebatesDir(rootDir);
	let entries: string[] = [];
	try {
		entries = await fs.readdir(dir);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
		throw error;
	}
	const debates: DebateFile[] = [];
	for (const entry of entries) {
		const debate = await readDebate(rootDir, entry);
		if (debate) debates.push(debate);
	}
	debates.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
	return debates;
}

async function readDebateEvents(rootDir: string, debateId: string): Promise<DebateEvent[]> {
	try {
		const raw = await fs.readFile(getDebateEventsPath(rootDir, debateId), "utf-8");
		return raw
			.split(/\r?\n/)
			.map((line) => line.trim())
			.filter(Boolean)
			.map((line) => JSON.parse(line) as DebateEvent)
			.sort((a, b) => a.seq - b.seq);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
		throw error;
	}
}

async function readDebateDeliveryState(rootDir: string, debateId: string, agentId: string): Promise<DebateDeliveryState> {
	return await readJsonFile<DebateDeliveryState>(getDebateDeliveryStatePath(rootDir, debateId, agentId), {
		debateId: normalizeDebateId(debateId),
		agentId,
		lastDeliveredSeq: 0,
	});
}

async function writeDebateDeliveryState(rootDir: string, debateId: string, state: DebateDeliveryState): Promise<void> {
	state.lastSeenAt = nowIso();
	await writeJsonFileAtomic(getDebateDeliveryStatePath(rootDir, debateId, state.agentId), state);
}

async function writeRootSignal(rootDir: string, baseName: string, fields: Record<string, unknown>, success = true): Promise<string> {
	return await writeSignalFile(path.join(getRootSignalsDir(rootDir), baseName), fields, success);
}

async function writeDebateSignal(rootDir: string, debateId: string, baseName: string, fields: Record<string, unknown>, success = true): Promise<string> {
	return await writeSignalFile(path.join(getDebateSignalsDir(rootDir, debateId), baseName), fields, success);
}

async function writeDebateReport(rootDir: string, debateId: string, baseName: string, markdown: string): Promise<string> {
	const reportFile = `${Date.now()}-${slugify(baseName) || "report"}.md`;
	const reportPath = path.join(getDebateReportsDir(rootDir, debateId), reportFile);
	await writeTextFileAtomic(reportPath, `${markdown.trim()}\n`);
	return reportPath;
}

async function appendDebateEvent(rootDir: string, debateId: string, event: Omit<DebateEvent, "eventId" | "seq" | "timestamp" | "debateId">): Promise<DebateEvent> {
	const debate = await readDebate(rootDir, debateId);
	if (!debate) throw new Error(`Debate not found: ${debateId}`);
	if (debate.status === "closed" && event.type !== "debate_closed") {
		throw new Error(`Debate is closed: ${debateId}`);
	}
	debate.lastSeq += 1;
	debate.updatedAt = nowIso();
	await writeDebate(rootDir, debate);
	const fullEvent: DebateEvent = {
		eventId: randomUUID(),
		seq: debate.lastSeq,
		debateId: debate.debateId,
		timestamp: nowIso(),
		...event,
	};
	await appendJsonLine(getDebateEventsPath(rootDir, debate.debateId), fullEvent);
	await writeDebateSignal(rootDir, debate.debateId, `${slugify(event.type) || "debate-event"}-${String(fullEvent.seq).padStart(6, "0")}-${fullEvent.eventId}`, {
		event_id: fullEvent.eventId,
		debate_id: debate.debateId,
		seq: fullEvent.seq,
		type: fullEvent.type,
		summary: fullEvent.summary,
		created_at: fullEvent.timestamp,
		report_path: fullEvent.reportPath ?? "",
	});
	return fullEvent;
}

async function listRelevantDebatesForAgent(rootDir: string, agentId: string): Promise<DebateFile[]> {
	const debates = await listDebates(rootDir);
	const relevant: DebateFile[] = [];
	for (const debate of debates) {
		if (!debate.participants.includes(agentId)) continue;
		if (debate.status === "open") {
			relevant.push(debate);
			continue;
		}
		const delivery = await readDebateDeliveryState(rootDir, debate.debateId, agentId);
		if (delivery.lastDeliveredSeq < debate.lastSeq) relevant.push(debate);
	}
	return relevant;
}

function isDebateEventVisibleToAgent(event: DebateEvent, debate: DebateFile, agentId: string): boolean {
	if (!debate.participants.includes(agentId)) return false;
	if (event.from.agentId === agentId) return false;
	if (event.targets.length === 0) return true;
	return event.targets.includes(agentId);
}

async function findDebateAcrossRoots(registry: RegistryFile, debateId: string): Promise<{ rootDir: string; debate: DebateFile } | undefined> {
	const normalizedDebateId = normalizeDebateId(debateId);
	for (const rootDir of uniqueStrings(registry.agents.map((agent) => agent.rootDir).filter((value): value is string => Boolean(value)))) {
		const debate = await readDebate(rootDir, normalizedDebateId);
		if (debate) return { rootDir, debate };
	}
	return undefined;
}

function getFinalAssistantMessage(messages: any[]): any | undefined {
	for (let i = messages.length - 1; i >= 0; i -= 1) {
		const message = messages[i];
		if (message?.role === "assistant") return message;
	}
	return undefined;
}

function getAssistantText(message: any): string {
	if (!message) return "";
	const content = message.content;
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content
		.filter((part) => part?.type === "text")
		.map((part) => String(part.text ?? ""))
		.join("\n")
		.trim();
}

function splitBullets(text: string, maxItems: number): string[] {
	const bulletLines = text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => /^[-*]\s+/.test(line))
		.map((line) => line.replace(/^[-*]\s+/, "").trim())
		.filter(Boolean);
	if (bulletLines.length > 0) return bulletLines.slice(0, maxItems);
	const sentences = text
		.replace(/\r?\n+/g, " ")
		.split(/(?<=[.!?])\s+/)
		.map((sentence) => sentence.trim())
		.filter(Boolean);
	return sentences.slice(0, maxItems).map((sentence) => truncate(sentence, 160));
}

function extractNextSteps(text: string): string[] {
	const lines = text.split(/\r?\n/);
	const start = lines.findIndex((line) => /^#{2,3}\s+next steps/i.test(line.trim()) || /^next steps:?$/i.test(line.trim()));
	if (start === -1) return [];
	const results: string[] = [];
	for (let i = start + 1; i < lines.length; i += 1) {
		const line = lines[i].trim();
		if (!line) continue;
		if (/^#{1,6}\s+/.test(line)) break;
		if (/^[-*]\s+/.test(line)) {
			results.push(line.replace(/^[-*]\s+/, "").trim());
			if (results.length >= 4) break;
		}
	}
	return results;
}

function buildAutoReportMarkdown(params: {
	launch: BridgeLaunchFile;
	kind: "completion" | "failure";
	assistantText: string;
	errorMessage?: string;
}): string {
	const body = params.assistantText.trim() || (params.errorMessage ? `Error: ${params.errorMessage}` : "No assistant text returned.");
	const findings = splitBullets(body, 5);
	const nextSteps = extractNextSteps(body);
	const purpose = params.launch.goal ?? params.launch.promptPreview;
	const outcome =
		params.kind === "failure"
			? truncate(params.errorMessage ?? "The child turn failed or stopped unexpectedly.", 160)
			: "Completed the requested child turn.";
	const next = nextSteps.length > 0 ? nextSteps : ["Review the details and decide whether follow-up instructions are needed."];
	const artifacts = [path.join(params.launch.bridgeDir, "child")];

	return [
		`# ${params.launch.role ? `${params.launch.role} report` : "tmux-agent report"}`,
		"",
		"## Table of Contents",
		"- [Executive Summary](#executive-summary)",
		"- [Details](#details)",
		"- [Artifacts](#artifacts)",
		"",
		"## Executive Summary",
		"",
		`**Purpose**: ${purpose}`,
		`**Outcome**: ${outcome}`,
		"**Key Findings**:",
		...(findings.length > 0 ? findings.map((item) => `- ${item}`) : ["- No key findings recorded."]),
		"",
		"### Next Steps",
		...next.map((item) => `- ${item}`),
		"",
		"---",
		"",
		"## Details",
		"",
		body,
		"",
		"## Artifacts",
		...artifacts.map((item) => `- ${item}`),
	].join("\n");
}

async function writeBridgeReport(bridgeDir: string, baseName: string, markdown: string): Promise<{ reportPath: string; reportNumber: number }> {
	const reportNumber = await nextBridgeReportNumber(bridgeDir);
	const reportFile = `${String(reportNumber).padStart(4, "0")}-${slugify(baseName) || "report"}.md`;
	const reportPath = path.join(bridgeDir, "child", reportFile);
	await writeTextFileAtomic(reportPath, `${markdown.trim()}\n`);
	return { reportPath, reportNumber };
}

async function writeBridgeLatestTerminalReport(bridgeDir: string, kind: "completion" | "failure", markdown: string): Promise<string> {
	const reportPath = path.join(bridgeDir, "child", `latest-${kind}.md`);
	await writeTextFileAtomic(reportPath, `${markdown.trim()}\n`);
	return reportPath;
}

function extractHeaders(content: string): string[] {
	const headers: string[] = [];
	for (const line of content.split(/\r?\n/)) {
		const match = line.match(/^(#{1,6})\s+(.+)$/);
		if (!match) continue;
		const indent = "  ".repeat(Math.max(0, match[1].length - 1));
		headers.push(`${indent}- ${match[2].trim()}`);
	}
	return headers;
}

function extractExecutiveSummary(content: string, maxBytes = DEFAULT_REPORT_BYTES): string {
	const lines = content.split(/\r?\n/);
	let start = -1;
	let end = lines.length;
	for (let i = 0; i < lines.length; i += 1) {
		if (/^##\s+Executive Summary/i.test(lines[i])) {
			start = i + 1;
			continue;
		}
		if (start >= 0 && (/^##\s+/.test(lines[i]) || lines[i].trim() === "---")) {
			end = i;
			break;
		}
	}
	if (start === -1) return "No Executive Summary section found";
	const section = lines.slice(start, end).join("\n").trim();
	return Buffer.from(section).byteLength > maxBytes ? Buffer.from(section).subarray(0, maxBytes).toString("utf-8") : section;
}

async function readBoundedReportSummary(reportPath: string, maxBytes = DEFAULT_REPORT_BYTES): Promise<string> {
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

async function writeLauncherFiles(params: {
	agentId: string;
	sessionName: string;
	cwd: string;
	model: string;
	prompt: string;
	role?: string;
	goal?: string;
	parentAgentId?: string;
	rootAgentId: string;
	rootDir: string;
	bridge: BridgeLaunchFile;
}): Promise<{ runDir: string; launcherPath: string; promptPath: string }> {
	await ensureStateDirs();
	const runDir = path.join(runsDir, params.agentId);
	await fs.mkdir(runDir, { recursive: true });
	const promptPath = path.join(runDir, "prompt.txt");
	const launcherPath = path.join(runDir, "launch.sh");
	await fs.writeFile(promptPath, `${params.prompt}\n`, "utf-8");

	const invocation = getPiInvocation(["--model", params.model]);
	const shellArray = [shellQuote(invocation.command), ...invocation.args.map(shellQuote)].join(" ");
	const script = `#!/usr/bin/env bash
set -uo pipefail
export ${ENV_AGENT_ID}=${shellQuote(params.agentId)}
export ${ENV_PARENT_AGENT_ID}=${shellQuote(params.parentAgentId ?? "")}
export ${ENV_ROOT_AGENT_ID}=${shellQuote(params.rootAgentId)}
export ${ENV_ROLE}=${shellQuote(params.role ?? "")}
export ${ENV_GOAL}=${shellQuote(params.goal ?? "")}
export ${ENV_BRIDGE_DIR}=${shellQuote(params.bridge.bridgeDir)}
export ${ENV_LAUNCH_ID}=${shellQuote(params.bridge.launchId)}
export ${ENV_PARENT_SESSION_FILE}=${shellQuote(params.bridge.parentSessionFile ?? "")}
export ${ENV_PARENT_SESSION_KEY}=${shellQuote(params.bridge.parentSessionKey)}
export ${ENV_PARENT_LEAF_ID}=${shellQuote(params.bridge.parentLeafId ?? "")}
export ${ENV_NOTIFICATION_MODE}=${shellQuote(params.bridge.notificationMode)}
export ${ENV_CONTEXT_BRIEF}=${shellQuote(params.bridge.contextBrief ?? "")}
export ${ENV_ROOT_DIR}=${shellQuote(params.rootDir)}
cd ${shellQuote(params.cwd)}
clear
printf 'Starting tmux agent %s\\nWorking dir: %s\\nModel: %s\\nBridge: %s\\n\\n' ${shellQuote(params.agentId)} ${shellQuote(params.cwd)} ${shellQuote(params.model)} ${shellQuote(params.bridge.launchId)}
PROMPT=$(cat ${shellQuote(promptPath)})
PI_CMD=(${shellArray})
"\${PI_CMD[@]}" "$PROMPT"
status=$?
printf '\\n[pi exited with status %s]\\n' "$status"
exec "\${SHELL:-/bin/bash}"
`;
	await fs.writeFile(launcherPath, script, { encoding: "utf-8", mode: 0o755 });
	await fs.chmod(launcherPath, 0o755);
	return { runDir, launcherPath, promptPath };
}

function buildAgentId(seed?: string, fallback?: string, attempt = 0): string {
	const primary = (slugify(seed || "") || slugify(fallback || "") || "agent").slice(0, 18) || "agent";
	const now = new Date();
	const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
	const suffix = attempt > 0 ? `-${attempt}` : "";
	return `${primary}-${timestamp}${suffix}`;
}

function buildSessionName(agentId: string): string {
	return truncate(`pi-${slugify(agentId) || "agent"}`, 48).replace(/\.+$/, "");
}

function resolveTargetFromInput(registry: RegistryFile, input: string | undefined, currentEnv: CurrentAgentEnv): ManagedAgentRecord | undefined {
	const trimmed = input?.trim();
	if (trimmed === "last" || !trimmed) {
		if (!trimmed && currentEnv.agentId) {
			const current = registry.agents.find((agent) => agent.agentId === currentEnv.agentId);
			if (current) return current;
		}
		return [...registry.agents].sort((a, b) => (b.updatedAt || b.createdAt).localeCompare(a.updatedAt || a.createdAt))[0];
	}
	return registry.agents.find((agent) => agent.agentId === trimmed || agent.sessionName === trimmed || agent.launchId === trimmed);
}

async function resolveStatuses(registry: RegistryFile): Promise<ResolvedStatus[]> {
	const results: ResolvedStatus[] = [];
	for (const record of registry.agents) {
		const hasSession = await tmuxHasSession(record.sessionName).catch(() => false);
		let effectiveStatus = record.status;
		if (record.status === "terminated") effectiveStatus = "terminated";
		else if (!hasSession) effectiveStatus = "missing";
		results.push({ record, hasSession, effectiveStatus });
	}
	return results;
}

function formatAgentSummary(status: ResolvedStatus): string {
	const parts = [
		status.record.agentId,
		`[${status.effectiveStatus}]`,
		status.record.role ? `role=${status.record.role}` : undefined,
		status.record.goal ? `goal=${truncate(status.record.goal, 60)}` : undefined,
		status.record.model,
	];
	return parts.filter(Boolean).join(" | ");
}

function formatAgentDetails(status: ResolvedStatus): string[] {
	return [
		`agentId: ${status.record.agentId}`,
		`sessionName: ${status.record.sessionName}`,
		`status: ${status.effectiveStatus}`,
		`cwd: ${status.record.cwd}`,
		`model: ${status.record.model}`,
		status.record.role ? `role: ${status.record.role}` : undefined,
		status.record.goal ? `goal: ${status.record.goal}` : undefined,
		status.record.parentAgentId ? `parent: ${status.record.parentAgentId}` : undefined,
		`root: ${status.record.rootAgentId}`,
		status.record.rootDir ? `rootDir: ${status.record.rootDir}` : undefined,
		status.record.peerMode ? `peerMode: ${status.record.peerMode}` : undefined,
		status.record.peerParticipants && status.record.peerParticipants.length > 0 ? `peerParticipants: ${status.record.peerParticipants.join(", ")}` : undefined,
		`visualMode: ${status.record.visualMode}`,
		`openCount: ${status.record.openCount}`,
		status.record.managedVisuals ? `managedVisuals: ${status.record.managedVisuals.length}` : undefined,
		status.record.launchId ? `launchId: ${status.record.launchId}` : undefined,
		status.record.bridgeDir ? `bridgeDir: ${status.record.bridgeDir}` : undefined,
		status.record.notificationMode ? `notificationMode: ${status.record.notificationMode}` : undefined,
		status.record.parentSessionFile ? `parentSessionFile: ${status.record.parentSessionFile}` : undefined,
		status.record.parentLeafId ? `parentLeafId: ${status.record.parentLeafId}` : undefined,
		`createdAt: ${status.record.createdAt}`,
		status.record.lastOpenedAt ? `lastOpenedAt: ${status.record.lastOpenedAt}` : undefined,
		status.record.lastMessageAt ? `lastMessageAt: ${status.record.lastMessageAt}` : undefined,
		status.record.lastSeenAt ? `lastSeenAt: ${status.record.lastSeenAt}` : undefined,
	].filter((line): line is string => Boolean(line));
}

function buildTreeLines(registry: RegistryFile, statuses: ResolvedStatus[]): string[] {
	const byId = new Map(registry.agents.map((agent) => [agent.agentId, agent]));
	const statusById = new Map(statuses.map((item) => [item.record.agentId, item]));
	const children = new Map<string, ManagedAgentRecord[]>();
	for (const agent of registry.agents) {
		if (!agent.parentAgentId) continue;
		const bucket = children.get(agent.parentAgentId) ?? [];
		bucket.push(agent);
		children.set(agent.parentAgentId, bucket);
	}
	const roots = registry.agents.filter((agent) => !agent.parentAgentId || !byId.has(agent.parentAgentId));
	roots.sort((a, b) => a.createdAt.localeCompare(b.createdAt));

	const lines: string[] = [];
	const visit = (agent: ManagedAgentRecord, depth: number) => {
		const status = statusById.get(agent.agentId);
		const marker = depth === 0 ? "" : `${"  ".repeat(Math.max(0, depth - 1))}└─ `;
		lines.push(`${marker}${agent.agentId} [${status?.effectiveStatus ?? agent.status}]${agent.role ? ` role=${agent.role}` : ""}${agent.goal ? ` goal=${truncate(agent.goal, 50)}` : ""}`);
		const childAgents = children.get(agent.agentId) ?? [];
		childAgents.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
		for (const child of childAgents) visit(child, depth + 1);
	};

	for (const root of roots) visit(root, 0);
	if (lines.length === 0) lines.push("No managed agents recorded.");
	return lines;
}

async function uniqueAgentIdentity(registry: RegistryFile, preferredAgentId: string | undefined, preferredSeed: string | undefined): Promise<{ agentId: string; sessionName: string }> {
	const explicit = normalizeOptional(preferredAgentId);
	if (explicit) {
		const normalized = slugify(explicit);
		if (!normalized) throw new Error("Invalid --agent-id. Use letters, numbers, and hyphens.");
		if (registry.agents.some((agent) => agent.agentId === normalized)) {
			throw new Error(`Agent ID already exists: ${normalized}`);
		}
		const sessionName = buildSessionName(normalized);
		if (await tmuxHasSession(sessionName)) {
			throw new Error(`tmux session already exists for ${normalized}: ${sessionName}`);
		}
		return { agentId: normalized, sessionName };
	}

	let attempt = 0;
	while (attempt < 50) {
		const agentId = buildAgentId(preferredSeed, preferredSeed, attempt);
		const sessionName = buildSessionName(agentId);
		const registryConflict = registry.agents.some((agent) => agent.agentId === agentId || agent.sessionName === sessionName);
		const tmuxConflict = await tmuxHasSession(sessionName).catch(() => false);
		if (!registryConflict && !tmuxConflict) return { agentId, sessionName };
		attempt += 1;
	}
	throw new Error("Failed to allocate a unique agent ID and tmux session name");
}

async function ensureDirectoryExists(targetCwd: string): Promise<void> {
	const resolved = path.resolve(targetCwd);
	const stat = await fs.stat(resolved).catch(() => undefined);
	if (!stat || !stat.isDirectory()) {
		throw new Error(`Directory not found: ${resolved}`);
	}
}

async function spawnManagedAgent(request: SpawnRequest, ctx: ExtensionContext): Promise<ManagedAgentRecord> {
	const prompt = request.prompt.trim();
	if (!prompt) throw new Error("A non-empty prompt is required to spawn a tmux agent");

	const cwd = path.resolve(request.cwd ?? ctx.cwd);
	await ensureDirectoryExists(cwd);
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const role = normalizeOptional(request.role) ?? inferRoleFromPrompt(prompt);
	const goal = normalizeOptional(request.goal) ?? summarizePrompt(prompt);
	const openIterm = request.openIterm ?? inferOpenItermFromPrompt(prompt);
	const notificationMode = request.notificationMode ?? (currentEnv.agentId ? "notify-and-follow-up" : "notify");
	const contextBrief = normalizeOptional(request.contextBrief);
	const createdByAgentId = currentEnv.agentId;
	const parentAgentId = normalizeOptional(request.parentAgentId) ?? currentEnv.agentId;
	let rootAgentId = normalizeOptional(request.rootAgentId);
	let rootDir = normalizeOptional(request.rootDir) ?? currentEnv.rootDir;
	if (!rootAgentId && parentAgentId) {
		const parent = registry.agents.find((agent) => agent.agentId === parentAgentId);
		rootAgentId = parent?.rootAgentId ?? parentAgentId;
		rootDir ??= parent?.rootDir;
	}
	rootAgentId ??= currentEnv.rootAgentId ?? currentEnv.agentId;

	const identitySeed = role ?? goal ?? prompt;
	const { agentId, sessionName } = await uniqueAgentIdentity(registry, request.agentId, identitySeed);
	rootAgentId ??= agentId;
	rootDir = await ensureRootCoordination(rootAgentId, registry, rootDir);
	const model = normalizeOptional(request.model) ?? formatCurrentModel(ctx) ?? DEFAULT_MODEL;
	const promptPreview = summarizePrompt(prompt);
	const bridge = await createLaunchBridge({
		agentId,
		sessionName,
		cwd,
		model,
		prompt,
		promptPreview,
		role,
		goal,
		parentAgentId,
		parentRootAgentId: rootAgentId,
		notificationMode,
		contextBrief,
		ctx,
	});
	const launcherFiles = await writeLauncherFiles({
		agentId,
		sessionName,
		cwd,
		model,
		prompt,
		role,
		goal,
		parentAgentId,
		rootAgentId,
		rootDir,
		bridge,
	});

	await appendBridgeEvent(bridge.bridgeDir, {
		launchId: bridge.launchId,
		direction: "parent_to_child",
		type: "instruction",
		from: {
			agentId: currentEnv.agentId ?? "human",
			sessionFile: ctx.sessionManager.getSessionFile() ?? undefined,
		},
		to: {
			agentId,
			sessionName,
		},
		message: prompt,
		summary: promptPreview,
	});

	await createTmuxSession(sessionName, cwd, launcherFiles.launcherPath);

	const createdAt = nowIso();
	const record: ManagedAgentRecord = {
		agentId,
		sessionName,
		cwd,
		model,
		promptPreview,
		role,
		goal,
		parentAgentId,
		rootAgentId,
		createdByAgentId,
		status: "running",
		visualMode: "headless",
		createdAt,
		updatedAt: createdAt,
		openCount: 0,
		runDir: launcherFiles.runDir,
		launcherPath: launcherFiles.launcherPath,
		promptPath: launcherFiles.promptPath,
		launchId: bridge.launchId,
		bridgeDir: bridge.bridgeDir,
		parentSessionFile: bridge.parentSessionFile,
		parentSessionKey: bridge.parentSessionKey,
		parentLeafId: bridge.parentLeafId,
		notificationMode,
		contextBrief,
		rootDir,
		peerMode: "alone",
		peerParticipants: [],
	};

	await updateRegistry((next) => {
		next.agents.push(record);
	});
	await syncRootAgentState(record);

	if (openIterm) {
		const visual = await openItermTab(cwd, sessionName);
		const openedAt = visual.openedAt;
		record.visualMode = "iterm-opened";
		record.managedVisuals = [visual];
		record.openCount = record.managedVisuals.length;
		record.lastOpenedAt = openedAt;
		record.updatedAt = openedAt;
		await updateRegistry((next) => {
			const found = next.agents.find((entry) => entry.agentId === record.agentId);
			if (found) {
				found.visualMode = "iterm-opened";
				found.managedVisuals = [visual];
				found.openCount = found.managedVisuals.length;
				found.lastOpenedAt = openedAt;
				found.updatedAt = openedAt;
			}
		});
	}

	await appendAuditLog({
		timestamp: nowIso(),
		event: "spawn",
		agentId,
		sessionName,
		cwd,
		model,
		role,
		goal,
		parentAgentId,
		rootAgentId,
		createdByAgentId,
		openIterm,
		launchId: bridge.launchId,
		bridgeDir: bridge.bridgeDir,
		notificationMode,
		rootDir,
	});

	return record;
}

async function openManagedAgent(target: string | undefined): Promise<ManagedAgentRecord> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	const hasSession = await tmuxHasSession(agent.sessionName).catch(() => false);
	if (!hasSession) {
		await updateRegistry((next) => {
			const found = next.agents.find((entry) => entry.agentId === agent.agentId);
			if (found) {
				found.status = found.status === "terminated" ? "terminated" : "missing";
				found.updatedAt = nowIso();
			}
		});
		throw new Error(`tmux session is not running for ${agent.agentId}`);
	}
	const visual = await openItermTab(agent.cwd, agent.sessionName);
	await updateRegistry((next) => {
		const found = next.agents.find((entry) => entry.agentId === agent.agentId);
		if (found) {
			const openedAt = visual.openedAt;
			found.lastOpenedAt = openedAt;
			found.updatedAt = openedAt;
			found.visualMode = "iterm-opened";
			found.managedVisuals = [...(found.managedVisuals ?? []), visual];
			found.openCount = found.managedVisuals.length;
		}
	});
	await appendAuditLog({ timestamp: nowIso(), event: "open_visual", agentId: agent.agentId, sessionName: agent.sessionName });
	return agent;
}

async function listManagedAgents(includeExited = true): Promise<ResolvedStatus[]> {
	const registry = await readRegistry();
	const statuses = await resolveStatuses(registry);
	statuses.sort((a, b) => (b.record.updatedAt || b.record.createdAt).localeCompare(a.record.updatedAt || a.record.createdAt));
	if (includeExited) return statuses;
	return statuses.filter((status) => status.effectiveStatus === "running");
}

async function statusManagedAgent(target: string | undefined, lines = 40): Promise<{ status: ResolvedStatus; capture?: string }> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	const statuses = await resolveStatuses(registry);
	const status = statuses.find((entry) => entry.record.agentId === agent.agentId);
	if (!status) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	let capture: string | undefined;
	if (status.hasSession) {
		capture = await captureTmuxPane(status.record.sessionName, lines).catch(() => undefined);
	}
	return { status, capture };
}

async function captureManagedAgent(target: string | undefined, lines = DEFAULT_CAPTURE_LINES): Promise<{ status: ResolvedStatus; capture: string }> {
	const result = await statusManagedAgent(target, lines);
	if (!result.capture) throw new Error(`No tmux pane capture available for ${target ?? "(current)"}`);
	return { status: result.status, capture: result.capture };
}

async function closeManagedAgentVisual(target: string | undefined): Promise<{ agent: ManagedAgentRecord; closedCount: number; missingCount: number }> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	const visuals = agent.managedVisuals ?? [];
	const { closedCount, missingCount } = await closeManagedVisualRefs(visuals);
	const closedAt = nowIso();
	await updateRegistry((next) => {
		const found = next.agents.find((entry) => entry.agentId === agent.agentId);
		if (found) {
			found.managedVisuals = [];
			found.visualMode = "headless";
			found.openCount = 0;
			found.lastClosedAt = closedAt;
			found.updatedAt = closedAt;
		}
	});
	await appendAuditLog({ timestamp: closedAt, event: "close_visual", agentId: agent.agentId, sessionName: agent.sessionName, closedCount, missingCount });
	return { agent, closedCount, missingCount };
}

async function killManagedAgent(target: string | undefined): Promise<ManagedAgentRecord> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${target ?? "(none)"}`);
	if ((agent.managedVisuals ?? []).length > 0) {
		await closeManagedVisualRefs(agent.managedVisuals ?? []);
	}
	const hasSession = await tmuxHasSession(agent.sessionName).catch(() => false);
	if (hasSession) {
		await killTmuxSession(agent.sessionName);
	}
	await updateRegistry((next) => {
		const found = next.agents.find((entry) => entry.agentId === agent.agentId);
		if (found) {
			const terminatedAt = nowIso();
			found.status = "terminated";
			found.terminatedAt = terminatedAt;
			found.updatedAt = terminatedAt;
			found.managedVisuals = [];
			found.visualMode = "headless";
			found.openCount = 0;
			found.lastClosedAt = terminatedAt;
		}
	});
	await updateRootAgentLifecycleState(agent.rootDir, agent.agentId, { status: "terminated" });
	await appendAuditLog({ timestamp: nowIso(), event: "kill", agentId: agent.agentId, sessionName: agent.sessionName, launchId: agent.launchId });
	return agent;
}

function formatRoutedMessage(message: string, senderAgentId: string): string {
	return [
		"[tmux-agent message]",
		`From: ${senderAgentId}`,
		"",
		message.trim(),
	].join("\n");
}

async function sendManagedMessage(request: SendMessageRequest): Promise<ManagedAgentRecord> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, request.target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${request.target}`);
	const hasSession = await tmuxHasSession(agent.sessionName).catch(() => false);
	if (!hasSession) throw new Error(`tmux session is not running for ${agent.agentId}`);
	const senderAgentId = normalizeOptional(request.senderAgentId) ?? currentEnv.agentId ?? "human";
	const routed = formatRoutedMessage(request.message, senderAgentId);
	await sendTmuxKeys(agent.sessionName, routed, true);
	await updateRegistry((next) => {
		const found = next.agents.find((entry) => entry.agentId === agent.agentId);
		if (found) {
			found.lastMessageAt = nowIso();
			found.updatedAt = found.lastMessageAt;
		}
	});
	if (agent.bridgeDir && agent.launchId) {
		await appendBridgeEvent(agent.bridgeDir, {
			launchId: agent.launchId,
			direction: "parent_to_child",
			type: currentEnv.agentId ? "instruction" : "answer",
			from: { agentId: senderAgentId, sessionFile: currentEnv.parentSessionFile ?? undefined },
			to: { agentId: agent.agentId, sessionName: agent.sessionName },
			message: request.message,
			summary: truncate(request.message, 160),
		});
	}
	await appendAuditLog({
		timestamp: nowIso(),
		event: "send_message",
		senderAgentId,
		targetAgentId: agent.agentId,
		sessionName: agent.sessionName,
		message: request.message,
		launchId: agent.launchId,
	});
	return agent;
}

async function reportParent(request: ReportParentRequest): Promise<{ bridgeDir: string; event: BridgeEvent }> {
	const currentEnv = getCurrentAgentEnv();
	if (!currentEnv.bridgeDir || !currentEnv.launchId || !currentEnv.agentId) {
		throw new Error("report_parent requires a tmux-agent child launch bridge");
	}
	const launch = await readBridgeLaunch(currentEnv.bridgeDir);
	let reportPath: string | undefined;
	if (request.reportMarkdown?.trim()) {
		const report = await writeBridgeReport(currentEnv.bridgeDir, request.kind, request.reportMarkdown);
		reportPath = report.reportPath;
	}
	const event = await appendBridgeEvent(currentEnv.bridgeDir, {
		launchId: currentEnv.launchId,
		direction: "child_to_parent",
		type: request.kind,
		from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
		summary: truncate(request.summary, 240),
		requiresResponse: request.requiresResponse ?? request.kind !== "progress",
		reportPath,
	});
	const signalPath = await writeBridgeEventSignal(currentEnv.bridgeDir, event, request.kind !== "failure");
	if (reportPath) {
		event.reportPath = reportPath;
		event.signalPath = signalPath;
	}
	await appendAuditLog({
		timestamp: nowIso(),
		event: "report_parent",
		launchId: currentEnv.launchId,
		bridgeDir: currentEnv.bridgeDir,
		agentId: currentEnv.agentId,
		kind: request.kind,
		summary: request.summary,
	});
	return { bridgeDir: currentEnv.bridgeDir, event };
}

async function resolveDebateRootContext(registry: RegistryFile, debateId: string | undefined, rootAgentId: string | undefined, currentEnv: CurrentAgentEnv, participantInputs: string[] = []): Promise<{ rootAgentId: string; rootDir: string }> {
	const explicitRootAgentId = normalizeOptional(rootAgentId);
	const normalizedRootAgentId = explicitRootAgentId ?? currentEnv.rootAgentId;
	const normalizedRootDir = currentEnv.rootDir;
	if (debateId && !explicitRootAgentId) {
		const located = await findDebateAcrossRoots(registry, debateId);
		if (located) return { rootAgentId: located.debate.rootAgentId, rootDir: located.rootDir };
	}
	if (normalizedRootAgentId && normalizedRootDir && (!explicitRootAgentId || explicitRootAgentId === currentEnv.rootAgentId)) {
		return { rootAgentId: normalizedRootAgentId, rootDir: normalizedRootDir };
	}
	if (participantInputs.length > 0) {
		const participants = resolveCanonicalAgents(registry, participantInputs);
		const participantRootAgentId = ensureSameRoot(participants);
		const rootDir = await ensureRootCoordination(participantRootAgentId, registry, participants.find((item) => item.rootDir)?.rootDir);
		return { rootAgentId: participantRootAgentId, rootDir };
	}
	if (normalizedRootAgentId) {
		const preferredRootDir = explicitRootAgentId && explicitRootAgentId !== currentEnv.rootAgentId ? undefined : normalizedRootDir;
		const rootDir = await ensureRootCoordination(normalizedRootAgentId, registry, preferredRootDir);
		return { rootAgentId: normalizedRootAgentId, rootDir };
	}
	throw new Error("Could not determine the root hierarchy. Provide rootAgentId, run inside a tmux-agent hierarchy, or specify participants from one root.");
}

async function startDebateChannel(request: DebateStartRequest): Promise<DebateFile> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const requestedParticipants = parseParticipantValues(request.participants);
	const { rootAgentId, rootDir } = await resolveDebateRootContext(registry, request.debateId, request.rootAgentId, currentEnv, requestedParticipants);
	const createdBy = normalizeOptional(request.createdBy) ?? currentEnv.agentId ?? "human";
	const mode = request.mode ?? (requestedParticipants.length > 0 ? "subset" : "all");
	const statuses = await resolveStatuses(registry);
	const currentAgentRecord = createdBy === "human" ? undefined : registry.agents.find((agent) => agent.agentId === createdBy && agent.rootAgentId === rootAgentId);

	let participantRecords: ManagedAgentRecord[] = [];
	let participants: string[] = [];
	if (mode === "all") {
		participantRecords = statuses
			.filter((status) => status.hasSession && status.record.rootAgentId === rootAgentId)
			.map((status) => status.record);
		participants = participantRecords.map((record) => record.agentId);
	} else if (mode === "subset" || mode === "direct") {
		if (requestedParticipants.length === 0) throw new Error(`${mode} debate requires --participants`);
		participantRecords = resolveCanonicalAgents(registry, requestedParticipants);
		if (ensureSameRoot(participantRecords) !== rootAgentId) {
			throw new Error("Debate participants must belong to the requested root hierarchy");
		}
		participants = participantRecords.map((record) => record.agentId);
	} else {
		participants = createdBy === "human" ? [] : [createdBy];
	}

	if (currentAgentRecord) participants = uniqueStrings([currentAgentRecord.agentId, ...participants]);
	const debateId = normalizeDebateId(request.debateId, request.topic ?? `${mode}-${createdBy}`);
	const existing = await readDebate(rootDir, debateId);
	if (existing && existing.status === "open") throw new Error(`Debate already exists: ${debateId}`);
	const debate: DebateFile = {
		debateId,
		rootAgentId,
		rootDir,
		createdBy,
		createdAt: nowIso(),
		updatedAt: nowIso(),
		mode,
		participants: uniqueStrings(participants),
		participantSessionNames: uniqueStrings(participantRecords.map((record) => record.sessionName)),
		mirrorToParent: request.mirrorToParent ?? "summary-only",
		status: "open",
		topic: normalizeOptional(request.topic),
		lastSeq: 0,
	};
	await writeDebate(rootDir, debate);
	await writeRootSignal(rootDir, `debate-${debate.debateId}-open`, {
		debate_id: debate.debateId,
		root_agent_id: rootAgentId,
		created_by: createdBy,
		created_at: debate.createdAt,
		mode,
		participants: debate.participants.join(","),
	});
	await appendAuditLog({
		timestamp: nowIso(),
		event: "debate_start",
		debateId: debate.debateId,
		rootAgentId,
		rootDir,
		createdBy,
		mode,
		participants: debate.participants,
		topic: debate.topic,
	});
	return debate;
}

async function sendDebateMessage(request: DebateSendRequest): Promise<{ debate: DebateFile; event: DebateEvent }> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const message = request.message.trim();
	if (!message) throw new Error("debate_send requires a non-empty message");
	const { rootDir } = await resolveDebateRootContext(registry, request.debateId, request.rootAgentId, currentEnv);
	const debate = await readDebate(rootDir, request.debateId);
	if (!debate) throw new Error(`Debate not found: ${request.debateId}`);
	if (debate.status !== "open") throw new Error(`Debate is closed: ${debate.debateId}`);
	const senderAgentId = normalizeOptional(request.senderAgentId) ?? currentEnv.agentId ?? "human";
	if (senderAgentId !== "human" && !debate.participants.includes(senderAgentId)) {
		throw new Error(`Sender ${senderAgentId} is not a participant in debate ${debate.debateId}`);
	}
	const explicitTargets = parseParticipantValues(request.participants);
	let targets = explicitTargets.length > 0 ? resolveCanonicalAgents(registry, explicitTargets).map((record) => record.agentId) : debate.participants.filter((agentId) => agentId !== senderAgentId);
	if (targets.length > 0) {
		const participantSet = new Set(debate.participants);
		targets = uniqueStrings(targets.filter((agentId) => participantSet.has(agentId) && agentId !== senderAgentId));
	}
	if (debate.mode === "alone") targets = [];
	let reportPath: string | undefined;
	if (request.reportMarkdown?.trim()) {
		reportPath = await writeDebateReport(rootDir, debate.debateId, `${senderAgentId}-${debate.debateId}`, request.reportMarkdown);
	}
	const event = await appendDebateEvent(rootDir, debate.debateId, {
		direction: "peer_to_peer",
		type: reportPath ? "debate_summary" : "debate_message",
		from: { agentId: senderAgentId },
		scope: debate.mode,
		targets,
		summary: inferDebateSummary(message, request.summary),
		message,
		requiresResponse: request.requiresResponse,
		reportPath,
	});
	await appendAuditLog({
		timestamp: nowIso(),
		event: "debate_send",
		debateId: debate.debateId,
		rootAgentId: debate.rootAgentId,
		senderAgentId,
		targets,
		requiresResponse: request.requiresResponse ?? false,
		reportPath,
	});
	return { debate, event };
}

async function closeDebateChannel(request: DebateCloseRequest): Promise<{ debate: DebateFile; summaryEvent?: DebateEvent; closeEvent: DebateEvent }> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const { rootDir } = await resolveDebateRootContext(registry, request.debateId, request.rootAgentId, currentEnv);
	const debate = await readDebate(rootDir, request.debateId);
	if (!debate) throw new Error(`Debate not found: ${request.debateId}`);
	if (debate.status === "closed") throw new Error(`Debate already closed: ${debate.debateId}`);
	const closedBy = normalizeOptional(request.closedBy) ?? currentEnv.agentId ?? "human";
	let summaryEvent: DebateEvent | undefined;
	let reportPath: string | undefined;
	if (request.reportMarkdown?.trim()) {
		reportPath = await writeDebateReport(rootDir, debate.debateId, `${closedBy}-closeout`, request.reportMarkdown);
	}
	if (request.summary?.trim() || reportPath) {
		summaryEvent = await appendDebateEvent(rootDir, debate.debateId, {
			direction: "peer_to_peer",
			type: "debate_summary",
			from: { agentId: closedBy },
			scope: debate.mode,
			targets: debate.participants.filter((agentId) => agentId !== closedBy),
			summary: inferDebateSummary(request.summary ?? "Debate summary", request.summary),
			message: request.summary,
			requiresResponse: false,
			reportPath,
		});
	}
	const closeEvent = await appendDebateEvent(rootDir, debate.debateId, {
		direction: "peer_to_peer",
		type: "debate_closed",
		from: { agentId: closedBy },
		scope: debate.mode,
		targets: [],
		summary: truncate(request.summary?.trim() || `Debate ${debate.debateId} closed`, 500),
		requiresResponse: false,
		reportPath,
	});
	debate.status = "closed";
	await writeDebate(rootDir, debate);
	await writeDebateSignal(rootDir, debate.debateId, "closed", {
		debate_id: debate.debateId,
		closed_by: closedBy,
		closed_at: nowIso(),
		summary: request.summary ?? "",
	});
	await writeRootSignal(rootDir, `debate-${debate.debateId}-closed`, {
		debate_id: debate.debateId,
		root_agent_id: debate.rootAgentId,
		closed_by: closedBy,
		closed_at: nowIso(),
	});
	await appendAuditLog({
		timestamp: nowIso(),
		event: "debate_close",
		debateId: debate.debateId,
		rootAgentId: debate.rootAgentId,
		closedBy,
		reportPath,
	});
	return { debate, summaryEvent, closeEvent };
}

async function setPeerMode(request: PeerModeSetRequest): Promise<RootAgentState> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	const agent = resolveTargetFromInput(registry, request.target, currentEnv);
	if (!agent) throw new Error(`Managed agent not found: ${request.target}`);
	const rootDir = await ensureRootCoordination(agent.rootAgentId, registry, agent.rootDir);
	const explicitPeers = parseParticipantValues(request.participants);
	const peerRecords = explicitPeers.length > 0 ? resolveCanonicalAgents(registry, explicitPeers) : [];
	if (peerRecords.length > 0 && ensureSameRoot([agent, ...peerRecords]) !== agent.rootAgentId) {
		throw new Error("Peer mode participants must belong to the same root hierarchy");
	}
	const existing = (await readRootAgentState(rootDir, agent.agentId)) ?? {
		agentId: agent.agentId,
		sessionName: agent.sessionName,
		rootAgentId: agent.rootAgentId,
		rootDir,
		role: agent.role,
		goal: agent.goal,
		status: agent.status,
		peerMode: "alone" as PeerMode,
		peerParticipants: [],
		createdAt: agent.createdAt,
		updatedAt: nowIso(),
	};
	const next: RootAgentState = {
		...existing,
		peerMode: request.mode,
		peerParticipants: uniqueStrings(peerRecords.map((record) => record.agentId)),
		updatedAt: nowIso(),
	};
	await writeRootAgentState(rootDir, next);
	await updateRegistry((nextRegistry) => {
		const found = nextRegistry.agents.find((entry) => entry.agentId === agent.agentId);
		if (found) {
			found.rootDir = rootDir;
			found.peerMode = next.peerMode;
			found.peerParticipants = next.peerParticipants;
			found.updatedAt = nowIso();
		}
	});
	await writeRootSignal(rootDir, `peer-mode-${agent.agentId}`, {
		agent_id: agent.agentId,
		peer_mode: request.mode,
		participants: next.peerParticipants.join(","),
		updated_at: next.updatedAt,
	});
	await appendAuditLog({
		timestamp: nowIso(),
		event: "peer_mode_set",
		agentId: agent.agentId,
		rootAgentId: agent.rootAgentId,
		mode: request.mode,
		participants: next.peerParticipants,
	});
	return next;
}

async function listPeerStates(target: string | undefined, rootAgentId?: string): Promise<PeerListEntry[]> {
	const registry = await readRegistry();
	const currentEnv = getCurrentAgentEnv();
	let resolvedRootAgentId = normalizeOptional(rootAgentId) ?? currentEnv.rootAgentId;
	let resolvedRootDir = currentEnv.rootDir;
	if (target) {
		const agent = resolveTargetFromInput(registry, target, currentEnv);
		if (!agent) throw new Error(`Managed agent not found: ${target}`);
		resolvedRootAgentId = agent.rootAgentId;
		resolvedRootDir = agent.rootDir ?? resolvedRootDir;
	}
	if (!resolvedRootAgentId) throw new Error("peer_list requires a target agent or a current tmux-agent root hierarchy");
	resolvedRootDir = await ensureRootCoordination(resolvedRootAgentId, registry, resolvedRootDir);
	const statuses = await resolveStatuses(registry);
	const peers = statuses.filter((status) => status.record.rootAgentId === resolvedRootAgentId);
	const results: PeerListEntry[] = [];
	for (const peer of peers) {
		const state = await readRootAgentState(resolvedRootDir, peer.record.agentId);
		results.push({
			agentId: peer.record.agentId,
			sessionName: peer.record.sessionName,
			rootAgentId: resolvedRootAgentId,
			rootDir: resolvedRootDir,
			status: peer.effectiveStatus,
			peerMode: state?.peerMode ?? peer.record.peerMode ?? "alone",
			peerParticipants: state?.peerParticipants ?? peer.record.peerParticipants ?? [],
		});
	}
	results.sort((a, b) => a.agentId.localeCompare(b.agentId));
	return results;
}

async function treeManagedAgents(): Promise<string[]> {
	const registry = await readRegistry();
	const statuses = await resolveStatuses(registry);
	return buildTreeLines(registry, statuses);
}

async function chooseAgent(ctx: ExtensionCommandContext, title: string, onlyLive = false): Promise<ManagedAgentRecord | undefined> {
	const statuses = await listManagedAgents(true);
	const filtered = onlyLive ? statuses.filter((status) => status.hasSession) : statuses;
	if (filtered.length === 0) {
		ctx.ui.notify("No managed agents available", "warning");
		return undefined;
	}
	const items = filtered.map((status) => ({ value: status.record.agentId, label: formatAgentSummary(status) }));
	const choice = await ctx.ui.select(title, items.map((item) => item.label));
	if (!choice) return undefined;
	const selected = filtered.find((status) => formatAgentSummary(status) === choice);
	return selected?.record;
}

async function collectSpawnRequestFromUI(parsed: ParsedArgs, ctx: ExtensionCommandContext): Promise<SpawnRequest> {
	const promptDefault = parsed.positionals.join(" ");
	const prompt = await ctx.ui.editor("tmux-agent task", promptDefault);
	if (!prompt?.trim()) throw new Error("Spawn cancelled: prompt is required");

	const baseRequest = buildSpawnRequest(parsed, prompt, ctx);
	if (!hasFlag(parsed, "advanced")) {
		return baseRequest;
	}

	const cwd = (await ctx.ui.input("tmux-agent cwd", baseRequest.cwd ?? ctx.cwd))?.trim();
	if (!cwd) throw new Error("Spawn cancelled: cwd is required");
	const model = (await ctx.ui.input("tmux-agent model", baseRequest.model ?? formatCurrentModel(ctx) ?? DEFAULT_MODEL))?.trim();
	if (!model) throw new Error("Spawn cancelled: model is required");
	const role = (await ctx.ui.input("tmux-agent role", baseRequest.role ?? ""))?.trim() ?? "";
	const goal = (await ctx.ui.input("tmux-agent goal", baseRequest.goal ?? summarizePrompt(prompt)))?.trim() ?? "";
	const agentId = (await ctx.ui.input("tmux-agent agent id", baseRequest.agentId ?? ""))?.trim() ?? "";
	const contextBrief = (await ctx.ui.editor("tmux-agent context brief (optional)", baseRequest.contextBrief ?? ""))?.trim() ?? "";
	const openIterm = hasFlag(parsed, "open-iterm", "open", "watch", "live", "headless")
		? baseRequest.openIterm ?? false
		: await ctx.ui.confirm("tmux-agent", `Open a new iTerm tab now?\n\nInferred role: ${baseRequest.role ?? "worker"}\nGoal: ${baseRequest.goal ?? summarizePrompt(prompt)}`);
	return {
		...baseRequest,
		agentId: agentId || undefined,
		cwd,
		model,
		role: role || undefined,
		goal: goal || undefined,
		contextBrief: contextBrief || undefined,
		openIterm,
	};
}

function spawnRequestFromParsed(parsed: ParsedArgs, ctx: ExtensionContext): SpawnRequest {
	const prompt = parsed.positionals.join(" ").trim();
	if (!prompt) throw new Error("spawn requires a prompt. Omit args in TUI mode to be prompted interactively.");
	return buildSpawnRequest(parsed, prompt, ctx);
}

async function presentText(ctx: ExtensionCommandContext, title: string, lines: string[]): Promise<void> {
	if (!ctx.hasUI) {
		console.log(lines.join("\n"));
		return;
	}
	await ctx.ui.select(title, lines.length > 0 ? lines : ["(empty)"]);
}

function buildToolResult(text: string, details: Record<string, unknown>) {
	return {
		content: [{ type: "text" as const, text }],
		details,
	};
}

function getSessionBridgeEntries(ctx: ExtensionContext): SessionBridgeEntry[] {
	const results: SessionBridgeEntry[] = [];
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "custom" || entry.customType !== "tmux-agent-bridge") continue;
		const data = entry.data as Partial<SessionBridgeEntry> | undefined;
		if (!data?.launchId || !data.bridgeDir || !data.agentId || !data.sessionName || !data.createdAt || !data.notificationMode) continue;
		results.push({
			launchId: data.launchId,
			bridgeDir: data.bridgeDir,
			agentId: data.agentId,
			sessionName: data.sessionName,
			createdAt: data.createdAt,
			notificationMode: data.notificationMode,
		});
	}
	return results;
}

function isTerminalBridgeEvent(event: BridgeEvent): boolean {
	return event.direction === "child_to_parent" && (event.type === "completion" || event.type === "failure");
}

function getLatestTerminalBridgeEvent(events: BridgeEvent[]): BridgeEvent | undefined {
	for (let i = events.length - 1; i >= 0; i -= 1) {
		if (isTerminalBridgeEvent(events[i])) return events[i];
	}
	return undefined;
}

function getLastBridgeActivityTimestamp(events: BridgeEvent[]): number | undefined {
	for (let i = events.length - 1; i >= 0; i -= 1) {
		const timestamp = Date.parse(events[i].timestamp);
		if (!Number.isNaN(timestamp)) return timestamp;
	}
	return undefined;
}

function hasBridgeExitEvent(events: BridgeEvent[]): boolean {
	return events.some((event) => event.direction === "system" && event.type === "exited");
}

function shouldTriggerTurnForEvent(event: BridgeEvent, launch: BridgeLaunchFile): boolean {
	if (launch.notificationMode === "silent") return false;
	if (event.type === "question" || event.type === "blocker") return true;
	return launch.notificationMode === "notify-and-follow-up";
}

async function buildParentDeliveryContent(
	event: BridgeEvent,
	launch: BridgeLaunchFile,
	options?: {
		terminalEventId?: string;
		finalizedAt?: string;
	},
): Promise<string> {
	const header = `[tmux-agent ${event.type}] ${launch.agentId}`;
	const terminalMetadata = options?.terminalEventId || options?.finalizedAt
		? [
			"## Completion Metadata",
			options?.terminalEventId ? `- Terminal Event ID: ${options.terminalEventId}` : undefined,
			options?.finalizedAt ? `- Finalized At: ${options.finalizedAt}` : undefined,
			"",
		].filter((line): line is string => Boolean(line))
		: [];
	if (event.reportPath) {
		try {
			const summary = await readBoundedReportSummary(event.reportPath);
			return [header, "", `Goal: ${launch.goal ?? launch.promptPreview}`, "", ...terminalMetadata, summary].join("\n");
		} catch {
			return [header, "", `Goal: ${launch.goal ?? launch.promptPreview}`, ...terminalMetadata, `Summary: ${event.summary ?? "Report unavailable."}`]
				.filter(Boolean)
				.join("\n");
		}
	}
	return [
		header,
		"",
		`Goal: ${launch.goal ?? launch.promptPreview}`,
		...terminalMetadata,
		event.summary ? `Summary: ${event.summary}` : "",
		event.message ? `Message: ${event.message}` : "",
	].filter(Boolean).join("\n");
}

async function buildDebateDeliveryContent(event: DebateEvent, debate: DebateFile): Promise<string> {
	const header = event.type === "debate_closed" ? `[peer debate closed: ${debate.debateId}]` : `[peer debate: ${debate.debateId}]`;
	if (event.reportPath) {
		try {
			const summary = await readBoundedReportSummary(event.reportPath);
			return [header, `Topic: ${debate.topic ?? "(none specified)"}`, `From: ${event.from.agentId}`, "", summary].join("\n");
		} catch {
			return [header, `Topic: ${debate.topic ?? "(none specified)"}`, `From: ${event.from.agentId}`, `Summary: ${event.summary}`].join("\n");
		}
	}
	return [
		header,
		`Topic: ${debate.topic ?? "(none specified)"}`,
		`From: ${event.from.agentId}`,
		`Mode: ${debate.mode}`,
		event.summary ? `Summary: ${event.summary}` : "",
		event.message ? `Message: ${truncate(event.message, 500)}` : "",
	].filter(Boolean).join("\n");
}

function shouldTriggerTurnForDebateEvent(event: DebateEvent): boolean {
	return Boolean(event.requiresResponse && event.type !== "debate_closed");
}

function formatPeerListLine(peer: PeerListEntry): string {
	const parts = [peer.agentId, `[${peer.status}]`, `mode=${peer.peerMode}`];
	if (peer.peerParticipants.length > 0) parts.push(`participants=${peer.peerParticipants.join(",")}`);
	return parts.join(" | ");
}

export default function tmuxAgentExtension(pi: ExtensionAPI) {
	const bridgeWatchers = new Map<string, FSWatcher>();
	const debateWatchers = new Map<string, FSWatcher>();
	const rootWatchers = new Map<string, FSWatcher>();
	const bridgeCompletionTimers = new Map<string, ReturnType<typeof setTimeout>>();
	const processingBridges = new Set<string>();
	const processingDebates = new Set<string>();

	const clearBridgeCompletionTimer = (bridgeDir: string) => {
		const timer = bridgeCompletionTimers.get(bridgeDir);
		if (!timer) return;
		clearTimeout(timer);
		bridgeCompletionTimers.delete(bridgeDir);
	};

	const scheduleBridgeCompletionReconcile = (bridgeDir: string, sessionKey: string, delayMs: number) => {
		clearBridgeCompletionTimer(bridgeDir);
		const timer = setTimeout(() => {
			bridgeCompletionTimers.delete(bridgeDir);
			void processBridgeDeliveries(bridgeDir, sessionKey);
		}, Math.max(250, delayMs));
		bridgeCompletionTimers.set(bridgeDir, timer);
	};

	const subscribeBridge = async (bridgeDir: string, sessionKey: string) => {
		if (bridgeWatchers.has(bridgeDir)) return;
		const watchTarget = getBridgeSignalsDir(bridgeDir);
		const watcher = watchFs(watchTarget, { persistent: false }, () => {
			void processBridgeDeliveries(bridgeDir, sessionKey);
		});
		bridgeWatchers.set(bridgeDir, watcher);
	};

	const unsubscribeUnusedBridges = (desired: Set<string>) => {
		for (const [bridgeDir, watcher] of bridgeWatchers.entries()) {
			if (desired.has(bridgeDir)) continue;
			watcher.close();
			bridgeWatchers.delete(bridgeDir);
			clearBridgeCompletionTimer(bridgeDir);
		}
	};

	const processBridgeDeliveries = async (bridgeDir: string, sessionKey: string) => {
		if (processingBridges.has(bridgeDir)) return;
		processingBridges.add(bridgeDir);
		try {
			const launch = await readBridgeLaunch(bridgeDir);
			if (launch.parentSessionKey !== sessionKey) return;
			const parentState = await readBridgeParentState(bridgeDir);
			const delivered = new Set(parentState.deliveredEventIds);
			let changed = false;
			let events: BridgeEvent[] = [];
			try {
				const raw = await fs.readFile(getBridgeEventsPath(bridgeDir), "utf-8");
				events = raw
					.split(/\r?\n/)
					.map((line) => line.trim())
					.filter(Boolean)
					.map((line) => JSON.parse(line) as BridgeEvent);
			} catch (error) {
				if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
			}

			const latestTerminalEvent = getLatestTerminalBridgeEvent(events);
			const lastBridgeActivityAt = getLastBridgeActivityTimestamp(events);
			const childExited = hasBridgeExitEvent(events);
			const quietForMs = lastBridgeActivityAt ? Date.now() - lastBridgeActivityAt : undefined;
			const shouldFinalizeLatestTerminal = Boolean(latestTerminalEvent) && (childExited || (quietForMs !== undefined && quietForMs >= TERMINAL_COMPLETION_SETTLE_MS));
			if (!latestTerminalEvent || shouldFinalizeLatestTerminal || parentState.terminalEventId) {
				clearBridgeCompletionTimer(bridgeDir);
			}

			for (const event of events) {
				if (delivered.has(event.eventId)) continue;
				if (event.direction !== "child_to_parent") {
					delivered.add(event.eventId);
					changed = true;
					continue;
				}

				if (isTerminalBridgeEvent(event)) {
					if (parentState.terminalEventId) {
						delivered.add(event.eventId);
						changed = true;
						continue;
					}
					if (!latestTerminalEvent || event.eventId !== latestTerminalEvent.eventId) {
						delivered.add(event.eventId);
						changed = true;
						continue;
					}
					if (!shouldFinalizeLatestTerminal) {
						parentState.pendingTerminalEventId = event.eventId;
						parentState.pendingTerminalObservedAt = event.timestamp;
						changed = true;
						if (quietForMs !== undefined) {
							scheduleBridgeCompletionReconcile(bridgeDir, sessionKey, TERMINAL_COMPLETION_SETTLE_MS - quietForMs);
						}
						continue;
					}
					const finalizedAt = nowIso();
					const content = await buildParentDeliveryContent(event, launch, {
						terminalEventId: event.eventId,
						finalizedAt,
					});
					if (launch.notificationMode !== "silent") {
						pi.sendMessage(
							{
								customType: "tmux-agent-report",
								content,
								display: true,
								details: { launch, event, terminalEventId: event.eventId, finalizedAt },
							},
							shouldTriggerTurnForEvent(event, launch)
								? { triggerTurn: true, deliverAs: "followUp" }
								: { triggerTurn: false },
						);
					}
					parentState.terminalEventId = event.eventId;
					parentState.terminalFinalizedAt = finalizedAt;
					parentState.pendingTerminalEventId = undefined;
					parentState.pendingTerminalObservedAt = undefined;
					delivered.add(event.eventId);
					changed = true;
					continue;
				}

				const content = await buildParentDeliveryContent(event, launch);
				if (launch.notificationMode !== "silent") {
					pi.sendMessage(
						{
							customType: "tmux-agent-report",
							content,
							display: true,
							details: { launch, event },
						},
						shouldTriggerTurnForEvent(event, launch)
							? { triggerTurn: true, deliverAs: "followUp" }
							: { triggerTurn: false },
					);
				}
				delivered.add(event.eventId);
				changed = true;
			}

			if (changed) {
				parentState.deliveredEventIds = Array.from(delivered).slice(-500);
				await writeBridgeParentState(bridgeDir, parentState);
			}
		} finally {
			processingBridges.delete(bridgeDir);
		}
	};

	const reconcileBridgeWatchers = async (ctx: ExtensionContext) => {
		const sessionKey = getSessionKey(ctx);
		const desired = new Set<string>();
		for (const entry of getSessionBridgeEntries(ctx)) {
			desired.add(entry.bridgeDir);
			await subscribeBridge(entry.bridgeDir, sessionKey);
			await processBridgeDeliveries(entry.bridgeDir, sessionKey);
		}
		unsubscribeUnusedBridges(desired);
	};

	const rememberBridge = async (record: ManagedAgentRecord, ctx: ExtensionContext) => {
		const entry = buildBridgeSessionEntry(record);
		if (!entry) return;
		pi.appendEntry("tmux-agent-bridge", entry);
		await reconcileBridgeWatchers(ctx);
	};

	const processDebateDeliveries = async (rootDir: string, debateId: string, agentId: string) => {
		const key = `${rootDir}::${debateId}::${agentId}`;
		if (processingDebates.has(key)) return;
		processingDebates.add(key);
		try {
			const debate = await readDebate(rootDir, debateId);
			if (!debate) return;
			const deliveryState = await readDebateDeliveryState(rootDir, debateId, agentId);
			const events = await readDebateEvents(rootDir, debateId);
			let lastDeliveredSeq = deliveryState.lastDeliveredSeq;
			for (const event of events) {
				if (event.seq <= deliveryState.lastDeliveredSeq) continue;
				lastDeliveredSeq = Math.max(lastDeliveredSeq, event.seq);
				if (!isDebateEventVisibleToAgent(event, debate, agentId)) continue;
				const content = await buildDebateDeliveryContent(event, debate);
				pi.sendMessage(
					{
						customType: "tmux-agent-peer-debate",
						content,
						display: true,
						details: { debate, event },
					},
					shouldTriggerTurnForDebateEvent(event)
						? { triggerTurn: true, deliverAs: "followUp" }
						: { triggerTurn: false },
				);
			}
			if (lastDeliveredSeq !== deliveryState.lastDeliveredSeq) {
				deliveryState.lastDeliveredSeq = lastDeliveredSeq;
				await writeDebateDeliveryState(rootDir, debateId, deliveryState);
			}
		} finally {
			processingDebates.delete(key);
		}
	};

	const subscribeDebate = async (rootDir: string, debateId: string, agentId: string) => {
		const key = `${rootDir}::${debateId}::${agentId}`;
		if (debateWatchers.has(key)) return;
		const watcher = watchFs(getDebateSignalsDir(rootDir, debateId), { persistent: false }, () => {
			void processDebateDeliveries(rootDir, debateId, agentId);
		});
		debateWatchers.set(key, watcher);
	};

	const unsubscribeUnusedDebates = (desired: Set<string>) => {
		for (const [key, watcher] of debateWatchers.entries()) {
			if (desired.has(key)) continue;
			watcher.close();
			debateWatchers.delete(key);
		}
	};

	const subscribeRoot = async (rootDir: string, ctx: ExtensionContext) => {
		if (rootWatchers.has(rootDir)) return;
		const watcher = watchFs(getRootSignalsDir(rootDir), { persistent: false }, () => {
			void reconcileDebateWatchers(ctx);
		});
		rootWatchers.set(rootDir, watcher);
	};

	const unsubscribeUnusedRoots = (desired: Set<string>) => {
		for (const [rootDir, watcher] of rootWatchers.entries()) {
			if (desired.has(rootDir)) continue;
			watcher.close();
			rootWatchers.delete(rootDir);
		}
	};

	const reconcileDebateWatchers = async (ctx: ExtensionContext) => {
		const currentEnv = getCurrentAgentEnv();
		const desiredDebates = new Set<string>();
		const desiredRoots = new Set<string>();
		if (currentEnv.agentId && currentEnv.rootDir) {
			desiredRoots.add(currentEnv.rootDir);
			await subscribeRoot(currentEnv.rootDir, ctx);
			const debates = await listRelevantDebatesForAgent(currentEnv.rootDir, currentEnv.agentId);
			for (const debate of debates) {
				const key = `${currentEnv.rootDir}::${debate.debateId}::${currentEnv.agentId}`;
				desiredDebates.add(key);
				await subscribeDebate(currentEnv.rootDir, debate.debateId, currentEnv.agentId);
				await processDebateDeliveries(currentEnv.rootDir, debate.debateId, currentEnv.agentId);
			}
		}
		unsubscribeUnusedDebates(desiredDebates);
		unsubscribeUnusedRoots(desiredRoots);
	};

	const handleCommand = async (rawArgs: string, ctx: ExtensionCommandContext) => {
		const trimmed = rawArgs.trim();
		if (!trimmed) {
			if (!ctx.hasUI) {
				console.log(buildUsage());
				return;
			}
			const selected = await ctx.ui.select("tmux-agent", ["spawn", "open", "close", "list", "status", "capture", "send", "kill", "tree", "debate", "peer-mode", "peer-list"]);
			if (!selected) return;
			await handleCommand(selected, ctx);
			return;
		}

		const tokens = tokenizeArgs(trimmed);
		const subcommand = tokens[0];
		const parsed = parseArgs(tokens.slice(1));

		switch (subcommand) {
			case "spawn": {
				const request = ctx.hasUI && (parsed.positionals.length === 0 || hasFlag(parsed, "advanced"))
					? await collectSpawnRequestFromUI(parsed, ctx)
					: spawnRequestFromParsed(parsed, ctx);
				const record = await spawnManagedAgent(request, ctx);
				await rememberBridge(record, ctx);
				const openedIterm = record.visualMode === "iterm-opened";
				const summary = `Spawned ${record.agentId} (${record.role ?? "worker"}, ${openedIterm ? "opened in iTerm" : "headless"})${openedIterm ? "." : ". Use /tmux-agent open last to watch it."}`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "open": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Open tmux-agent in iTerm", true);
					target = selected?.agentId;
				}
				const record = await openManagedAgent(target);
				const summary = `Opened ${record.agentId} (${record.sessionName}) in the current iTerm window without stealing focus.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "close": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Close tmux-agent iTerm tabs", false);
					target = selected?.agentId;
				}
				const result = await closeManagedAgentVisual(target);
				const summary = `Closed ${result.closedCount} managed iTerm tab(s) for ${result.agent.agentId}${result.missingCount > 0 ? ` (${result.missingCount} already gone)` : ""}.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "list": {
				const statuses = await listManagedAgents(true);
				const lines = statuses.length > 0 ? statuses.map(formatAgentSummary) : ["No managed agents recorded."];
				await presentText(ctx, "Managed tmux agents", lines);
				return;
			}
			case "status": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "tmux-agent status", false);
					target = selected?.agentId;
				}
				const result = await statusManagedAgent(target, 40);
				const lines = [...formatAgentDetails(result.status)];
				if (result.capture) lines.push("", "capture:", ...result.capture.trimEnd().split(/\r?\n/).slice(-20));
				await presentText(ctx, `tmux-agent status: ${result.status.record.agentId}`, lines);
				return;
			}
			case "capture": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Capture tmux-agent pane", true);
					target = selected?.agentId;
				}
				const linesFlag = parsed.flags.get("lines");
				const lines = typeof linesFlag === "string" ? Number(linesFlag) : DEFAULT_CAPTURE_LINES;
				const result = await captureManagedAgent(target, Number.isFinite(lines) ? lines : DEFAULT_CAPTURE_LINES);
				await presentText(ctx, `tmux-agent capture: ${result.status.record.agentId}`, result.capture.trimEnd().split(/\r?\n/));
				return;
			}
			case "send": {
				let target = parsed.positionals[0];
				let message = parsed.positionals.slice(1).join(" ").trim();
				if (ctx.hasUI && !target) {
					const selected = await chooseAgent(ctx, "Send message to tmux-agent", true);
					target = selected?.agentId;
				}
				if (ctx.hasUI && !message) {
					message = (await ctx.ui.editor("tmux-agent message", ""))?.trim() ?? "";
				}
				if (!target) throw new Error("send requires a target agent ID or session name");
				if (!message) throw new Error("send requires a non-empty message");
				const record = await sendManagedMessage({ target, message });
				const summary = `Sent message to ${record.agentId}.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "kill": {
				let target = parsed.positionals[0];
				if (!target && ctx.hasUI) {
					const selected = await chooseAgent(ctx, "Kill tmux-agent session", false);
					target = selected?.agentId;
				}
				if (!target) throw new Error("kill requires a target agent ID or session name");
				if (ctx.hasUI) {
					const ok = await ctx.ui.confirm("tmux-agent", `Kill ${target}?`);
					if (!ok) return;
				}
				const record = await killManagedAgent(target);
				const summary = `Killed ${record.agentId} (${record.sessionName}).`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "tree": {
				const lines = await treeManagedAgents();
				await presentText(ctx, "tmux-agent tree", lines);
				return;
			}
			case "debate": {
				const debateAction = parsed.positionals[0];
				const debateArgs = { flags: parsed.flags, positionals: parsed.positionals.slice(1) } satisfies ParsedArgs;
				if (debateAction === "start") {
					const participants = inferTargetList(debateArgs);
					const mode = inferPeerMode(debateArgs, participants.length > 0 ? "subset" : "all");
					const debate = await startDebateChannel({
						debateId: getStringFlag(debateArgs, "id"),
						rootAgentId: getStringFlag(debateArgs, "root"),
						mode,
						participants,
						topic: getStringFlag(debateArgs, "topic") ?? inferDebateTopic(debateArgs.positionals),
						mirrorToParent: inferMirrorMode(getStringFlag(debateArgs, "mirror")),
					});
					const summary = `Started debate ${debate.debateId} (${debate.mode}) with ${debate.participants.length} participant(s).`;
					if (ctx.hasUI) ctx.ui.notify(summary, "info");
					else console.log(summary);
					return;
				}
				if (debateAction === "send") {
					const debateId = debateArgs.positionals[0];
					const message = debateArgs.positionals.slice(1).join(" ").trim();
					if (!debateId) throw new Error("debate send requires a debate ID");
					if (!message) throw new Error("debate send requires a non-empty message");
					const result = await sendDebateMessage({
						debateId,
						message,
						summary: getStringFlag(debateArgs, "summary"),
						participants: inferTargetList(debateArgs),
						rootAgentId: getStringFlag(debateArgs, "root"),
						requiresResponse: inferRequiresResponse(debateArgs),
					});
					const summary = `Sent debate message in ${result.debate.debateId}.`;
					if (ctx.hasUI) ctx.ui.notify(summary, "info");
					else console.log(summary);
					return;
				}
				if (debateAction === "close") {
					const debateId = debateArgs.positionals[0];
					const summaryText = debateArgs.positionals.slice(1).join(" ").trim();
					if (!debateId) throw new Error("debate close requires a debate ID");
					const result = await closeDebateChannel({
						debateId,
						rootAgentId: getStringFlag(debateArgs, "root"),
						summary: summaryText || getStringFlag(debateArgs, "summary"),
					});
					const summary = `Closed debate ${result.debate.debateId}.`;
					if (ctx.hasUI) ctx.ui.notify(summary, "info");
					else console.log(summary);
					return;
				}
				throw new Error("debate requires start, send, or close");
			}
			case "peer-mode": {
				const target = parsed.positionals[0];
				const mode = inferPeerModeValue(parsed.positionals[1]);
				if (!target) throw new Error("peer-mode requires a target agent or session name");
				if (!mode) throw new Error("peer-mode requires one of: alone, all, subset, direct");
				const state = await setPeerMode({ target, mode, participants: inferTargetList(parsed) });
				const summary = `Set peer mode for ${state.agentId} to ${state.peerMode}.`;
				if (ctx.hasUI) ctx.ui.notify(summary, "info");
				else console.log(summary);
				return;
			}
			case "peer-list": {
				const peers = await listPeerStates(parsed.positionals[0], getStringFlag(parsed, "root"));
				const lines = peers.length > 0 ? peers.map(formatPeerListLine) : ["No peer agents found for this root."];
				await presentText(ctx, "tmux-agent peer list", lines);
				return;
			}
			default:
				throw new Error(`Unknown tmux-agent subcommand: ${subcommand}\n\n${buildUsage()}`);
		}
	};

	pi.on("session_start", async (_event, ctx) => {
		await ensureStateDirs();
		const currentEnv = getCurrentAgentEnv();
		if (currentEnv.agentId) {
			pi.setSessionName(currentEnv.role ? `${currentEnv.role}: ${currentEnv.agentId}` : currentEnv.agentId);
			ctx.ui.setStatus(EXTENSION_NAME, `agent:${currentEnv.agentId}${currentEnv.role ? ` role:${currentEnv.role}` : ""}`);
			const updatedRegistry = await updateRegistry((registry) => {
				const existing = registry.agents.find((agent) => agent.agentId === currentEnv.agentId);
				if (existing) {
					existing.status = "running";
					existing.lastSeenAt = nowIso();
					existing.updatedAt = existing.lastSeenAt;
					existing.role ??= currentEnv.role;
					existing.goal ??= currentEnv.goal;
					existing.parentAgentId ??= currentEnv.parentAgentId;
					existing.rootAgentId = existing.rootAgentId || currentEnv.rootAgentId || existing.agentId;
					existing.rootDir = existing.rootDir || currentEnv.rootDir;
				}
			});
			const existing = updatedRegistry.agents.find((agent) => agent.agentId === currentEnv.agentId);
			if (existing?.rootDir) await syncRootAgentState(existing);
		}
		if (currentEnv.bridgeDir && currentEnv.launchId && currentEnv.agentId) {
			const launch = await readBridgeLaunch(currentEnv.bridgeDir);
			const launchedEvent = await appendBridgeEvent(currentEnv.bridgeDir, {
				launchId: currentEnv.launchId,
				direction: "system",
				type: "launched",
				from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
				summary: `${currentEnv.agentId} launched`,
			});
			await writeSignalFile(path.join(getBridgeSignalsDir(currentEnv.bridgeDir), makeSignalName("launched", true)), {
				event_id: launchedEvent.eventId,
				launch_id: currentEnv.launchId,
				agent_id: currentEnv.agentId,
				status: "success",
				created_at: launchedEvent.timestamp,
			});
		}
		await reconcileBridgeWatchers(ctx);
		await reconcileDebateWatchers(ctx);
	});

	pi.on("session_switch", async (_event, ctx) => {
		await reconcileBridgeWatchers(ctx);
		await reconcileDebateWatchers(ctx);
	});
	pi.on("session_tree", async (_event, ctx) => {
		await reconcileBridgeWatchers(ctx);
		await reconcileDebateWatchers(ctx);
	});
	pi.on("session_fork", async (_event, ctx) => {
		await reconcileBridgeWatchers(ctx);
		await reconcileDebateWatchers(ctx);
	});

	pi.on("before_agent_start", async (event, _ctx) => {
		const currentEnv = getCurrentAgentEnv();
		if (!currentEnv.bridgeDir) return;
		const protocolPath = path.join(currentEnv.bridgeDir, "child", "protocol.md");
		const protocol = await fs.readFile(protocolPath, "utf-8").catch(() => undefined);
		if (!protocol?.trim()) return;
		return {
			systemPrompt: `${event.systemPrompt}\n\n${protocol.trim()}`,
		};
	});

	pi.on("agent_end", async (event, _ctx) => {
		const currentEnv = getCurrentAgentEnv();
		if (!currentEnv.bridgeDir || !currentEnv.launchId || !currentEnv.agentId) return;
		const launch = await readBridgeLaunch(currentEnv.bridgeDir);
		const finalAssistant = getFinalAssistantMessage(event.messages as any[]);
		const assistantText = getAssistantText(finalAssistant);
		const stopReason = finalAssistant?.stopReason as string | undefined;
		const errorMessage = typeof finalAssistant?.errorMessage === "string" ? finalAssistant.errorMessage : undefined;
		const kind: "completion" | "failure" = stopReason === "error" || stopReason === "aborted" ? "failure" : "completion";
		const markdown = buildAutoReportMarkdown({ launch, kind, assistantText, errorMessage });
		const reportPath = await writeBridgeLatestTerminalReport(currentEnv.bridgeDir, kind, markdown);
		const bridgeEvent = await appendBridgeEvent(currentEnv.bridgeDir, {
			launchId: currentEnv.launchId,
			direction: "child_to_parent",
			type: kind,
			from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
			summary: truncate(assistantText || errorMessage || `${kind} reported by ${currentEnv.agentId}`, 240),
			reportPath,
		});
		const signalPath = await writeBridgeEventSignal(currentEnv.bridgeDir, bridgeEvent, kind === "completion");
		await appendAuditLog({
			timestamp: nowIso(),
			event: "child_turn_report",
			launchId: currentEnv.launchId,
			bridgeDir: currentEnv.bridgeDir,
			agentId: currentEnv.agentId,
			kind,
			reportPath,
			signalPath,
		});
	});

	pi.on("session_shutdown", async (_event, _ctx) => {
		const currentEnv = getCurrentAgentEnv();
		if (currentEnv.agentId) {
			await updateRegistry((registry) => {
				const existing = registry.agents.find((agent) => agent.agentId === currentEnv.agentId);
				if (existing && existing.status !== "terminated") {
					existing.status = "exited";
					existing.updatedAt = nowIso();
				}
			});
			await updateRootAgentLifecycleState(currentEnv.rootDir, currentEnv.agentId, { status: "exited" });
		}
		if (currentEnv.bridgeDir && currentEnv.launchId && currentEnv.agentId) {
			const launch = await readBridgeLaunch(currentEnv.bridgeDir);
			const eventRecord = await appendBridgeEvent(currentEnv.bridgeDir, {
				launchId: currentEnv.launchId,
				direction: "system",
				type: "exited",
				from: { agentId: currentEnv.agentId, sessionName: launch.sessionName },
				summary: `${currentEnv.agentId} exited`,
			});
			await writeSignalFile(path.join(getBridgeSignalsDir(currentEnv.bridgeDir), makeSignalName("exited", true)), {
				event_id: eventRecord.eventId,
				launch_id: currentEnv.launchId,
				agent_id: currentEnv.agentId,
				status: "success",
				created_at: eventRecord.timestamp,
			});
		}
		for (const watcher of bridgeWatchers.values()) watcher.close();
		for (const watcher of debateWatchers.values()) watcher.close();
		for (const watcher of rootWatchers.values()) watcher.close();
		for (const timer of bridgeCompletionTimers.values()) clearTimeout(timer);
		bridgeWatchers.clear();
		debateWatchers.clear();
		rootWatchers.clear();
		bridgeCompletionTimers.clear();
	});

	pi.registerCommand("tmux-agent", {
		description: "Spawn and manage long-lived tmux-backed Pi agents",
		getArgumentCompletions: (prefix) => {
			const subcommands = ["spawn", "open", "close", "list", "status", "capture", "send", "kill", "tree", "debate", "peer-mode", "peer-list"];
			const trimmed = prefix.trim();
			if (!trimmed || !trimmed.includes(" ")) {
				return subcommands.filter((item) => item.startsWith(trimmed)).map((item) => ({ value: item, label: item }));
			}
			return null;
		},
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
		name: "tmux_agent",
		label: "Tmux Agent",
		description: "Spawn and manage long-lived tmux-backed Pi agents, optionally open or close managed iTerm tabs, preserve parent-child context, report back through a bounded private bridge, and coordinate peer debates under a shared root.",
		promptSnippet: "Launch or manage long-lived tmux-backed Pi agents, optionally open or close managed iTerm tabs, inspect status, send messages, use bounded parent-child reporting via private bridge directories, and coordinate peer debates under shared roots.",
		promptGuidelines: [
			"Use this tool when the user wants a long-lived or visually inspectable Pi agent, not a short ephemeral subagent.",
			"Default to headless agents unless the user asks to watch live or inspect a running session.",
			"When opening a visual, open a background tab in the current iTerm window without stealing focus when possible.",
			"For spawn, only set advanced fields like role, agentId, parentAgentId, rootAgentId, notificationMode, and contextBrief when the task really needs them; otherwise rely on defaults.",
			"When building hierarchies, set role, parentAgentId, and rootAgentId deliberately so the org tree stays understandable.",
			"Use report_parent from a child session only for blocker/question/progress/failure escalation. Normal completion is reported automatically.",
			"Use debate_start, debate_send, and debate_close only for explicit peer collaboration. Default peer behavior should remain isolated unless the user asks for cross-peer discussion.",
		],
		parameters: TMUX_AGENT_PARAMS,
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
								notificationMode: params.notificationMode,
								contextBrief: params.contextBrief,
							},
							ctx,
						);
						await rememberBridge(record, ctx);
						const openedIterm = record.visualMode === "iterm-opened";
						return buildToolResult(`Spawned ${record.agentId} (${record.role ?? "worker"}, ${openedIterm ? "opened in iTerm" : "headless"}).`, { action: params.action, agent: record });
					}
					case "open_visual": {
						const record = await openManagedAgent(params.target);
						return buildToolResult(`Opened ${record.agentId} in the current iTerm window without stealing focus.`, { action: params.action, agent: record });
					}
					case "close_visual": {
						const result = await closeManagedAgentVisual(params.target);
						return buildToolResult(`Closed ${result.closedCount} managed iTerm tab(s) for ${result.agent.agentId}${result.missingCount > 0 ? ` (${result.missingCount} already gone)` : ""}.`, { action: params.action, agent: result.agent, closedCount: result.closedCount, missingCount: result.missingCount });
					}
					case "list": {
						const statuses = await listManagedAgents(params.includeExited ?? true);
						const lines = statuses.map(formatAgentSummary);
						return buildToolResult(lines.join("\n") || "No managed agents recorded.", {
							action: params.action,
							agents: statuses.map((status) => ({ ...status.record, effectiveStatus: status.effectiveStatus })),
						});
					}
					case "status": {
						const result = await statusManagedAgent(params.target, params.lines ?? 40);
						const lines = formatAgentDetails(result.status);
						if (result.capture) lines.push("", "capture:", ...result.capture.trimEnd().split(/\r?\n/).slice(-20));
						return buildToolResult(lines.join("\n"), { action: params.action, agent: result.status.record, capture: result.capture });
					}
					case "capture": {
						const result = await captureManagedAgent(params.target, params.lines ?? DEFAULT_CAPTURE_LINES);
						return buildToolResult(result.capture, { action: params.action, agent: result.status.record, lines: params.lines ?? DEFAULT_CAPTURE_LINES });
					}
					case "send_message": {
						if (!params.target?.trim()) throw new Error("send_message requires target");
						if (!params.message?.trim()) throw new Error("send_message requires message");
						const record = await sendManagedMessage({ target: params.target, message: params.message, senderAgentId: params.senderAgentId });
						return buildToolResult(`Sent message to ${record.agentId}.`, { action: params.action, agent: record });
					}
					case "kill": {
						const record = await killManagedAgent(params.target);
						return buildToolResult(`Killed ${record.agentId}.`, { action: params.action, agent: record });
					}
					case "tree": {
						const lines = await treeManagedAgents();
						return buildToolResult(lines.join("\n"), { action: params.action, tree: lines });
					}
					case "report_parent": {
						if (!params.reportKind) throw new Error("report_parent requires reportKind");
						if (!params.summary?.trim()) throw new Error("report_parent requires summary");
						const result = await reportParent({
							kind: params.reportKind,
							summary: params.summary,
							reportMarkdown: params.reportMarkdown,
							requiresResponse: params.requiresResponse,
						});
						return buildToolResult(`Reported ${params.reportKind} to parent.`, { action: params.action, event: result.event, bridgeDir: result.bridgeDir });
					}
					case "debate_start": {
						const mode = params.peerMode ?? (params.participants && params.participants.length > 0 ? "subset" : "all");
						const debate = await startDebateChannel({
							debateId: params.debateId,
							rootAgentId: params.rootAgentId,
							mode,
							participants: params.participants,
							topic: params.topic,
							mirrorToParent: params.mirrorToParent,
							createdBy: params.senderAgentId,
						});
						return buildToolResult(`Started debate ${debate.debateId} (${debate.mode}).`, { action: params.action, debate });
					}
					case "debate_send": {
						if (!params.debateId?.trim()) throw new Error("debate_send requires debateId");
						if (!params.message?.trim()) throw new Error("debate_send requires message");
						const result = await sendDebateMessage({
							debateId: params.debateId,
							message: params.message,
							summary: params.summary,
							participants: params.participants,
							rootAgentId: params.rootAgentId,
							senderAgentId: params.senderAgentId,
							requiresResponse: params.requiresResponse,
							reportMarkdown: params.reportMarkdown,
						});
						return buildToolResult(`Sent debate message in ${result.debate.debateId}.`, { action: params.action, debate: result.debate, event: result.event });
					}
					case "debate_close": {
						if (!params.debateId?.trim()) throw new Error("debate_close requires debateId");
						const result = await closeDebateChannel({
							debateId: params.debateId,
							rootAgentId: params.rootAgentId,
							closedBy: params.senderAgentId,
							summary: params.summary,
							reportMarkdown: params.reportMarkdown,
						});
						return buildToolResult(`Closed debate ${result.debate.debateId}.`, { action: params.action, debate: result.debate, summaryEvent: result.summaryEvent, closeEvent: result.closeEvent });
					}
					case "peer_mode_set": {
						if (!params.target?.trim()) throw new Error("peer_mode_set requires target");
						if (!params.peerMode) throw new Error("peer_mode_set requires peerMode");
						const state = await setPeerMode({ target: params.target, mode: params.peerMode, participants: params.participants });
						return buildToolResult(`Set peer mode for ${state.agentId} to ${state.peerMode}.`, { action: params.action, peer: state });
					}
					case "peer_list": {
						const peers = await listPeerStates(params.target, params.rootAgentId);
						return buildToolResult(peers.map(formatPeerListLine).join("\n") || "No peer agents found.", { action: params.action, peers });
					}
					default:
						throw new Error(`Unsupported tmux_agent action: ${(params as { action: string }).action}`);
				}
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				return buildToolResult(`Error: ${message}`, { action: params.action, error: message });
			}
		},
	});
}
