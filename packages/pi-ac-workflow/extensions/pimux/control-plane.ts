import { execFileSync } from "node:child_process";
import { promises as fs, readdirSync, type Dirent } from "node:fs";
import * as path from "node:path";

export const CONTROL_PLANE_LOCK_ENTRY_TYPE = "pimux-control-plane-lock";
export const NO_POLLING_SUPERVISION_ENTRY_TYPE = "pimux-no-polling-supervision";

export type ControlPlaneMode = "mux" | "mux-ospec" | "mux-roadmap";
export type ControlPlanePhase = "pre_spawn" | "post_spawn";
export type ControlPlaneTriggerSource = "skill-command" | "alias-command" | "embedded-skill";

export interface ControlPlaneTrigger {
	mode: ControlPlaneMode;
	source: ControlPlaneTriggerSource;
	specPath?: string;
	requiresSpecPath: boolean;
}

export interface ControlPlaneLockState {
	active: boolean;
	mode?: ControlPlaneMode;
	phase?: ControlPlanePhase;
	lockedAt?: string;
	previousActiveTools?: string[];
	specPath?: string;
	requiresSpecPath?: boolean;
	lastSpawnedAgentId?: string;
	lastChildEventId?: string;
	lastChildActivityAt?: string;
	lastSupervisionResetAt?: string;
	initialVerificationUsed?: boolean;
	recoveryMessageUsed?: boolean;
	settlementVerificationPending?: boolean;
}

export interface ControlPlaneToolDecision {
	allow: boolean;
	reason?: string;
}

export interface NoPollingSupervisionState {
	active: boolean;
	lastSpawnedAgentId?: string;
	lastChildEventId?: string;
	lastChildActivityAt?: string;
	lastSupervisionResetAt?: string;
	settlementVerificationPending?: boolean;
}

export interface PreparedControlPlaneSpawn {
	prompt: string;
	specPath?: string;
	specCreated: boolean;
}

const MODE_ALIASES: Record<string, ControlPlaneMode> = {
	mux: "mux",
	"ac-workflow-mux": "mux",
	"mux-ospec": "mux-ospec",
	"ac-workflow-mux-ospec": "mux-ospec",
	"mux-roadmap": "mux-roadmap",
	"ac-workflow-mux-roadmap": "mux-roadmap",
};

const MUX_OSPEC_MODIFIERS = new Set([
	"FULL",
	"LEAN",
	"LEANEST",
	"CREATE",
	"GATHER",
	"RESEARCH",
	"CONSOLIDATE",
	"SUCCESS_CRITERIA",
	"CONFIRM_SC",
	"PLAN",
	"IMPLEMENT",
	"REVIEW",
	"FIX",
	"TEST",
	"DOCUMENT",
	"SENTINEL",
	"SELF_VALIDATION",
]);

const POST_SPAWN_ALLOWED_ACTIONS = new Set(["spawn", "status", "capture", "tree", "list", "send_message", "open", "kill"]);
const SUPERVISION_CHECK_ACTIONS = new Set(["status", "capture", "tree", "list", "open"]);
const SUPERVISION_RECOVERY_ACTIONS = new Set(["send_message"]);
const UNRESTRICTED_POST_SPAWN_ACTIONS = new Set(["spawn", "kill"]);
const BASH_WAIT_LOOP_PATTERN = /\b(?:while|until|for)\b[\s\S]*\b(?:sleep|wait)\b/i;
const BASH_SLEEP_OR_WAIT_PATTERN = /(?:^|[\s;&|()])(?:sleep\s+\d+(?:\.\d+)?|wait)(?:\s|[;&|)]|$)/i;
const ROADMAP_CONTROL_TOKENS = new Set(["START", "CONTINUE"]);
export const CONTROL_PLANE_INACTIVITY_WATCHDOG_MS = 10 * 60_000;
const CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL = "10m";

interface BranchSpecEntry {
	year: string;
	month: string;
	sequence: number;
}

function tokenize(text: string): string[] {
	const matches = text.match(/"[^"]*"|'[^']*'|\S+/g) ?? [];
	return matches.map(stripQuotes).filter((token) => token.length > 0);
}

function stripQuotes(token: string): string {
	if ((token.startsWith('"') && token.endsWith('"')) || (token.startsWith("'") && token.endsWith("'"))) {
		return token.slice(1, -1);
	}
	return token;
}

function normalizeMode(raw: string | undefined): ControlPlaneMode | undefined {
	if (!raw) return undefined;
	return MODE_ALIASES[raw.trim().toLowerCase()];
}

function normalizeSpecSegment(value: string, maxLength = 80): string {
	return value
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
		.replace(/-{2,}/g, "-")
		.slice(0, maxLength);
}

function isCommandLikeSlashToken(token: string): boolean {
	const value = token.trim();
	return /^\/[a-z0-9:-]+$/i.test(value);
}

function looksLikeExplicitPath(token: string): boolean {
	const value = token.trim();
	if (!value || value.startsWith("-") || isCommandLikeSlashToken(value)) return false;
	return /[\\/]/.test(value) || /\.(?:md|done)$/i.test(value) || value.startsWith(".specs") || value.startsWith("specs/");
}

function extractMuxOspecSpecPath(tokens: string[]): string | undefined {
	const remaining = [...tokens];
	if (remaining.length > 0 && MUX_OSPEC_MODIFIERS.has(remaining[0].toUpperCase())) {
		remaining.shift();
	}
	return remaining.find(looksLikeExplicitPath);
}

function extractExplicitPath(mode: ControlPlaneMode, tokens: string[]): string | undefined {
	if (mode === "mux-ospec") {
		return extractMuxOspecSpecPath(tokens);
	}
	return tokens.find(looksLikeExplicitPath);
}

function extractInlinePrompt(mode: ControlPlaneMode, tokens: string[]): string | undefined {
	const remaining = [...tokens];
	if (mode === "mux-ospec" && remaining.length > 0 && MUX_OSPEC_MODIFIERS.has(remaining[0].toUpperCase())) {
		remaining.shift();
	}
	if (remaining.length > 0 && isCommandLikeSlashToken(remaining[0])) {
		return undefined;
	}
	const promptTokens = remaining.filter((token) => !looksLikeExplicitPath(token) && !token.startsWith("--"));
	if (promptTokens.length === 0) return undefined;
	if (mode === "mux-roadmap" && promptTokens.length === 1 && ROADMAP_CONTROL_TOKENS.has(promptTokens[0].toUpperCase())) {
		return undefined;
	}
	const prompt = promptTokens.join(" ").trim();
	return prompt || undefined;
}

function safeReadDir(directory: string): Dirent[] {
	try {
		return readdirSync(directory, { withFileTypes: true });
	} catch {
		return [];
	}
}

function resolveCurrentBranchSlug(cwd: string): string {
	const commands = [
		["symbolic-ref", "--short", "HEAD"],
		["rev-parse", "--abbrev-ref", "HEAD"],
	] as const;
	for (const args of commands) {
		try {
			const branch = execFileSync("git", [...args], {
				cwd,
				encoding: "utf8",
				stdio: ["ignore", "pipe", "ignore"],
			}).trim();
			if (branch && branch !== "HEAD") {
				return normalizeSpecSegment(branch) || "current-branch";
			}
		} catch {
			// Keep trying the fallback branch-resolution commands.
		}
	}
	return "current-branch";
}

function collectBranchSpecEntries(cwd: string, branchSlug: string): BranchSpecEntry[] {
	const specsRoot = path.join(cwd, ".specs", "specs");
	const entries: BranchSpecEntry[] = [];
	for (const yearEntry of safeReadDir(specsRoot)) {
		if (!yearEntry.isDirectory() || !/^\d{4}$/.test(yearEntry.name)) continue;
		const yearRoot = path.join(specsRoot, yearEntry.name);
		for (const monthEntry of safeReadDir(yearRoot)) {
			if (!monthEntry.isDirectory() || !/^\d{2}$/.test(monthEntry.name)) continue;
			const branchRoot = path.join(yearRoot, monthEntry.name, branchSlug);
			for (const specEntry of safeReadDir(branchRoot)) {
				if (!specEntry.isFile()) continue;
				const match = specEntry.name.match(/^(\d{3})-.*\.md$/i);
				if (!match) continue;
				entries.push({
					year: yearEntry.name,
					month: monthEntry.name,
					sequence: Number.parseInt(match[1], 10),
				});
			}
		}
	}
	return entries;
}

function deriveNextSpecPath(prompt: string, cwd: string): string {
	const branchSlug = resolveCurrentBranchSlug(cwd);
	const branchEntries = collectBranchSpecEntries(cwd, branchSlug).sort((left, right) => {
		return left.year.localeCompare(right.year) || left.month.localeCompare(right.month) || left.sequence - right.sequence;
	});
	const latestEntry = branchEntries.at(-1);
	const year = latestEntry?.year ?? String(new Date().getFullYear());
	const month = latestEntry?.month ?? String(new Date().getMonth() + 1).padStart(2, "0");
	const nextSequence = latestEntry
		? Math.max(
				...branchEntries
					.filter((entry) => entry.year === latestEntry.year && entry.month === latestEntry.month)
					.map((entry) => entry.sequence),
			) + 1
		: 1;
	const filename = `${String(nextSequence).padStart(3, "0")}-${normalizeSpecSegment(prompt) || "spec"}.md`;
	return path.posix.join(".specs", "specs", year, month, branchSlug, filename);
}

function isCanonicalSpecPath(specPath: string): boolean {
	return /^\.specs\/specs\/\d{4}\/\d{2}\/[^/]+\/\d{3}-[^/]+\.md$/i.test(specPath.replace(/\\/g, "/"));
}

function humanizeSpecTitle(specPath: string): string {
	const filename = path.posix.basename(specPath.replace(/\\/g, "/"), ".md");
	const slug = filename.replace(/^\d+-/, "");
	return slug
		.split("-")
		.filter((segment) => segment.length > 0)
		.map((segment) => segment.toUpperCase() === segment ? segment : `${segment.charAt(0).toUpperCase()}${segment.slice(1)}`)
		.join(" ") || "Spec";
}

function buildSpecSeedDocument(specPath: string, prompt: string): string {
	const objective = prompt.trim().replace(/\s+/g, " ") || `Complete ${humanizeSpecTitle(specPath)}.`;
	return [
		"# Human Section",
		"Critical: any text/subsection here cannot be modified by AI.",
		"",
		"## High-Level Objective (HLO)",
		objective,
		"",
		"## Mid-Level Objectives (MLO)",
		"- REFINE this spec from the bound mux prompt.",
		"",
		"## Details (DT)",
		"### Constraints",
		`- Use this exact spec path: \`${specPath}\`.`,
		"- This file was auto-created by the pimux control-plane runtime because the bound spec target did not exist yet.",
		"",
		"## Behavior",
		"Continue the mux-ospec or mux-roadmap run using this bound spec path and fill the remaining sections during the normal stage flow.",
		"",
		"# AI Section",
		"Critical: AI can ONLY modify this section.",
		"",
		"## Research",
		"",
		"## Success Criteria",
		"",
		"## Plan",
		"",
		"## Plan Review",
		"",
		"## Implement",
		"",
		"## Test Evidence & Outputs",
		"",
		"## Updated Doc",
		"",
		"## Post-Implement Review",
	].join("\n");
}

async function ensureBoundSpecPathExists(specPath: string, cwd: string, prompt: string): Promise<boolean> {
	if (!isCanonicalSpecPath(specPath)) return false;
	const resolvedPath = path.resolve(cwd, specPath);
	const relativeFromCwd = path.relative(cwd, resolvedPath);
	if (relativeFromCwd.startsWith("..") || path.isAbsolute(relativeFromCwd)) {
		return false;
	}
	try {
		await fs.access(resolvedPath);
		return false;
	} catch {
		await fs.mkdir(path.dirname(resolvedPath), { recursive: true });
		await fs.writeFile(resolvedPath, `${buildSpecSeedDocument(specPath, prompt)}\n`, "utf-8");
		return true;
	}
}

function buildTrigger(mode: ControlPlaneMode, source: ControlPlaneTriggerSource, tokens: string[], cwd: string): ControlPlaneTrigger {
	const specPath = extractExplicitPath(mode, tokens) ?? (() => {
		if (mode !== "mux-ospec" && mode !== "mux-roadmap") return undefined;
		const inlinePrompt = extractInlinePrompt(mode, tokens);
		return inlinePrompt ? deriveNextSpecPath(inlinePrompt, cwd) : undefined;
	})();
	return {
		mode,
		source,
		specPath,
		requiresSpecPath: (mode === "mux-ospec" || mode === "mux-roadmap") && !specPath,
	};
}

function parseCommandTrigger(text: string, cwd = process.cwd()): ControlPlaneTrigger | undefined {
	const prefixedMatch = text.match(/^\s*(?<prefix>\/skill:|\/)(?<name>ac-workflow-mux-ospec|mux-ospec|ac-workflow-mux-roadmap|mux-roadmap|ac-workflow-mux|mux)\b(?<args>[^\n]*)/i);
	const bareMatch = prefixedMatch
		? undefined
		: text.match(/^\s*(?<name>ac-workflow-mux-ospec|mux-ospec|ac-workflow-mux-roadmap|mux-roadmap|ac-workflow-mux|mux)\b(?<args>[^\n]*)/i);
	const match = prefixedMatch ?? bareMatch;
	const mode = normalizeMode(match?.groups?.name);
	if (!mode) return undefined;
	const args = tokenize(match?.groups?.args ?? "");
	return buildTrigger(mode, prefixedMatch?.groups?.prefix === "/skill:" ? "skill-command" : "alias-command", args, cwd);
}

function parseEmbeddedSkillTrigger(text: string, cwd = process.cwd()): ControlPlaneTrigger | undefined {
	const skillMatch = text.match(/<skill\b[^>]*\bname="(?<name>[^"]+)"[^>]*>/i);
	const mode = normalizeMode(skillMatch?.groups?.name);
	if (!mode) return undefined;
	const remainder = text.split(/<\/skill>/i).slice(1).join("\n");
	return buildTrigger(mode, "embedded-skill", tokenize(remainder), cwd);
}

export function parseExplicitControlPlaneTrigger(text: string, cwd = process.cwd()): ControlPlaneTrigger | undefined {
	return parseCommandTrigger(text, cwd) ?? parseEmbeddedSkillTrigger(text, cwd);
}

export function extractSpecPathFromUserInput(text: string, cwd = process.cwd()): string | undefined {
	const explicitTrigger = parseExplicitControlPlaneTrigger(text, cwd);
	if (explicitTrigger?.specPath) {
		return explicitTrigger.specPath;
	}
	return tokenize(text).find(looksLikeExplicitPath);
}

export function resolvePendingControlPlaneSpecPath(
	lock: ControlPlaneLockState | undefined,
	text: string,
	cwd = process.cwd(),
): string | undefined {
	const explicitSpecPath = extractSpecPathFromUserInput(text, cwd);
	if (explicitSpecPath) {
		return explicitSpecPath;
	}
	if (!lock?.active || !lock.mode || !lock.requiresSpecPath) {
		return undefined;
	}
	if (lock.mode !== "mux-ospec" && lock.mode !== "mux-roadmap") {
		return undefined;
	}
	const inlinePrompt = extractInlinePrompt(lock.mode, tokenize(text));
	return inlinePrompt ? deriveNextSpecPath(inlinePrompt, cwd) : undefined;
}

export async function prepareControlPlaneSpawn(
	lock: ControlPlaneLockState | undefined,
	prompt: string,
	cwd = process.cwd(),
): Promise<PreparedControlPlaneSpawn> {
	const trimmedPrompt = prompt.trim();
	if (!trimmedPrompt) {
		throw new Error("spawn requires prompt");
	}
	if (!lock?.active || !lock.mode || !lock.specPath || (lock.mode !== "mux-ospec" && lock.mode !== "mux-roadmap")) {
		return {
			prompt: trimmedPrompt,
			specCreated: false,
		};
	}
	const specCreated = await ensureBoundSpecPathExists(lock.specPath, cwd, trimmedPrompt);
	const boundPrompt = trimmedPrompt.includes(lock.specPath)
		? trimmedPrompt
		: `Use this spec path for the run, and create it first if missing:\n${lock.specPath}\n\n${trimmedPrompt}`;
	return {
		prompt: boundPrompt,
		specPath: lock.specPath,
		specCreated,
	};
}

export function buildControlPlaneLock(trigger: ControlPlaneTrigger, previousActiveTools?: string[]): ControlPlaneLockState {
	return {
		active: true,
		mode: trigger.mode,
		phase: "pre_spawn",
		lockedAt: new Date().toISOString(),
		previousActiveTools,
		specPath: trigger.specPath,
		requiresSpecPath: trigger.requiresSpecPath,
	};
}

function parseTimestampMs(value: string | undefined): number | undefined {
	if (!value) return undefined;
	const parsed = Date.parse(value);
	return Number.isFinite(parsed) ? parsed : undefined;
}

function resolveNowMs(now?: string | number): number {
	if (typeof now === "number" && Number.isFinite(now)) return now;
	if (typeof now === "string") {
		const parsed = Date.parse(now);
		if (Number.isFinite(parsed)) return parsed;
	}
	return Date.now();
}

function resolveNowIso(now?: string | number): string {
	return new Date(resolveNowMs(now)).toISOString();
}

function isSupervisionCheckAction(action: string): boolean {
	return SUPERVISION_CHECK_ACTIONS.has(action);
}

function isRecoveryAction(action: string): boolean {
	return SUPERVISION_RECOVERY_ACTIONS.has(action);
}

function isTrackedDirectChild(lock: ControlPlaneLockState, agentId?: string): boolean {
	return !lock.lastSpawnedAgentId || !agentId || lock.lastSpawnedAgentId === agentId;
}

function isInactivityWatchdogReached(lock: ControlPlaneLockState, now?: string | number): boolean {
	const referenceMs = parseTimestampMs(lock.lastSupervisionResetAt) ?? parseTimestampMs(lock.lastChildActivityAt);
	if (referenceMs === undefined) return false;
	return resolveNowMs(now) - referenceMs >= CONTROL_PLANE_INACTIVITY_WATCHDOG_MS;
}

function hasDeliveredChildActivity(lock: ControlPlaneLockState): boolean {
	return Boolean(lock.lastChildActivityAt || lock.lastChildEventId || lock.settlementVerificationPending);
}

function buildPostSpawnSupervisionState(
	lock: ControlPlaneLockState,
	occurredAt: string,
	options: {
		agentId?: string;
		eventId?: string;
		settlementVerificationPending?: boolean;
	},
): ControlPlaneLockState {
	return {
		...lock,
		phase: "post_spawn",
		lastSpawnedAgentId: options.agentId ?? lock.lastSpawnedAgentId,
		lastChildEventId: options.eventId ?? lock.lastChildEventId,
		lastChildActivityAt: occurredAt,
		lastSupervisionResetAt: occurredAt,
		initialVerificationUsed: false,
		recoveryMessageUsed: false,
		settlementVerificationPending: options.settlementVerificationPending ?? false,
	};
}

function buildNotifyFirstReason(lock: ControlPlaneLockState, detail: string): ControlPlaneToolDecision {
	return {
		allow: false,
		reason: buildRestrictedReason(lock, detail),
	};
}

function buildNoPollingReason(detail: string): ControlPlaneToolDecision {
	return {
		allow: false,
		reason: `pimux no-polling supervision is active. ${detail}`,
	};
}

function isRoutineWaitBashCommand(command: unknown): boolean {
	if (typeof command !== "string") return false;
	const trimmed = command.trim();
	if (!trimmed) return false;
	return BASH_WAIT_LOOP_PATTERN.test(trimmed) || BASH_SLEEP_OR_WAIT_PATTERN.test(trimmed);
}

export function resolveControlPlaneSpecPath(lock: ControlPlaneLockState, specPath: string): ControlPlaneLockState {
	if (!lock.active) return lock;
	return {
		...lock,
		specPath,
		requiresSpecPath: false,
	};
}

export function buildUnlockedControlPlaneLock(previousActiveTools?: string[]): ControlPlaneLockState {
	return {
		active: false,
		previousActiveTools,
	};
}

export function buildNoPollingSupervisionForSpawn(agentId: string | undefined, now?: string | number): NoPollingSupervisionState {
	return {
		active: true,
		lastSpawnedAgentId: agentId,
		lastSupervisionResetAt: resolveNowIso(now),
		settlementVerificationPending: false,
	};
}

function normalizeToolName(value: string | undefined): string {
	return String(value ?? "").trim().toLowerCase();
}

function isAskUserQuestionTool(toolName: string): boolean {
	return normalizeToolName(toolName) === "askuserquestion";
}

function isPimuxTool(toolName: string): boolean {
	return normalizeToolName(toolName) === "pimux";
}

function isSayTool(toolName: string): boolean {
	return normalizeToolName(toolName) === "say";
}

function isBashTool(toolName: string): boolean {
	return normalizeToolName(toolName) === "bash";
}

function buildRestrictedReason(lock: ControlPlaneLockState, detail: string): string {
	return `Explicit ${lock.mode ?? "mux-family"} parent is control-plane locked. ${detail}`;
}

export function evaluateNoPollingSupervisionToolCall(
	supervision: NoPollingSupervisionState | undefined,
	event: { toolName?: string; input?: Record<string, unknown> },
	now?: string | number,
): ControlPlaneToolDecision {
	if (!supervision?.active) return { allow: true };

	if (isPimuxTool(event.toolName)) {
		const action = String(event.input?.action ?? "").trim();
		if (!action || !isSupervisionCheckAction(action)) return { allow: true };
		if (supervision.settlementVerificationPending && action === "status") return { allow: true };
		if (supervision.settlementVerificationPending) {
			return buildNoPollingReason("Terminal settlement is ready. Use one final pimux status check, then stop supervising this child.");
		}
		if (isInactivityWatchdogReached(supervision, now)) return { allow: true };
		return buildNoPollingReason(
			`Do not poll pimux; wait for delivered child activity. status/capture/tree/list/open are recovery-only and allowed only after terminal settlement or the ${CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL} inactivity watchdog.`,
		);
	}

	if (isBashTool(event.toolName) && isRoutineWaitBashCommand(event.input?.command)) {
		return buildNoPollingReason(
			"Do not use Bash sleep/wait loops for supervision; stop and wait for delivered bridge activity instead.",
		);
	}

	return { allow: true };
}

export function evaluateControlPlaneToolCall(
	lock: ControlPlaneLockState | undefined,
	event: { toolName?: string; input?: Record<string, unknown> },
	now?: string | number,
): ControlPlaneToolDecision {
	if (!lock?.active || !lock.mode || !lock.phase) {
		return { allow: true };
	}

	if (isSayTool(event.toolName) || isAskUserQuestionTool(event.toolName)) {
		return { allow: true };
	}

	if (!isPimuxTool(event.toolName)) {
		return {
			allow: false,
			reason: buildRestrictedReason(
				lock,
				"Only pimux, AskUserQuestion, and say are allowed in the parent while the wrapper lock is active.",
			),
		};
	}

	const action = String(event.input?.action ?? "").trim();
	if (!action) {
		return {
			allow: false,
			reason: buildRestrictedReason(lock, "pimux calls must declare an action."),
		};
	}

	if (lock.phase === "pre_spawn") {
		if (action !== "spawn") {
			return {
				allow: false,
				reason: buildRestrictedReason(
					lock,
					"Before the first child exists, the only allowed pimux action is spawn.",
				),
			};
		}
		if (lock.requiresSpecPath) {
			const missingInputReason =
				lock.mode === "mux-roadmap"
					? "Explicit mux-roadmap requires an explicit roadmap/spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either."
					: "Explicit mux-ospec requires an explicit spec path or inline prompt before pimux spawn. Use AskUserQuestion only when the user has not provided either.";
			return {
				allow: false,
				reason: buildRestrictedReason(lock, missingInputReason),
			};
		}
		return { allow: true };
	}

	if (!POST_SPAWN_ALLOWED_ACTIONS.has(action)) {
		return {
			allow: false,
			reason: buildRestrictedReason(
				lock,
				`After spawn, parent supervision is limited to pimux ${[...POST_SPAWN_ALLOWED_ACTIONS].join(", ")}, plus AskUserQuestion and say.`,
			),
		};
	}

	if (UNRESTRICTED_POST_SPAWN_ACTIONS.has(action)) {
		return { allow: true };
	}

	if (lock.settlementVerificationPending) {
		if (action === "status") {
			return { allow: true };
		}
		return buildNotifyFirstReason(
			lock,
			"Terminal settlement is ready. Use one final pimux status check, then stop supervising this child.",
		);
	}

	if (isSupervisionCheckAction(action)) {
		if (isInactivityWatchdogReached(lock, now)) {
			return { allow: true };
		}
		return buildNotifyFirstReason(
			lock,
			`Notify-first pacing is active. Do not poll pimux; wait for delivered child activity. status/capture/tree/list/open are recovery-only and allowed only after terminal settlement or the ${CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL} inactivity watchdog.`,
		);
	}

	if (isRecoveryAction(action)) {
		const watchdogReached = isInactivityWatchdogReached(lock, now);
		if (lock.recoveryMessageUsed && !watchdogReached) {
			return buildNotifyFirstReason(
				lock,
				`Notify-first pacing is active. A recovery send_message already went out for the current activity window. Wait for new child activity or the ${CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL} inactivity watchdog before nudging again.`,
			);
		}
		if (!hasDeliveredChildActivity(lock) && !watchdogReached) {
			return buildNotifyFirstReason(
				lock,
				`Notify-first pacing is active. Wait for a delivered child report before sending messages, unless the ${CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL} inactivity watchdog has fired for recovery.`,
			);
		}
		return { allow: true };
	}

	return { allow: true };
}

export function updateNoPollingSupervisionForToolResult(
	supervision: NoPollingSupervisionState | undefined,
	event: { toolName?: string; details?: Record<string, unknown>; isError?: boolean },
	now?: string | number,
): NoPollingSupervisionState | undefined {
	if (!supervision?.active || !isPimuxTool(event.toolName)) return supervision;
	const action = String(event.details?.action ?? "").trim();
	if (!action || event.isError || typeof event.details?.error === "string") return supervision;
	const occurredAt = resolveNowIso(now);
	if (supervision.settlementVerificationPending && action === "status") {
		return {
			...supervision,
			active: false,
			lastSupervisionResetAt: occurredAt,
			settlementVerificationPending: false,
		};
	}
	if (isSupervisionCheckAction(action) && isInactivityWatchdogReached(supervision, now)) {
		return {
			...supervision,
			lastSupervisionResetAt: occurredAt,
		};
	}
	return supervision;
}

export function updateControlPlaneLockForToolResult(
	lock: ControlPlaneLockState | undefined,
	event: { toolName?: string; details?: Record<string, unknown>; isError?: boolean },
	now?: string | number,
): ControlPlaneLockState | undefined {
	if (!lock?.active || !lock.mode) return lock;
	if (!isPimuxTool(event.toolName)) return lock;
	const action = String(event.details?.action ?? "").trim();
	if (!action) return lock;
	if (event.isError || typeof event.details?.error === "string") return lock;

	const occurredAt = resolveNowIso(now);
	if (action === "spawn") {
		const agent = event.details?.agent;
		const agentId = agent && typeof agent === "object" && typeof (agent as { agentId?: unknown }).agentId === "string"
			? (agent as { agentId: string }).agentId
			: undefined;
		return {
			...lock,
			phase: "post_spawn",
			lastSpawnedAgentId: agentId ?? lock.lastSpawnedAgentId,
			lastSupervisionResetAt: occurredAt,
			initialVerificationUsed: false,
			recoveryMessageUsed: false,
			settlementVerificationPending: false,
		};
	}

	if (lock.phase !== "post_spawn") return lock;

	if (lock.settlementVerificationPending && action === "status") {
		return {
			...lock,
			lastSupervisionResetAt: occurredAt,
			initialVerificationUsed: true,
			recoveryMessageUsed: true,
			settlementVerificationPending: false,
		};
	}

	if (isSupervisionCheckAction(action)) {
		return {
			...lock,
			lastSupervisionResetAt: isInactivityWatchdogReached(lock, now) ? occurredAt : lock.lastSupervisionResetAt,
			initialVerificationUsed: true,
			recoveryMessageUsed: isInactivityWatchdogReached(lock, now) ? false : lock.recoveryMessageUsed,
		};
	}

	if (isRecoveryAction(action)) {
		return {
			...lock,
			lastSupervisionResetAt: isInactivityWatchdogReached(lock, now) ? occurredAt : lock.lastSupervisionResetAt,
			recoveryMessageUsed: true,
		};
	}

	return lock;
}

export function updateNoPollingSupervisionForChildActivity(
	supervision: NoPollingSupervisionState | undefined,
	event: { agentId?: string; eventId?: string; timestamp?: string },
	now?: string | number,
): NoPollingSupervisionState | undefined {
	if (!supervision?.active || !isTrackedDirectChild({ active: true, lastSpawnedAgentId: supervision.lastSpawnedAgentId }, event.agentId)) {
		return supervision;
	}
	const occurredAt = event.timestamp?.trim() || resolveNowIso(now);
	return {
		...supervision,
		lastSpawnedAgentId: event.agentId ?? supervision.lastSpawnedAgentId,
		lastChildEventId: event.eventId ?? supervision.lastChildEventId,
		lastChildActivityAt: occurredAt,
		lastSupervisionResetAt: occurredAt,
		settlementVerificationPending: false,
	};
}

export function updateNoPollingSupervisionForTerminalSettlement(
	supervision: NoPollingSupervisionState | undefined,
	event: { agentId?: string; eventId?: string; timestamp?: string },
	now?: string | number,
): NoPollingSupervisionState | undefined {
	if (!supervision?.active || !isTrackedDirectChild({ active: true, lastSpawnedAgentId: supervision.lastSpawnedAgentId }, event.agentId)) {
		return supervision;
	}
	const occurredAt = event.timestamp?.trim() || resolveNowIso(now);
	return {
		...supervision,
		lastSpawnedAgentId: event.agentId ?? supervision.lastSpawnedAgentId,
		lastChildEventId: event.eventId ?? supervision.lastChildEventId,
		lastChildActivityAt: occurredAt,
		lastSupervisionResetAt: occurredAt,
		settlementVerificationPending: true,
	};
}

export function updateControlPlaneLockForChildActivity(
	lock: ControlPlaneLockState | undefined,
	event: { agentId?: string; eventId?: string; timestamp?: string },
	now?: string | number,
): ControlPlaneLockState | undefined {
	if (!lock?.active || !lock.mode || lock.phase !== "post_spawn") return lock;
	if (!isTrackedDirectChild(lock, event.agentId)) return lock;
	const occurredAt = event.timestamp?.trim() || resolveNowIso(now);
	const nextLock = buildPostSpawnSupervisionState(lock, occurredAt, {
		agentId: event.agentId,
		eventId: event.eventId,
	});
	if (
		nextLock.lastChildEventId === lock.lastChildEventId
		&& nextLock.lastChildActivityAt === lock.lastChildActivityAt
		&& nextLock.lastSupervisionResetAt === lock.lastSupervisionResetAt
		&& nextLock.initialVerificationUsed === lock.initialVerificationUsed
		&& nextLock.recoveryMessageUsed === lock.recoveryMessageUsed
		&& nextLock.settlementVerificationPending === lock.settlementVerificationPending
	) {
		return lock;
	}
	return nextLock;
}

export function updateControlPlaneLockForTerminalSettlement(
	lock: ControlPlaneLockState | undefined,
	event: { agentId?: string; eventId?: string; timestamp?: string },
	now?: string | number,
): ControlPlaneLockState | undefined {
	if (!lock?.active || !lock.mode || lock.phase !== "post_spawn") return lock;
	if (!isTrackedDirectChild(lock, event.agentId)) return lock;
	const occurredAt = event.timestamp?.trim() || resolveNowIso(now);
	const nextLock = buildPostSpawnSupervisionState(lock, occurredAt, {
		agentId: event.agentId,
		eventId: event.eventId,
		settlementVerificationPending: true,
	});
	if (
		nextLock.lastChildEventId === lock.lastChildEventId
		&& nextLock.lastChildActivityAt === lock.lastChildActivityAt
		&& nextLock.lastSupervisionResetAt === lock.lastSupervisionResetAt
		&& nextLock.initialVerificationUsed === lock.initialVerificationUsed
		&& nextLock.recoveryMessageUsed === lock.recoveryMessageUsed
		&& nextLock.settlementVerificationPending === lock.settlementVerificationPending
	) {
		return lock;
	}
	return nextLock;
}

export function normalizeControlPlaneLockState(data: unknown): ControlPlaneLockState | undefined {
	if (!data || typeof data !== "object" || Array.isArray(data)) return undefined;
	const record = data as Record<string, unknown>;
	if (typeof record.active !== "boolean") return undefined;

	const previousActiveTools = Array.isArray(record.previousActiveTools)
		? record.previousActiveTools.filter((item): item is string => typeof item === "string")
		: undefined;

	if (!record.active) {
		return {
			active: false,
			previousActiveTools,
		};
	}

	const mode = normalizeMode(typeof record.mode === "string" ? record.mode : undefined);
	const phase = record.phase === "pre_spawn" || record.phase === "post_spawn" ? record.phase : undefined;
	if (!mode || !phase) return undefined;

	return {
		active: true,
		mode,
		phase,
		lockedAt: typeof record.lockedAt === "string" ? record.lockedAt : undefined,
		previousActiveTools,
		specPath: typeof record.specPath === "string" ? record.specPath : undefined,
		requiresSpecPath: typeof record.requiresSpecPath === "boolean" ? record.requiresSpecPath : false,
		lastSpawnedAgentId: typeof record.lastSpawnedAgentId === "string" ? record.lastSpawnedAgentId : undefined,
		lastChildEventId: typeof record.lastChildEventId === "string" ? record.lastChildEventId : undefined,
		lastChildActivityAt: typeof record.lastChildActivityAt === "string" ? record.lastChildActivityAt : undefined,
		lastSupervisionResetAt: typeof record.lastSupervisionResetAt === "string" ? record.lastSupervisionResetAt : undefined,
		initialVerificationUsed: typeof record.initialVerificationUsed === "boolean" ? record.initialVerificationUsed : false,
		recoveryMessageUsed: typeof record.recoveryMessageUsed === "boolean" ? record.recoveryMessageUsed : false,
		settlementVerificationPending: typeof record.settlementVerificationPending === "boolean" ? record.settlementVerificationPending : false,
	};
}

export function normalizeNoPollingSupervisionState(data: unknown): NoPollingSupervisionState | undefined {
	if (!data || typeof data !== "object" || Array.isArray(data)) return undefined;
	const record = data as Record<string, unknown>;
	if (typeof record.active !== "boolean") return undefined;
	if (!record.active) return { active: false };
	return {
		active: true,
		lastSpawnedAgentId: typeof record.lastSpawnedAgentId === "string" ? record.lastSpawnedAgentId : undefined,
		lastChildEventId: typeof record.lastChildEventId === "string" ? record.lastChildEventId : undefined,
		lastChildActivityAt: typeof record.lastChildActivityAt === "string" ? record.lastChildActivityAt : undefined,
		lastSupervisionResetAt: typeof record.lastSupervisionResetAt === "string" ? record.lastSupervisionResetAt : undefined,
		settlementVerificationPending: typeof record.settlementVerificationPending === "boolean" ? record.settlementVerificationPending : false,
	};
}

export function buildControlPlaneSystemPrompt(lock: ControlPlaneLockState | undefined): string | undefined {
	if (!lock?.active || !lock.mode || !lock.phase) return undefined;
	const lines = [
		"FIRST: do not poll pimux and do not use Bash sleep/wait loops; wait for delivered child activity.",
		"pimux control-plane lock is active.",
		`- wrapper mode: ${lock.mode}`,
		"- parent may use only pimux, AskUserQuestion, and say while this lock is active.",
		lock.phase === "pre_spawn"
			? "- Phase A before first child report: the only allowed pimux action is spawn."
			: "- Phase B/C after spawn: wait for delivered child reports; send_message only after child activity; status/capture/tree/list/open are recovery-only.",
		"- do not use parent-side Read/Bash/Edit/Write/NotebookEdit/Grep/Glob/web_search/subagent for repo work.",
	];
	if (lock.phase === "post_spawn") {
		lines.push("- PIMUX HAPPY-PATH DISCIPLINE: this run is notify-first, not poll-first.");
		lines.push("- Do not poll pimux or use Bash sleep/wait loops; wait for delivered child activity, and treat status/capture/tree/list/open as recovery-only.");
		lines.push("- Allowed happy-path sequence: spawn -> wait for child report -> send_message once if needed -> wait for closeout -> final status verification.");
		lines.push(
			`- Use status/capture/tree/list/open only for explicit live inspection, suspected stall/protocol violation/failure, terminal settlement verification, or the ${CONTROL_PLANE_INACTIVITY_WATCHDOG_LABEL} inactivity watchdog.`,
		);
		lines.push("- after terminal settlement, use one final pimux status check before advancing.");
	}
	if (lock.mode === "mux-ospec" || lock.mode === "mux-roadmap") {
		if (lock.specPath) {
			lines.push(`- bound spec path: ${lock.specPath}`);
			lines.push("- create the bound spec file before spawn if it does not exist yet.");
		} else if (lock.requiresSpecPath) {
			lines.push(
				lock.mode === "mux-roadmap"
					? "- explicit mux-roadmap still needs an explicit roadmap/spec path or inline prompt; use AskUserQuestion only when the user has not provided either."
					: "- explicit mux-ospec still needs an explicit spec path or inline prompt; use AskUserQuestion only when the user has not provided either.",
			);
		}
	}
	return lines.join("\n");
}
