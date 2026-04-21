import { reportManagedLauncherExit } from "./launcher-exit.ts";

function readFlag(name: string): string | undefined {
	const index = process.argv.indexOf(name);
	if (index === -1) return undefined;
	return process.argv[index + 1];
}

async function main(): Promise<void> {
	const bridgeDir = readFlag("--bridge-dir");
	const exitStatusRaw = readFlag("--exit-status");
	const logPath = readFlag("--log-path");
	if (!bridgeDir || exitStatusRaw === undefined) {
		throw new Error("launcher-exit requires --bridge-dir and --exit-status");
	}
	const exitStatus = Number(exitStatusRaw);
	if (!Number.isFinite(exitStatus)) {
		throw new Error(`Invalid --exit-status: ${exitStatusRaw}`);
	}
	await reportManagedLauncherExit({ bridgeDir, exitStatus, logPath });
}

main().catch((error) => {
	console.error(String(error instanceof Error ? error.stack ?? error.message : error));
	process.exit(1);
});
