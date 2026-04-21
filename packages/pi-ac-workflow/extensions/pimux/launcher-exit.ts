import { promises as fs } from "node:fs";
import { appendBridgeEvent, readBridgeEvents, readBridgeLaunch, writeBridgeEventSignal, writeBridgeReport } from "./bridge.ts";

function hasTerminalChildReport(events: Awaited<ReturnType<typeof readBridgeEvents>>): boolean {
	return events.some(
		(event) =>
			event.direction === "child_to_parent" &&
			(event.type === "closeout" || event.type === "failure" || event.type === "blocker" || event.type === "question"),
	);
}

function hasExitedEvent(events: Awaited<ReturnType<typeof readBridgeEvents>>): boolean {
	return events.some((event) => event.direction === "system" && event.type === "exited");
}

async function readLogTail(logPath: string | undefined, maxChars = 4000): Promise<string | undefined> {
	if (!logPath) return undefined;
	try {
		const text = await fs.readFile(logPath, "utf-8");
		if (text.length <= maxChars) return text.trim();
		return text.slice(-maxChars).trim();
	} catch {
		return undefined;
	}
}

async function appendExitedEventIfMissing(bridgeDir: string): Promise<void> {
	const launch = await readBridgeLaunch(bridgeDir);
	const events = await readBridgeEvents(bridgeDir);
	if (hasExitedEvent(events)) return;
	const exitedEvent = await appendBridgeEvent(bridgeDir, {
		launchId: launch.launchId,
		direction: "system",
		type: "exited",
		from: { agentId: launch.agentId, sessionName: launch.sessionName },
		summary: `${launch.agentId} exited before managed terminal settlement was finalized`,
	});
	await writeBridgeEventSignal(bridgeDir, exitedEvent, true);
}

export async function reportManagedLauncherExit(params: {
	bridgeDir: string;
	exitStatus: number;
	logPath?: string;
}): Promise<void> {
	const launch = await readBridgeLaunch(params.bridgeDir);
	const events = await readBridgeEvents(params.bridgeDir);

	if (hasTerminalChildReport(events)) {
		await appendExitedEventIfMissing(params.bridgeDir);
		return;
	}

	if (params.exitStatus !== 0) {
		const logTail = await readLogTail(params.logPath);
		const reportLines = [
			"## Managed child launcher failure",
			"",
			`- Agent ID: ${launch.agentId}`,
			`- Session Name: ${launch.sessionName}`,
			`- Working Directory: ${launch.cwd}`,
			`- Model: ${launch.model}`,
			`- Exit Status: ${params.exitStatus}`,
			launch.extensionPath ? `- Extension Path: ${launch.extensionPath}` : undefined,
			params.logPath ? `- Log Path: ${params.logPath}` : undefined,
			"",
			"## Summary",
			"The managed pimux child exited before it could complete a valid terminal handoff.",
			logTail
				? [
					"",
					"## Launcher Log Tail",
					"```text",
					logTail,
					"```",
				].join("\n")
				: undefined,
		]
			.filter((line): line is string => Boolean(line));
		const { reportPath } = await writeBridgeReport(params.bridgeDir, "failure", reportLines.join("\n"));
		const failureEvent = await appendBridgeEvent(params.bridgeDir, {
			launchId: launch.launchId,
			direction: "child_to_parent",
			type: "failure",
			from: { agentId: launch.agentId, sessionName: launch.sessionName },
			to: launch.parentAgentId ? { agentId: launch.parentAgentId } : undefined,
			summary: `${launch.agentId} exited before terminal handoff (status ${params.exitStatus})`,
			reportPath,
		});
		await writeBridgeEventSignal(params.bridgeDir, failureEvent, true);
	}

	await appendExitedEventIfMissing(params.bridgeDir);
}
