import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import {
	ENV_AGENT_ID,
	ENV_BRIDGE_DIR,
	ENV_CONTEXT_BRIEF,
	ENV_EXTENSION_PATH,
	ENV_GOAL,
	ENV_LAUNCH_ID,
	ENV_NOTIFICATION_MODE,
	ENV_PARENT_AGENT_ID,
	ENV_PARENT_SESSION_KEY,
	ENV_ROLE,
	ENV_ROOT_AGENT_ID,
	ENV_ROOT_OWNER_SESSION_KEY,
	ENV_STATE_ROOT,
	SESSION_WINDOW,
	shellQuote,
} from "./paths.ts";

export interface RunCommandOptions {
	cwd?: string;
	input?: string;
	signal?: AbortSignal;
}

export interface RunCommandResult {
	code: number;
	stdout: string;
	stderr: string;
}

export interface ManagedVisualRef {
	kind: "iterm-session";
	sessionUniqueId: string;
	openedAt: string;
}

export async function runCommand(
	command: string,
	args: string[],
	options: RunCommandOptions = {},
): Promise<RunCommandResult> {
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

export async function tmuxHasSession(sessionName: string): Promise<boolean> {
	const result = await runCommand("tmux", ["has-session", "-t", sessionName]);
	if (result.code === 0) return true;
	if (result.code === 1) return false;
	throw new Error(result.stderr.trim() || result.stdout.trim() || `tmux has-session failed for ${sessionName}`);
}

export async function createTmuxSession(sessionName: string, cwd: string, launcherPath: string): Promise<void> {
	const result = await runCommand("tmux", ["new-session", "-d", "-s", sessionName, "-n", SESSION_WINDOW, "-c", cwd, launcherPath]);
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to create tmux session ${sessionName}`);
	}
}

export async function captureTmuxPane(sessionName: string, lines = 80): Promise<string> {
	const target = `${sessionName}:${SESSION_WINDOW}`;
	const result = await runCommand("tmux", ["capture-pane", "-p", "-t", target, "-S", `-${Math.max(1, lines)}`]);
	if (result.code !== 0) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to capture tmux pane for ${sessionName}`);
	}
	return result.stdout;
}

export async function killTmuxSession(sessionName: string): Promise<void> {
	const result = await runCommand("tmux", ["kill-session", "-t", sessionName]);
	if (result.code !== 0 && !(result.stderr.includes("can't find session") || result.stdout.includes("can't find session"))) {
		throw new Error(result.stderr.trim() || result.stdout.trim() || `Failed to kill tmux session ${sessionName}`);
	}
}

export function parseManagedVisualRef(output: string): ManagedVisualRef {
	const sessionUniqueId = output.trim();
	if (!sessionUniqueId) throw new Error("Failed to capture iTerm session unique id");
	return {
		kind: "iterm-session",
		sessionUniqueId,
		openedAt: new Date().toISOString(),
	};
}

export async function openItermTab(cwd: string, sessionName: string): Promise<ManagedVisualRef> {
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

export async function closeItermTab(visual: ManagedVisualRef): Promise<boolean> {
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

export async function closeItermTabs(visuals: ManagedVisualRef[]): Promise<{ closedCount: number; missingCount: number }> {
	let closedCount = 0;
	let missingCount = 0;
	for (const visual of visuals) {
		const closed = await closeItermTab(visual);
		if (closed) closedCount += 1;
		else missingCount += 1;
	}
	return { closedCount, missingCount };
}

function getPiInvocation(): { command: string; args: string[] } {
	const currentScript = process.argv[1];
	if (currentScript) {
		return { command: process.execPath, args: [currentScript] };
	}
	return { command: "pi", args: [] };
}

function shellArray(values: string[]): string {
	return values.map((value) => shellQuote(value)).join(" ");
}

export function buildSessionName(agentId: string): string {
	return `pi-${agentId}`.slice(0, 48).replace(/\.+$/, "");
}

export async function writeLauncherScript(params: {
	launcherPath: string;
	promptPath: string;
	cwd: string;
	model: string;
	agentId: string;
	parentAgentId?: string;
	rootAgentId: string;
	role?: string;
	goal?: string;
	bridgeDir: string;
	launchId: string;
	parentSessionKey: string;
	notificationMode: string;
	contextBrief?: string;
	stateRoot: string;
	rootOwnerSessionKey: string;
	extensionPath: string;
	extensionPaths: string[];
}): Promise<void> {
	const invocation = getPiInvocation();
	const commandParts = [
		invocation.command,
		...invocation.args,
		"--no-extensions",
		...params.extensionPaths.flatMap((extensionPath) => ["-e", extensionPath]),
		"--model",
		params.model,
	];
	const launcherExitHelperPath = fileURLToPath(new URL("./launcher-exit-cli.ts", import.meta.url));
	const launcherExitCommandParts = [process.execPath, "--experimental-strip-types", launcherExitHelperPath];
	const launcherLogPath = path.join(params.bridgeDir, "child", "pi.log");
	const script = `#!/usr/bin/env bash
set -uo pipefail
export ${ENV_AGENT_ID}=${shellQuote(params.agentId)}
export ${ENV_PARENT_AGENT_ID}=${shellQuote(params.parentAgentId ?? "")}
export ${ENV_ROOT_AGENT_ID}=${shellQuote(params.rootAgentId)}
export ${ENV_ROLE}=${shellQuote(params.role ?? "")}
export ${ENV_GOAL}=${shellQuote(params.goal ?? "")}
export ${ENV_BRIDGE_DIR}=${shellQuote(params.bridgeDir)}
export ${ENV_LAUNCH_ID}=${shellQuote(params.launchId)}
export ${ENV_PARENT_SESSION_KEY}=${shellQuote(params.parentSessionKey)}
export ${ENV_NOTIFICATION_MODE}=${shellQuote(params.notificationMode)}
export ${ENV_CONTEXT_BRIEF}=${shellQuote(params.contextBrief ?? "")}
export ${ENV_STATE_ROOT}=${shellQuote(params.stateRoot)}
export ${ENV_ROOT_OWNER_SESSION_KEY}=${shellQuote(params.rootOwnerSessionKey)}
export ${ENV_EXTENSION_PATH}=${shellQuote(params.extensionPath)}
cd ${shellQuote(params.cwd)}
clear
printf 'Starting pimux agent %s\nWorking dir: %s\nModel: %s\nBridge: %s\n\n' ${shellQuote(params.agentId)} ${shellQuote(params.cwd)} ${shellQuote(params.model)} ${shellQuote(params.launchId)}
PROMPT=$(cat ${shellQuote(params.promptPath)})
PI_CMD=(${shellArray(commandParts)})
PI_EXIT_CMD=(${shellArray(launcherExitCommandParts)})
PI_LOG=${shellQuote(launcherLogPath)}
"\${PI_CMD[@]}" "$PROMPT" 2>&1 | tee "$PI_LOG"
status=\${PIPESTATUS[0]}
printf '\n[pi exited with status %s]\n' "$status"
"\${PI_EXIT_CMD[@]}" --bridge-dir ${shellQuote(params.bridgeDir)} --exit-status "$status" --log-path "$PI_LOG" || true
exit "$status"
`;
	await fs.mkdir(path.dirname(params.launcherPath), { recursive: true });
	await fs.writeFile(params.launcherPath, script, { encoding: "utf-8", mode: 0o755 });
	await fs.chmod(params.launcherPath, 0o755);
}

export function extensionEntryPath(): string {
	return fileURLToPath(new URL("./index.ts", import.meta.url));
}
