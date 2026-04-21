import { StringEnum } from "@mariozechner/pi-ai";
import { Type } from "@sinclair/typebox";

export const PIMUX_PARAMS = Type.Object({
	action: StringEnum(["spawn", "open", "list", "tree", "status", "capture", "send_message", "report_parent", "kill", "prune"] as const),
	target: Type.Optional(Type.String({ description: "Target agent ID, session name, or 'last'" })),
	agentId: Type.Optional(Type.String({ description: "Preferred agent ID when spawning" })),
	cwd: Type.Optional(Type.String({ description: "Working directory for a spawned agent" })),
	model: Type.Optional(Type.String({ description: "Model for a spawned agent, e.g. openai-codex/gpt-5.3-codex" })),
	prompt: Type.Optional(Type.String({ description: "Initial prompt for a spawned agent" })),
	role: Type.Optional(Type.String({ description: "Short role label for the agent" })),
	goal: Type.Optional(Type.String({ description: "Short mission summary" })),
	parentAgentId: Type.Optional(Type.String({ description: "Parent agent ID for hierarchy tracking" })),
	rootAgentId: Type.Optional(Type.String({ description: "Root agent ID for hierarchy tracking" })),
	openIterm: Type.Optional(Type.Boolean({ description: "Open the spawned agent in a background iTerm tab" })),
	contextBrief: Type.Optional(Type.String({ description: "Optional compact context handoff" })),
	lines: Type.Optional(Type.Number({ description: "Number of tmux pane lines to capture" })),
	message: Type.Optional(Type.String({ description: "Message for send_message" })),
	senderAgentId: Type.Optional(Type.String({ description: "Optional sender override for send_message" })),
	scope: Type.Optional(StringEnum(["session", "root", "all"] as const)),
	includeExited: Type.Optional(Type.Boolean({ description: "Include exited, terminated, or missing agents" })),
	olderThan: Type.Optional(Type.String({ description: "Age threshold for prune, e.g. 0s, 1h, 7d" })),
	dryRun: Type.Optional(Type.Boolean({ description: "Preview prune candidates without archiving/removing them" })),
	reportKind: Type.Optional(StringEnum(["question", "blocker", "progress", "failure", "closeout"] as const)),
	summary: Type.Optional(Type.String({ description: "Short structured summary for report_parent" })),
	reportMarkdown: Type.Optional(Type.String({ description: "Optional markdown artifact body for report_parent" })),
	requiresResponse: Type.Optional(Type.Boolean({ description: "Whether the parent must answer before the child continues" })),
});
