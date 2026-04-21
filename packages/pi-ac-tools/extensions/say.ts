import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, dirname, join } from "node:path";

import { getAgentDir, type ExtensionAPI, type ExtensionContext } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

type AutoMode = "off" | "always" | "long";

type VoiceSettings = {
	autoMode: AutoMode;
	voice?: string;
	rate?: number;
	longTaskSeconds: number;
};

type VoiceInfo = {
	name: string;
	locale?: string;
	sample?: string;
	label: string;
	raw: string;
};

type AgentRun = {
	startedAt: number;
	spoke: boolean;
	project: string;
};

const DEFAULT_SETTINGS: VoiceSettings = {
	autoMode: "always",
	longTaskSeconds: 30,
};

function isTrueLike(value: string | undefined): boolean {
	if (!value) return false;
	const normalized = value.trim().toLowerCase();
	return normalized === "1" || normalized === "true" || normalized === "yes";
}

function isSubagentProcess(): boolean {
	return isTrueLike(process.env.PI_SUBAGENT);
}

function isMacOS(): boolean {
	return process.platform === "darwin";
}

function getProjectName(cwd: string): string {
	const name = basename(cwd);
	return name && name !== "/" ? name : "project";
}

function normalizeVoice(value: unknown): string | undefined {
	if (typeof value !== "string") return undefined;
	const voice = value.trim();
	return voice.length > 0 ? voice : undefined;
}

function normalizeRate(value: unknown): number | undefined {
	if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
	const rate = Math.round(value);
	if (rate < 80 || rate > 400) return undefined;
	return rate;
}

function normalizeLongTaskSeconds(value: unknown): number {
	if (typeof value !== "number" || !Number.isFinite(value)) return DEFAULT_SETTINGS.longTaskSeconds;
	const seconds = Math.round(value);
	if (seconds < 1 || seconds > 3600) return DEFAULT_SETTINGS.longTaskSeconds;
	return seconds;
}

function normalizeAutoMode(value: unknown, legacyAuto?: unknown): AutoMode {
	if (value === "off" || value === "always" || value === "long") {
		return value;
	}
	if (typeof legacyAuto === "boolean") {
		return legacyAuto ? "always" : "off";
	}
	return DEFAULT_SETTINGS.autoMode;
}

function normalizeSettings(value: unknown): VoiceSettings {
	if (!value || typeof value !== "object") {
		return { ...DEFAULT_SETTINGS };
	}

	const input = value as {
		auto?: unknown;
		autoMode?: unknown;
		voice?: unknown;
		rate?: unknown;
		longTaskSeconds?: unknown;
	};

	return {
		autoMode: normalizeAutoMode(input.autoMode, input.auto),
		voice: normalizeVoice(input.voice),
		rate: normalizeRate(input.rate),
		longTaskSeconds: normalizeLongTaskSeconds(input.longTaskSeconds),
	};
}

function formatAutoMode(settings: VoiceSettings): string {
	if (settings.autoMode === "long") return `long ≥${settings.longTaskSeconds}s`;
	return settings.autoMode;
}

function parseVoiceLine(line: string): VoiceInfo {
	const match = line.match(/^(.+?)\s{2,}(\S+)(?:\s+#\s*(.*))?$/);
	if (!match) {
		const name = line.trim();
		return {
			name,
			label: name,
			raw: line,
		};
	}

	const [, rawName, locale, sample] = match;
	const name = rawName.trim();
	const label = [
		`${name}${locale ? ` (${locale})` : ""}`,
		sample ? `— ${sample.trim()}` : undefined,
	]
		.filter(Boolean)
		.join(" ");

	return {
		name,
		locale,
		sample: sample?.trim(),
		label,
		raw: line,
	};
}

function isDefaultListedVoice(voice: VoiceInfo): boolean {
	const locale = (voice.locale ?? "").toLowerCase();
	return locale.startsWith("en") || locale.startsWith("es");
}

function matchesVoiceFilter(voice: VoiceInfo, filter: string): boolean {
	if (filter === "all") return true;
	if (filter) {
		const haystack = `${voice.name} ${voice.locale ?? ""} ${voice.sample ?? ""}`.toLowerCase();
		return haystack.includes(filter);
	}
	return isDefaultListedVoice(voice);
}

export default function (pi: ExtensionAPI) {
	const settingsPath = join(getAgentDir(), "voice.json");
	const subagentProcess = isSubagentProcess();
	let settings: VoiceSettings = { ...DEFAULT_SETTINGS };
	let settingsPromise: Promise<void> | undefined;
	let currentRun: AgentRun | undefined;

	async function ensureSettingsLoaded(): Promise<void> {
		if (!settingsPromise) {
			settingsPromise = (async () => {
				try {
					const raw = await readFile(settingsPath, "utf8");
					settings = normalizeSettings(JSON.parse(raw));
				} catch (error) {
					const code = (error as NodeJS.ErrnoException).code;
					if (code !== "ENOENT") {
						console.error(`[say extension] Failed to load ${settingsPath}:`, error);
					}
					settings = { ...DEFAULT_SETTINGS };
				}
			})();
		}

		await settingsPromise;
	}

	async function saveSettings(): Promise<void> {
		await mkdir(dirname(settingsPath), { recursive: true });
		await writeFile(settingsPath, `${JSON.stringify(settings, null, 2)}\n`, "utf8");
	}

	function queueStatusUpdate(ctx: ExtensionContext | undefined): void {
		if (!ctx) return;
		setTimeout(() => {
			void updateStatus(ctx);
		}, 0);
	}

	async function updateStatus(ctx: ExtensionContext | undefined): Promise<void> {
		if (!ctx) return;
		await ensureSettingsLoaded();

		const theme = ctx.ui.theme;
		const icon = settings.autoMode === "off" ? theme.fg("muted", "🔇") : theme.fg("accent", "🔊");
		const auto =
			settings.autoMode === "off"
				? theme.fg("warning", "auto off")
				: settings.autoMode === "long"
					? theme.fg("accent", `auto long≥${settings.longTaskSeconds}s`)
					: theme.fg("success", "auto on");
		const voice = theme.fg("dim", `voice ${settings.voice ?? "system"}`);
		const rate = theme.fg("dim", `rate ${settings.rate ?? "system"}`);
		ctx.ui.setStatus("zz-voice", `${icon} ${auto} | ${voice} | ${rate} | /voice-auto`);
	}

	async function runSay(text: string, options?: { voice?: string; rate?: number; signal?: AbortSignal }) {
		if (subagentProcess) {
			throw new Error("The say extension is disabled in subagents.");
		}
		if (!isMacOS()) {
			throw new Error("The say extension is only available on macOS.");
		}

		await ensureSettingsLoaded();
		const voice = normalizeVoice(options?.voice) ?? settings.voice;
		const rate = normalizeRate(options?.rate) ?? settings.rate;
		const args: string[] = [];
		if (voice) args.push("-v", voice);
		if (typeof rate === "number") args.push("-r", String(rate));
		args.push(text);

		const result = await pi.exec("say", args, { signal: options?.signal });
		if (result.code !== 0) {
			throw new Error(result.stderr.trim() || result.stdout.trim() || "say failed");
		}

		return { voice, rate };
	}

	async function getAvailableVoices(): Promise<VoiceInfo[]> {
		if (!isMacOS()) {
			throw new Error("Voice listing is only available on macOS.");
		}

		const result = await pi.exec("say", ["-v", "?"]);
		if (result.code !== 0) {
			throw new Error(result.stderr.trim() || result.stdout.trim() || "Failed to list macOS voices.");
		}

		return result.stdout
			.split(/\r?\n/)
			.map((line) => line.trimEnd())
			.filter((line) => line.length > 0)
			.map(parseVoiceLine)
			.sort((a, b) => a.name.localeCompare(b.name));
	}

	function formatStatusReport(): string {
		return [
			"voice status",
			`- automatic voice mode: ${formatAutoMode(settings)}`,
			`- default voice: ${settings.voice ?? "system default"}`,
			`- default speaking rate: ${settings.rate ?? "system default"}`,
			`- long-task threshold: ${settings.longTaskSeconds}s`,
			`- settings file: ${settingsPath}`,
			"",
			"commands:",
			"- /voice-auto off|always|long|toggle|status",
			"- /voice-voice <name>|system|status",
			"- /voice-pick [filter|all]",
			"- /voice-rate <80-400>|system|status",
			"- /voice-threshold <seconds>|status",
			"- /voice-voices [filter|all]",
			"- /voice-preview [voice]",
		].join("\n");
	}

	function buildVoicePrompt(project: string): string {
		if (settings.autoMode === "always") {
			return [
				"Voice alerts:",
				"- If you finish a meaningful task or need the user's attention, confirmation, approval, or input, call the say tool once.",
				"- Keep the spoken message under 50 words.",
				`- Use this spoken format: \"${project} - <what you need>\".`,
				"- Keep the detailed explanation in the normal written response.",
				"- Do not speak code, secrets, tokens, stack traces, or long technical output.",
			].join("\n");
		}

		return [
			"Voice alerts:",
			"- If you need the user's attention, confirmation, approval, or input, call the say tool once.",
			"- Keep the spoken message under 50 words.",
			`- Use this spoken format: \"${project} - <what you need>\".`,
			"- Do not use say just to announce normal completion; the extension handles long-task completion alerts when needed.",
			"- Keep the detailed explanation in the normal written response.",
			"- Do not speak code, secrets, tokens, stack traces, or long technical output.",
		].join("\n");
	}

	if (!subagentProcess) {
		pi.registerTool({
			name: "say",
			label: "Say",
			description: "Speak a one-way voice message aloud to the user via macOS say",
			promptSnippet: "Speak a short one-way voice message aloud to the user via macOS say.",
			promptGuidelines: [
				"Use this tool for short one-way voice alerts to the user.",
				"Keep spoken output concise and leave the full explanation in the normal written response.",
			],
			parameters: Type.Object({
				text: Type.String({ description: "Text to speak aloud" }),
				voice: Type.Optional(Type.String({ description: "Optional macOS voice name, e.g. Samantha" })),
				rate: Type.Optional(
					Type.Integer({
						minimum: 80,
						maximum: 400,
						description: "Optional speaking rate in words per minute",
					}),
				),
			}),
			async execute(_toolCallId, params, signal) {
				const result = await runSay(params.text, {
					voice: params.voice,
					rate: params.rate,
					signal,
				});
				if (currentRun) currentRun.spoke = true;

				return {
					content: [{ type: "text", text: `Spoke${result.voice ? ` with ${result.voice}` : ""}: ${params.text}` }],
					details: {
						text: params.text,
						voice: result.voice ?? null,
						rate: result.rate ?? null,
					},
				};
			},
		});
	}

	pi.registerCommand("voice-status", {
		description: "Show voice settings and commands",
		handler: async (_args, ctx) => {
			await ensureSettingsLoaded();
			queueStatusUpdate(ctx);
			ctx.ui.notify(formatStatusReport(), "info");
		},
	});

	pi.registerCommand("voice-auto", {
		description: "Set automatic voice mode: /voice-auto off|always|long|toggle|status",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const action = (args || "status").trim().toLowerCase();

			if (action === "" || action === "status") {
				queueStatusUpdate(ctx);
				ctx.ui.notify(`Automatic voice mode: ${formatAutoMode(settings)}.`, "info");
				return;
			}

			if (action === "toggle") {
				settings.autoMode =
					settings.autoMode === "off" ? "always" : settings.autoMode === "always" ? "long" : "off";
			} else if (action === "on" || action === "always") {
				settings.autoMode = "always";
			} else if (action === "long") {
				settings.autoMode = "long";
			} else if (action === "off") {
				settings.autoMode = "off";
			} else {
				ctx.ui.notify("Usage: /voice-auto off|always|long|toggle|status", "error");
				return;
			}

			await saveSettings();
			queueStatusUpdate(ctx);
			ctx.ui.notify(`Automatic voice mode set to ${formatAutoMode(settings)}.`, "info");
		},
	});

	pi.registerCommand("voice-voice", {
		description: "Set the default macOS voice: /voice-voice <name>|system|status",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const value = (args || "status").trim();
			const normalized = value.toLowerCase();

			if (value === "" || normalized === "status") {
				queueStatusUpdate(ctx);
				ctx.ui.notify(`Default voice: ${settings.voice ?? "system default"}.`, "info");
				return;
			}

			if (["system", "default", "off", "clear", "none"].includes(normalized)) {
				settings.voice = undefined;
				await saveSettings();
				queueStatusUpdate(ctx);
				ctx.ui.notify("Default voice cleared; macOS system voice will be used.", "info");
				return;
			}

			settings.voice = value;
			await saveSettings();
			queueStatusUpdate(ctx);
			ctx.ui.notify(`Default voice set to ${value}. Use /voice-preview to test it.`, "info");
		},
	});

	pi.registerCommand("voice-pick", {
		description: "Interactively pick and preview a macOS voice: /voice-pick [filter|all]",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			if (!ctx.hasUI) {
				ctx.ui.notify("Interactive voice picking requires the UI. Use /voice-voices and /voice-voice instead.", "warning");
				return;
			}

			const filter = (args || "").trim().toLowerCase();
			const voices = (await getAvailableVoices()).filter((voice) => matchesVoiceFilter(voice, filter));

			if (voices.length === 0) {
				ctx.ui.notify(
					filter
						? `No macOS voices matched: ${filter}`
						: "No English or Spanish macOS voices found. Use /voice-pick all to show every voice.",
					"info",
				);
				return;
			}

			const systemOption = `System default${settings.voice ? ` (current override: ${settings.voice})` : ""}`;
			const choices = [systemOption, ...voices.map((voice) => voice.label)];
			const voiceByChoice = new Map(voices.map((voice) => [voice.label, voice]));

			while (true) {
				const choice = await ctx.ui.select("Pick a macOS voice", choices);
				if (!choice) return;

				if (choice === systemOption) {
					settings.voice = undefined;
					await saveSettings();
					queueStatusUpdate(ctx);
					ctx.ui.notify("Default voice cleared; macOS system voice will be used.", "info");
					return;
				}

				const voice = voiceByChoice.get(choice);
				if (!voice) {
					ctx.ui.notify("Could not resolve the selected voice.", "error");
					return;
				}

				await runSay(`${getProjectName(ctx.cwd)} - this is ${voice.name}.`, { voice: voice.name });
				const details = [voice.locale, voice.sample].filter(Boolean).join("\n");
				const ok = await ctx.ui.confirm("Use this voice?", details ? `${voice.name}\n${details}` : voice.name);
				if (!ok) continue;

				settings.voice = voice.name;
				await saveSettings();
				queueStatusUpdate(ctx);
				ctx.ui.notify(`Default voice set to ${voice.name}.`, "info");
				return;
			}
		},
	});

	pi.registerCommand("voice-rate", {
		description: "Set the default speaking rate: /voice-rate <80-400>|system|status",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const value = (args || "status").trim();
			const normalized = value.toLowerCase();

			if (value === "" || normalized === "status") {
				queueStatusUpdate(ctx);
				ctx.ui.notify(`Default speaking rate: ${settings.rate ?? "system default"}.`, "info");
				return;
			}

			if (["system", "default", "off", "clear", "none"].includes(normalized)) {
				settings.rate = undefined;
				await saveSettings();
				queueStatusUpdate(ctx);
				ctx.ui.notify("Default speaking rate cleared; macOS system rate will be used.", "info");
				return;
			}

			const parsed = Number(value);
			const rate = normalizeRate(parsed);
			if (rate === undefined) {
				ctx.ui.notify("Usage: /voice-rate <80-400>|system|status", "error");
				return;
			}

			settings.rate = rate;
			await saveSettings();
			queueStatusUpdate(ctx);
			ctx.ui.notify(`Default speaking rate set to ${rate}.`, "info");
		},
	});

	pi.registerCommand("voice-threshold", {
		description: "Set the long-task auto-voice threshold in seconds: /voice-threshold <seconds>|status",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const value = (args || "status").trim().toLowerCase();

			if (value === "" || value === "status") {
				queueStatusUpdate(ctx);
				ctx.ui.notify(`Long-task threshold: ${settings.longTaskSeconds}s.`, "info");
				return;
			}

			const parsed = Number(value);
			const seconds = normalizeLongTaskSeconds(parsed);
			if (!Number.isFinite(parsed) || seconds !== Math.round(parsed)) {
				ctx.ui.notify("Usage: /voice-threshold <seconds>|status", "error");
				return;
			}

			settings.longTaskSeconds = seconds;
			await saveSettings();
			queueStatusUpdate(ctx);
			ctx.ui.notify(`Long-task threshold set to ${seconds}s.`, "info");
		},
	});

	pi.registerCommand("voice-voices", {
		description: "List available macOS voices: /voice-voices [filter|all]",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const filter = (args || "").trim().toLowerCase();
			const lines = (await getAvailableVoices())
				.filter((voice) => matchesVoiceFilter(voice, filter))
				.map((voice) => voice.raw);

			if (lines.length === 0) {
				ctx.ui.notify(
					filter
						? `No macOS voices matched: ${filter}`
						: "No English or Spanish macOS voices found. Use /voice-voices all to show every voice.",
					"info",
				);
				return;
			}

			const preview = lines.slice(0, 30);
			let message = preview.join("\n");
			if (lines.length > preview.length) {
				message += `\n...and ${lines.length - preview.length} more. Use /voice-voices <filter|all> or /voice-pick <filter|all> to narrow it down.`;
			}
			ctx.ui.notify(message, "info");
		},
	});

	pi.registerCommand("voice-preview", {
		description: "Speak a short preview using the selected or provided voice: /voice-preview [voice]",
		handler: async (args, ctx) => {
			await ensureSettingsLoaded();
			const voice = normalizeVoice(args);
			const voiceLabel = voice ?? settings.voice ?? "system default";
			const result = await runSay(`${getProjectName(ctx.cwd)} - this is a voice preview.`, { voice });
			ctx.ui.notify(`Played voice preview with ${voiceLabel} at rate ${result.rate ?? "system default"}.`, "info");
		},
	});

	pi.on("session_start", async (_event, ctx) => {
		await ensureSettingsLoaded();
		queueStatusUpdate(ctx);
	});

	pi.on("session_switch", async (_event, ctx) => {
		await ensureSettingsLoaded();
		queueStatusUpdate(ctx);
	});

	pi.on("session_fork", async (_event, ctx) => {
		await ensureSettingsLoaded();
		queueStatusUpdate(ctx);
	});

	pi.on("session_tree", async (_event, ctx) => {
		await ensureSettingsLoaded();
		queueStatusUpdate(ctx);
	});

	pi.on("agent_start", async (_event, ctx) => {
		if (subagentProcess) {
			currentRun = undefined;
			return;
		}
		await ensureSettingsLoaded();
		currentRun = {
			startedAt: Date.now(),
			spoke: false,
			project: getProjectName(ctx.cwd),
		};
		queueStatusUpdate(ctx);
	});

	pi.on("agent_end", async () => {
		const run = currentRun;
		currentRun = undefined;
		if (subagentProcess) return;
		await ensureSettingsLoaded();
		if (!run) return;
		if (settings.autoMode !== "long") return;
		if (run.spoke) return;
		if (Date.now() - run.startedAt < settings.longTaskSeconds * 1000) return;

		try {
			await runSay(`${run.project} - task complete.`);
		} catch (error) {
			console.error("[say extension] Failed to announce long-task completion:", error);
		}
	});

	pi.on("before_agent_start", async (event, ctx) => {
		if (subagentProcess) return;
		await ensureSettingsLoaded();
		queueStatusUpdate(ctx);
		if (settings.autoMode === "off") return;

		const project = getProjectName(ctx.cwd);
		return {
			systemPrompt: `${event.systemPrompt}\n\n${buildVoicePrompt(project)}`,
		};
	});
}
