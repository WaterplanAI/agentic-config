import { createHash } from "node:crypto";
import * as path from "node:path";

export const EXTENSION_NAME = "pimux";
export const PROTOCOL_VERSION = 1;
export const REGISTRY_VERSION = 1;
export const DEFAULT_MODEL = "openai-codex/gpt-5.3-codex";
export const DEFAULT_CAPTURE_LINES = 80;
export const DEFAULT_REPORT_BYTES = 2048;
export const SESSION_WINDOW = "agent";

export const ENV_AGENT_ID = "PI_PIMUX_AGENT_ID";
export const ENV_PARENT_AGENT_ID = "PI_PIMUX_PARENT_AGENT_ID";
export const ENV_ROOT_AGENT_ID = "PI_PIMUX_ROOT_AGENT_ID";
export const ENV_ROLE = "PI_PIMUX_ROLE";
export const ENV_GOAL = "PI_PIMUX_GOAL";
export const ENV_BRIDGE_DIR = "PI_PIMUX_BRIDGE_DIR";
export const ENV_LAUNCH_ID = "PI_PIMUX_LAUNCH_ID";
export const ENV_PARENT_SESSION_KEY = "PI_PIMUX_PARENT_SESSION_KEY";
export const ENV_NOTIFICATION_MODE = "PI_PIMUX_NOTIFICATION_MODE";
export const ENV_CONTEXT_BRIEF = "PI_PIMUX_CONTEXT_BRIEF";
export const ENV_STATE_ROOT = "PI_PIMUX_STATE_ROOT";
export const ENV_ROOT_OWNER_SESSION_KEY = "PI_PIMUX_ROOT_OWNER_SESSION_KEY";
export const ENV_EXTENSION_PATH = "PI_PIMUX_EXTENSION_PATH";

export type NotificationMode = "notify-and-follow-up";
export const DEFAULT_NOTIFICATION_MODE: NotificationMode = "notify-and-follow-up";

export interface PimuxEnv {
	agentId?: string;
	parentAgentId?: string;
	rootAgentId?: string;
	role?: string;
	goal?: string;
	bridgeDir?: string;
	launchId?: string;
	parentSessionKey?: string;
	notificationMode?: NotificationMode;
	contextBrief?: string;
	stateRoot?: string;
	rootOwnerSessionKey?: string;
	extensionPath?: string;
}

export function nowIso(): string {
	return new Date().toISOString();
}

export function normalizeOptional(value: string | undefined): string | undefined {
	const trimmed = value?.trim();
	return trimmed ? trimmed : undefined;
}

export function slugify(value: string): string {
	return value
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
		.replace(/-{2,}/g, "-")
		.slice(0, 40);
}

export function truncate(text: string, maxLength: number): string {
	const normalized = text.replace(/\s+/g, " ").trim();
	if (normalized.length <= maxLength) return normalized;
	return `${normalized.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

export function firstNonEmptyLine(text: string): string {
	for (const line of text.split(/\r?\n/)) {
		const trimmed = line.trim();
		if (trimmed) return trimmed;
	}
	return "";
}

export function summarizePrompt(prompt: string): string {
	const firstLine = firstNonEmptyLine(prompt);
	return truncate(firstLine || prompt, 120);
}

export function shellQuote(value: string): string {
	return `'${value.replace(/'/g, `'"'"'`)}'`;
}

export function hashKey(value: string): string {
	return createHash("sha1").update(value).digest("hex").slice(0, 16);
}

export function sessionKeyToId(sessionKey: string): string {
	return hashKey(sessionKey);
}

export function normalizeNotificationMode(value: string | undefined): NotificationMode | undefined {
	return normalizeOptional(value) ? DEFAULT_NOTIFICATION_MODE : undefined;
}

export function getCurrentEnv(): PimuxEnv {
	return {
		agentId: normalizeOptional(process.env[ENV_AGENT_ID]),
		parentAgentId: normalizeOptional(process.env[ENV_PARENT_AGENT_ID]),
		rootAgentId: normalizeOptional(process.env[ENV_ROOT_AGENT_ID]),
		role: normalizeOptional(process.env[ENV_ROLE]),
		goal: normalizeOptional(process.env[ENV_GOAL]),
		bridgeDir: normalizeOptional(process.env[ENV_BRIDGE_DIR]),
		launchId: normalizeOptional(process.env[ENV_LAUNCH_ID]),
		parentSessionKey: normalizeOptional(process.env[ENV_PARENT_SESSION_KEY]),
		notificationMode: normalizeNotificationMode(process.env[ENV_NOTIFICATION_MODE]),
		contextBrief: normalizeOptional(process.env[ENV_CONTEXT_BRIEF]),
		stateRoot: normalizeOptional(process.env[ENV_STATE_ROOT]),
		rootOwnerSessionKey: normalizeOptional(process.env[ENV_ROOT_OWNER_SESSION_KEY]),
		extensionPath: normalizeOptional(process.env[ENV_EXTENSION_PATH]),
	};
}

export function getStateRoot(cwd: string): string {
	return normalizeOptional(process.env[ENV_STATE_ROOT]) ?? path.resolve(cwd, "tmp", EXTENSION_NAME);
}

export function getRegistryPath(stateRoot: string): string {
	return path.join(stateRoot, "registry.json");
}

export function getRegistryArchivePath(stateRoot: string): string {
	return path.join(stateRoot, "registry.archive.jsonl");
}

export function getSessionsDir(stateRoot: string): string {
	return path.join(stateRoot, "sessions");
}

export function getSessionRegistryPath(stateRoot: string, sessionKey: string): string {
	return path.join(getSessionsDir(stateRoot), sessionKeyToId(sessionKey), "registry.json");
}

export function getAgentsDir(stateRoot: string): string {
	return path.join(stateRoot, "agents");
}

export function getAgentDir(stateRoot: string, agentId: string): string {
	return path.join(getAgentsDir(stateRoot), slugify(agentId) || agentId);
}

export function getAgentPromptPath(stateRoot: string, agentId: string): string {
	return path.join(getAgentDir(stateRoot, agentId), "prompt.txt");
}

export function getAgentLaunchPacketPath(stateRoot: string, agentId: string): string {
	return path.join(getAgentDir(stateRoot, agentId), "launch.md");
}

export function getAgentManifestPath(stateRoot: string, agentId: string): string {
	return path.join(getAgentDir(stateRoot, agentId), "agent.json");
}

export function getAgentLauncherPath(stateRoot: string, agentId: string): string {
	return path.join(getAgentDir(stateRoot, agentId), "launch.sh");
}

export function getBridgeLaunchPath(bridgeDir: string): string {
	return path.join(bridgeDir, "bridge.json");
}

export function getBridgeEventsPath(bridgeDir: string): string {
	return path.join(bridgeDir, "events.ndjson");
}

export function getBridgeSignalsDir(bridgeDir: string): string {
	return path.join(bridgeDir, ".signals");
}

export function getBridgeParentStatePath(bridgeDir: string): string {
	return path.join(bridgeDir, "parent", "state.json");
}

export function getBridgeChildStatePath(bridgeDir: string): string {
	return path.join(bridgeDir, "child", "state.json");
}

export function getBridgeReportsDir(bridgeDir: string): string {
	return path.join(bridgeDir, "reports");
}

export function makeSignalName(baseName: string, success: boolean): string {
	return `${baseName}.${success ? "done" : "fail"}`;
}
