import type { BridgeEvent, BridgeLaunchFile } from "./bridge.ts";
import { readBoundedReportSummary } from "./bridge.ts";
import { truncate } from "./paths.ts";
import type { SettledTerminalState } from "./settlement.ts";

function resolveEventRoute(
	event: BridgeEvent,
	launch: BridgeLaunchFile,
): { from?: string; to?: string } {
	if (event.direction === "system") {
		return { from: event.from?.agentId ?? launch.agentId };
	}
	if (event.direction === "parent_to_child") {
		return {
			from: event.from?.agentId ?? launch.parentAgentId ?? "parent",
			to: event.to?.agentId ?? launch.agentId,
		};
	}
	return {
		from: event.from?.agentId ?? launch.agentId,
		to: event.to?.agentId ?? launch.parentAgentId ?? "parent",
	};
}

function buildParentDeliveryHeader(event: BridgeEvent, launch: BridgeLaunchFile): string {
	const route = resolveEventRoute(event, launch);
	if (!route.from || !route.to || event.direction === "system") {
		return `[pimux ${event.type}] ${launch.agentId}`;
	}
	return `[pimux ${event.type}] ${route.from} -> ${route.to}`;
}

export async function buildParentDeliveryContent(
	event: BridgeEvent,
	launch: BridgeLaunchFile,
	options?: {
		terminalEventId?: string;
		finalizedAt?: string;
		settledState?: SettledTerminalState;
		settlementReason?: string;
	},
): Promise<string> {
	const header = buildParentDeliveryHeader(event, launch);
	const route = resolveEventRoute(event, launch);
	const routeMetadata = route.from && route.to ? [`Route: ${route.from} -> ${route.to}`, ""] : [];
	const settlementMetadata = options?.terminalEventId || options?.finalizedAt || options?.settledState || options?.settlementReason
		? [
			"## Settlement Metadata",
			options?.settledState ? `- Settled State: ${options.settledState}` : undefined,
			options?.terminalEventId ? `- Terminal Event ID: ${options.terminalEventId}` : undefined,
			options?.finalizedAt ? `- Finalized At: ${options.finalizedAt}` : undefined,
			options?.settlementReason ? `- Reason: ${options.settlementReason}` : undefined,
			"",
		].filter((line): line is string => Boolean(line))
		: [];
	if (event.reportPath) {
		try {
			const summary = await readBoundedReportSummary(event.reportPath);
			return [header, "", `Goal: ${launch.goal ?? launch.promptPreview}`, "", ...routeMetadata, ...settlementMetadata, summary].join("\n");
		} catch {
			return [header, "", `Goal: ${launch.goal ?? launch.promptPreview}`, ...routeMetadata, ...settlementMetadata, `Summary: ${event.summary ?? "Report unavailable."}`]
				.filter(Boolean)
				.join("\n");
		}
	}
	return [
		header,
		"",
		`Goal: ${launch.goal ?? launch.promptPreview}`,
		...routeMetadata,
		...settlementMetadata,
		event.summary ? `Summary: ${event.summary}` : "",
		event.message ? `Message: ${truncate(event.message, 500)}` : "",
	].filter(Boolean).join("\n");
}

export function buildProtocolViolationDeliveryContent(
	launch: BridgeLaunchFile,
	finalizedAt: string,
	reason: string,
): string {
	return [
		`[pimux protocol_violation] ${launch.agentId}`,
		"",
		`Goal: ${launch.goal ?? launch.promptPreview}`,
		"",
		"## Settlement Metadata",
		"- Settled State: protocol_violation",
		`- Finalized At: ${finalizedAt}`,
		`- Reason: ${reason}`,
	].join("\n");
}

export function buildChildMessageContent(event: BridgeEvent): string {
	return event.message?.trim() || event.summary?.trim() || "";
}
